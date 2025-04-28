# catalog/management/commands/parse_kodik.py

import logging
import time
from datetime import datetime, timezone
from typing import Optional

from dateutil.parser import isoparse
from django.core.management.base import BaseCommand, CommandError

# Import the processor and the necessary model
from catalog.models import Source
from catalog.services.kodik_client import KodikApiClient
from catalog.services.kodik_mapper import map_kodik_item_to_models
from catalog.services.media_item_processor import MediaItemProcessor  # Import processor

# Remove direct model imports no longer needed here
# from django.db import transaction, IntegrityError
# from django.db.models import Q
# from catalog.models import (
#     MediaItem, Genre, Country, Source, MediaItemSourceMetadata
# )

try:
    from tqdm import tqdm

    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False

logger = logging.getLogger(__name__)
KODIK_SOURCE_SLUG = 'kodik'


class Command(BaseCommand):
    help = 'Parses CORE media data (MediaItem, Genres, Countries, Metadata) from Kodik API /list using MediaItemProcessor.'

    # --- add_arguments - без изменений ---
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

    # --- _get_kodik_source, _log - без изменений ---
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

    # --- Removed _build_exact_match_query, _find_subset_match, _process_single_item ---

    def handle(self, *args, **options):
        """Handles the command execution."""
        self.verbosity = options['verbosity']
        self._log(f"Starting Kodik CORE data parsing with verbosity level: {self.verbosity}", self.style.NOTICE)

        # --- Initialization ---
        kodik_source = self._get_kodik_source()
        fill_empty_fields = options['fill_empty_fields']
        try:
            client = KodikApiClient()
        except ValueError as e:
            raise CommandError(f"API Client initialization failed: {e}")

        # --- Initialize Processor ---
        processor = MediaItemProcessor(
            kodik_source=kodik_source,
            fill_empty_fields=fill_empty_fields,
            verbosity=self.verbosity
        )

        # --- API parameters ---
        api_params = {}
        limit_per_page = min(max(options['limit_items_per_page'], 1), 100)
        if options['types']: api_params['types'] = options['types']
        if options['year']: api_params['year'] = options['year']
        if options['sort']: api_params['sort'] = options['sort']
        if options['order']: api_params['order'] = options['order']
        api_params['with_material_data'] = 'true'  # Always request material data now

        self._log(f"Using API parameters: {api_params}", verbosity=2)
        self._log(f"Items per page: {limit_per_page}", verbosity=2)
        if options['target_page']: self._log(f"Will skip processing until page {options['target_page']}", verbosity=1)
        if fill_empty_fields: self._log(f"Will attempt to fill empty fields.", verbosity=1)

        # --- Statistics counters ---
        stats = {
            'created': 0, 'updated': 0, 'skipped': 0, 'error': 0,
            'skipped_no_ids': 0, 'skipped_mapping_failed': 0,
            'skipped_missing_title': 0, 'skipped_missing_date': 0,
            'skipped_invalid_date': 0
        }

        # --- Paging Loop ---
        page_count = 0
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
            response_data = None
            try:
                if next_page_link:
                    response_data = client.list_items(page_link=next_page_link)
                else:
                    core_api_params = api_params.copy()
                    response_data = client.list_items(limit=limit_per_page, **core_api_params)
            except Exception as e:
                logger.exception(f"Error during API request for page {page_count}: {e}")
                self.stderr.write(self.style.ERROR(f"Failed to fetch data for page {page_count}. Check logs."))
                stats['error'] += 1  # Count as error
                break  # Stop processing if API fails

            fetch_duration = time.time() - start_time
            self._log(f"Page {page_count} fetched in {fetch_duration:.2f}s.", verbosity=2)

            if response_data is None:
                self.stderr.write(self.style.ERROR(f"Failed to get response data for page {page_count}."))
                stats['error'] += 1  # Count as error
                break

            results = response_data.get('results', [])
            total_api = response_data.get('total', 'N/A')
            next_page_link = response_data.get('next_page')  # Update next_page_link
            should_process_page = not (target_page and page_count < target_page)

            if not should_process_page:
                self._log(f"Skipping processing for page {page_count} (target: {target_page}).", verbosity=1)
                if not next_page_link: break  # Still check if it was the last page
                continue  # Go to next page fetch

            # --- Process items on page ---
            if not results:
                self._log(f"No results found on page {page_count}.", verbosity=1)
            else:
                self._log(f"Processing {len(results)} items from page {page_count} (API Total: {total_api})...",
                          verbosity=1)
                results_iterable = results
                if TQDM_AVAILABLE and self.verbosity == 1:
                    results_iterable = tqdm(results, desc=f"Page {page_count}", unit="item", leave=False, ncols=100)

                page_start_time = time.time()
                for item_data in results_iterable:
                    # Parse updated_at here before passing to processor
                    api_updated_at_str = item_data.get('updated_at')
                    api_updated_at: Optional[datetime] = None
                    action_taken = 'skipped_invalid_date'  # Default if parsing fails

                    if api_updated_at_str:
                        try:
                            api_updated_at = isoparse(api_updated_at_str)
                            if api_updated_at.tzinfo is None:
                                api_updated_at = api_updated_at.replace(tzinfo=timezone.utc)

                            # Map data
                            mapped_data = map_kodik_item_to_models(item_data)

                            # Process using the processor
                            if mapped_data and api_updated_at:
                                try:
                                    # Use transaction.atomic around the processor call if needed,
                                    # though processor uses it internally now.
                                    # with transaction.atomic():
                                    processed_item, action_taken = processor.process_api_item(mapped_data,
                                                                                              api_updated_at)
                                except Exception as proc_err:
                                    # Catch unexpected errors from processor itself
                                    logger.exception(
                                        f"Unhandled error from MediaItemProcessor for item {item_data.get('id', 'N/A')}: {proc_err}")
                                    action_taken = 'error_processor_unhandled'

                            elif not mapped_data:
                                action_taken = 'skipped_mapping_failed'

                        except (ValueError, TypeError) as e:
                            logger.warning(
                                f"Could not parse updated_at '{api_updated_at_str}' for item {item_data.get('id', 'N/A')}: {e}. Skipping.")
                            action_taken = 'skipped_invalid_date'
                    else:
                        logger.warning(
                            f"Missing 'updated_at' in API data for item {item_data.get('id', 'N/A')}. Skipping.")
                        action_taken = 'skipped_missing_date'

                    # Update statistics
                    if action_taken in stats:
                        stats[action_taken] += 1
                    elif 'error' in action_taken:
                        stats['error'] += 1  # General error counter
                    else:  # Fallback for unknown statuses
                        stats['skipped'] += 1

                page_duration = time.time() - page_start_time
                if TQDM_AVAILABLE and self.verbosity == 1:
                    self.stdout.write("\r" + " " * 110 + "\r", ending='')  # Clear tqdm line

                # Log page summary using the collected stats
                self._log(f"Page {page_count} processed in {page_duration:.2f}s. "
                          f"Counts: C={stats['created']}, U={stats['updated']}, "
                          f"S(ok)={stats['skipped']}, E={stats['error']}", verbosity=1)

            if not next_page_link:
                self._log("\nNo 'next_page' link found. Assuming end of results.", self.style.NOTICE)
                break

        # --- Final Summary ---
        self._log(f"\nFinished parsing CORE data.", self.style.SUCCESS)
        self._log(f"  Total Created: {stats['created']}", self.style.SUCCESS)
        self._log(f"  Total Updated: {stats['updated']}", self.style.SUCCESS)
        total_skips = sum(v for k, v in stats.items() if k.startswith('skipped'))
        self._log(f"  Total Skipped (various reasons): {total_skips}", self.style.SUCCESS)
        self._log(f"  Total Errors: {stats['error']}", self.style.ERROR if stats['error'] else self.style.SUCCESS)
