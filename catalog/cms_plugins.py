# catalog/cms_plugins.py
from cms.plugin_base import CMSPluginBase
from cms.plugin_pool import plugin_pool
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.db.models import Q, OuterRef, Subquery, Max, F, Case, When, Value

from .models import (
    LatestMediaPluginModel, FeaturedMediaPluginModel, MediaListByCriteriaPluginModel,
    ContinueWatchingPluginModel,  # <-- Add model
    MediaItem, Genre, Country, ViewingHistory  # <-- Add ViewingHistory
)


@plugin_pool.register_plugin
class LatestMediaPlugin(CMSPluginBase):
    """ Displays the N most recently updated MediaItems. """
    # ... (no changes) ...
    model = LatestMediaPluginModel
    name = _("Latest Media Items")
    render_template = "catalog/plugins/latest_media.html"
    cache = False

    def render(self, context, instance, placeholder):
        context = super().render(context, instance, placeholder)
        latest_items = MediaItem.objects.order_by('-updated_at').prefetch_related('genres')[:instance.latest_count]
        context['media_items'] = latest_items
        context['instance'] = instance
        return context


@plugin_pool.register_plugin
class FeaturedMediaPlugin(CMSPluginBase):
    """ Displays manually selected MediaItems. """
    # ... (no changes) ...
    model = FeaturedMediaPluginModel
    name = _("Featured Media Items")
    render_template = "catalog/plugins/featured_media.html"
    cache = True

    def render(self, context, instance, placeholder):
        context = super().render(context, instance, placeholder)
        featured_items = instance.items.prefetch_related('genres').all()
        context['media_items'] = featured_items
        context['instance'] = instance
        context['title'] = instance.title
        return context


@plugin_pool.register_plugin
class MediaListByCriteriaPlugin(CMSPluginBase):
    """ Displays a list of MediaItems filtered by various criteria. """
    # ... (no changes) ...
    model = MediaListByCriteriaPluginModel
    name = _("Media List by Criteria")
    render_template = "catalog/plugins/media_list_by_criteria.html"
    cache = False

    def render(self, context, instance, placeholder):
        context = super().render(context, instance, placeholder)
        queryset = MediaItem.objects.all().prefetch_related('genres')
        if instance.media_type: queryset = queryset.filter(media_type=instance.media_type)
        if instance.year_from: queryset = queryset.filter(release_year__gte=instance.year_from)
        if instance.year_to: queryset = queryset.filter(release_year__lte=instance.year_to)
        selected_genres = instance.genres.all()
        if selected_genres.exists(): queryset = queryset.filter(genres__in=selected_genres).distinct()
        selected_countries = instance.countries.all()
        if selected_countries.exists(): queryset = queryset.filter(countries__in=selected_countries).distinct()
        if instance.sort_by: queryset = queryset.order_by(instance.sort_by)
        filtered_items = queryset[:instance.max_items]
        context['media_items'] = filtered_items
        context['instance'] = instance
        context['title'] = instance.title
        return context


@plugin_pool.register_plugin
class ContinueWatchingPlugin(CMSPluginBase):
    """
    Displays a list of media items the user was recently watching.
    Shows the latest watched episode/link per MediaItem.
    """
    model = ContinueWatchingPluginModel
    name = _("Continue Watching List")
    render_template = "catalog/plugins/continue_watching.html"
    # Cache per user? This is tricky. Let's disable cache for now.
    # Cache needs to be user-aware if enabled.
    cache = False

    def render(self, context, instance, placeholder):
        """Renders the plugin."""
        context = super().render(context, instance, placeholder)
        request = context.get('request')
        history_items = []

        # Only display for authenticated users
        if request and request.user.is_authenticated:
            user = request.user

            # 1. Find the latest 'watched_at' timestamp for each MediaItem the user interacted with.
            #    We group by the MediaItem associated with the link (either via episode or direct link).
            latest_watch_times = ViewingHistory.objects.filter(
                user=user
            ).annotate(
                # Determine the relevant MediaItem PK based on the link type
                media_item_pk=Case(
                    When(link__episode__isnull=False, then=F('link__episode__season__media_item__pk')),
                    When(link__media_item__isnull=False, then=F('link__media_item__pk')),
                    default=Value(None, output_field=models.IntegerField()),
                    output_field=models.IntegerField()
                )
            ).filter(
                media_item_pk__isnull=False  # Ensure we have a media item to group by
            ).values(
                'media_item_pk'  # Group by the determined media item PK
            ).annotate(
                latest_watched_at=Max('watched_at')  # Find the latest time within each group
            ).order_by(
                '-latest_watched_at'  # Order groups by most recent activity
            )[:instance.items_count]  # Limit the number of groups (MediaItems)

            # Extract the PKs of the latest history entries we care about
            latest_pks_to_fetch = []
            if latest_watch_times:
                # 2. For each MediaItem group, find the specific ViewingHistory entry
                #    (or entries, if multiple links watched exactly simultaneously)
                #    that corresponds to the latest 'watched_at' timestamp.
                subquery = ViewingHistory.objects.filter(
                    user=user,
                    watched_at=OuterRef('latest_watched_at'),
                    # Re-annotate media_item_pk within the subquery for matching
                    media_item_pk_inner=Case(
                        When(link__episode__isnull=False, then=F('link__episode__season__media_item__pk')),
                        When(link__media_item__isnull=False, then=F('link__media_item__pk')),
                        default=Value(None, output_field=models.IntegerField()),
                        output_field=models.IntegerField()
                    )
                ).filter(
                    # Match the media item PK from the outer query
                    media_item_pk_inner=OuterRef('media_item_pk')
                )

                # We want the PKs of these latest history entries
                history_pks_subquery = subquery.values('pk')[:1]  # Get pk of one entry per group

                # Fetch the actual ViewingHistory objects using the PKs determined
                latest_pks_to_fetch = ViewingHistory.objects.filter(
                    pk__in=Subquery(history_pks_subquery.filter(media_item_pk=OuterRef('media_item_pk')))
                ).values_list('pk', flat=True)

            # 3. Fetch the actual ViewingHistory objects with all related data needed for the template
            if latest_pks_to_fetch:
                history_items = ViewingHistory.objects.filter(
                    pk__in=list(latest_pks_to_fetch)  # Use the PKs we found
                ).select_related(
                    'link__translation',
                    'link__episode__season__media_item',  # Needed for title, poster etc. via episode
                    'link__media_item',  # Needed for title, poster etc. via direct link
                    'episode',  # Explicit episode link
                ).prefetch_related(
                    # Prefetch screenshots if needed for display
                    'link__episode__screenshots',
                ).order_by('-watched_at')  # Final ordering for display

        context['history_items'] = history_items
        context['title'] = instance.title
        context['instance'] = instance
        return context
