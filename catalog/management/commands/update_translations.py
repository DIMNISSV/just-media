# catalog/management/commands/update_translations.py

import logging
# Import timedelta from datetime
from datetime import timedelta
from typing import Dict, Set

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q, OuterRef, Subquery
# Keep timezone import for now()
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

    # --- add_arguments, _get_kodik_source, _log, _get_translation_map - без изменений ---
    def add_arguments(self, parser):
        parser.add_argument('--pk', type=int, nargs='+', help='Specify one or more MediaItem PKs to update.')
        parser.add_argument('--all', action='store_true',
                            help='Update translations for ALL MediaItems in the database.')
        parser.add_argument('--limit', type=int, default=None,
                            help='Limit the number of MediaItems processed when using --all.')
        parser.add_argument('--skip-recently-updated-meta', type=int, default=None, metavar='HOURS',
                            help='Skip items whose source metadata was updated within the last X hours (useful for --all).')
        parser.add_argument('--cleanup', action='store_true',
                            help='Remove stale MediaSourceLinks for processed items after updating.')

    def _get_kodik_source(self) -> Source:
        try:
            return Source.objects.get(slug=KODIK_SOURCE_SLUG)
        except Source.DoesNotExist:
            raise CommandError(f"Source with slug '{KODIK_SOURCE_SLUG}' not found.")

    def _log(self, message, style=None, verbosity=1, ending='\n'):
        if self.verbosity >= verbosity:
            styled_message = style(message) if style else message
            self.stdout.write(styled_message, ending=ending)

    def _get_translation_map(self) -> Dict[int, Translation]:
        return {t.kodik_id: t for t in Translation.objects.all()}

    @transaction.atomic
    def _process_media_item(self, media_item: MediaItem, kodik_source: Source, client: KodikApiClient,
                            translation_map: Dict[int, Translation], cleanup: bool):
        """Processes a single MediaItem: fetches all translations and updates related objects."""
        self._log(f"Processing MediaItem PK {media_item.pk}: '{media_item.title}'", verbosity=2)
        search_ids = {
            'kinopoisk_id': media_item.kinopoisk_id, 'imdb_id': media_item.imdb_id,
            'shikimori_id': media_item.shikimori_id, 'mydramalist_id': media_item.mydramalist_id
        }
        search_ids_filtered = {k: v for k, v in search_ids.items() if v}
        if not search_ids_filtered:
            self._log(f"  Skipping Item {media_item.pk}: No external IDs found for search.", style=self.style.WARNING)
            return 0

        search_params = {
            **search_ids_filtered,
            'with_episodes_data': 'true',
            'with_material_data': 'true'
        }
        self._log(f"  Searching Kodik using IDs: {search_ids_filtered}", verbosity=3)
        response_data = client.search_by_ids(**search_params, limit=100)

        if response_data is None or 'results' not in response_data:
            self._log(f"  Failed to fetch search results for Item {media_item.pk}. Check logs.", style=self.style.ERROR)
            return 0

        search_results = response_data.get('results', [])
        processed_count = 1  # Assume processed if we got this far

        if not search_results:
            self._log(f"  No search results (translations) found for Item {media_item.pk}.", verbosity=2)
        else:
            self._log(f"  Found {len(search_results)} translation variants for Item {media_item.pk}.", verbosity=2)

        processed_link_pks: Set[int] = set()
        check_start_time = timezone.now()

        for item_variant_data in search_results:
            variant_translation_data = item_variant_data.get('translation')
            if not variant_translation_data or 'id' not in variant_translation_data:
                logger.warning(f"Skipping variant for Item {media_item.pk}: Missing translation data.")
                continue

            kodik_translation_id = variant_translation_data['id']
            translation_obj = translation_map.get(kodik_translation_id)
            if not translation_obj:
                logger.warning(
                    f"Skipping variant for Item {media_item.pk}: Translation ID {kodik_translation_id} not found.")
                continue

            variant_link = item_variant_data.get('link')
            variant_quality = item_variant_data.get('quality')
            variant_source_specific_id = item_variant_data.get('id')

            if variant_link:
                link_defaults = {
                    'player_link': variant_link, 'quality_info': variant_quality,
                    'last_seen_at': check_start_time, 'source_specific_id': variant_source_specific_id
                }
                link_lookup = {
                    'source': kodik_source, 'media_item': media_item,
                    'episode': None, 'translation': translation_obj
                }
                try:
                    link_obj, created = MediaSourceLink.objects.update_or_create(defaults=link_defaults, **link_lookup)
                    log_action = "Created" if created else "Updated"
                    self._log(f"    {log_action} Main Link: {translation_obj.title}", verbosity=3)
                    processed_link_pks.add(link_obj.pk)
                except Exception as e:
                    logger.error(
                        f"Error saving main link for Item {media_item.pk}, Translation {translation_obj.title}: {e}")

            api_seasons_data = item_variant_data.get('seasons', {})
            if api_seasons_data:
                for season_num_str, season_content in api_seasons_data.items():
                    try:
                        season_number = int(season_num_str)
                    except (ValueError, TypeError):
                        continue
                    if season_number < -1:
                        continue

                    episodes_list_data = season_content.get('episodes') if isinstance(season_content, dict) else None

                    try:
                        season, season_created = Season.objects.get_or_create(media_item=media_item,
                                                                              season_number=season_number)
                    except Exception as e:
                        logger.error(f"Error get/create Season {season_number} for Item {media_item.pk}: {e}")
                        continue

                    if episodes_list_data and isinstance(episodes_list_data, dict):
                        for episode_num_str, episode_content in episodes_list_data.items():
                            try:
                                episode_number = int(episode_num_str)
                            except (ValueError, TypeError):
                                continue
                            if episode_number <= 0:
                                continue

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
                                episode, episode_created = Episode.objects.update_or_create(
                                    season=season, episode_number=episode_number, defaults={'title': episode_title}
                                )
                            except Exception as e:
                                logger.error(f"Error get/create/update Episode {episode_number} for {season}: {e}")
                                continue

                            if episode_screenshots:
                                existing_screenshot_urls = set(episode.screenshots.values_list('url', flat=True))
                                for screenshot_url in episode_screenshots:
                                    if screenshot_url not in existing_screenshot_urls:
                                        try:
                                            Screenshot.objects.get_or_create(episode=episode, url=screenshot_url)
                                        except Exception as e:
                                            logger.error(f"Error saving screenshot {screenshot_url} for {episode}: {e}")

                            if episode_link:
                                ep_link_defaults = {
                                    'player_link': episode_link, 'quality_info': variant_quality,
                                    'last_seen_at': check_start_time
                                }
                                ep_link_lookup = {
                                    'source': kodik_source, 'media_item': None,
                                    'episode': episode, 'translation': translation_obj
                                }
                                try:
                                    ep_link_obj, ep_created = MediaSourceLink.objects.update_or_create(
                                        defaults=ep_link_defaults, **ep_link_lookup)
                                    log_ep_action = "Created" if ep_created else "Updated"
                                    self._log(
                                        f"      {log_ep_action} Ep Link: S{season_number}E{episode_number} - {translation_obj.title}",
                                        verbosity=3)
                                    processed_link_pks.add(ep_link_obj.pk)
                                except Exception as e:
                                    logger.error(
                                        f"Error saving episode link for {episode}, Translation {translation_obj.title}: {e}")
        if cleanup:
            stale_links_qs = MediaSourceLink.objects.filter(
                Q(episode__season__media_item=media_item) | Q(media_item=media_item, episode=None),
                source=kodik_source
            ).exclude(pk__in=processed_link_pks)
            deleted_count, _ = stale_links_qs.delete()
            if deleted_count > 0:
                self._log(f"  Cleaned up {deleted_count} stale links for Item {media_item.pk}.",
                          style=self.style.WARNING)

        return processed_count

    def handle(self, *args, **options):
        """Handles the command execution."""
        self.verbosity = options['verbosity']
        pk_list = options['pk']
        process_all = options['all']
        limit = options['limit']
        skip_hours = options['skip_recently_updated_meta']
        cleanup = options['cleanup']

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
                skip_time = timezone.now() - timedelta(hours=skip_hours)
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
            # Random order significantly slows down pagination on large tables
            # Use default ordering or pk ordering instead if performance is an issue
            # media_items_qs = media_items_qs.order_by('?')
            media_items_qs = media_items_qs.order_by('pk')
            if limit:
                media_items_qs = media_items_qs[:limit]

        total_items_to_process = media_items_qs.count()
        self._log(f"Found {total_items_to_process} MediaItems to process.", verbosity=1)

        processed_count = 0
        items_iterable = media_items_qs
        if TQDM_AVAILABLE and self.verbosity == 1:
            items_iterable = tqdm(media_items_qs, total=total_items_to_process, desc="Updating Translations",
                                  unit="item")

        for media_item in items_iterable:
            try:
                processed_count += self._process_media_item(
                    media_item, kodik_source, client, translation_map, cleanup
                )
            except Exception as e:
                logger.exception(f"Critical error processing MediaItem PK {media_item.pk}. Skipping.")

        self._log(f"\nFinished update. Processed/Attempted {processed_count} / {total_items_to_process} items.",
                  self.style.SUCCESS)
