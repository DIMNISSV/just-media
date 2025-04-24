# catalog/admin.py
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from .models import (
    Genre, Country, Source, Translation,  # <<< Import Translation
    MediaItem, Season, Episode, MediaSourceLink,
    MediaItemSourceMetadata, Screenshot
)


# --- Register Translation model ---
@admin.register(Translation)
class TranslationAdmin(admin.ModelAdmin):
    list_display = ('title', 'kodik_id')
    search_fields = ('title', 'kodik_id')


# ... (Genre, Country, SourceAdmin registration remains the same) ...
admin.site.register(Genre)
admin.site.register(Country)


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    search_fields = ('name', 'slug')


# ... (MediaItemSourceMetadataInline, SeasonInline registration remains the same) ...
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


# ... (MediaItemAdmin registration remains the same) ...
@admin.register(MediaItem)
class MediaItemAdmin(admin.ModelAdmin):
    list_display = ('title', 'release_year', 'media_type', 'kinopoisk_id', 'imdb_id', 'updated_at')
    list_filter = ('media_type', 'release_year', 'genres', 'countries')
    search_fields = ('title', 'original_title', 'kinopoisk_id', 'imdb_id', 'shikimori_id', 'mydramalist_id')
    filter_horizontal = ('genres', 'countries',)
    readonly_fields = ('created_at', 'updated_at')
    inlines = [MediaItemSourceMetadataInline, SeasonInline]
    fieldsets = (
        (None, {'fields': ('title', 'original_title', 'media_type', 'release_year', 'poster_url')}),
        ('External IDs', {'fields': ('kinopoisk_id', 'imdb_id', 'shikimori_id', 'mydramalist_id')}),
        ('Metadata', {'fields': ('genres', 'countries', 'description')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )


# ... (EpisodeInline registration remains the same) ...
class EpisodeInline(admin.TabularInline):
    model = Episode
    extra = 0
    fields = ('episode_number', 'title')
    ordering = ('episode_number',)


# ... (SeasonAdmin registration remains the same) ...
@admin.register(Season)
class SeasonAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'media_item_link', 'season_number')
    list_filter = ('media_item__media_type',)
    search_fields = ('media_item__title', 'season_number')
    inlines = [EpisodeInline]
    autocomplete_fields = ('media_item',)

    @admin.display(description='Media Item')
    def media_item_link(self, obj):
        if obj.media_item:
            link = reverse("admin:catalog_mediaitem_change", args=[obj.media_item.pk])
            return format_html('<a href="{}">{}</a>', link, obj.media_item)
        return "-"

    media_item_link.admin_order_field = 'media_item'


# ... (EpisodeAdmin registration remains the same) ...
@admin.register(Episode)
class EpisodeAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'season_link', 'episode_number', 'title')
    list_filter = ('season__media_item__media_type',)
    search_fields = ('title', 'season__media_item__title', 'episode_number')
    list_display_links = ('__str__',)
    autocomplete_fields = ['season']

    @admin.display(description='Season')
    def season_link(self, obj):
        if obj.season:
            link = reverse("admin:catalog_season_change", args=[obj.season.pk])
            return format_html('<a href="{}">{}</a>', link, obj.season)
        return "-"

    season_link.admin_order_field = 'season'


# --- Updated MediaSourceLinkAdmin ---
@admin.register(MediaSourceLink)
class MediaSourceLinkAdmin(admin.ModelAdmin):
    # --- CHANGED: Replaced translation_info with translation ---
    list_display = (
    'get_target_str', 'source', 'quality_info', 'translation', 'added_at', 'last_seen_at')  # Added last_seen_at
    list_filter = (
    'source', 'quality_info', 'translation', 'added_at', 'last_seen_at')  # Added translation and last_seen_at
    # --- END CHANGE ---
    search_fields = ('media_item__title', 'episode__title', 'player_link', 'source_specific_id',
                     'translation__title')  # Added translation title search
    readonly_fields = ('added_at', 'last_seen_at')  # Added last_seen_at
    autocomplete_fields = ['media_item', 'episode', 'source', 'translation']  # Added translation

    @admin.display(description='Target')
    def get_target_str(self, obj):
        target_obj = None
        link = "#"
        text = "Orphaned Link"

        if obj.episode:
            target_obj = obj.episode
            try:
                link = reverse("admin:catalog_episode_change", args=[target_obj.pk])
                text = str(target_obj)
            except Exception:
                text = f"Episode pk={target_obj.pk}"
        elif obj.media_item:
            target_obj = obj.media_item
            try:
                link = reverse("admin:catalog_mediaitem_change", args=[target_obj.pk])
                text = str(target_obj)
            except Exception:
                text = f"MediaItem pk={target_obj.pk}"

        return format_html('<a href="{}">{}</a>', link, text)

    get_target_str.admin_order_field = ('episode', 'media_item')


# --- Updated MediaItemSourceMetadataAdmin ---
@admin.register(MediaItemSourceMetadata)
class MediaItemSourceMetadataAdmin(admin.ModelAdmin):
    list_display = ('media_item_link', 'source', 'source_last_updated_at')
    list_filter = ('source', 'source_last_updated_at')
    search_fields = ('media_item__title', 'source__name')
    readonly_fields = ('source_last_updated_at',)
    autocomplete_fields = ('media_item', 'source')

    @admin.display(description='Media Item')
    def media_item_link(self, obj):
        if obj.media_item:
            link = reverse("admin:catalog_mediaitem_change", args=[obj.media_item.pk])
            return format_html('<a href="{}">{}</a>', link, obj.media_item)
        return "-"

    media_item_link.admin_order_field = 'media_item'


# --- Register Screenshot model ---
@admin.register(Screenshot)
class ScreenshotAdmin(admin.ModelAdmin):
    list_display = ('episode_link', 'url_thumbnail')
    search_fields = ('url', 'episode__season__media_item__title')
    readonly_fields = ('url_thumbnail',)
    autocomplete_fields = ('episode',)

    @admin.display(description='Episode')
    def episode_link(self, obj):
        if obj.episode:
            link = reverse("admin:catalog_episode_change", args=[obj.episode.pk])
            return format_html('<a href="{}">{}</a>', link, obj.episode)
        return "-"

    episode_link.admin_order_field = 'episode'

    @admin.display(description='Thumbnail')
    def url_thumbnail(self, obj):
        if obj.url:
            return format_html('<a href="{0}" target="_blank"><img src="{0}" height="50" /></a>', obj.url)
        return ""
