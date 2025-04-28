# catalog/cms_plugins.py
from cms.plugin_base import CMSPluginBase
from cms.plugin_pool import plugin_pool
from django.db import models
from django.db.models import Max, F, Case, When, Value
from django.utils.translation import gettext_lazy as _

from .models import (
    LatestMediaPluginModel, FeaturedMediaPluginModel, MediaListByCriteriaPluginModel,
    ContinueWatchingPluginModel,  # <-- Add model
    MediaItem, ViewingHistory  # <-- Add ViewingHistory
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
    cache = False

    def render(self, context, instance, placeholder):
        """Renders the plugin."""
        context = super().render(context, instance, placeholder)
        request = context.get('request')
        history_items = []
        pks_to_fetch = []  # List to store the PKs of the specific history entries

        if request and request.user.is_authenticated:
            user = request.user

            # 1. Find the latest 'watched_at' for each MediaItem the user interacted with.
            latest_watch_times_per_item = ViewingHistory.objects.filter(
                user=user
            ).annotate(
                media_item_pk=Case(
                    When(link__episode__isnull=False, then=F('link__episode__season__media_item__pk')),
                    When(link__media_item__isnull=False, then=F('link__media_item__pk')),
                    default=Value(None, output_field=models.IntegerField()),
                    output_field=models.IntegerField()
                )
            ).filter(
                media_item_pk__isnull=False
            ).values(
                'media_item_pk'
            ).annotate(
                latest_watched_at=Max('watched_at')
            ).order_by(
                '-latest_watched_at'
            )[:instance.items_count]  # Limit the number of MediaItems

            # Create a dictionary for quick lookup: {media_item_pk: latest_watched_at}
            latest_times_dict = {
                item['media_item_pk']: item['latest_watched_at']
                for item in latest_watch_times_per_item
            }

            if latest_times_dict:
                # 2. Fetch all history entries for this user related to the target media items.
                #    We need to determine the media item PK again for filtering.
                relevant_history_entries_qs = ViewingHistory.objects.filter(
                    user=user
                ).annotate(
                    # Annotate again to filter based on the keys we found
                    media_item_pk_for_filter=Case(
                        When(link__episode__isnull=False, then=F('link__episode__season__media_item__pk')),
                        When(link__media_item__isnull=False, then=F('link__media_item__pk')),
                        default=Value(None, output_field=models.IntegerField()),
                        output_field=models.IntegerField()
                    )
                ).filter(
                    media_item_pk_for_filter__in=latest_times_dict.keys()
                ).select_related(  # Select related needed for the loop below
                    'link__episode__season__media_item',
                    'link__media_item'
                ).order_by('-watched_at')  # Order by watched_at to process latest first

                # 3. Iterate through these entries in Python to find the exact latest one for each media item.
                pks_to_fetch_set = set()
                processed_media_items = set()

                for entry in relevant_history_entries_qs:
                    media_item_pk = None
                    if entry.link.episode:
                        media_item_pk = entry.link.episode.season.media_item_id
                    elif entry.link.media_item:
                        media_item_pk = entry.link.media_item_id

                    # Check if it's a target media item and the time matches the latest known time for it
                    if (media_item_pk in latest_times_dict and
                            entry.watched_at == latest_times_dict[media_item_pk] and
                            media_item_pk not in processed_media_items):
                        pks_to_fetch_set.add(entry.pk)
                        processed_media_items.add(media_item_pk)  # Mark this media item as processed

                    # Optimization: Stop if we've found entries for all items
                    if len(processed_media_items) == len(latest_times_dict):
                        break

                pks_to_fetch = list(pks_to_fetch_set)

            # 4. Fetch the final ViewingHistory objects with all related data needed for the template
            if pks_to_fetch:
                history_items = ViewingHistory.objects.filter(
                    pk__in=pks_to_fetch
                ).select_related(
                    'link__translation',
                    'link__episode__season__media_item',
                    'link__media_item',
                    'episode',
                ).prefetch_related(
                    'link__episode__screenshots',
                    'link__media_item__genres',
                    'link__episode__season__media_item__genres'
                ).order_by('-watched_at')  # Final ordering for display

        context['history_items'] = history_items
        context['title'] = instance.title
        context['instance'] = instance
        return context
