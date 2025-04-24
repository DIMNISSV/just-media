# catalog/views.py
import json
from urllib.parse import urlparse, parse_qs
from typing import Optional
from django.views.generic import ListView, DetailView
from django.utils.translation import gettext_lazy as _
from django.db.models import Q, Prefetch
from .models import MediaItem, MediaSourceLink, Screenshot, Season, Episode, Source
from .forms import AdvancedMediaSearchForm


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
        main_links_prefetch = Prefetch(
            'source_links',
            queryset=MediaSourceLink.objects.filter(episode__isnull=True).select_related('translation', 'source'),
            to_attr='main_source_links'
        )
        nested_seasons_prefetch = Prefetch(
            'seasons',
            queryset=Season.objects.order_by('season_number').prefetch_related(
                Prefetch(
                    'episodes',
                    queryset=Episode.objects.order_by('episode_number').prefetch_related(
                        'screenshots',
                        Prefetch(
                            'source_links',
                            queryset=MediaSourceLink.objects.select_related('translation', 'source')
                        )
                    ),
                    to_attr='prefetched_episodes'
                )
            ),
            to_attr='prefetched_seasons'
        )

        return MediaItem.objects.prefetch_related(
            'genres',
            'countries',
            'source_metadata__source',
            main_links_prefetch,
            nested_seasons_prefetch
        ).all()

    def get_context_data(self, **kwargs):
        """Adds structured episode and translation data to the context."""
        context = super().get_context_data(**kwargs)
        media_item: MediaItem = context['media_item']
        episodes_data = {}
        main_links_data = {}

        if hasattr(media_item, 'prefetched_seasons'):
            for season in media_item.prefetched_seasons:
                if hasattr(season, 'prefetched_episodes'):
                    for episode in season.prefetched_episodes:
                        episode_links = []
                        if hasattr(episode, 'source_links'):
                            for link in episode.source_links.all():
                                if link.translation:
                                    start_from = self._extract_start_from(link.player_link)
                                    episode_links.append({
                                        'translation_id': link.translation.kodik_id,
                                        'translation_title': link.translation.title,
                                        'link_pk': link.pk,
                                        'quality': link.quality_info,
                                        'start_from': start_from,
                                    })
                        episode_links.sort(key=lambda x: x['translation_title'])
                        episodes_data[episode.pk] = episode_links

        if hasattr(media_item, 'main_source_links'):
            for link in media_item.main_source_links:
                if link.translation:
                    start_from = self._extract_start_from(link.player_link)
                    main_links_data[link.translation.kodik_id] = {
                        'translation_id': link.translation.kodik_id,
                        'link_pk': link.pk,
                        'translation_title': link.translation.title,
                        'quality': link.quality_info,
                        'start_from': start_from,
                    }

        context['episodes_links_json'] = json.dumps(episodes_data)
        context['main_links_json'] = json.dumps(main_links_data)
        context['has_main_links'] = bool(main_links_data)
        # Pass translated strings needed by JS to the context
        context['js_translations'] = json.dumps({
            'error_loading_player': _("Error loading player."),
            'no_content_available': _("No content available."),
            'select_translation': _("Select a translation to start watching"),
            'select_episode': _("Select an episode to start watching"),
            'select_episode_or_translation': _("Select an episode or translation to start watching"),
            'no_translations_for_episode': _("No translations found for this episode."),
            'player_only_unavailable': _("Player only option unavailable (no main item link found)"),
            'player_only_enabled': _("Player only (hide episodes)"),
        })
        return context

    def _extract_start_from(self, player_link: str) -> Optional[int]:
        """Extracts the 'start_from' parameter from a Kodik player URL if present."""
        if not player_link: return None
        try:
            effective_link = player_link
            if player_link.startswith("//"):
                effective_link = "http:" + player_link
            parsed_url = urlparse(effective_link)
            query_params = parse_qs(parsed_url.query)
            start_from_list = query_params.get('start_from')
            if start_from_list:
                return int(start_from_list[0])
        except (ValueError, TypeError, IndexError):
            pass
        return None


class PlaySourceLinkView(DetailView):
    """ Renders a minimal HTML page containing only the player iframe. """
    model = MediaSourceLink
    template_name = 'catalog/play_source_link.html'
    context_object_name = 'source_link'

    def get_queryset(self):
        """Selects related data needed *within* the simplified player page."""
        return MediaSourceLink.objects.select_related(
            'source',
            'translation',
            'episode__season__media_item', # Needed for getting media item pk if only episode is linked
            'media_item' # Needed for getting media item pk if linked directly
        ).all()

    def get_context_data(self, **kwargs):
        """Provides minimal context needed for the iframe source page."""
        context = super().get_context_data(**kwargs)
        source_link_obj = context['source_link']
        start_from = self._extract_start_from(source_link_obj.player_link)
        player_url = source_link_obj.player_link

        # Ensure start_from is appended if needed (logic remains the same)
        if start_from is not None and player_url:
            if f'start_from={start_from}' not in player_url:
                try:
                    effective_link = player_url
                    if player_url.startswith("//"):
                        effective_link = "http:" + player_url
                    parsed = urlparse(effective_link)
                    query_params = parse_qs(parsed.query)
                    if 'start_from' not in query_params:
                        separator = '&' if parsed.query else '?'
                        player_url += f"{separator}start_from={start_from}"
                except Exception:
                    pass
        context['player_url_with_start'] = player_url
        return context

    def _extract_start_from(self, player_link: str) -> Optional[int]:
        """ Helper to extract start_from. """
        if not player_link: return None
        try:
            effective_link = player_link
            if player_link.startswith("//"):
                effective_link = "http:" + player_link
            parsed_url = urlparse(effective_link)
            query_params = parse_qs(parsed_url.query)
            start_from_list = query_params.get('start_from')
            if start_from_list:
                return int(start_from_list[0])
        except (ValueError, TypeError, IndexError):
            pass
        return None


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
                queryset = queryset.filter(genres__in=genres).distinct()

        else:
            # If form is invalid (e.g., year_from > year_to), return empty
            if form.errors:
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