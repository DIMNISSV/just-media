# catalog/management/commands/parse_kodik.py

import logging
from typing import Dict, Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalog.models import (
    MediaItem, Genre, Country, Source, Season, Episode, MediaSourceLink
)
from catalog.services.kodik_client import KodikApiClient
from catalog.services.kodik_mapper import map_kodik_item_to_models

logger = logging.getLogger(__name__)

# Slug for the Kodik source - should match the one you'd create in DB/admin
KODIK_SOURCE_SLUG = 'kodik'


class Command(BaseCommand):
    help = 'Parses media data from the Kodik API and updates the local database.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Limit the number of API pages to process (for testing).',
        )
        parser.add_argument(
            '--types',
            type=str,
            default=None,
            help='Comma-separated list of media types to fetch from Kodik (e.g., "anime-serial,foreign-serial").',
        )
        parser.add_argument(
            '--with-material-data',
            action='store_true',
            help='Request additional material data (description, poster, genres, etc.) from Kodik.',
        )
        parser.add_argument(
            '--with-episodes-data',  # More detailed than with_episodes
            action='store_true',
            help='Request detailed season and episode data (including links and titles) from Kodik.',
        )
        # Add more arguments as needed based on Kodik API parameters (year, sort, etc.)

    @transaction.atomic  # Wrap the entire item processing in a transaction
    def _process_single_item(self, item_data: Dict[str, Any], kodik_source: Source):
        """ Processes a single item from the API response. """
        mapped_data = map_kodik_item_to_models(item_data)
        if not mapped_data:
            return 0  # Indicate no item processed

        media_item_data = mapped_data.get('media_item_data', {})
        genre_names = mapped_data.get('genres', [])
        country_names = mapped_data.get('countries', [])
        main_link_data = mapped_data.get('main_source_link_data')
        seasons_data = mapped_data.get('seasons_data', [])

        if not media_item_data.get('title'):
            logger.warning(f"Skipping item due to missing title after mapping: {item_data.get('id', 'N/A')}")
            return 0

        # --- Find or Create MediaItem ---
        # Prioritize finding by external IDs
        lookup_fields = {}
        if media_item_data.get('kinopoisk_id'):
            lookup_fields['kinopoisk_id'] = media_item_data['kinopoisk_id']
        elif media_item_data.get('shikimori_id'):  # Shikimori seems more common for anime from Kodik
            lookup_fields['shikimori_id'] = media_item_data['shikimori_id']
        elif media_item_data.get('imdb_id'):
            lookup_fields['imdb_id'] = media_item_data['imdb_id']
        elif media_item_data.get('mydramalist_id'):
            lookup_fields['mydramalist_id'] = media_item_data['mydramalist_id']
        else:
            # Fallback: Use title, year, and type (less reliable)
            # Be cautious with this, might lead to duplicates if data is inconsistent
            if media_item_data.get('release_year') and media_item_data.get('media_type'):
                lookup_fields = {
                    'title__iexact': media_item_data['title'],  # Case-insensitive match
                    'release_year': media_item_data['release_year'],
                    'media_type': media_item_data['media_type'],
                }
            else:
                logger.warning(
                    f"Cannot reliably identify item, missing external IDs and year/type: {media_item_data['title']}")
                return 0  # Skip if we cannot identify

        try:
            media_item, created = MediaItem.objects.update_or_create(
                defaults=media_item_data,
                **lookup_fields
            )
            action = "Created" if created else "Updated"
            self.stdout.write(self.style.SUCCESS(f"  {action} MediaItem: {media_item}"), ending='\r')  # Overwrite line
        except Exception as e:
            logger.error(f"Error creating/updating MediaItem for {lookup_fields}: {e}")
            logger.debug(f"Data used: {media_item_data}")
            return 0  # Skip processing links/genres if item failed

        # --- Update Genres and Countries (M2M) ---
        try:
            # Genres
            genres_to_set = []
            for name in genre_names:
                genre, _ = Genre.objects.get_or_create(name__iexact=name, defaults={'name': name})
                genres_to_set.append(genre)
            if genres_to_set:
                media_item.genres.set(genres_to_set)

            # Countries
            countries_to_set = []
            for name in country_names:
                country, _ = Country.objects.get_or_create(name__iexact=name, defaults={'name': name})
                countries_to_set.append(country)
            if countries_to_set:
                media_item.countries.set(countries_to_set)
        except Exception as e:
            logger.error(f"Error updating M2M for MediaItem {media_item.id}: {e}")
            # Continue processing links even if M2M fails? Decide on strategy.

        # --- Update/Create Main Source Link (for the item itself) ---
        if main_link_data and main_link_data.get('player_link'):
            link_defaults = {
                'player_link': main_link_data['player_link'],
                'quality_info': main_link_data.get('quality_info'),
                'translation_info': main_link_data.get('translation_info'),
            }
            # Use source_specific_id from the link data for uniqueness with this source
            link_lookup = {
                'source': kodik_source,
                'media_item': media_item,
                'episode': None,  # This link is for the main item
                'source_specific_id': main_link_data.get('source_specific_id')
            }
            if link_lookup['source_specific_id']:  # Only use this if ID is present
                try:
                    _, link_created = MediaSourceLink.objects.update_or_create(
                        defaults=link_defaults,
                        **link_lookup
                    )
                    # Optionally log link creation/update
                except Exception as e:
                    logger.error(f"Error updating/creating main link for MediaItem {media_item.id}: {e}")
                    logger.debug(f"Link lookup: {link_lookup}, Link defaults: {link_defaults}")
            else:
                logger.warning(
                    f"Skipping main link for MediaItem {media_item.id} due to missing source_specific_id in mapping.")

        # --- Update/Create Seasons and Episodes and their Links ---
        processed_episodes = 0
        if seasons_data:
            for season_item in seasons_data:
                season_number = season_item.get('number')
                episodes_list = season_item.get('episodes_data', [])

                if season_number is None: continue

                try:
                    season, _ = Season.objects.get_or_create(
                        media_item=media_item,
                        season_number=season_number
                    )
                except Exception as e:
                    logger.error(f"Error getting/creating Season {season_number} for MediaItem {media_item.id}: {e}")
                    continue  # Skip episodes for this season if season fails

                for episode_item in episodes_list:
                    episode_number = episode_item.get('number')
                    episode_title = episode_item.get('title')
                    episode_link_data = episode_item.get('link_data')

                    if episode_number is None: continue

                    try:
                        episode, _ = Episode.objects.update_or_create(
                            season=season,
                            episode_number=episode_number,
                            defaults={'title': episode_title}
                        )
                        processed_episodes += 1
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
                            # Explicitly set to None for episode links? Or keep parent? Let's try None.
                            'episode': episode,
                            'source_specific_id': episode_link_data.get('source_specific_id')
                        }
                        if ep_link_lookup['source_specific_id']:
                            try:
                                _, ep_link_created = MediaSourceLink.objects.update_or_create(
                                    defaults=ep_link_defaults,
                                    **ep_link_lookup
                                )
                            except Exception as e:
                                logger.error(f"Error updating/creating episode link for {episode}: {e}")
                                logger.debug(f"Link lookup: {ep_link_lookup}, Link defaults: {ep_link_defaults}")
                        else:
                            logger.warning(
                                f"Skipping episode link for {episode} due to missing source_specific_id in mapping.")

        if processed_episodes > 0:
            self.stdout.write(
                self.style.SUCCESS(f"  Processed {processed_episodes} episodes for MediaItem: {media_item.id}"),
                ending='\r')

        return 1  # Indicate one item processed successfully

    def handle(self, *args, **options):
        self.stdout.write("Starting Kodik API parsing...")

        # --- Get Source Object ---
        try:
            kodik_source = Source.objects.get(slug=KODIK_SOURCE_SLUG)
        except Source.DoesNotExist:
            raise CommandError(
                f"Source with slug '{KODIK_SOURCE_SLUG}' not found. Please create it first (e.g., via admin).")

        # --- Initialize API Client ---
        try:
            client = KodikApiClient()
        except ValueError as e:
            raise CommandError(f"API Client initialization failed: {e}")

        # --- Prepare API Parameters ---
        api_params = {}
        if options['types']:
            api_params['types'] = options['types']  # Assumes comma-separated string is fine
        if options['with_material_data']:
            api_params['with_material_data'] = 'true'
        if options['with_episodes_data']:
            # Kodik docs say use with_episodes_data OR with_episodes
            # with_episodes_data provides more info (title, screenshots)
            api_params['with_episodes_data'] = 'true'

        # --- Pagination Loop ---
        page_count = 0
        total_processed_items = 0
        next_page_link = None  # Start with no specific page link
        page_limit = options['limit']

        while True:
            page_count += 1
            if page_limit is not None and page_count > page_limit:
                self.stdout.write(f"\nReached page limit ({page_limit}). Stopping.")
                break

            self.stdout.write(f"\nFetching page {page_count}...")

            # Use the next_page_link if available, otherwise use base params
            if next_page_link:
                response_data = client.list_items(page_link=next_page_link)
                current_api_params = {'page_link': next_page_link}  # For logging
            else:
                # Pass limit from command line if first page (Kodik default is 50)
                limit_per_page = client.DEFAULT_LIMIT  # Use client default
                response_data = client.list_items(limit=limit_per_page, **api_params)
                current_api_params = {'limit': limit_per_page, **api_params}

            if response_data is None:
                self.stderr.write(
                    self.style.ERROR(f"Failed to fetch data for page {page_count}. Params: {current_api_params}"))
                # Decide whether to stop or try next page (if possible) - stopping for now
                break

            results = response_data.get('results', [])
            total_api = response_data.get('total', 'N/A')
            next_page_link = response_data.get('next_page')  # Get the link for the *next* iteration

            if not results:
                self.stdout.write("No results found on this page.")
                if not next_page_link:  # Stop if no results and no next page
                    break
                else:
                    continue  # Go to next page even if this one was empty

            self.stdout.write(f"Processing {len(results)} items from page {page_count} (API Total: {total_api})...")

            items_on_page_processed = 0
            for item_data in results:
                try:
                    items_on_page_processed += self._process_single_item(item_data, kodik_source)
                except Exception as e:
                    # Catch unexpected errors during single item processing
                    logger.exception(f"Unexpected error processing item {item_data.get('id', 'N/A')}: {e}")
                    # Continue with the next item

            total_processed_items += items_on_page_processed
            self.stdout.write(f"\nPage {page_count} processed. {items_on_page_processed} items saved/updated.")

            if not next_page_link:
                self.stdout.write("\nNo more pages found.")
                break  # Exit the loop if there's no next page

        self.stdout.write(
            self.style.SUCCESS(f"\nFinished parsing. Total items processed/updated in DB: {total_processed_items}"))
