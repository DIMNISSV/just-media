# catalog/admin.py
from django.contrib import admin

from .models import (
    Genre, Country, Source, MediaItem, Season, Episode, MediaSourceLink,
    MediaItemSourceMetadata  # Import the new model
)

# Simple registration for basic models
admin.site.register(Genre)
admin.site.register(Country)


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    search_fields = ('name', 'slug')


class MediaItemSourceMetadataInline(admin.TabularInline):
    model = MediaItemSourceMetadata
    extra = 0
    fields = ('source', 'source_last_updated_at')
    readonly_fields = ('source_last_updated_at',)
    autocomplete_fields = ('source',)


class SeasonInline(admin.TabularInline):
    model = Season
    extra = 0
    fields = ('season_number',)
    ordering = ('season_number',)
    # Optional: Add link to season admin page
    # show_change_link = True


# Customized admin for MediaItem
@admin.register(MediaItem)
class MediaItemAdmin(admin.ModelAdmin):
    list_display = ('title', 'release_year', 'media_type', 'kinopoisk_id', 'imdb_id', 'updated_at')
    list_filter = ('media_type', 'release_year', 'genres', 'countries')
    search_fields = ('title', 'original_title', 'kinopoisk_id', 'imdb_id', 'shikimori_id', 'mydramalist_id')
    filter_horizontal = ('genres', 'countries',)
    readonly_fields = ('created_at', 'updated_at')
    inlines = [MediaItemSourceMetadataInline, SeasonInline]  # Add metadata inline
    fieldsets = (
        (None, {
            'fields': ('title', 'original_title', 'media_type', 'release_year', 'poster_url')
        }),
        ('External IDs', {
            'fields': ('kinopoisk_id', 'imdb_id', 'shikimori_id', 'mydramalist_id')
        }),
        ('Metadata', {
            'fields': ('genres', 'countries', 'description')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


class EpisodeInline(admin.TabularInline):
    model = Episode
    extra = 0
    fields = ('episode_number', 'title')
    ordering = ('episode_number',)


@admin.register(Season)
class SeasonAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'media_item_link', 'season_number')  # Changed media_item to link
    list_filter = ('media_item__media_type',)
    search_fields = ('media_item__title', 'season_number')
    inlines = [EpisodeInline]
    autocomplete_fields = ('media_item',)  # Make selection easier

    # Helper to create a link to the MediaItem admin page
    @admin.display(description='Media Item')
    def media_item_link(self, obj):
        from django.urls import reverse
        from django.utils.html import format_html
        if obj.media_item:
            link = reverse("admin:catalog_mediaitem_change", args=[obj.media_item.pk])
            return format_html('<a href="{}">{}</a>', link, obj.media_item)
        return "-"

    media_item_link.admin_order_field = 'media_item'


@admin.register(Episode)
class EpisodeAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'season_link', 'episode_number', 'title')  # Changed season to link
    list_filter = ('season__media_item__media_type',)
    search_fields = ('title', 'season__media_item__title', 'episode_number')
    list_display_links = ('__str__',)
    autocomplete_fields = ['season']

    # Helper to create a link to the Season admin page
    @admin.display(description='Season')
    def season_link(self, obj):
        from django.urls import reverse
        from django.utils.html import format_html
        if obj.season:
            link = reverse("admin:catalog_season_change", args=[obj.season.pk])
            # Use the season's improved __str__ method
            return format_html('<a href="{}">{}</a>', link, obj.season)
        return "-"

    season_link.admin_order_field = 'season'


@admin.register(MediaSourceLink)
class MediaSourceLinkAdmin(admin.ModelAdmin):
    list_display = ('get_target_str', 'source', 'quality_info', 'translation_info', 'added_at')
    list_filter = ('source', 'quality_info', 'translation_info', 'added_at')
    search_fields = ('media_item__title', 'episode__title', 'player_link', 'source_specific_id')
    readonly_fields = ('added_at',)
    autocomplete_fields = ['media_item', 'episode', 'source']

    @admin.display(description='Target')
    def get_target_str(self, obj):
        from django.urls import reverse
        from django.utils.html import format_html
        target_obj = None
        link = "#"
        text = "Orphaned Link"

        if obj.episode:
            target_obj = obj.episode
            try:
                link = reverse("admin:catalog_episode_change", args=[target_obj.pk])
                text = str(target_obj)
            except Exception:
                text = f"Episode pk={target_obj.pk}"  # Fallback if reverse fails
        elif obj.media_item:
            target_obj = obj.media_item
            try:
                link = reverse("admin:catalog_mediaitem_change", args=[target_obj.pk])
                text = str(target_obj)
            except Exception:
                text = f"MediaItem pk={target_obj.pk}"  # Fallback

        return format_html('<a href="{}">{}</a>', link, text)

    get_target_str.admin_order_field = ('episode', 'media_item')  # Allow sorting


# Register the new metadata model (optional, can be managed via MediaItem inline)
@admin.register(MediaItemSourceMetadata)
class MediaItemSourceMetadataAdmin(admin.ModelAdmin):
    list_display = ('media_item_link', 'source', 'source_last_updated_at')
    list_filter = ('source', 'source_last_updated_at')
    search_fields = ('media_item__title', 'source__name')
    readonly_fields = ('source_last_updated_at',)  # Usually managed by parser
    autocomplete_fields = ('media_item', 'source')

    @admin.display(description='Media Item')
    def media_item_link(self, obj):
        from django.urls import reverse
        from django.utils.html import format_html
        if obj.media_item:
            link = reverse("admin:catalog_mediaitem_change", args=[obj.media_item.pk])
            return format_html('<a href="{}">{}</a>', link, obj.media_item)
        return "-"

    media_item_link.admin_order_field = 'media_item'
