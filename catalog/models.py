# catalog/models.py
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _


class Genre(models.Model):
    name = models.CharField(_("Name"), max_length=100, unique=True)

    class Meta:
        verbose_name = _("Genre")
        verbose_name_plural = _("Genres")
        ordering = ['name']

    def __str__(self):
        return self.name


class Country(models.Model):
    name = models.CharField(_("Name"), max_length=100, unique=True)

    class Meta:
        verbose_name = _("Country")
        verbose_name_plural = _("Countries")
        ordering = ['name']

    def __str__(self):
        return self.name


class Source(models.Model):
    name = models.CharField(_("Name"), max_length=100, unique=True)
    slug = models.SlugField(_("Slug"), max_length=50, unique=True,
                            help_text=_("Short identifier for the source (e.g., 'kodik')"))

    class Meta:
        verbose_name = _("Source")
        verbose_name_plural = _("Sources")
        ordering = ['name']

    def __str__(self):
        return self.name


class MediaItem(models.Model):
    class MediaType(models.TextChoices):
        MOVIE = 'movie', _('Movie')
        TV_SHOW = 'tv_show', _('TV Show')
        ANIME_SERIES = 'anime_series', _('Anime Series')
        CARTOON = 'cartoon', _('Cartoon')
        DOCUMENTARY = 'documentary', _('Documentary')
        # Add more types as needed based on Kodik or other sources
        FOREIGN_MOVIE = 'foreign-movie', _('Foreign Movie (Kodik)')
        SOVIET_CARTOON = 'soviet-cartoon', _('Soviet Cartoon (Kodik)')
        FOREIGN_CARTOON = 'foreign-cartoon', _('Foreign Cartoon (Kodik)')
        RUSSIAN_CARTOON = 'russian-cartoon', _('Russian Cartoon (Kodik)')
        ANIME = 'anime', _('Anime (Kodik)')  # Could be movie or series
        RUSSIAN_MOVIE = 'russian-movie', _('Russian Movie (Kodik)')
        CARTOON_SERIAL = 'cartoon-serial', _('Cartoon Serial (Kodik)')
        DOCUMENTARY_SERIAL = 'documentary-serial', _('Documentary Serial (Kodik)')
        RUSSIAN_SERIAL = 'russian-serial', _('Russian Serial (Kodik)')
        FOREIGN_SERIAL = 'foreign-serial', _('Foreign Serial (Kodik)')
        ANIME_SERIAL = 'anime-serial', _('Anime Serial (Kodik)')  # Duplicate of ANIME_SERIES?
        MULTI_PART_FILM = 'multi-part-film', _('Multi-part Film (Kodik)')
        UNKNOWN = 'unknown', _('Unknown')

    title = models.CharField(_("Title"), max_length=255)
    original_title = models.CharField(_("Original Title"), max_length=255, blank=True, null=True)
    media_type = models.CharField(
        _("Media Type"),
        max_length=30,
        choices=MediaType.choices,
        default=MediaType.UNKNOWN,
        db_index=True
    )
    release_year = models.PositiveIntegerField(_("Release Year"), blank=True, null=True, db_index=True)
    description = models.TextField(_("Description"), blank=True, null=True)
    poster_url = models.URLField(_("Poster URL"), max_length=1024, blank=True, null=True)

    # External IDs
    kinopoisk_id = models.CharField(_("Kinopoisk ID"), max_length=20, unique=True, blank=True, null=True, db_index=True)
    imdb_id = models.CharField(_("IMDb ID"), max_length=20, unique=True, blank=True, null=True, db_index=True)
    shikimori_id = models.CharField(_("Shikimori ID"), max_length=20, unique=True, blank=True, null=True, db_index=True)
    mydramalist_id = models.CharField(_("MyDramaList ID"), max_length=20, unique=True, blank=True, null=True,
                                      db_index=True)
    # Consider adding more specific IDs like worldart_link, mdl_id if needed frequently

    genres = models.ManyToManyField(Genre, verbose_name=_("Genres"), blank=True, related_name="media_items")
    countries = models.ManyToManyField(Country, verbose_name=_("Countries"), blank=True, related_name="media_items")

    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Media Item")
        verbose_name_plural = _("Media Items")
        ordering = ['-updated_at', 'title']
        # Ensure unique items based on primary external IDs if available
        constraints = [
            models.UniqueConstraint(fields=['kinopoisk_id'], name='unique_kinopoisk_id',
                                    condition=models.Q(kinopoisk_id__isnull=False)),
            models.UniqueConstraint(fields=['imdb_id'], name='unique_imdb_id',
                                    condition=models.Q(imdb_id__isnull=False)),
            models.UniqueConstraint(fields=['shikimori_id'], name='unique_shikimori_id',
                                    condition=models.Q(shikimori_id__isnull=False)),
            models.UniqueConstraint(fields=['mydramalist_id'], name='unique_mydramalist_id',
                                    condition=models.Q(mydramalist_id__isnull=False)),
            # Add a fallback uniqueness constraint? E.g., title+year+type might be too broad.
            # models.UniqueConstraint(fields=['title', 'release_year', 'media_type'], name='unique_title_year_type')
        ]

    def __str__(self):
        year_str = f" ({self.release_year})" if self.release_year else ""
        return f"{self.title}{year_str} [{self.get_media_type_display()}]"


class Season(models.Model):
    media_item = models.ForeignKey(MediaItem, on_delete=models.CASCADE, related_name='seasons',
                                   verbose_name=_("Media Item"))
    season_number = models.IntegerField(_("Season Number"), db_index=True)

    # Add other season-specific info if needed (e.g., title, year)

    class Meta:
        verbose_name = _("Season")
        verbose_name_plural = _("Seasons")
        ordering = ['media_item', 'season_number']
        unique_together = ('media_item', 'season_number')  # Ensure one season number per media item

    def __str__(self):
        media_title = self.media_item.title if self.media_item else "Unknown Media"
        if self.season_number == 0:
            season_str = "Season 0 (OVA/Movie)"  # Or just "OVA/Movie"
        elif self.season_number == -1:
            season_str = "Specials"
        else:
            season_str = f"Season {self.season_number}"
        return f"{media_title} - {season_str}"


class Episode(models.Model):
    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name='episodes', verbose_name=_("Season"))
    episode_number = models.PositiveIntegerField(_("Episode Number"))
    title = models.CharField(_("Title"), max_length=255, blank=True, null=True)

    # Add other episode-specific info if needed (e.g., air_date, description)

    class Meta:
        verbose_name = _("Episode")
        verbose_name_plural = _("Episodes")
        ordering = ['season', 'episode_number']
        unique_together = ('season', 'episode_number')  # Ensure one episode number per season

    def __str__(self):
        title_str = f": {self.title}" if self.title else ""
        return f"{self.season} - Episode {self.episode_number}{title_str}"


class MediaSourceLink(models.Model):
    media_item = models.ForeignKey(
        MediaItem,
        on_delete=models.CASCADE,
        related_name='source_links',
        verbose_name=_("Media Item"),
        blank=True, null=True  # Allow link to be associated only with an episode
    )
    episode = models.ForeignKey(
        Episode,
        on_delete=models.CASCADE,
        related_name='source_links',
        verbose_name=_("Episode"),
        blank=True, null=True  # Allow link to be associated only with a media item (e.g., movie)
    )
    source = models.ForeignKey(Source, on_delete=models.CASCADE, related_name='links', verbose_name=_("Source"))
    player_link = models.URLField(_("Player Link"), max_length=2048)  # Increased length for potentially long URLs
    translation_info = models.CharField(_("Translation Info"), max_length=150, blank=True, null=True,
                                        help_text=_(
                                            "Voiceover/subtitle info from the source (e.g., 'ColdFilm', 'Sub')"))
    quality_info = models.CharField(_("Quality Info"), max_length=50, blank=True, null=True,
                                    help_text=_("Quality reported by the source (e.g., '720p', 'HDTVRip')"))
    source_specific_id = models.CharField(_("Source Specific ID"), max_length=100, blank=True, null=True, db_index=True,
                                          help_text=_(
                                              "ID of the content within the source system (e.g., 'movie-12345')"))

    added_at = models.DateTimeField(_("Added At"), auto_now_add=True)

    class Meta:
        verbose_name = _("Media Source Link")
        verbose_name_plural = _("Media Source Links")
        ordering = ['-added_at']
        # Ensure we don't add the exact same link from the same source twice
        # This might need refinement based on how sources update links (e.g., quality change)
        unique_together = ('source', 'player_link')
        # Or perhaps unique on source + media_item/episode + translation + quality? Depends on API behavior.
        # unique_together = ('source', 'media_item', 'episode', 'translation_info', 'quality_info')

    def clean(self):
        # Ensure that either media_item or episode is set, but not neither. Both is technically okay for episode links.
        if self.media_item is None and self.episode is None:
            raise ValidationError(_("A source link must be associated with either a Media Item or an Episode."))
        # Ensure episode belongs to the media_item if both are set
        if self.media_item and self.episode and self.episode.season.media_item != self.media_item:
            raise ValidationError(_("The selected Episode does not belong to the selected Media Item."))

    def __str__(self):
        target = self.episode if self.episode else self.media_item
        return f"Link from {self.source.name} for {target}"


class MediaItemSourceMetadata(models.Model):
    """ Stores metadata about a MediaItem from a specific Source """
    media_item = models.ForeignKey(
        MediaItem,
        on_delete=models.CASCADE,
        related_name='source_metadata',
        verbose_name=_("Media Item")
    )
    source = models.ForeignKey(
        Source,
        on_delete=models.CASCADE,
        related_name='media_metadata',
        verbose_name=_("Source")
    )
    source_last_updated_at = models.DateTimeField(
        _("Source Last Updated At"),
        blank=True, null=True, db_index=True,
        help_text=_("Timestamp of the last update received from this source for this item")
    )

    class Meta:
        verbose_name = _("Media Item Source Metadata")
        verbose_name_plural = _("Media Item Source Metadata")
        # Ensure only one metadata record per media_item/source combination
        unique_together = ('media_item', 'source')
        ordering = ['media_item', 'source']

    def __str__(self):
        updated_str = self.source_last_updated_at.strftime(
            '%Y-%m-%d %H:%M:%S') if self.source_last_updated_at else 'Never'
        return f"Metadata for '{self.media_item}' from '{self.source.name}' (Source Updated: {updated_str})"
