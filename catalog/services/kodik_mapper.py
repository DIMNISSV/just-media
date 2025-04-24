# catalog/services/kodik_mapper.py

import logging
from typing import Dict, Any, Optional, List, Tuple, Set
from ..models import MediaItem

logger = logging.getLogger(__name__)


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
    """ Maps Kodik's type string to generic MediaItem.MediaType enum value. """
    if not kodik_type:
        return MediaItem.MediaType.UNKNOWN

    # Mapping based on Kodik documentation examples
    type_map = {
        'foreign-movie': MediaItem.MediaType.MOVIE,
        'russian-movie': MediaItem.MediaType.MOVIE,
        'soviet-cartoon': MediaItem.MediaType.CARTOON_MOVIE,  # Or SERIES if applicable? Assuming movie
        'foreign-cartoon': MediaItem.MediaType.CARTOON_MOVIE,
        'russian-cartoon': MediaItem.MediaType.CARTOON_MOVIE,
        'anime': MediaItem.MediaType.ANIME_MOVIE,  # Defaulting 'anime' type to movie, serial handled below
        'cartoon-serial': MediaItem.MediaType.CARTOON_SERIES,
        'documentary-serial': MediaItem.MediaType.DOCUMENTARY_SERIES,
        'russian-serial': MediaItem.MediaType.TV_SHOW,
        'foreign-serial': MediaItem.MediaType.TV_SHOW,
        'anime-serial': MediaItem.MediaType.ANIME_SERIES,
        'multi-part-film': MediaItem.MediaType.TV_SHOW,  # Or a specific type if needed?
        # Add mappings for other potential types if discovered
    }

    generic_type = type_map.get(kodik_type, MediaItem.MediaType.UNKNOWN)

    if generic_type == MediaItem.MediaType.UNKNOWN:
        logger.warning(f"Unknown Kodik type encountered: {kodik_type}. Falling back to UNKNOWN.")

    return generic_type


def map_kodik_item_to_models(item_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Maps a single item dictionary from Kodik API '/list' or '/search' response
    to a structured dictionary suitable for creating/updating Django models.
    Focuses on MediaItem core data, genres, countries.
    """
    if not item_data or not isinstance(item_data, dict) or 'id' not in item_data:
        logger.warning("Skipping item due to missing data or invalid format.")
        return None

    mapped_data = {}
    source_specific_id = item_data.get('id')

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
        media_item_map['description'] = _get_safe_string(material_data, 'description') or _get_safe_string(
            material_data, 'anime_description')
        media_item_map['poster_url'] = _get_safe_string(material_data, 'poster_url') or _get_safe_string(material_data,
                                                                                                         'anime_poster_url') or _get_safe_string(
            material_data, 'drama_poster_url')

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

        countries.update(_get_string_list(material_data, 'countries'))

    mapped_data['media_item_data'] = {k: v for k, v in media_item_map.items() if v is not None}
    mapped_data['genres'] = sorted(list(genres))
    mapped_data['countries'] = sorted(list(countries))

    return mapped_data
