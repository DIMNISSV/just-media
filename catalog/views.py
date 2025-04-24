# catalog/views.py
from django.views.generic import ListView, DetailView

from .models import MediaItem, MediaSourceLink


class MediaItemListView(ListView):
    """ Displays a list of Media Items. """
    model = MediaItem
    template_name = 'catalog/mediaitem_list.html'
    context_object_name = 'media_items'
    paginate_by = 20

    def get_queryset(self):
        return MediaItem.objects.prefetch_related('genres', 'countries').order_by('-updated_at', 'title')


class MediaItemDetailView(DetailView):
    """ Displays details for a single Media Item. """
    model = MediaItem
    template_name = 'catalog/mediaitem_detail.html'
    context_object_name = 'media_item'

    def get_queryset(self):
        return MediaItem.objects.prefetch_related(
            'genres',
            'countries',
            'source_metadata__source',
            'seasons__episodes__screenshots',
            'seasons__episodes__source_links__source'
        ).all()


class PlaySourceLinkView(DetailView):
    """ Displays the player iframe for a specific MediaSourceLink. """
    model = MediaSourceLink
    template_name = 'catalog/play_source_link.html'
    context_object_name = 'source_link'

    def get_queryset(self):

        return MediaSourceLink.objects.select_related(
            'source',
            'media_item',
            'episode__season__media_item'
        ).all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        source_link = context['source_link']
        if source_link.episode:
            context['media_title'] = source_link.episode.season.media_item.title
            context['episode_str'] = f"S{source_link.episode.season.season_number}E{source_link.episode.episode_number}"
            context[
                'back_url'] = source_link.episode.season.media_item.get_absolute_url()
        elif source_link.media_item:
            context['media_title'] = source_link.media_item.title
            context['back_url'] = source_link.media_item.get_absolute_url()
        else:
            context['media_title'] = "Unknown Media"
            context['back_url'] = "/"

        return context
