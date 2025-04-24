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
    title = translation_data.get('title')
    type_ = translation_data.get('type')
    if title and type_:
        return f"{title} ({type_})", str(translation_data.get('id'))
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

    try:
        return MediaItem.MediaType(kodik_type).value
    except ValueError:
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
    source_specific_id = item_data.get('id')

    # 1. Map MediaItem core fields
    media_item_map = {
        'title': item_data.get('title'),
        'original_title': item_data.get('title_orig'),
        'release_year': item_data.get('year'),
        'media_type': _map_kodik_type_to_model_type(item_data.get('type')),
        'kinopoisk_id': item_data.get('kinopoisk_id'),
        'imdb_id': item_data.get('imdb_id'),
        'shikimori_id': item_data.get('shikimori_id'),
        'mydramalist_id': item_data.get('mdl_id'),
    }

    if not media_item_map['title'] and media_item_map['original_title']:
        media_item_map['title'] = media_item_map['original_title']

    if not media_item_map['title']:
        logger.warning(f"Skipping item {source_specific_id}: Missing title.")
        return None

    for key in ['original_title', 'kinopoisk_id', 'imdb_id', 'shikimori_id', 'mydramalist_id']:
        if media_item_map[key] == '':
            media_item_map[key] = None

    material_data = item_data.get('material_data')
    genres: Set[str] = set()
    countries: Set[str] = set()

    if material_data and isinstance(material_data, dict):
        media_item_map['description'] = _get_safe_string(material_data, 'description')
        media_item_map['poster_url'] = _get_safe_string(material_data, 'poster_url')
        media_item_map['kinopoisk_id'] = _get_safe_string(material_data, 'kinopoisk_id') or media_item_map[
            'kinopoisk_id']
        media_item_map['imdb_id'] = _get_safe_string(material_data, 'imdb_id') or media_item_map['imdb_id']
        media_item_map['shikimori_id'] = _get_safe_string(material_data, 'shikimori_id') or media_item_map[
            'shikimori_id']
        media_item_map['mydramalist_id'] = _get_safe_string(material_data, 'mydramalist_id') or media_item_map[
            'mydramalist_id']

        genres.update(_get_string_list(material_data, 'genres'))
        genres.update(_get_string_list(material_data, 'anime_genres'))
        genres.update(_get_string_list(material_data, 'drama_genres'))
        # TODO: Consider `all_genres` if provided? Need clarity on its format/use.

        countries.update(_get_string_list(material_data, 'countries'))

    mapped_data['media_item_data'] = {k: v for k, v in media_item_map.items() if v is not None}
    mapped_data['genres'] = sorted(list(genres))
    mapped_data['countries'] = sorted(list(countries))

    translation_info, translation_id_str = _parse_translation(item_data.get('translation'))
    main_link_data = {
        'player_link': item_data.get('link'),
        'quality_info': item_data.get('quality'),
        'translation_info': translation_info,
        'source_specific_id': source_specific_id,
    }
    if main_link_data['player_link']:
        mapped_data['main_source_link_data'] = {k: v for k, v in main_link_data.items() if v is not None}

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
                    if isinstance(episode_content, str):
                        episode_link = episode_content
                    elif isinstance(episode_content, dict):
                        episode_link = episode_content.get('link')
                        episode_title = episode_content.get('title')

                    episode_entry = {'number': episode_number, 'title': episode_title}

                    if episode_link:
                        episode_link_data = {
                            'player_link': episode_link,
                            'quality_info': item_data.get('quality'),
                            'translation_info': translation_info,
                            'source_specific_id': f"{source_specific_id}_s{season_number}_e{episode_number}"
                        }
                        episode_entry['link_data'] = {k: v for k, v in episode_link_data.items() if v is not None}

                    season_entry['episodes_data'].append(episode_entry)

                season_entry['episodes_data'].sort(key=lambda x: x['number'])

            mapped_seasons.append(season_entry)

        mapped_seasons.sort(key=lambda x: x['number'])
        mapped_data['seasons_data'] = mapped_seasons

    return mapped_data
