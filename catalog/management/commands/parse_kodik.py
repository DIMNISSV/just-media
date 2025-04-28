# catalog/management/commands/parse_kodik.py

import json
import logging
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple

from dateutil.parser import isoparse
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction  # Import models
from django.db.models import Q

from catalog.models import (
    MediaItem, Genre, Country, Source, MediaItemSourceMetadata
)
from catalog.services.kodik_client import KodikApiClient
from catalog.services.kodik_mapper import map_kodik_item_to_models

try:
    from tqdm import tqdm

    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False

logger = logging.getLogger(__name__)
KODIK_SOURCE_SLUG = 'kodik'


class Command(BaseCommand):
    help = 'Parses CORE media data (MediaItem, Genres, Countries, Metadata) from Kodik API /list.'

    def add_arguments(self, parser):
        """Adds command line arguments."""
        parser.add_argument('--limit-pages', type=int, default=None, dest='limit_pages',
                            help='Limit the number of API pages to process.')
        parser.add_argument('--start-page-link', type=str, default=None, dest='start_page_link',
                            help='Start parsing from a specific Kodik "next_page" URL.')
        parser.add_argument('--target-page', type=int, default=None, dest='target_page',
                            help='Fetch pages sequentially but only start processing from this page number.')
        parser.add_argument('--limit-items-per-page', type=int, default=KodikApiClient.DEFAULT_LIMIT,
                            dest='limit_items_per_page',
                            help=f'Number of items per API page (1-100, default: {KodikApiClient.DEFAULT_LIMIT}).')
        parser.add_argument('--types', type=str, default=None, help='Comma-separated list of media types to fetch.')
        parser.add_argument('--year', type=str, default=None, help='Filter by year or comma-separated years.')
        parser.add_argument('--sort-by', type=str, default='updated_at', dest='sort',
                            choices=['updated_at', 'created_at', 'year', 'kinopoisk_rating', 'imdb_rating',
                                     'shikimori_rating'], help='Field to sort results by.')
        parser.add_argument('--sort-direction', type=str, default='desc', dest='order', choices=['asc', 'desc'],
                            help='Sort direction.')
        parser.add_argument('--with-material-data', action='store_true',
                            help='Request additional material data (needed for genres, countries, description, poster).')
        parser.add_argument('--fill-empty-fields', action='store_true',
                            help='Update empty fields on existing items even if API data is not newer.')

    def _get_kodik_source(self) -> Source:
        """Gets the Kodik source object or raises CommandError."""
        try:
            return Source.objects.get(slug=KODIK_SOURCE_SLUG)
        except Source.DoesNotExist:
            raise CommandError(f"Source with slug '{KODIK_SOURCE_SLUG}' not found. Please create it first.")

    def _log(self, message, style=None, verbosity=1, ending='\n'):
        """Logs messages to stdout based on verbosity level."""
        if self.verbosity >= verbosity:
            styled_message = style(message) if style else message
            self.stdout.write(styled_message, ending=ending)

    def _build_exact_match_query(self, api_ids: Dict[str, Optional[str]]) -> Q:
        """Builds a Q object for exact match based on all provided IDs (including None)."""
        q_object = Q()
        id_fields = ['kinopoisk_id', 'imdb_id', 'shikimori_id', 'mydramalist_id']
        for field in id_fields:
            value = api_ids.get(field)  # Get value or None
            # Use __isnull for None values to ensure correct matching
            if value is None:
                q_object &= Q(**{f"{field}__isnull": True})
            else:
                q_object &= Q(**{field: value})
        return q_object

    @transaction.atomic
    def _process_single_item(self, item_data: Dict[str, Any], kodik_source: Source, fill_empty_fields: bool) -> Tuple[
        Optional[MediaItem], str]:
        """
        Processes a single item from Kodik API.
        Tries to find an exact match, then updates or creates.
        Returns the processed MediaItem (or None) and an action string ('created', 'updated', 'skipped', 'error').
        """
        item_id_str = item_data.get('id', 'N/A')
        api_updated_at_str = item_data.get('updated_at')
        api_updated_at: Optional[datetime] = None
        action = 'skipped'  # Default action

        if api_updated_at_str:
            try:
                api_updated_at = isoparse(api_updated_at_str)
                if api_updated_at.tzinfo is None:
                    api_updated_at = api_updated_at.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError) as e:
                logger.warning(
                    f"Could not parse updated_at '{api_updated_at_str}' for item {item_id_str}: {e}. Skipping.")
                return None, 'skipped'
        else:
            logger.warning(f"Missing 'updated_at' in API data for item {item_id_str}. Skipping.")
            return None, 'skipped'

        try:
            mapped_data = map_kodik_item_to_models(item_data)
            if not mapped_data:
                return None, 'skipped'

            media_item_data = mapped_data.get('media_item_data', {})
            genre_names = mapped_data.get('genres', [])
            country_names = mapped_data.get('countries', [])

            if not media_item_data.get('title'):
                logger.warning(f"Skipping item {item_id_str} due to missing title after mapping.")
                return None, 'skipped'

            # Extract all potential IDs from the mapped data for matching
            api_ids = {
                'kinopoisk_id': media_item_data.get('kinopoisk_id'),
                'imdb_id': media_item_data.get('imdb_id'),
                'shikimori_id': media_item_data.get('shikimori_id'),
                'mydramalist_id': media_item_data.get('mydramalist_id'),
            }
            api_non_empty_ids = {k: v for k, v in api_ids.items() if v}

            if not api_non_empty_ids:
                logger.warning(
                    f"Skipping item {item_id_str} ('{media_item_data['title']}'): No external IDs provided by API.")
                return None, 'skipped'

            media_item = None
            created = False

            # --- Step 1: Exact Match Lookup ---
            exact_match_query = self._build_exact_match_query(api_ids)
            try:
                media_item = MediaItem.objects.get(exact_match_query)
                action = 'exact_match_found'
                self._log(
                    f"  Found exact match by ID combination for item {item_id_str} -> MediaItem PK {media_item.pk}",
                    verbosity=2)
            except MediaItem.DoesNotExist:
                self._log(f"  No exact match found for item {item_id_str}. Proceeding to check for updates/creation.",
                          verbosity=3)
                action = 'no_exact_match'  # Placeholder, will be updated
                pass  # Continue processing later
            except MediaItem.MultipleObjectsReturned:
                logger.error(
                    f"CRITICAL: Multiple MediaItems found with exact ID combination {api_ids} for Kodik item {item_id_str}. Manual intervention needed.")
                return None, 'error'
            except Exception as e:
                logger.exception(
                    f"Unexpected error during exact match lookup for item {item_id_str} with query {exact_match_query}: {e}")
                return None, 'error'

            # --- If exact match found, proceed to update check ---
            if action == 'exact_match_found' and media_item:
                metadata, meta_created = MediaItemSourceMetadata.objects.get_or_create(
                    media_item=media_item, source=kodik_source
                )

                should_update_main_data = False
                fields_to_update = {}
                # Prepare data for potential update, excluding the IDs used for matching
                defaults_for_update = media_item_data.copy()
                for key in api_ids.keys():
                    defaults_for_update.pop(key, None)

                if meta_created or metadata.source_last_updated_at is None or api_updated_at > metadata.source_last_updated_at:
                    should_update_main_data = True
                    fields_to_update = defaults_for_update
                    self._log(f"    API data is newer or metadata created for MediaItem {media_item.pk}.", verbosity=3)
                elif fill_empty_fields:
                    for field, value in defaults_for_update.items():
                        if hasattr(media_item, field) and not getattr(media_item, field, None) and value:
                            fields_to_update[field] = value
                    if fields_to_update:
                        self._log(
                            f"    Planning to fill empty fields for MediaItem {media_item.pk}: {list(fields_to_update.keys())}",
                            verbosity=2)

                if fields_to_update:
                    self._log(f"    Updating fields for MediaItem {media_item.pk} ('{media_item.title}').", verbosity=2)
                    update_fields_list = list(fields_to_update.keys())
                    for field, value in fields_to_update.items():
                        setattr(media_item, field, value)
                    try:
                        # Ensure 'updated_at' is handled by auto_now=True, exclude it if present
                        if 'updated_at' in update_fields_list:
                            update_fields_list.remove('updated_at')
                        media_item.save(update_fields=update_fields_list)
                        action = 'updated'  # Final action status
                        self._log(f"      Updated fields: {', '.join(update_fields_list)}", verbosity=3)
                    except Exception as e:
                        logger.exception(f"Error saving updated fields for existing MediaItem {media_item.pk}: {e}")
                        return media_item, 'error'

                    # Update M2M only if primary fields were updated
                    try:
                        genres_qs = Genre.objects.filter(name__in=[name.strip() for name in genre_names])
                        current_genres = set(media_item.genres.all())
                        target_genres = set(genres_qs) | {
                            Genre.objects.get_or_create(name__iexact=name, defaults={'name': name.strip()})[0] for name
                            in genre_names if name.strip()}  # Ensure creation too

                        if current_genres != target_genres:
                            media_item.genres.set(list(target_genres))

                        countries_qs = Country.objects.filter(name__in=[name.strip() for name in country_names])
                        current_countries = set(media_item.countries.all())
                        target_countries = set(countries_qs) | {
                            Country.objects.get_or_create(name__iexact=name, defaults={'name': name.strip()})[0] for
                            name in country_names if name.strip()}

                        if current_countries != target_countries:
                            media_item.countries.set(list(target_countries))

                        self._log(f"      Checked/Updated M2M relations for MediaItem {media_item.pk}", verbosity=3)
                    except Exception as e:
                        logger.error(f"Error updating M2M for MediaItem {media_item.pk} during update: {e}")

                elif should_update_main_data:  # No specific fields changed, but API was newer (maybe only M2M changed)
                    try:
                        genres_qs = Genre.objects.filter(name__in=[name.strip() for name in genre_names])
                        current_genres = set(media_item.genres.all())
                        target_genres = set(genres_qs) | {
                            Genre.objects.get_or_create(name__iexact=name, defaults={'name': name.strip()})[0] for name
                            in genre_names if name.strip()}

                        countries_qs = Country.objects.filter(name__in=[name.strip() for name in country_names])
                        current_countries = set(media_item.countries.all())
                        target_countries = set(countries_qs) | {
                            Country.objects.get_or_create(name__iexact=name, defaults={'name': name.strip()})[0] for
                            name in country_names if name.strip()}

                        m2m_changed = False
                        if current_genres != target_genres:
                            media_item.genres.set(list(target_genres))
                            m2m_changed = True
                        if current_countries != target_countries:
                            media_item.countries.set(list(target_countries))
                            m2m_changed = True

                        if m2m_changed:
                            action = 'updated'  # Mark as updated if only M2M changed
                            self._log(f"      Updated M2M relations (API newer) for MediaItem {media_item.pk}",
                                      verbosity=3)
                        else:
                            action = 'skipped'  # Nothing changed even if API date was newer

                    except Exception as e:
                        logger.error(f"Error updating M2M for MediaItem {media_item.pk} when API newer: {e}")
                        action = 'skipped'  # Treat as skipped if M2M update fails

                else:
                    self._log(
                        f"    Skipping update for MediaItem {media_item.pk} (API data not newer/no empty fields/no M2M changes)",
                        verbosity=2)
                    action = 'skipped'  # No changes were made

                # Update metadata timestamp if we considered updating (API newer or meta created)
                if should_update_main_data:
                    try:
                        metadata.source_last_updated_at = api_updated_at
                        metadata.save(update_fields=['source_last_updated_at'])
                        self._log(f"      Updated metadata timestamp for MediaItem {media_item.pk}", verbosity=3)
                    except Exception as e:
                        logger.error(f"Failed to update metadata timestamp for MediaItem {media_item.pk}: {e}")

                return media_item, action

            # --- Placeholder for next steps if no exact match ---
            elif action == 'no_exact_match':
                self._log(f"  Exact match not found for {item_id_str}. Further processing deferred.", verbosity=2)
                return None, 'skipped_no_match'  # Special status for now

            else:  # Should not happen
                logger.error(f"Unexpected state for item {item_id_str}. Action: {action}")
                return None, 'error'


        except Exception as e:
            logger.error(f"Outer error processing item {item_id_str}.")
            logger.exception(
                f"Exception details: {e}\n"
                f"Problematic item data:\n{json.dumps(item_data, indent=2, ensure_ascii=False)}"
            )
            return None, 'error'

    def handle(self, *args, **options):
        """Handles the command execution."""
        self.verbosity = options['verbosity']
        self._log(f"Starting Kodik CORE data parsing with verbosity level: {self.verbosity}", self.style.NOTICE)

        kodik_source = self._get_kodik_source()
        fill_empty_fields = options['fill_empty_fields']

        try:
            client = KodikApiClient()
        except ValueError as e:
            raise CommandError(f"API Client initialization failed: {e}")

        api_params = {}
        if options['types']: api_params['types'] = options['types']
        if options['year']: api_params['year'] = options['year']
        if options['sort']: api_params['sort'] = options['sort']
        if options['order']: api_params['order'] = options['order']
        api_params['with_material_data'] = 'true'  # Always request material data
        limit_per_page = min(max(options['limit_items_per_page'], 1), 100)

        self._log(f"Using API parameters: {api_params}", verbosity=2)
        self._log(f"Items per page: {limit_per_page}", verbosity=2)
        if options['target_page']: self._log(f"Will skip processing until page {options['target_page']}", verbosity=1)
        if fill_empty_fields: self._log(f"Will attempt to fill empty fields.", verbosity=1)

        page_count = 0
        total_processed_count = 0
        total_created_count = 0
        total_updated_count = 0
        total_skipped_count = 0
        total_error_count = 0
        next_page_link = options['start_page_link']
        page_limit = options['limit_pages']
        target_page = options['target_page']

        while True:
            page_count += 1
            if page_limit is not None and page_count > page_limit:
                self._log(f"\nReached page limit ({page_limit}). Stopping.", self.style.WARNING)
                break

            self._log(f"\nFetching page {page_count}...", verbosity=1)
            start_time = time.time()
            current_api_params_for_log = {}
            response_data = None

            try:
                if next_page_link:
                    response_data = client.list_items(page_link=next_page_link)
                    current_api_params_for_log = {'page_link': 'used'}
                else:
                    core_api_params = api_params.copy()  # Use configured params
                    response_data = client.list_items(limit=limit_per_page, **core_api_params)
                    current_api_params_for_log = {'limit': limit_per_page, **core_api_params}
            except Exception as e:
                logger.exception(f"Error during API request for page {page_count}: {e}")
                self.stderr.write(self.style.ERROR(f"Failed to fetch data for page {page_count}. Check logs."))
                break

            fetch_duration = time.time() - start_time
            self._log(f"Page {page_count} fetched in {fetch_duration:.2f}s.", verbosity=2)

            if response_data is None:
                self.stderr.write(self.style.ERROR(
                    f"Failed to get response data for page {page_count}. Params: {current_api_params_for_log}"))
                break

            results = response_data.get('results', [])
            total_api = response_data.get('total', 'N/A')
            next_page_link_from_response = response_data.get('next_page')

            should_process_page = not (target_page and page_count < target_page)
            if not should_process_page:
                self._log(f"Skipping processing for page {page_count} (target: {target_page}).", verbosity=1)

            if should_process_page:
                if not results:
                    self._log(f"No results found on page {page_count}.", verbosity=1)
                else:
                    self._log(f"Processing {len(results)} items from page {page_count} (API Total: {total_api})...",
                              verbosity=1)
                    items_on_page_processed = 0
                    results_iterable = results
                    if TQDM_AVAILABLE and self.verbosity == 1:
                        # leave=False makes the bar disappear after the loop for the page finishes
                        results_iterable = tqdm(results, desc=f"Page {page_count}", unit="item", leave=False, ncols=100)

                    page_start_time = time.time()
                    for item_data in results_iterable:
                        processed_item, action_taken = self._process_single_item(
                            item_data, kodik_source, fill_empty_fields
                        )
                        # Count item if it resulted in creation, update or error.
                        # Skipped items (due to unchanged data or API errors) are tracked separately.
                        # 'skipped_no_match' is not counted towards processed yet.
                        if action_taken in ['created', 'updated', 'error']:
                            items_on_page_processed += 1

                        if action_taken == 'created':
                            total_created_count += 1
                        elif action_taken == 'updated':
                            total_updated_count += 1
                        elif action_taken == 'skipped':
                            total_skipped_count += 1  # Only count skips due to unchanged data
                        elif action_taken == 'error':
                            total_error_count += 1

                    page_duration = time.time() - page_start_time
                    total_processed_count += items_on_page_processed  # Add processed items from this page

                    # Clear tqdm bar if it was used
                    if TQDM_AVAILABLE and self.verbosity == 1:
                        self.stdout.write("\r" + " " * 110 + "\r", ending='')  # Clear line wider than bar

                    self._log(f"Page {page_count} processed in {page_duration:.2f}s. "
                              f"Counts: Created={total_created_count}, Updated={total_updated_count}, "
                              f"Skipped(up-to-date)={total_skipped_count}, Errors={total_error_count}", verbosity=1)

            next_page_link = next_page_link_from_response
            if not next_page_link:
                self._log("\nNo 'next_page' link found. Assuming end of results.", self.style.NOTICE)
                break

        self._log(f"\nFinished parsing CORE data.", self.style.SUCCESS)
        self._log(f"  Total Created: {total_created_count}", self.style.SUCCESS)
        self._log(f"  Total Updated: {total_updated_count}", self.style.SUCCESS)
        self._log(f"  Total Skipped (up-to-date): {total_skipped_count}", self.style.SUCCESS)
        self._log(f"  Total Errors: {total_error_count}", self.style.ERROR if total_error_count else self.style.SUCCESS)
