# catalog/admin.py
from django.contrib import admin
from .models import (
    Genre, Country, Source, MediaItem, Season, Episode, MediaSourceLink
)

# Simple registration for basic models
admin.site.register(Genre)
admin.site.register(Country)


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    search_fields = ('name', 'slug')


# Customized admin for MediaItem for better readability
@admin.register(MediaItem)
class MediaItemAdmin(admin.ModelAdmin):
    list_display = ('title', 'release_year', 'media_type', 'kinopoisk_id', 'imdb_id', 'updated_at')
    list_filter = ('media_type', 'release_year', 'genres', 'countries')
    search_fields = ('title', 'original_title', 'kinopoisk_id', 'imdb_id', 'shikimori_id', 'mydramalist_id')
    filter_horizontal = ('genres', 'countries',)  # Easier M2M selection
    readonly_fields = ('created_at', 'updated_at')
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
            'classes': ('collapse',)  # Keep timestamps collapsed by default
        }),
    )


# Inline admin for Seasons within MediaItem admin
class SeasonInline(admin.TabularInline):  # Or admin.StackedInline
    model = Season
    extra = 0  # Don't show extra empty forms
    fields = ('season_number',)  # Add more fields if Season model grows
    ordering = ('season_number',)


# Inline admin for Episodes within Season admin
class EpisodeInline(admin.TabularInline):
    model = Episode
    extra = 0
    fields = ('episode_number', 'title')
    ordering = ('episode_number',)
    # Optional: Add search fields if episode titles are relevant
    # search_fields = ('title',)


@admin.register(Season)
class SeasonAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'media_item', 'season_number')
    list_filter = ('media_item__media_type',)  # Filter by type of parent media
    search_fields = ('media_item__title', 'season_number')
    inlines = [EpisodeInline]  # Show episodes directly within the season admin


@admin.register(Episode)
class EpisodeAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'season', 'episode_number', 'title')
    list_filter = ('season__media_item__media_type',)
    search_fields = ('title', 'season__media_item__title', 'episode_number')
    # Link back to parent objects for easier navigation
    list_display_links = ('__str__',)
    autocomplete_fields = ['season']  # Makes selecting season easier if many exist


@admin.register(MediaSourceLink)
class MediaSourceLinkAdmin(admin.ModelAdmin):
    list_display = ('get_target_str', 'source', 'quality_info', 'translation_info', 'added_at')
    list_filter = ('source', 'quality_info', 'translation_info', 'added_at')
    search_fields = ('media_item__title', 'episode__title', 'player_link', 'source_specific_id')
    readonly_fields = ('added_at',)
    autocomplete_fields = ['media_item', 'episode', 'source']  # Make FK selection easier

    @admin.display(description='Target')
    def get_target_str(self, obj):
        # Helper method to display which item/episode the link belongs to
        if obj.episode:
            return str(obj.episode)
        elif obj.media_item:
            return str(obj.media_item)
        return "Orphaned Link"  # Should not happen with clean() method
