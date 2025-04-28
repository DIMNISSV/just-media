# catalog/services/media_item_processor.py

import logging
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List, Set

from django.db import transaction, IntegrityError
from django.db.models import Q

from catalog.models import (
    MediaItem, Genre, Country, Source, MediaItemSourceMetadata
)

logger = logging.getLogger(__name__)


class MediaItemProcessorError(Exception):
    """Custom exception for processor errors."""
    pass


class MediaItemProcessor:
    """
    Handles the logic of finding, creating, or updating a MediaItem
    based on data received from an external API (like Kodik).
    """

    def __init__(self, kodik_source: Source, fill_empty_fields: bool = False, verbosity: int = 1):
        self.kodik_source = kodik_source
        self.fill_empty_fields = fill_empty_fields
        self.verbosity = verbosity
        # Define ID fields once
        self.id_fields = ['kinopoisk_id', 'imdb_id', 'shikimori_id', 'mydramalist_id']

    def _log(self, message, level=logging.INFO, log_verbosity=2):
        """Logs messages if command verbosity allows."""
        # Map logging levels if needed, or just use INFO/DEBUG
        if self.verbosity >= log_verbosity:
            logger.log(level, message)  # Use standard logger

    def _build_exact_match_query(self, api_ids: Dict[str, Optional[str]]) -> Q:
        """Builds a Q object for exact match based on all ID fields."""
        q_object = Q()
        for field in self.id_fields:
            value = api_ids.get(field)
            q_object &= Q(**{f"{field}__isnull": True}) if value is None else Q(**{field: value})
        return q_object

    def _find_exact_match(self, api_ids: Dict[str, Optional[str]]) -> Optional[MediaItem]:
        """Attempts to find an exact match based on all IDs."""
        exact_match_query = self._build_exact_match_query(api_ids)
        try:
            return MediaItem.objects.get(exact_match_query)
        except MediaItem.DoesNotExist:
            return None
        except MediaItem.MultipleObjectsReturned:
            logger.error(
                f"CRITICAL: Multiple MediaItems found with exact ID combination {api_ids}. Manual intervention needed.")
            # Raise specific error?
            raise MediaItemProcessorError("Multiple exact matches found")
        except Exception as e:
            logger.exception(f"Unexpected error during exact match lookup with query {exact_match_query}: {e}")
            raise MediaItemProcessorError("Error during exact match lookup")

    def _find_subset_match(self, api_non_empty_ids: Dict[str, str]) -> Optional[MediaItem]:
        """Finds an existing MediaItem that is a 'subset' of the provided API IDs."""
        if not api_non_empty_ids:
            return None

        # Build query to find candidates sharing at least one ID
        candidate_query = Q()
        for field, value in api_non_empty_ids.items():
            candidate_query |= Q(**{field: value})

        # Exclude candidates with conflicting IDs
        for field, api_value in api_non_empty_ids.items():
            candidate_query &= ~Q(**{f"{field}__isnull": False}) | Q(**{field: api_value})

        candidates = MediaItem.objects.filter(candidate_query)
        if not candidates.exists():
            self._log(f"    _find_subset_match: No candidates found after initial filter.", log_verbosity=3)
            return None

        best_match = None
        highest_priority_found = -1
        self._log(
            f"    _find_subset_match: Checking {candidates.count()} candidates against api_ids={api_non_empty_ids}",
            log_verbosity=3)

        for item in candidates:
            item_ids = {field: getattr(item, field, None) for field in self.id_fields}
            item_non_empty_ids = {k: v for k, v in item_ids.items() if v}
            if not item_non_empty_ids: continue

            is_subset = all(
                field in api_non_empty_ids and api_non_empty_ids[field] == value
                for field, value in item_non_empty_ids.items()
            )
            if not is_subset:
                self._log(f"      Candidate PK {item.pk} failed subset check.", log_verbosity=3)
                continue

            api_has_new_id = any(field not in item_non_empty_ids for field in api_non_empty_ids)
            if not api_has_new_id:
                self._log(f"      Candidate PK {item.pk} has same non-empty IDs. Skipping as subset.", log_verbosity=3)
                continue

            # Check priority
            current_priority = 1 if item_ids.get('kinopoisk_id') or item_ids.get('imdb_id') else 0
            if current_priority == 0 and ('kinopoisk_id' in api_non_empty_ids or 'imdb_id' in api_non_empty_ids):
                current_priority = -1  # Downgrade if API brings higher priority IDs

            self._log(f"      Candidate PK {item.pk} is valid subset. Priority: {current_priority}", log_verbosity=3)
            if current_priority > highest_priority_found:
                highest_priority_found = current_priority
                best_match = item
                self._log(f"      Candidate PK {item.pk} is new best match.", log_verbosity=3)

        if best_match:
            self._log(
                f"    _find_subset_match: Selected best match PK {best_match.pk} with priority {highest_priority_found}",
                log_verbosity=3)
        else:
            self._log(f"    _find_subset_match: No suitable subset match found.", log_verbosity=3)
        return best_match

    def _get_or_create_m2m(self, model_class, names: List[str]) -> Set:
        """Gets or creates M2M related objects."""
        target_objects = set()
        valid_names = [name.strip() for name in names if name.strip()]
        if not valid_names:
            return target_objects

        # Bulk get existing
        existing_qs = model_class.objects.filter(name__in=valid_names)
        existing_map = {obj.name.lower(): obj for obj in existing_qs}
        target_objects.update(existing_map.values())

        # Create missing
        for name in valid_names:
            if name.lower() not in existing_map:
                # Use get_or_create for race-condition safety within the loop
                obj, created = model_class.objects.get_or_create(
                    name__iexact=name, defaults={'name': name}
                )
                target_objects.add(obj)
                if created:
                    self._log(f"      Created new {model_class.__name__}: {name}", log_verbosity=3)
        return target_objects

    def _update_m2m_relations(self, media_item: MediaItem, genre_names: List[str], country_names: List[str]) -> bool:
        """Updates M2M relations (genres, countries) and returns True if changed."""
        m2m_changed = False

        # Genres
        current_genres = set(media_item.genres.all())
        target_genres = self._get_or_create_m2m(Genre, genre_names)
        if current_genres != target_genres:
            media_item.genres.set(list(target_genres))
            m2m_changed = True

        # Countries
        current_countries = set(media_item.countries.all())
        target_countries = self._get_or_create_m2m(Country, country_names)
        if current_countries != target_countries:
            media_item.countries.set(list(target_countries))
            m2m_changed = True

        if m2m_changed:
            self._log(f"      Updated M2M relations for MediaItem {media_item.pk}", log_verbosity=3)
        else:
            self._log(f"      M2M relations unchanged for MediaItem {media_item.pk}", log_verbosity=3)

        return m2m_changed

    def _update_metadata(self, media_item: MediaItem, api_updated_at: datetime, meta_created: bool) -> None:
        """Creates or updates the MediaItemSourceMetadata record."""
        try:
            metadata, created = MediaItemSourceMetadata.objects.get_or_create(
                media_item=media_item,
                source=self.kodik_source,
                defaults={'source_last_updated_at': api_updated_at}
            )
            # Always update if API time is different, or if meta was just created via outer scope
            if not created and (metadata.source_last_updated_at != api_updated_at or meta_created):
                metadata.source_last_updated_at = api_updated_at
                metadata.save(update_fields=['source_last_updated_at'])
                self._log(f"      Updated metadata timestamp for MediaItem {media_item.pk}", log_verbosity=3)
            elif created:  # Already set via defaults
                self._log(f"      Created metadata timestamp for MediaItem {media_item.pk}", log_verbosity=3)

        except Exception as e:
            logger.error(f"Failed to update metadata timestamp for MediaItem {media_item.pk}: {e}")
            # Non-critical error, processing can continue

    def _update_item(self, media_item: MediaItem, media_item_data: Dict[str, Any], api_ids: Dict[str, Optional[str]],
                     genre_names: List[str], country_names: List[str], api_updated_at: datetime,
                     is_subset_match: bool) -> str:
        """Handles the logic for updating an existing MediaItem."""
        action = 'skipped'  # Default if no changes needed
        metadata, meta_created = MediaItemSourceMetadata.objects.get_or_create(
            media_item=media_item, source=self.kodik_source
        )
        should_update_main_data = False
        fields_to_update = {}

        if is_subset_match:
            should_update_main_data = True
            fields_to_update = media_item_data.copy()  # Start with all API data
            # Ensure all API IDs are set correctly
            for field, value in api_ids.items():
                if value != getattr(media_item, field, None):
                    fields_to_update[field] = value
            self._log(f"    Subset match: Forcing update and merging IDs for MediaItem {media_item.pk}.",
                      log_verbosity=3)
        else:  # Exact match logic
            defaults_for_update = media_item_data.copy()
            for key in api_ids.keys(): defaults_for_update.pop(key, None)  # Exclude IDs from default update

            if meta_created or metadata.source_last_updated_at is None or api_updated_at > metadata.source_last_updated_at:
                should_update_main_data = True
                fields_to_update = defaults_for_update
                self._log(f"    API data is newer or metadata created for MediaItem {media_item.pk}.", log_verbosity=3)
            elif self.fill_empty_fields:
                for field, value in defaults_for_update.items():
                    if hasattr(media_item, field) and not getattr(media_item, field, None) and value:
                        fields_to_update[field] = value
                if fields_to_update:
                    self._log(
                        f"    Planning to fill empty fields for MediaItem {media_item.pk}: {list(fields_to_update.keys())}",
                        log_verbosity=2)

        if fields_to_update or should_update_main_data:  # Check if any update is needed
            self._log(f"    Updating fields/M2M for MediaItem {media_item.pk} ('{media_item.title}').", log_verbosity=2)
            update_fields_list = list(fields_to_update.keys())

            # Apply field updates
            for field, value in fields_to_update.items():
                setattr(media_item, field, value)

            try:
                if 'updated_at' in update_fields_list: update_fields_list.remove('updated_at')
                if update_fields_list:
                    media_item.save(update_fields=update_fields_list)
                    action = 'updated'
                    self._log(f"      Updated fields: {', '.join(update_fields_list)}", log_verbosity=3)
            except Exception as e:
                logger.exception(f"Error saving updated fields for existing MediaItem {media_item.pk}: {e}")
                raise MediaItemProcessorError(f"Error saving fields for MediaItem {media_item.pk}")

            # Update M2M if needed
            m2m_changed = False
            if should_update_main_data:
                try:
                    m2m_changed = self._update_m2m_relations(media_item, genre_names, country_names)
                    if m2m_changed:
                        action = 'updated'  # Ensure status reflects M2M change
                except Exception as e:
                    logger.error(f"Error updating M2M for MediaItem {media_item.pk} during update: {e}")
                    # Optionally raise, but currently just logs

            # Update metadata timestamp
            if should_update_main_data:
                self._update_metadata(media_item, api_updated_at, meta_created)

            # If only metadata timestamp changed, action should still be 'skipped' or 'updated' if M2M changed
            if action == 'skipped' and m2m_changed:
                action = 'updated'
            elif not fields_to_update and not m2m_changed and should_update_main_data:
                # Only timestamp might have updated, consider it skipped for overall stats
                action = 'skipped'

        else:
            self._log(f"    Skipping update for MediaItem {media_item.pk} (Reason: data not newer/no changes needed)",
                      log_verbosity=2)
            action = 'skipped'

        return action

    def _create_item(self, media_item_data: Dict[str, Any], genre_names: List[str], country_names: List[str],
                     api_updated_at: datetime) -> Tuple[MediaItem, str]:
        """Creates a new MediaItem and its relations."""
        self._log(f"  Creating new MediaItem ('{media_item_data.get('title')}')", log_verbosity=2)
        try:
            media_item = MediaItem.objects.create(**media_item_data)

            # Add M2M relations
            self._update_m2m_relations(media_item, genre_names, country_names)

            # Create metadata record
            self._update_metadata(media_item, api_updated_at, True)  # meta_created is True

            self._log(f"    Successfully created MediaItem PK {media_item.pk}", log_verbosity=3)
            return media_item, 'created'

        except IntegrityError as e:
            logger.error(f"Integrity error creating MediaItem with data {media_item_data}: {e}")
            raise MediaItemProcessorError("Integrity error during creation")
        except Exception as e:
            logger.exception(f"Unexpected error creating MediaItem with data {media_item_data}: {e}")
            raise MediaItemProcessorError("Unexpected error during creation")

    # --- Main Processing Method ---
    @transaction.atomic  # Ensure atomicity for find/create/update logic
    def process_api_item(self, mapped_data: Dict[str, Any], api_updated_at: datetime) -> Tuple[
        Optional[MediaItem], str]:
        """
        Processes mapped data for a single item from the API.
        Finds exact match, subset match, or creates a new item.
        Returns the processed MediaItem (or None) and a status string.
        """
        if not mapped_data:
            return None, 'skipped_mapping_failed'

        media_item_data = mapped_data.get('media_item_data', {})
        genre_names = mapped_data.get('genres', [])
        country_names = mapped_data.get('countries', [])

        if not media_item_data.get('title'):
            logger.warning(f"Skipping item due to missing title after mapping.")
            return None, 'skipped_missing_title'

        api_ids = {field: media_item_data.get(field) for field in self.id_fields}
        api_non_empty_ids = {k: v for k, v in api_ids.items() if v}

        if not api_non_empty_ids:
            logger.warning(f"Skipping item ('{media_item_data['title']}'): No external IDs provided by API.")
            return None, 'skipped_no_ids'  # Add kodik_internal_id logic here later

        try:
            # 1. Try exact match
            media_item = self._find_exact_match(api_ids)
            if media_item:
                self._log(f"  Found exact match -> MediaItem PK {media_item.pk}", log_verbosity=2)
                action = self._update_item(media_item, media_item_data, api_ids, genre_names, country_names,
                                           api_updated_at, is_subset_match=False)
                return media_item, action

            # 2. Try subset match
            media_item = self._find_subset_match(api_non_empty_ids)
            if media_item:
                self._log(f"  Found subset match -> MediaItem PK {media_item.pk}", log_verbosity=2)
                action = self._update_item(media_item, media_item_data, api_ids, genre_names, country_names,
                                           api_updated_at, is_subset_match=True)
                return media_item, action

            # 3. Create new item
            self._log(f"  No existing match found. Creating new item.", log_verbosity=3)
            media_item, action = self._create_item(media_item_data, genre_names, country_names, api_updated_at)
            return media_item, action

        except MediaItemProcessorError as e:
            logger.error(f"Processor error for item with API IDs {api_ids}: {e}")
            return None, f'error_{type(e).__name__}'  # e.g., error_MediaItemProcessorError
        except Exception as e:
            logger.exception(f"Unexpected outer error processing item with API IDs {api_ids}: {e}")
            return None, 'error_outer_processor'
