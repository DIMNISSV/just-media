# catalog/views.py
from django.views.generic import ListView, DetailView

from .models import MediaItem, MediaSourceLink, Screenshot


class MediaItemListView(ListView):
    """ Displays a list of Media Items. """
    model = MediaItem
    template_name = 'catalog/mediaitem_list.html'  # Specify the template
    context_object_name = 'media_items'  # Name for the list object in the template (default is object_list)
    paginate_by = 20  # Optional: Add pagination

    def get_queryset(self):
        # Optional: Modify the queryset if needed (e.g., filtering, ordering)
        # Prefetch related objects to optimize queries in the template
        return MediaItem.objects.prefetch_related('genres', 'countries').order_by('-updated_at', 'title')


class MediaItemDetailView(DetailView):
    """ Displays details for a single Media Item. """
    model = MediaItem
    template_name = 'catalog/mediaitem_detail.html'  # Specify the template
    context_object_name = 'media_item'  # Name for the single object in the template (default is object or model name)

    def get_queryset(self):
        # Optional: Prefetch related objects needed on the detail page
        # Prefetch source links, seasons with episodes, etc.
        return MediaItem.objects.prefetch_related(
            'genres',
            'countries',
            'source_metadata__source',
            'seasons__episodes__screenshots',
            'seasons__episodes__source_links__source'
        ).all()

    # Optional: Add extra context if needed
    # def get_context_data(self, **kwargs):
    #     context = super().get_context_data(**kwargs)
    #     # Add extra data here
    #     # context['related_items'] = ...
    #     return context


class PlaySourceLinkView(DetailView):
    """ Displays the player iframe for a specific MediaSourceLink. """
    model = MediaSourceLink  # The model we are displaying details for
    template_name = 'catalog/play_source_link.html'  # New template
    context_object_name = 'source_link'  # Name for the object in the template

    def get_queryset(self):
        # Prefetch related objects needed for displaying context on the player page
        return MediaSourceLink.objects.select_related(
            'source',
            'media_item',  # Needed for title if it's a movie link
            'episode__season__media_item'  # Needed for title if it's an episode link
        ).all()

    # Optional: Add extra context like the media item title consistently
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        source_link = context['source_link']
        if source_link.episode:
            context['media_title'] = source_link.episode.season.media_item.title
            context['episode_str'] = f"S{source_link.episode.season.season_number}E{source_link.episode.episode_number}"
            context[
                'back_url'] = source_link.episode.season.media_item.get_absolute_url()  # Assumes get_absolute_url on MediaItem
        elif source_link.media_item:
            context['media_title'] = source_link.media_item.title
            context['back_url'] = source_link.media_item.get_absolute_url()
        else:
            context['media_title'] = "Unknown Media"
            context['back_url'] = "/"  # Fallback back URL

        # Add get_absolute_url to MediaItem model if you haven't already
        # Example in MediaItem model:
        # from django.urls import reverse
        # def get_absolute_url(self):
        #     return reverse('catalog:mediaitem_detail', kwargs={'pk': self.pk})

        return context
