# catalog/management/commands/parse_kodik.py

import json
import logging
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from dateutil.parser import isoparse
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, IntegrityError

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
        try:
            return Source.objects.get(slug=KODIK_SOURCE_SLUG)
        except Source.DoesNotExist:
            raise CommandError(f"Source with slug '{KODIK_SOURCE_SLUG}' not found. Please create it first.")

    def _log(self, message, style=None, verbosity=1, ending='\n'):
        if self.verbosity >= verbosity:
            styled_message = style(message) if style else message
            self.stdout.write(styled_message, ending=ending)

    @transaction.atomic
    def _process_single_item(self, item_data: Dict[str, Any], kodik_source: Source, fill_empty_fields: bool) -> int:
        item_id_str = item_data.get('id', 'N/A')
        api_updated_at_str = item_data.get('updated_at')
        api_updated_at: Optional[datetime] = None

        if api_updated_at_str:
            try:
                api_updated_at = isoparse(api_updated_at_str)
                if api_updated_at.tzinfo is None: api_updated_at = api_updated_at.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError) as e:
                logger.warning(
                    f"Could not parse updated_at '{api_updated_at_str}' for item {item_id_str}: {e}. Skipping.")
                return 0
        else:
            logger.warning(f"Missing 'updated_at' in API data for item {item_id_str}. Skipping.")
            return 0

        try:
            mapped_data = map_kodik_item_to_models(item_data)
            if not mapped_data: return 0

            media_item_data = mapped_data.get('media_item_data', {})
            genre_names = mapped_data.get('genres', [])
            country_names = mapped_data.get('countries', [])

            if not media_item_data.get('title'):
                logger.warning(f"Skipping item {item_id_str} due to missing title after mapping.")
                return 0

            lookup_fields = {}
            create_kwargs = {}
            id_fields_priority = ['kinopoisk_id', 'shikimori_id', 'imdb_id', 'mydramalist_id']
            found_id_field = None

            for field in id_fields_priority:
                if media_item_data.get(field):
                    lookup_fields[field] = media_item_data[field]
                    create_kwargs[field] = media_item_data[field]
                    found_id_field = field
                    break

            if not found_id_field:
                if media_item_data.get('release_year') and media_item_data.get(
                        'media_type') != MediaItem.MediaType.UNKNOWN:
                    lookup_fields = {'title__iexact': media_item_data['title'],
                                     'release_year': media_item_data['release_year'],
                                     'media_type': media_item_data['media_type']}
                    create_kwargs = {'title': media_item_data['title'], 'release_year': media_item_data['release_year'],
                                     'media_type': media_item_data['media_type']}
                else:
                    logger.warning(
                        f"Cannot reliably identify item {item_id_str} ('{media_item_data['title']}'): Missing required fields for lookup.")
                    return 0

            defaults_for_update = media_item_data.copy()
            for key in list(lookup_fields.keys()) + list(create_kwargs.keys()):
                base_key = key.split('__')[0]
                defaults_for_update.pop(base_key, None)

            media_item = None
            created = False
            try:
                media_item = MediaItem.objects.get(**lookup_fields)
            except MediaItem.DoesNotExist:
                try:
                    final_create_kwargs = {**create_kwargs, **defaults_for_update}
                    media_item = MediaItem.objects.create(**final_create_kwargs)
                    created = True
                except IntegrityError as e:
                    logger.error(
                        f"Integrity error creating MediaItem {item_id_str} with data {final_create_kwargs}: {e}")
                    return 0
                except Exception as e:
                    logger.exception(
                        f"Unexpected error creating MediaItem {item_id_str} with data {final_create_kwargs}: {e}")
                    return 0
            except Exception as e:
                logger.exception(f"Unexpected error getting MediaItem {item_id_str} with lookup {lookup_fields}: {e}")
                return 0

            if media_item is None:
                logger.error(f"Failed to get or create MediaItem {item_id_str}.")
                return 0

            metadata, meta_created = MediaItemSourceMetadata.objects.get_or_create(
                media_item=media_item, source=kodik_source
            )

            should_update_main_data = False
            fields_to_update = {}

            if meta_created or metadata.source_last_updated_at is None or api_updated_at > metadata.source_last_updated_at:
                should_update_main_data = True
                fields_to_update = defaults_for_update
            elif fill_empty_fields and not created:
                for field, value in defaults_for_update.items():
                    if not getattr(media_item, field, None) and value: fields_to_update[field] = value
                if fields_to_update:
                    self._log(
                        f"  Planning to fill empty fields for '{media_item.title}': {list(fields_to_update.keys())}",
                        verbosity=2)

            if should_update_main_data or fields_to_update:
                action = "Created" if created else "Updated"
                self._log(f"  {action} MediaItem fields for: {media_item.id} ('{media_item.title}')", verbosity=2)

                if not created and fields_to_update:
                    update_fields_list = list(fields_to_update.keys())
                    for field, value in fields_to_update.items(): setattr(media_item, field, value)
                    try:
                        media_item.save(update_fields=update_fields_list)
                        log_reason = "API data newer" if should_update_main_data else "filling empty fields"
                        self._log(
                            f"    Updated fields ({log_reason}): {', '.join(update_fields_list)} for existing MediaItem {media_item.id}",
                            verbosity=3)
                    except Exception as e:
                        logger.exception(f"Error saving updated fields for existing MediaItem {media_item.id}: {e}")
                        return 0

                if should_update_main_data:  # Update M2M only if newer
                    try:
                        genres_to_set = [
                            Genre.objects.get_or_create(name__iexact=name, defaults={'name': name.strip()})[0] for name
                            in genre_names]
                        if genres_to_set or genre_names == []: media_item.genres.set(genres_to_set)
                        countries_to_set = [
                            Country.objects.get_or_create(name__iexact=name, defaults={'name': name.strip()})[0] for
                            name in country_names]
                        if countries_to_set or country_names == []: media_item.countries.set(countries_to_set)
                        self._log(f"    Updated M2M for {media_item.id}", verbosity=3)
                    except Exception as e:
                        logger.error(f"Error updating M2M for MediaItem {media_item.id} during update: {e}")

            else:
                if not created: self._log(
                    f"  Skipping main data update for '{media_item.title}' (API data not newer/no empty fields)",
                    verbosity=2)


            if should_update_main_data:
                try:
                    metadata.source_last_updated_at = api_updated_at
                    metadata.save(update_fields=['source_last_updated_at'])
                    self._log(f"    Updated metadata timestamp for {media_item.id}", verbosity=3)
                except Exception as e:
                    logger.error(f"Failed to update metadata timestamp for {media_item.id}: {e}")

            self._log(f"  Finished core processing for MediaItem {media_item.id}.", verbosity=2)
            return 1

        except Exception as e:
            logger.error(f"Outer error processing item {item_id_str}.")
            logger.exception(
                f"Exception details: {e}\n"
                f"Problematic item data:\n{json.dumps(item_data, indent=2, ensure_ascii=False)}"
            )
            return 0

    def handle(self, *args, **options):
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
        api_params['with_material_data'] = 'true'
        limit_per_page = min(max(options['limit_items_per_page'], 1), 100)

        self._log(f"Using API parameters: {api_params}", verbosity=2)
        self._log(f"Items per page: {limit_per_page}", verbosity=2)
        if options['target_page']: self._log(f"Will skip processing until page {options['target_page']}", verbosity=1)
        if fill_empty_fields: self._log(f"Will attempt to fill empty fields even if item data is not newer.",
                                        verbosity=1)

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

            try:
                if next_page_link:
                    response_data = client.list_items(page_link=next_page_link)
                    current_api_params_for_log = {'page_link': 'used'}
                else:
                    # Pass only necessary params for core data
                    core_api_params = {k: v for k, v in api_params.items() if k != 'with_episodes_data'}
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

            should_process_page = True
            if target_page and page_count < target_page:
                should_process_page = False
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
                        results_iterable = tqdm(results, desc=f"Page {page_count}", unit="item", leave=True)

                    page_start_time = time.time()
                    for item_data in results_iterable:
                        items_on_page_processed += self._process_single_item(
                            item_data, kodik_source, fill_empty_fields
                        )

                    page_duration = time.time() - page_start_time
                    total_processed_items += items_on_page_processed
                    if TQDM_AVAILABLE and self.verbosity >= 1:
                        self.stdout.write("\r" + " " * 80 + "\r", ending='')
                    self._log(
                        f"Page {page_count} processed in {page_duration:.2f}s. {items_on_page_processed} items saved/updated checks.",
                        verbosity=1)

            next_page_link = next_page_link_from_response

            if not next_page_link:
                self._log("\nNo 'next_page' link found in API response. Assuming end of results.", self.style.NOTICE)
                break

            # time.sleep(0.1)

        self._log(f"\nFinished parsing CORE data. Total items processed/updated checks in DB: {total_processed_items}",
                  self.style.SUCCESS)
