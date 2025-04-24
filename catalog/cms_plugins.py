# catalog/cms_plugins.py
from cms.plugin_base import CMSPluginBase
from cms.plugin_pool import plugin_pool
from django.utils.translation import gettext_lazy as _

from .models import (
    LatestMediaPluginModel, FeaturedMediaPluginModel, MediaListByCriteriaPluginModel,
    MediaItem
)


@plugin_pool.register_plugin
class LatestMediaPlugin(CMSPluginBase):
    """
    Displays the N most recently updated MediaItems.
    """
    model = LatestMediaPluginModel
    name = _("Latest Media Items")
    render_template = "catalog/plugins/latest_media.html"
    cache = False  # Content changes frequently

    def render(self, context, instance, placeholder):
        """Renders the plugin."""
        context = super().render(context, instance, placeholder)
        latest_items = MediaItem.objects.order_by('-updated_at').prefetch_related(
            'genres'  # Prefetch for card display
        )[:instance.latest_count]
        context['media_items'] = latest_items
        context['instance'] = instance
        return context


@plugin_pool.register_plugin
class FeaturedMediaPlugin(CMSPluginBase):
    """
    Displays manually selected MediaItems.
    """
    model = FeaturedMediaPluginModel
    name = _("Featured Media Items")
    render_template = "catalog/plugins/featured_media.html"
    cache = True

    def render(self, context, instance, placeholder):
        """Renders the plugin."""
        context = super().render(context, instance, placeholder)
        # Access related items via the instance
        featured_items = instance.items.prefetch_related('genres').all()
        context['media_items'] = featured_items
        context['instance'] = instance
        context['title'] = instance.title
        return context


@plugin_pool.register_plugin
class MediaListByCriteriaPlugin(CMSPluginBase):
    """
    Displays a list of MediaItems filtered by various criteria.
    """
    model = MediaListByCriteriaPluginModel
    name = _("Media List by Criteria")
    render_template = "catalog/plugins/media_list_by_criteria.html"
    cache = False  # Criteria might lead to frequent changes depending on usage

    def render(self, context, instance, placeholder):
        """Renders the plugin."""
        context = super().render(context, instance, placeholder)
        queryset = MediaItem.objects.all().prefetch_related('genres')

        # Apply filters
        if instance.media_type:
            queryset = queryset.filter(media_type=instance.media_type)
        if instance.year_from:
            queryset = queryset.filter(release_year__gte=instance.year_from)
        if instance.year_to:
            queryset = queryset.filter(release_year__lte=instance.year_to)

        # M2M Filters (ANY match)
        selected_genres = instance.genres.all()
        if selected_genres.exists():
            queryset = queryset.filter(genres__in=selected_genres).distinct()

        selected_countries = instance.countries.all()
        if selected_countries.exists():
            queryset = queryset.filter(countries__in=selected_countries).distinct()

        # Apply sorting
        if instance.sort_by:
            queryset = queryset.order_by(instance.sort_by)

        # Apply limit
        filtered_items = queryset[:instance.max_items]

        context['media_items'] = filtered_items
        context['instance'] = instance
        context['title'] = instance.title
        return context
