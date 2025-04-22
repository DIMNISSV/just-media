# catalog/management/commands/parse_kodik.py

import logging
import time
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, IntegrityError
from django.conf import settings
from catalog.models import (
    MediaItem, Genre, Country, Source, Season, Episode, MediaSourceLink
)
from catalog.services.kodik_client import KodikApiClient
from catalog.services.kodik_mapper import map_kodik_item_to_models
from typing import Dict, Any, Optional, List, Set

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
            dest='limit_pages',  # Renamed for clarity
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
            '--limit-items-per-page',  # Allow overriding the API default
            type=int,
            default=KodikApiClient.DEFAULT_LIMIT,  # Use client default
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
            type=str,  # Allow ranges like 2020,2021 or single year
            default=None,
            help='Filter by year or comma-separated years (e.g., "2023" or "2020,2021,2022").',
        )
        parser.add_argument(
            '--sort-by',
            type=str,
            default='updated_at',  # Default sort as per Kodik docs
            dest='sort',  # Match API parameter name
            choices=['updated_at', 'created_at', 'year', 'kinopoisk_rating', 'imdb_rating', 'shikimori_rating'],
            help='Field to sort results by.',
        )
        parser.add_argument(
            '--sort-direction',
            type=str,
            default='desc',
            dest='order',  # Match API parameter name
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
        # Example of a future option:
        # parser.add_argument(
        #     '--skip-existing-items',
        #     action='store_true',
        #     help='Only create new MediaItems, do not update existing ones (only add links).',
        # )

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
            styled_message = style(message) if style else message
            self.stdout.write(styled_message, ending=ending)

    @transaction.atomic  # Wrap the entire item processing in a transaction
    def _process_single_item(self, item_data: Dict[str, Any], kodik_source: Source) -> int:
        """
        Processes a single item from the API response.
        Returns: 1 if processed successfully, 0 otherwise.
        """
        item_id_str = item_data.get('id', 'N/A')  # For logging
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
        # Determine primary lookup field (prefer external IDs)
        id_fields_priority = ['kinopoisk_id', 'shikimori_id', 'imdb_id', 'mydramalist_id']
        found_id_field = None
        for field in id_fields_priority:
            if media_item_data.get(field):
                lookup_fields[field] = media_item_data[field]
                found_id_field = field
                break

        if not found_id_field:
            # Fallback: Use title, year, and type
            if media_item_data.get('release_year') and media_item_data.get('media_type') != MediaItem.MediaType.UNKNOWN:
                lookup_fields = {
                    'title__iexact': media_item_data['title'],
                    'release_year': media_item_data['release_year'],
                    'media_type': media_item_data['media_type'],
                }
            else:
                logger.warning(f"Cannot reliably identify item {item_id_str} ('{media_item_data['title']}'): "
                               f"Missing external IDs and year/type.")
                return 0  # Skip if we cannot identify

        try:
            # Separate defaults from lookup keys to avoid potential conflicts if a lookup key is also in defaults
            defaults = media_item_data.copy()
            for key in lookup_fields.keys():
                defaults.pop(key, None)  # Remove lookup keys from defaults

            media_item, created = MediaItem.objects.update_or_create(
                defaults=defaults,
                **lookup_fields
            )
            action = "Created" if created else "Updated"
            # Log detailed info only at higher verbosity
            self._log(f"  {action} MediaItem: {media_item.id} ('{media_item.title}')", verbosity=2, ending='\r')

        except IntegrityError as e:
            logger.error(
                f"Database integrity error processing MediaItem {item_id_str} with lookup {lookup_fields}: {e}. "
                f"Potential duplicate conflicting with DB constraints.")
            return 0  # Skip processing links/genres if item failed due to integrity
        except Exception as e:
            logger.exception(
                f"Unexpected error creating/updating MediaItem {item_id_str} with lookup {lookup_fields}: {e}")
            logger.debug(f"Data used (defaults): {defaults}")
            return 0  # Skip processing links/genres if item failed

        # --- Update Genres and Countries (M2M) ---
        try:
            # Genres
            genres_to_set = []
            for name in genre_names:
                # Use iexact for case-insensitivity, but save with potentially corrected case from defaults
                genre, _ = Genre.objects.get_or_create(name__iexact=name, defaults={'name': name.strip()})
                genres_to_set.append(genre)
            if genres_to_set or genre_names == []:  # Allow clearing M2M if API returns empty list
                media_item.genres.set(genres_to_set)

            # Countries
            countries_to_set = []
            for name in country_names:
                country, _ = Country.objects.get_or_create(name__iexact=name, defaults={'name': name.strip()})
                countries_to_set.append(country)
            if countries_to_set or country_names == []:
                media_item.countries.set(countries_to_set)
            self._log(f"    Updated M2M for {media_item.id}", verbosity=3, ending='\r')

        except Exception as e:
            logger.error(f"Error updating M2M relationships for MediaItem {media_item.id}: {e}")
            # Continue processing links? For now, yes.

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
                try:
                    link_obj, link_created = MediaSourceLink.objects.update_or_create(
                        defaults=link_defaults, **link_lookup
                    )
                    link_action = "Created" if link_created else "Updated"
                    self._log(f"    {link_action} Main Link for {media_item.id}", verbosity=3, ending='\r')
                except IntegrityError as e:
                    logger.warning(
                        f"Integrity error saving main link for {media_item.id} (lookup: {link_lookup}): {e}. Likely duplicate.")
                except Exception as e:
                    logger.error(f"Error saving main link for MediaItem {media_item.id}: {e}")
                    logger.debug(f"Link lookup: {link_lookup}, Link defaults: {link_defaults}")
            else:
                logger.warning(
                    f"Skipping main link for MediaItem {media_item.id} due to missing source_specific_id in mapping.")

        # --- Update/Create Seasons and Episodes and their Links ---
        processed_episodes_count = 0
        if seasons_data:
            for season_item in seasons_data:
                season_number = season_item.get('number')
                episodes_list = season_item.get('episodes_data', [])
                if season_number is None: continue

                try:
                    season, season_created = Season.objects.get_or_create(
                        media_item=media_item, season_number=season_number
                    )
                    if season_created:
                        self._log(f"    Created Season {season_number} for {media_item.id}", verbosity=2)
                except Exception as e:
                    logger.error(f"Error getting/creating Season {season_number} for MediaItem {media_item.id}: {e}")
                    continue  # Skip episodes for this season

                for episode_item in episodes_list:
                    episode_number = episode_item.get('number')
                    episode_title = episode_item.get('title')
                    episode_link_data = episode_item.get('link_data')
                    if episode_number is None: continue

                    try:
                        # Update title if it exists
                        episode, episode_created = Episode.objects.update_or_create(
                            season=season,
                            episode_number=episode_number,
                            defaults={'title': episode_title}
                        )
                        processed_episodes_count += 1
                        if episode_created:
                            self._log(f"    Created Episode S{season_number}E{episode_number} for {media_item.id}",
                                      verbosity=2)

                    except Exception as e:
                        logger.error(
                            f"Error getting/creating Episode S{season_number}E{episode_number} for MediaItem {media_item.id}: {e}")
                        continue  # Skip link if episode fails

                    # Update/Create Source Link for the episode
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
                            try:
                                ep_link, ep_link_created = MediaSourceLink.objects.update_or_create(
                                    defaults=ep_link_defaults, **ep_link_lookup
                                )
                                ep_link_action = "Created" if ep_link_created else "Updated"
                                self._log(f"      {ep_link_action} Link for S{season_number}E{episode_number}",
                                          verbosity=3, ending='\r')
                            except IntegrityError as e:
                                logger.warning(
                                    f"Integrity error saving episode link for {episode} (lookup: {ep_link_lookup}): {e}. Likely duplicate.")
                            except Exception as e:
                                logger.error(f"Error saving episode link for {episode}: {e}")
                                logger.debug(f"Link lookup: {ep_link_lookup}, Link defaults: {ep_link_defaults}")
                        else:
                            logger.warning(
                                f"Skipping episode link for {episode} due to missing source_specific_id in mapping.")

        self._log(f"  Finished processing MediaItem {media_item.id}. {processed_episodes_count} episodes.", verbosity=2,
                  ending='\r')
        return 1  # Indicate one item processed successfully

    def handle(self, *args, **options):
        self.verbosity = options['verbosity']  # Store verbosity level
        self._log("Starting Kodik API parsing...", self.style.NOTICE)

        kodik_source = self._get_kodik_source()

        try:
            client = KodikApiClient()
        except ValueError as e:
            raise CommandError(f"API Client initialization failed: {e}")

        # --- Prepare API Parameters from Options ---
        api_params = {}
        if options['types']: api_params['types'] = options['types']
        if options['year']: api_params['year'] = options['year']
        if options['sort']: api_params['sort'] = options['sort']
        if options['order']: api_params['order'] = options['order']
        if options['with_material_data']: api_params['with_material_data'] = 'true'
        if options['with_episodes_data']: api_params['with_episodes_data'] = 'true'
        # Ensure limit is valid
        limit_per_page = min(max(options['limit_items_per_page'], 1), 100)

        self._log(f"Using API parameters: {api_params}", verbosity=2)
        self._log(f"Items per page: {limit_per_page}", verbosity=2)

        # --- Pagination Loop ---
        page_count = 0
        total_processed_items = 0
        next_page_link = options['start_page_link']  # Start from specific link if provided
        page_limit = options['limit_pages']

        while True:
            page_count += 1
            if page_limit is not None and page_count > page_limit:
                self._log(f"\nReached page limit ({page_limit}). Stopping.", self.style.WARNING)
                break

            self._log(f"\nFetching page {page_count}...", verbosity=1)
            start_time = time.time()

            current_api_params_for_log = {}  # For logging clarity
            if next_page_link:
                response_data = client.list_items(page_link=next_page_link)
                current_api_params_for_log = {'page_link': next_page_link}
                # Clear next_page_link here? No, client handles it.
            else:
                # Only pass limit and other filters on the *first* request without a page_link
                response_data = client.list_items(limit=limit_per_page, **api_params)
                current_api_params_for_log = {'limit': limit_per_page, **api_params}

            fetch_duration = time.time() - start_time
            self._log(f"Page {page_count} fetched in {fetch_duration:.2f}s.", verbosity=2)

            if response_data is None:
                # Client already logged the error, just inform the user
                self.stderr.write(self.style.ERROR(
                    f"Failed to fetch data for page {page_count}. See logs for details. Params: {current_api_params_for_log}"))
                # Should we stop? Maybe add a retry mechanism later. For now, stop.
                break

            results = response_data.get('results', [])
            total_api = response_data.get('total', 'N/A')
            next_page_link = response_data.get('next_page')  # IMPORTANT: Get the link for the *next* iteration

            if not results:
                self._log(f"No results found on page {page_count}.", verbosity=1)
                if not next_page_link:
                    self._log("No results and no next page link. Assuming end of API results.", verbosity=1)
                    break
                else:
                    self._log("Continuing to next page link...", verbosity=2)
                    continue  # Try the next page

            self._log(f"Processing {len(results)} items from page {page_count} (API Total: {total_api})...",
                      verbosity=1)

            items_on_page_processed = 0
            # Setup progress bar if available and verbosity allows
            results_iterable = results
            if TQDM_AVAILABLE and self.verbosity >= 1:
                results_iterable = tqdm(results, desc=f"Page {page_count}", unit="item", leave=False)

            page_start_time = time.time()
            for item_data in results_iterable:
                try:
                    # Use transaction inside _process_single_item
                    items_on_page_processed += self._process_single_item(item_data, kodik_source)
                except Exception as e:
                    # Catch unexpected errors during the loop iteration itself
                    logger.exception(
                        f"Critical unexpected error processing item {item_data.get('id', 'N/A')} on page {page_count}: {e}")
                    # Continue with the next item? Yes.

            page_duration = time.time() - page_start_time
            total_processed_items += items_on_page_processed
            # Clear the line from progress bar / item processing updates
            self.stdout.write("\r" + " " * 80 + "\r", ending='')  # Clear line hack
            self._log(
                f"Page {page_count} processed in {page_duration:.2f}s. {items_on_page_processed} items saved/updated.",
                verbosity=1)

            if not next_page_link:
                self._log("\nNo 'next_page' link found in API response. Assuming end of results.", self.style.NOTICE)
                break  # Exit the loop

            # Optional: Add a small delay between pages to be nice to the API
            # time.sleep(0.5)

        self._log(f"\nFinished parsing. Total items processed/updated in DB: {total_processed_items}",
                  self.style.SUCCESS)
