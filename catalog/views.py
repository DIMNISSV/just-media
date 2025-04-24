# catalog/views.py
import json
from django.views.generic import ListView, DetailView
from django.utils.translation import gettext_lazy as _
from django.db.models import Q
from .models import MediaItem, MediaSourceLink, Screenshot
from .forms import AdvancedMediaSearchForm  # Import the new form


class MediaItemListView(ListView):
    """ Displays a list of Media Items. """
    model = MediaItem
    template_name = 'catalog/mediaitem_list.html'
    context_object_name = 'media_items'
    paginate_by = 20

    def get_queryset(self):
        """Prefetches related data."""
        queryset = MediaItem.objects.prefetch_related('genres', 'countries').order_by('-updated_at', 'title')
        return queryset


class MediaItemDetailView(DetailView):
    """ Displays details for a single Media Item. """
    model = MediaItem
    template_name = 'catalog/mediaitem_detail.html'
    context_object_name = 'media_item'

    def get_queryset(self):
        """Prefetches all necessary related data for the detail view."""
        return MediaItem.objects.prefetch_related(
            'genres',
            'countries',
            'source_metadata__source',
            'seasons__episodes__screenshots',
            'seasons__episodes__source_links__translation',
            'seasons__episodes__source_links__source'
        ).all()

    def get_context_data(self, **kwargs):
        """Adds structured episode and translation data to the context."""
        context = super().get_context_data(**kwargs)
        media_item = context['media_item']
        episodes_data = {}

        if hasattr(media_item, 'seasons'):
            seasons = media_item.seasons.all()
            for season in seasons:
                if hasattr(season, 'episodes'):
                    episodes = season.episodes.all()
                    for episode in episodes:
                        episode_links = []
                        if hasattr(episode, 'source_links'):
                            links = episode.source_links.all()
                            for link in links:
                                if link.translation:
                                    episode_links.append({
                                        'translation_id': link.translation.kodik_id,
                                        'translation_title': link.translation.title,
                                        'link_pk': link.pk,
                                        'quality': link.quality_info
                                    })
                        episode_links.sort(key=lambda x: x['translation_title'])
                        episodes_data[episode.pk] = episode_links

        context['episodes_links_json'] = json.dumps(episodes_data)
        return context


class PlaySourceLinkView(DetailView):
    """ Renders a minimal HTML page containing only the player iframe. """
    model = MediaSourceLink
    template_name = 'catalog/play_source_link.html'
    context_object_name = 'source_link'

    def get_queryset(self):
        """Selects related data needed *within* the simplified player page."""
        return MediaSourceLink.objects.select_related(
            'source',
            'translation'
        ).all()

    def get_context_data(self, **kwargs):
        """Provides minimal context needed for the iframe source page."""
        context = super().get_context_data(**kwargs)
        return context


class MediaItemSearchView(ListView):
    """ Displays search results for Media Items with advanced filtering. """
    model = MediaItem
    template_name = 'catalog/mediaitem_search_results.html'
    context_object_name = 'search_results'
    paginate_by = 20

    def get_queryset(self):
        """ Filters the queryset based on GET parameters using the form. """
        queryset = MediaItem.objects.prefetch_related('genres', 'countries').order_by('-updated_at', 'title')
        form = AdvancedMediaSearchForm(self.request.GET)

        if form.is_valid():
            query = form.cleaned_data.get('q')
            year_from = form.cleaned_data.get('year_from')
            year_to = form.cleaned_data.get('year_to')
            media_type = form.cleaned_data.get('media_type')
            genres = form.cleaned_data.get('genres')

            if query:
                queryset = queryset.filter(Q(title__icontains=query) | Q(original_title__icontains=query))
            if year_from:
                queryset = queryset.filter(release_year__gte=year_from)
            if year_to:
                queryset = queryset.filter(release_year__lte=year_to)
            if media_type:
                queryset = queryset.filter(media_type=media_type)
            if genres:
                # Filter by items that have ALL selected genres? Or ANY? Let's use ANY for now.
                # For ALL: iterate and chain filter calls:
                # for genre in genres:
                #     queryset = queryset.filter(genres=genre)
                # For ANY:
                queryset = queryset.filter(genres__in=genres).distinct()  # Use distinct with M2M filter

        else:
            # If form is invalid (shouldn't happen with GET unless tampered), return empty
            queryset = MediaItem.objects.none()

        return queryset

    def get_context_data(self, **kwargs):
        """ Adds the search form and query parameters to the context. """
        context = super().get_context_data(**kwargs)
        # Pass the bound form to the template to display filter values
        context['search_form'] = AdvancedMediaSearchForm(self.request.GET or None)
        # Keep original query parameters for pagination
        context['query_params'] = self.request.GET.urlencode()
        return context
