# catalog/views.py
from django.views.generic import ListView, DetailView

from .models import MediaItem


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
            'source_links__source',  # Prefetch source for each link
            'seasons__episodes__source_links__source'  # Prefetch links for each episode in each season
        ).all()

    # Optional: Add extra context if needed
    # def get_context_data(self, **kwargs):
    #     context = super().get_context_data(**kwargs)
    #     # Add extra data here
    #     # context['related_items'] = ...
    #     return context
