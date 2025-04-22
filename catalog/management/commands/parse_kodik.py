# catalog/management/commands/parse_kodik.py

import json
import logging
import time
from typing import Dict, Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalog.models import (
    MediaItem, Genre, Country, Source, Season, Episode, MediaSourceLink
)
from catalog.services.kodik_client import KodikApiClient
from catalog.services.kodik_mapper import map_kodik_item_to_models

# Optional: Import tqdm for progress bar
try:
    from tqdm import tqdm

    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False

logger = logging.getLogger(__name__)  # Use Django's logging configuration

# Slug for the Kodik source - should match the one you'd create in DB/admin
KODIK_SOURCE_SLUG = 'kodik'


class Command(BaseCommand):
    help = 'Parses media data from the Kodik API and updates the local database.'

    def add_arguments(self, parser):
        # Pagination and Limits
        parser.add_argument(
            '--limit-pages',
            type=int,
            default=None,
            dest='limit_pages',
            help='Limit the number of API pages to process (for testing).',
        )
        parser.add_argument(
            '--start-page-link',
            type=str,
            default=None,
            dest='start_page_link',
            help='Start parsing from a specific Kodik "next_page" URL.',
        )
        parser.add_argument(
            '--target-page',  # New argument to jump to a specific page number
            type=int,
            default=None,
            dest='target_page',
            help='Fetch pages sequentially but only start processing from this page number (for debugging).',
        )
        parser.add_argument(
            '--limit-items-per-page',
            type=int,
            default=KodikApiClient.DEFAULT_LIMIT,
            dest='limit_items_per_page',
            help=f'Number of items to request per API page (1-100, default: {KodikApiClient.DEFAULT_LIMIT}).',
        )

        # Kodik API Filtering / Sorting
        parser.add_argument(
            '--types',
            type=str,
            default=None,
            help='Comma-separated list of media types to fetch from Kodik (e.g., "anime-serial,foreign-serial").',
        )
        parser.add_argument(
            '--year',
            type=str,
            default=None,
            help='Filter by year or comma-separated years (e.g., "2023" or "2020,2021,2022").',
        )
        parser.add_argument(
            '--sort-by',
            type=str,
            default='updated_at',
            dest='sort',
            choices=['updated_at', 'created_at', 'year', 'kinopoisk_rating', 'imdb_rating', 'shikimori_rating'],
            help='Field to sort results by.',
        )
        parser.add_argument(
            '--sort-direction',
            type=str,
            default='desc',
            dest='order',
            choices=['asc', 'desc'],
            help='Sort direction.',
        )

        # Data Enrichment Flags
        parser.add_argument(
            '--with-material-data',
            action='store_true',
            help='Request additional material data (description, poster, genres, etc.) from Kodik.',
        )
        parser.add_argument(
            '--with-episodes-data',
            action='store_true',
            help='Request detailed season and episode data (including links and titles) from Kodik.',
        )

    def _get_kodik_source(self) -> Source:
        """ Retrieves or raises CommandError for the Kodik source object. """
        try:
            return Source.objects.get(slug=KODIK_SOURCE_SLUG)
        except Source.DoesNotExist:
            raise CommandError(
                f"Source with slug '{KODIK_SOURCE_SLUG}' not found. "
                f"Please create it first (e.g., via admin or migrations)."
            )

    def _log(self, message, style=None, verbosity=1, ending='\n'):
        """ Helper for logging based on verbosity level. """
        if self.verbosity >= verbosity:
            # Always use specified ending for verbosity >= 1
            styled_message = style(message) if style else message
            self.stdout.write(styled_message, ending=ending)

    # Removed @transaction.atomic here - apply it around the loop in handle if needed,
    # or keep it here for per-item transactionality. Keeping it here for now.
    @transaction.atomic
    def _process_single_item(self, item_data: Dict[str, Any], kodik_source: Source) -> int:
        """
        Processes a single item from the API response.
        Returns: 1 if processed successfully, 0 otherwise.
        Logs full item_data on exception.
        """
        item_id_str = item_data.get('id', 'N/A')  # For logging
        try:
            mapped_data = map_kodik_item_to_models(item_data)
            if not mapped_data:
                logger.warning(f"Skipping item {item_id_str}: Mapping failed or returned no data.")
                return 0

            media_item_data = mapped_data.get('media_item_data', {})
            genre_names = mapped_data.get('genres', [])
            country_names = mapped_data.get('countries', [])
            main_link_data = mapped_data.get('main_source_link_data')
            seasons_data = mapped_data.get('seasons_data', [])

            if not media_item_data.get('title'):
                logger.warning(f"Skipping item {item_id_str} due to missing title after mapping.")
                return 0

            # --- Find or Create MediaItem ---
            lookup_fields = {}
            id_fields_priority = ['kinopoisk_id', 'shikimori_id', 'imdb_id', 'mydramalist_id']
            found_id_field = None
            for field in id_fields_priority:
                if media_item_data.get(field):
                    lookup_fields[field] = media_item_data[field]
                    found_id_field = field
                    break

            if not found_id_field:
                if media_item_data.get('release_year') and media_item_data.get(
                        'media_type') != MediaItem.MediaType.UNKNOWN:
                    lookup_fields = {
                        'title__iexact': media_item_data['title'],
                        'release_year': media_item_data['release_year'],
                        'media_type': media_item_data['media_type'],
                    }
                else:
                    logger.warning(f"Cannot reliably identify item {item_id_str} ('{media_item_data['title']}'): "
                                   f"Missing external IDs and year/type.")
                    return 0

            defaults = media_item_data.copy()
            for key in lookup_fields.keys():
                defaults.pop(key, None)

            media_item, created = MediaItem.objects.update_or_create(
                defaults=defaults,
                **lookup_fields
            )
            action = "Created" if created else "Updated"
            self._log(f"  {action} MediaItem: {media_item.id} ('{media_item.title}')", verbosity=2)

            # --- Update Genres and Countries (M2M) ---
            genres_to_set = []
            for name in genre_names:
                genre, _ = Genre.objects.get_or_create(name__iexact=name, defaults={'name': name.strip()})
                genres_to_set.append(genre)
            if genres_to_set or genre_names == []:
                media_item.genres.set(genres_to_set)

            countries_to_set = []
            for name in country_names:
                country, _ = Country.objects.get_or_create(name__iexact=name, defaults={'name': name.strip()})
                countries_to_set.append(country)
            if countries_to_set or country_names == []:
                media_item.countries.set(countries_to_set)
            self._log(f"    Updated M2M for {media_item.id}", verbosity=3)

            # --- Update/Create Main Source Link ---
            if main_link_data and main_link_data.get('player_link'):
                link_defaults = {
                    'player_link': main_link_data['player_link'],
                    'quality_info': main_link_data.get('quality_info'),
                    'translation_info': main_link_data.get('translation_info'),
                }
                link_lookup = {
                    'source': kodik_source,
                    'media_item': media_item,
                    'episode': None,
                    'source_specific_id': main_link_data.get('source_specific_id')
                }
                if link_lookup['source_specific_id']:
                    link_obj, link_created = MediaSourceLink.objects.update_or_create(
                        defaults=link_defaults, **link_lookup
                    )
                    link_action = "Created" if link_created else "Updated"
                    self._log(f"    {link_action} Main Link for {media_item.id}", verbosity=3)
                else:
                    logger.warning(
                        f"Skipping main link for MediaItem {media_item.id} due to missing source_specific_id in mapping.")

            # --- Update/Create Seasons and Episodes and their Links ---
            processed_episodes_count = 0
            if seasons_data:
                for season_item in seasons_data:
                    season_number = season_item.get('number')
                    episodes_list = season_item.get('episodes_data', [])
                    if season_number is None:
                        logger.debug(f"Skipping season with None number for MediaItem {media_item.id}")
                        continue

                    season, season_created = Season.objects.get_or_create(
                        media_item=media_item, season_number=season_number
                    )
                    if season_created:
                        self._log(f"    Created Season {season_number} for {media_item.id}", verbosity=2)

                    for episode_item in episodes_list:
                        episode_number = episode_item.get('number')
                        episode_title = episode_item.get('title')
                        episode_link_data = episode_item.get('link_data')
                        if episode_number is None: continue

                        episode, episode_created = Episode.objects.update_or_create(
                            season=season,
                            episode_number=episode_number,
                            defaults={'title': episode_title}
                        )
                        processed_episodes_count += 1
                        if episode_created:
                            self._log(f"    Created Episode S{season_number}E{episode_number} for {media_item.id}",
                                      verbosity=2)

                        if episode_link_data and episode_link_data.get('player_link'):
                            ep_link_defaults = {
                                'player_link': episode_link_data['player_link'],
                                'quality_info': episode_link_data.get('quality_info'),
                                'translation_info': episode_link_data.get('translation_info'),
                            }
                            ep_link_lookup = {
                                'source': kodik_source,
                                'media_item': None,
                                'episode': episode,
                                'source_specific_id': episode_link_data.get('source_specific_id')
                            }
                            if ep_link_lookup['source_specific_id']:
                                ep_link, ep_link_created = MediaSourceLink.objects.update_or_create(
                                    defaults=ep_link_defaults, **ep_link_lookup
                                )
                                ep_link_action = "Created" if ep_link_created else "Updated"
                                self._log(f"      {ep_link_action} Link for S{season_number}E{episode_number}",
                                          verbosity=3)
                            else:
                                logger.warning(
                                    f"Skipping episode link for {episode} due to missing source_specific_id in mapping.")

            self._log(f"  Finished processing MediaItem {media_item.id}. {processed_episodes_count} episodes.",
                      verbosity=2)
            return 1  # Indicate one item processed successfully

        # --- MODIFIED: Catch all exceptions within item processing ---
        except Exception as e:
            # Log the exception traceback AND the problematic item data
            logger.error(f"Failed processing item {item_id_str}.")
            logger.exception(
                f"Exception details: {e}\n"
                f"Problematic item data:\n{json.dumps(item_data, indent=2, ensure_ascii=False)}"
            )

            # Re-raise the exception if you want the command to fail hard on the first error,
            # or return 0 to continue processing other items on the page.
            # For debugging, continuing might be better.
            # transaction.set_rollback(True) # Ensure transaction for this item is rolled back if atomic
            return 0

    def handle(self, *args, **options):
        self.verbosity = options['verbosity']
        self._log(f"Starting Kodik API parsing with verbosity level: {self.verbosity}", self.style.NOTICE)
        self._log("Starting Kodik API parsing...", self.style.NOTICE)

        kodik_source = self._get_kodik_source()

        try:
            client = KodikApiClient()
        except ValueError as e:
            raise CommandError(f"API Client initialization failed: {e}")

        api_params = {}
        if options['types']: api_params['types'] = options['types']
        if options['year']: api_params['year'] = options['year']
        if options['sort']: api_params['sort'] = options['sort']
        if options['order']: api_params['order'] = options['order']
        if options['with_material_data']: api_params['with_material_data'] = 'true'
        if options['with_episodes_data']: api_params['with_episodes_data'] = 'true'
        limit_per_page = min(max(options['limit_items_per_page'], 1), 100)

        self._log(f"Using API parameters: {api_params}", verbosity=2)
        self._log(f"Items per page: {limit_per_page}", verbosity=2)
        if options['target_page']:
            self._log(f"Will skip processing until page {options['target_page']}", verbosity=1)

        page_count = 0
        total_processed_items = 0
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

            # --- Fetching Logic ---
            try:
                if next_page_link:
                    response_data = client.list_items(page_link=next_page_link)
                    current_api_params_for_log = {'page_link': 'used'}  # Simplified log
                else:
                    # Only pass limit and other filters on the *first* request without a page_link
                    response_data = client.list_items(limit=limit_per_page, **api_params)
                    current_api_params_for_log = {'limit': limit_per_page, **api_params}
            except Exception as e:
                # Catch potential errors during client call itself
                logger.exception(f"Error during API request for page {page_count}: {e}")
                self.stderr.write(self.style.ERROR(f"Failed to fetch data for page {page_count}. Check logs."))
                break  # Stop if fetching fails critically

            fetch_duration = time.time() - start_time
            self._log(f"Page {page_count} fetched in {fetch_duration:.2f}s.", verbosity=2)

            if response_data is None:
                self.stderr.write(self.style.ERROR(
                    f"Failed to get response data for page {page_count}. Params: {current_api_params_for_log}"))
                break

            results = response_data.get('results', [])
            total_api = response_data.get('total', 'N/A')
            # IMPORTANT: Get the link for the *next* iteration BEFORE potentially skipping processing
            next_page_link_from_response = response_data.get('next_page')

            # --- Target Page Skipping Logic ---
            should_process_page = True
            if target_page and page_count < target_page:
                should_process_page = False
                self._log(f"Skipping processing for page {page_count} (target: {target_page}).", verbosity=1)

            # --- Processing Logic ---
            if should_process_page:
                if not results:
                    self._log(f"No results found on page {page_count}.", verbosity=1)
                else:
                    self._log(f"Processing {len(results)} items from page {page_count} (API Total: {total_api})...",
                              verbosity=1)
                    items_on_page_processed = 0
                    results_iterable = results
                    if TQDM_AVAILABLE and self.verbosity >= 1:
                        results_iterable = tqdm(results, desc=f"Page {page_count}", unit="item", leave=False)

                    page_start_time = time.time()
                    for item_data in results_iterable:
                        items_on_page_processed += self._process_single_item(item_data, kodik_source)
                        # Add small sleep inside item loop if hitting rate limits?
                        # time.sleep(0.01)

                    page_duration = time.time() - page_start_time
                    total_processed_items += items_on_page_processed
                    # Clear the line from progress bar / item processing updates
                    if TQDM_AVAILABLE and self.verbosity >= 1:
                        self.stdout.write("\r" + " " * 80 + "\r", ending='')  # Clear line hack
                    self._log(
                        f"Page {page_count} processed in {page_duration:.2f}s. {items_on_page_processed} items saved/updated.",
                        verbosity=1)

            # --- Update next_page_link for the next loop iteration ---
            next_page_link = next_page_link_from_response

            if not next_page_link:
                self._log("\nNo 'next_page' link found in API response. Assuming end of results.", self.style.NOTICE)
                break  # Exit the loop

            # Optional: Add a small delay between pages
            # time.sleep(0.2)

        self._log(f"\nFinished parsing. Total items processed/updated in DB: {total_processed_items}",
                  self.style.SUCCESS)
