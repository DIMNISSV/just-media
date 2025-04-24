# catalog/management/commands/update_translations.py

import logging
# Note: We might not need the mapper here as we process structured data from /search results directly
# from catalog.services.kodik_mapper import map_kodik_item_to_models
from typing import Dict, Optional, Set

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q, OuterRef, Subquery  # Import database functions
from django.utils import timezone

from catalog.models import (
    MediaItem, Source, Season, Episode, MediaSourceLink, Screenshot, Translation, MediaItemSourceMetadata
)
from catalog.services.kodik_client import KodikApiClient

try:
    from tqdm import tqdm

    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False

logger = logging.getLogger(__name__)
KODIK_SOURCE_SLUG = 'kodik'


class Command(BaseCommand):
    help = ('Updates or creates Seasons, Episodes, Screenshots, and MediaSourceLinks '
            'for all available translations for specified MediaItems using Kodik API /search.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--pk',
            type=int,
            nargs='+',  # Allows multiple PKs: --pk 1 2 3
            help='Specify one or more MediaItem PKs to update.',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Update translations for ALL MediaItems in the database.',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Limit the number of MediaItems processed when using --all.',
        )
        parser.add_argument(
            '--skip-recently-updated-meta',
            type=int,
            default=None,
            metavar='HOURS',
            help='Skip items whose source metadata was updated within the last X hours (useful for --all).',
        )
        parser.add_argument(
            '--with-episodes-data',
            action='store_true',  # Keep this flag to request screenshots etc.
            default=True,  # Default to True as this command needs episode data
            help='Request detailed season and episode data (including screenshots) from Kodik /search.',
        )
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Remove stale MediaSourceLinks for processed items after updating.',
        )

    def _get_kodik_source(self) -> Source:
        try:
            return Source.objects.get(slug=KODIK_SOURCE_SLUG)
        except Source.DoesNotExist:
            raise CommandError(f"Source with slug '{KODIK_SOURCE_SLUG}' not found.")

    def _log(self, message, style=None, verbosity=1, ending='\n'):
        if self.verbosity >= verbosity:
            styled_message = style(message) if style else message
            self.stdout.write(styled_message, ending=ending)

    def _get_external_ids(self, media_item: MediaItem) -> Dict[str, Optional[str]]:
        """Extracts available external IDs from a MediaItem."""
        return {
            'kinopoisk_id': media_item.kinopoisk_id,
            'imdb_id': media_item.imdb_id,
            'shikimori_id': media_item.shikimori_id,
            'mydramalist_id': media_item.mydramalist_id,
        }

    def _get_translation_map(self) -> Dict[int, Translation]:
        """Fetches all translations from DB into a dict keyed by kodik_id."""
        return {t.kodik_id: t for t in Translation.objects.all()}

    @transaction.atomic
    def _process_media_item(self, media_item: MediaItem, kodik_source: Source, client: KodikApiClient,
                            translation_map: Dict[int, Translation], cleanup: bool, with_episodes_data: bool):
        """Processes a single MediaItem: fetches all translations and updates related objects."""
        self._log(f"Processing MediaItem PK {media_item.pk}: '{media_item.title}'", verbosity=2)
        external_ids = self._get_external_ids(media_item)

        if not any(external_ids.values()):
            self._log(f"  Skipping Item {media_item.pk}: No external IDs found for search.", style=self.style.WARNING)
            return 0

        search_params = external_ids.copy()
        if with_episodes_data:
            search_params['with_episodes_data'] = 'true'
            search_params['with_material_data'] = 'true'  # Often useful together

        response_data = client.search_by_ids(**search_params, limit=100)  # Increase limit in case of many translations

        if response_data is None or 'results' not in response_data:
            self._log(f"  Failed to fetch search results for Item {media_item.pk}. Check logs.", style=self.style.ERROR)
            return 0

        search_results = response_data.get('results', [])
        if not search_results:
            self._log(f"  No search results (translations) found for Item {media_item.pk}.", verbosity=2)
            # Optionally cleanup existing links if cleanup is enabled and no results found?
            # Or keep them? Let's keep them for now.
            return 1  # Count as processed (checked)

        self._log(f"  Found {len(search_results)} translation variants for Item {media_item.pk}.", verbosity=2)

        processed_link_pks: Set[int] = set()  # Track Link PKs seen in this run for cleanup
        check_start_time = timezone.now()  # Timestamp for cleanup

        for item_variant_data in search_results:
            # Each item_variant_data represents one translation for the same MediaItem
            variant_translation_data = item_variant_data.get('translation')
            if not variant_translation_data or 'id' not in variant_translation_data:
                logger.warning(
                    f"Skipping translation variant for Item {media_item.pk}: Missing translation data or ID. Variant data: {item_variant_data.get('id', 'N/A')}")
                continue

            kodik_translation_id = variant_translation_data['id']
            translation_obj = translation_map.get(kodik_translation_id)
            if not translation_obj:
                logger.warning(
                    f"Skipping translation variant for Item {media_item.pk}: Translation with Kodik ID {kodik_translation_id} not found in local DB. Run populate_translations.")
                continue

            variant_link = item_variant_data.get('link')
            variant_quality = item_variant_data.get('quality')
            variant_source_specific_id = item_variant_data.get('id')  # e.g., movie-123 or serial-456

            # Create/Update link for the main item
            if variant_link:
                link_defaults = {'player_link': variant_link, 'quality_info': variant_quality,
                                 'last_seen_at': check_start_time}
                link_lookup = {'source': kodik_source, 'media_item': media_item, 'episode': None,
                               'translation': translation_obj}
                try:
                    link_obj, created = MediaSourceLink.objects.update_or_create(defaults=link_defaults, **link_lookup)
                    if created:
                        self._log(f"    Created Main Link: {translation_obj.title}", verbosity=3)
                    else:
                        self._log(f"    Updated Main Link: {translation_obj.title}", verbosity=3)
                    processed_link_pks.add(link_obj.pk)
                except Exception as e:
                    logger.error(
                        f"Error saving main link for Item {media_item.pk}, Translation {translation_obj.title}: {e}")

            # Process Seasons and Episodes for this translation variant
            api_seasons_data = item_variant_data.get('seasons', {})
            if api_seasons_data:
                for season_num_str, season_content in api_seasons_data.items():
                    try:
                        season_number = int(season_num_str)
                    except (ValueError, TypeError):
                        continue
                    if season_number < -1: continue

                    episodes_list_data = season_content.get('episodes') if isinstance(season_content, dict) else None
                    season_link = season_content.get('link')  # Link for the whole season

                    try:
                        season, _ = Season.objects.get_or_create(media_item=media_item, season_number=season_number)
                    except Exception as e:
                        logger.error(f"Error getting/creating Season {season_number} for Item {media_item.pk}: {e}")
                        continue

                    if episodes_list_data and isinstance(episodes_list_data, dict):
                        for episode_num_str, episode_content in episodes_list_data.items():
                            try:
                                episode_number = int(episode_num_str)
                            except (ValueError, TypeError):
                                continue
                            if episode_number <= 0: continue

                            episode_title = None
                            episode_link = None
                            episode_screenshots = []

                            if isinstance(episode_content, str):
                                episode_link = episode_content
                            elif isinstance(episode_content, dict):
                                episode_link = episode_content.get('link')
                                episode_title = episode_content.get('title')
                                screenshots_raw = episode_content.get('screenshots')
                                if isinstance(screenshots_raw, list):
                                    episode_screenshots = [s for s in screenshots_raw if
                                                           isinstance(s, str) and s.startswith('http')]

                            episode = None
                            try:
                                episode, _ = Episode.objects.update_or_create(
                                    season=season, episode_number=episode_number, defaults={'title': episode_title}
                                )
                            except Exception as e:
                                logger.error(f"Error getting/creating Episode {episode_number} for {season}: {e}")
                                continue

                            if episode_screenshots:
                                for screenshot_url in episode_screenshots:
                                    try:
                                        Screenshot.objects.get_or_create(episode=episode, url=screenshot_url)
                                    except Exception as e:
                                        logger.error(f"Error saving screenshot {screenshot_url} for {episode}: {e}")

                            if episode_link:
                                ep_link_defaults = {'player_link': episode_link, 'quality_info': variant_quality,
                                                    'last_seen_at': check_start_time}
                                ep_link_lookup = {'source': kodik_source, 'media_item': None, 'episode': episode,
                                                  'translation': translation_obj}
                                # Generate a specific ID if needed, or rely on unique constraint
                                # ep_link_lookup['source_specific_id'] = f"{variant_source_specific_id}_s{season_number}_e{episode_number}"
                                try:
                                    ep_link_obj, ep_created = MediaSourceLink.objects.update_or_create(
                                        defaults=ep_link_defaults, **ep_link_lookup)
                                    if ep_created:
                                        self._log(
                                            f"      Created Ep Link: S{season_number}E{episode_number} - {translation_obj.title}",
                                            verbosity=3)
                                    else:
                                        self._log(
                                            f"      Updated Ep Link: S{season_number}E{episode_number} - {translation_obj.title}",
                                            verbosity=3)
                                    processed_link_pks.add(ep_link_obj.pk)
                                except Exception as e:
                                    logger.error(
                                        f"Error saving episode link for {episode}, Translation {translation_obj.title}: {e}")

        # --- Cleanup Stale Links ---
        if cleanup:
            stale_links_qs = MediaSourceLink.objects.filter(
                Q(episode__season__media_item=media_item) | Q(media_item=media_item, episode=None),
                source=kodik_source
            ).exclude(pk__in=processed_link_pks)  # Exclude links we just processed

            # Alternative cleanup: by timestamp
            # stale_links_qs = MediaSourceLink.objects.filter(
            #     Q(episode__season__media_item=media_item) | Q(media_item=media_item, episode=None),
            #     source=kodik_source,
            #     Q(last_seen_at__lt=check_start_time) | Q(last_seen_at__isnull=True)
            # )

            deleted_count, _ = stale_links_qs.delete()
            if deleted_count > 0:
                self._log(f"  Cleaned up {deleted_count} stale links for Item {media_item.pk}.",
                          style=self.style.WARNING)

        return 1  # Processed successfully

    def handle(self, *args, **options):
        self.verbosity = options['verbosity']
        pk_list = options['pk']
        process_all = options['all']
        limit = options['limit']
        skip_hours = options['skip_recently_updated_meta']
        cleanup = options['cleanup']
        with_episodes_data = options['with_episodes_data']

        if not pk_list and not process_all:
            raise CommandError("Please specify at least one MediaItem PK using --pk or use --all.")
        if pk_list and process_all:
            raise CommandError("Cannot use --pk and --all together.")

        self._log("Starting Kodik translation and episode update...", self.style.NOTICE)
        kodik_source = self._get_kodik_source()
        try:
            client = KodikApiClient()
        except ValueError as e:
            raise CommandError(f"API Client initialization failed: {e}")

        translation_map = self._get_translation_map()
        if not translation_map:
            self._log("Warning: Translation table is empty. Run 'populate_translations' first.", self.style.WARNING)
            # Continue? Or raise error? Let's continue but links won't be saved properly.

        media_items_qs = MediaItem.objects.none()
        if pk_list:
            media_items_qs = MediaItem.objects.filter(pk__in=pk_list)
            if media_items_qs.count() != len(pk_list):
                found_pks = set(media_items_qs.values_list('pk', flat=True))
                missing_pks = set(pk_list) - found_pks
                self._log(f"Warning: Could not find MediaItems with PKs: {missing_pks}", self.style.WARNING)
        elif process_all:
            media_items_qs = MediaItem.objects.all()
            if skip_hours is not None:
                skip_time = timezone.now() - timezone.timedelta(hours=skip_hours)
                # Subquery to get the latest update time for the Kodik source for each item
                latest_meta_update = MediaItemSourceMetadata.objects.filter(
                    media_item=OuterRef('pk'),
                    source=kodik_source
                ).values('source_last_updated_at')[:1]

                media_items_qs = media_items_qs.annotate(
                    kodik_meta_updated_at=Subquery(latest_meta_update)
                ).filter(
                    Q(kodik_meta_updated_at__isnull=True) | Q(kodik_meta_updated_at__lt=skip_time)
                )
                self._log(f"Processing items whose metadata was updated before {skip_time} or never.", verbosity=1)

            media_items_qs = media_items_qs.order_by('?')  # Process in random order? Or by PK?
            if limit:
                media_items_qs = media_items_qs[:limit]

        total_items = media_items_qs.count()
        self._log(f"Found {total_items} MediaItems to process.", verbosity=1)

        processed_count = 0
        items_iterable = media_items_qs
        if TQDM_AVAILABLE and self.verbosity == 1:
            items_iterable = tqdm(media_items_qs, total=total_items, desc="Updating Translations", unit="item")

        for media_item in items_iterable:
            try:
                processed_count += self._process_media_item(
                    media_item, kodik_source, client, translation_map, cleanup, with_episodes_data
                )
            except Exception as e:
                logger.exception(f"Critical error processing MediaItem PK {media_item.pk}. Skipping.")

        self._log(f"\nFinished update. Processed {processed_count} / {total_items} items.", self.style.SUCCESS)
