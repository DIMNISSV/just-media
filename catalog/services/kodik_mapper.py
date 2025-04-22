# catalog/services/kodik_mapper.py

import logging
from typing import Dict, Any, Optional, List, Tuple, Set
from ..models import MediaItem

logger = logging.getLogger(__name__)


# --- Helper Functions ---

def _parse_translation(translation_data: Optional[Dict[str, Any]]) -> Tuple[Optional[str], Optional[str]]:
    """ Parses translation object from Kodik API """
    if not translation_data or not isinstance(translation_data, dict):
        return None, None
    # Combine title and type for richer info, e.g., "ColdFilm (voice)"
    title = translation_data.get('title')
    type_ = translation_data.get('type')
    if title and type_:
        return f"{title} ({type_})", str(translation_data.get('id'))  # Return info and source-specific translation ID
    elif title:
        return title, str(translation_data.get('id'))
    return None, str(translation_data.get('id'))


def _get_string_list(data: Optional[Dict[str, Any]], key: str) -> List[str]:
    """ Safely gets a list of strings from material_data """
    if not data or not isinstance(data, dict):
        return []
    value = data.get(key)
    if isinstance(value, list):
        return [str(item).strip() for item in value if item]
    return []


def _get_safe_string(data: Optional[Dict[str, Any]], key: str) -> Optional[str]:
    """ Safely gets a string value from a dictionary """
    if not data or not isinstance(data, dict):
        return None
    value = data.get(key)
    return str(value) if value is not None else None


def _map_kodik_type_to_model_type(kodik_type: Optional[str]) -> str:
    """ Maps Kodik's type string to MediaItem.MediaType enum value. """
    if not kodik_type:
        return MediaItem.MediaType.UNKNOWN

    # Direct mapping based on the enum definition in models.py
    try:
        # Attempt direct conversion (enum value matches kodik type)
        return MediaItem.MediaType(kodik_type).value
    except ValueError:
        # Handle potential variations or fallback logic if needed
        logger.warning(f"Unknown Kodik type encountered: {kodik_type}. Falling back to UNKNOWN.")
        return MediaItem.MediaType.UNKNOWN


# --- Main Mapping Function ---

def map_kodik_item_to_models(item_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Maps a single item dictionary from Kodik API '/list' response
    to a structured dictionary suitable for creating/updating Django models.

    Args:
        item_data: Dictionary representing one item from the 'results' list.

    Returns:
        A dictionary containing structured data for models, or None if essential data is missing.
        Example structure:
        {
            'media_item_data': {'title': ..., 'release_year': ..., ...},
            'genres': ['Action', 'Drama'],
            'countries': ['USA'],
            'main_source_link_data': {'player_link': ..., 'quality_info': ...},
            'seasons_data': [
                {
                    'number': 1,
                    'episodes_data': [
                        {'number': 1, 'title': ..., 'link_data': {'player_link': ...}},
                        {'number': 2, 'title': ..., 'link_data': {'player_link': ...}},
                    ]
                },
                # ... more seasons
            ]
        }
    """
    if not item_data or not isinstance(item_data, dict) or 'id' not in item_data:
        logger.warning("Skipping item due to missing data or invalid format.")
        return None

    mapped_data = {}
    source_specific_id = item_data.get('id')  # e.g., "movie-12345" or "serial-67890"

    # 1. Map MediaItem core fields
    media_item_map = {
        'title': item_data.get('title'),
        'original_title': item_data.get('title_orig'),
        'release_year': item_data.get('year'),
        'media_type': _map_kodik_type_to_model_type(item_data.get('type')),
        # IDs will be filled from material_data if available, or direct fields
        'kinopoisk_id': item_data.get('kinopoisk_id'),
        'imdb_id': item_data.get('imdb_id'),
        'shikimori_id': item_data.get('shikimori_id'),
        'mydramalist_id': item_data.get('mdl_id'),  # Kodik uses 'mdl_id'
    }

    # Use title_orig if title is missing (less likely but possible)
    if not media_item_map['title'] and media_item_map['original_title']:
        media_item_map['title'] = media_item_map['original_title']

    # Basic validation - title is essential
    if not media_item_map['title']:
        logger.warning(f"Skipping item {source_specific_id}: Missing title.")
        return None

    # Clean up empty strings to None for optional fields
    for key in ['original_title', 'kinopoisk_id', 'imdb_id', 'shikimori_id', 'mydramalist_id']:
        if media_item_map[key] == '':
            media_item_map[key] = None

    # 2. Process optional material_data (if requested via 'with_material_data')
    material_data = item_data.get('material_data')
    genres: Set[str] = set()
    countries: Set[str] = set()

    if material_data and isinstance(material_data, dict):
        # Override/add fields from material_data if they exist
        media_item_map['description'] = _get_safe_string(material_data, 'description')
        media_item_map['poster_url'] = _get_safe_string(material_data, 'poster_url')
        # Use material_data IDs if they are more reliable or present
        media_item_map['kinopoisk_id'] = _get_safe_string(material_data, 'kinopoisk_id') or media_item_map[
            'kinopoisk_id']
        media_item_map['imdb_id'] = _get_safe_string(material_data, 'imdb_id') or media_item_map['imdb_id']
        media_item_map['shikimori_id'] = _get_safe_string(material_data, 'shikimori_id') or media_item_map[
            'shikimori_id']
        media_item_map['mydramalist_id'] = _get_safe_string(material_data, 'mydramalist_id') or media_item_map[
            'mydramalist_id']

        # Extract genres and countries (using sets to avoid duplicates)
        # Kodik has multiple genre fields (genres, anime_genres, drama_genres)
        genres.update(_get_string_list(material_data, 'genres'))
        genres.update(_get_string_list(material_data, 'anime_genres'))
        genres.update(_get_string_list(material_data, 'drama_genres'))
        # TODO: Consider `all_genres` if provided? Need clarity on its format/use.

        countries.update(_get_string_list(material_data, 'countries'))

    mapped_data['media_item_data'] = {k: v for k, v in media_item_map.items() if v is not None}  # Remove None values
    mapped_data['genres'] = sorted(list(genres))
    mapped_data['countries'] = sorted(list(countries))

    # 3. Map main Source Link data (always present in basic response)
    translation_info, translation_id_str = _parse_translation(item_data.get('translation'))
    main_link_data = {
        'player_link': item_data.get('link'),
        'quality_info': item_data.get('quality'),
        'translation_info': translation_info,
        # 'translation_id': translation_id_str, # Store if needed for matching/updates
        'source_specific_id': source_specific_id,  # Link this source link to the main Kodik ID
    }
    # Only include if a player link exists
    if main_link_data['player_link']:
        mapped_data['main_source_link_data'] = {k: v for k, v in main_link_data.items() if v is not None}

    # 4. Process seasons and episodes (if requested via 'with_episodes' or 'with_episodes_data')
    seasons_api_data = item_data.get('seasons')
    mapped_seasons = []
    if seasons_api_data and isinstance(seasons_api_data, dict):
        for season_num_str, season_content in seasons_api_data.items():
            try:
                season_number = int(season_num_str)
            except (ValueError, TypeError):
                logger.warning(f"Skipping invalid season number '{season_num_str}' for item {source_specific_id}")
                continue

            season_entry = {'number': season_number, 'episodes_data': []}
            episodes_api_data = season_content.get('episodes') if isinstance(season_content, dict) else None

            if episodes_api_data and isinstance(episodes_api_data, dict):
                for episode_num_str, episode_content in episodes_api_data.items():
                    try:
                        episode_number = int(episode_num_str)
                    except (ValueError, TypeError):
                        logger.warning(
                            f"Skipping invalid episode number '{episode_num_str}' in S{season_number} for item {source_specific_id}")
                        continue

                    episode_link = None
                    episode_title = None
                    # Check if content is a simple link (with_episodes=true) or an object (with_episodes_data=true)
                    if isinstance(episode_content, str):
                        episode_link = episode_content
                    elif isinstance(episode_content, dict):
                        episode_link = episode_content.get('link')
                        episode_title = episode_content.get('title')
                        # Could also extract screenshots here: episode_content.get('screenshots')

                    episode_entry = {'number': episode_number, 'title': episode_title}

                    # Create source link data specifically for this episode
                    if episode_link:
                        # Episode links inherit quality/translation from the main item by default in Kodik API structure
                        episode_link_data = {
                            'player_link': episode_link,
                            'quality_info': item_data.get('quality'),  # Inherited
                            'translation_info': translation_info,  # Inherited
                            # 'translation_id': translation_id_str,   # Inherited
                            'source_specific_id': f"{source_specific_id}_s{season_number}_e{episode_number}"
                            # Create a unique ID
                        }
                        episode_entry['link_data'] = {k: v for k, v in episode_link_data.items() if v is not None}

                    season_entry['episodes_data'].append(episode_entry)

                # Sort episodes by number
                season_entry['episodes_data'].sort(key=lambda x: x['number'])

            mapped_seasons.append(season_entry)

        # Sort seasons by number
        mapped_seasons.sort(key=lambda x: x['number'])
        mapped_data['seasons_data'] = mapped_seasons

    return mapped_data
