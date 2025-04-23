# catalog/services/kodik_client.py
import httpx
from django.conf import settings
from urllib.parse import urljoin, urlencode  # Import urlencode
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class KodikApiClient:
    DEFAULT_LIMIT = 50

    def __init__(self, base_url: str = settings.KODIK_API_BASE_URL, token: str = settings.KODIK_API_TOKEN,
                 timeout: int = 30):  # Increased timeout for potentially slower searches
        if not base_url or not token:
            raise ValueError("Kodik API base URL and token must be configured in settings.")
        self.base_url = base_url
        self.token = token
        self.timeout = timeout

    def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        if params is None: params = {}
        params['token'] = self.token
        url = urljoin(self.base_url, endpoint)

        try:
            # Use httpx.Client for synchronous requests
            # Pass parameters without encoding lists manually, httpx handles it
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url, params=params)
                # Log request details for debugging complex requests
                logger.debug(f"Making Kodik API request to: {response.url}")
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Kodik API request failed for {e.request.url!r}: Status {e.response.status_code} - {e.response.text}")
        except httpx.RequestError as e:
            logger.error(f"Kodik API request error for {e.request.url!r}: {e}")
        except Exception as e:
            logger.exception(f"An unexpected error occurred during Kodik API request to {url}: {e}")

        return None

    def list_items(self, limit: int = DEFAULT_LIMIT, page_link: Optional[str] = None, **kwargs: Any) -> Optional[
        Dict[str, Any]]:
        if page_link:
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.get(page_link)
                    response.raise_for_status()
                    return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"Kodik API request failed for {e.request.url!r}: Status {e.response.status_code} - {e.response.text}")
            except httpx.RequestError as e:
                logger.error(f"Kodik API request error for {e.request.url!r}: {e}")
            except Exception as e:
                logger.exception(f"An unexpected error occurred during Kodik API request to {page_link}: {e}")
            return None
        else:
            endpoint = 'list'
            params = {'limit': min(max(limit, 1), 100)}
            # httpx handles list-to-comma-separated conversion automatically for query params
            # We just need to ensure values are strings or convertible
            for key, value in kwargs.items():
                if value is not None:
                    if isinstance(value, bool):
                        params[key] = str(value).lower()  # Convert bool to 'true'/'false'
                    elif isinstance(value, (list, tuple)):
                        # Join lists/tuples manually if httpx doesn't do it as expected by Kodik
                        params[key] = ','.join(map(str, value))
                    else:
                        params[key] = str(value)

            return self._make_request(endpoint, params=params)

    def get_translations(self, **kwargs: Any) -> Optional[Dict[str, Any]]:
        endpoint = 'translations/v2'
        return self._make_request(endpoint, params=kwargs)

    # --- NEW METHOD: search_by_ids ---
    def search_by_ids(self,
                      kinopoisk_id: Optional[str] = None,
                      imdb_id: Optional[str] = None,
                      shikimori_id: Optional[str] = None,
                      mydramalist_id: Optional[str] = None,
                      limit: int = 100,  # Allow fetching more results if many translations exist
                      **kwargs: Any) -> Optional[Dict[str, Any]]:
        """
        Searches for materials using external IDs via the /search endpoint.
        According to docs, returns results for different available translations.

        Args:
            kinopoisk_id: Kinopoisk ID.
            imdb_id: IMDb ID.
            shikimori_id: Shikimori ID.
            mydramalist_id: MyDramaList ID (mdl_id in API).
            limit: Max number of results (translations) to return.
            **kwargs: Additional filter parameters for /search (e.g., with_material_data, with_episodes_data).

        Returns:
            The parsed JSON response dictionary from the API, or None on failure.
            Expected keys: 'time', 'total', 'results' (list of dicts, each representing a translation variant).
        """
        endpoint = 'search'
        params = {
            # Use only provided IDs
            'kinopoisk_id': kinopoisk_id,
            'imdb_id': imdb_id,
            'shikimori_id': shikimori_id,
            'mdl_id': mydramalist_id,  # API uses mdl_id for MyDramaList
            'limit': min(max(limit, 1), 100)
        }
        # Remove None values from ID params
        params = {k: v for k, v in params.items() if v is not None}

        if not any(params.get(id_field) for id_field in ['kinopoisk_id', 'imdb_id', 'shikimori_id', 'mdl_id']):
            logger.error("Search by IDs requires at least one external ID (KP, IMDb, Shiki, MDL).")
            return None

        # Add other kwargs, converting bools etc.
        for key, value in kwargs.items():
            if value is not None:
                if isinstance(value, bool):
                    params[key] = str(value).lower()
                elif isinstance(value, (list, tuple)):
                    params[key] = ','.join(map(str, value))
                else:
                    params[key] = str(value)

        return self._make_request(endpoint, params=params)
    # --- END NEW METHOD ---

    # Optional: Add methods for get_genres, get_countries if needed later
    # def get_genres(self, **kwargs: Any) -> Optional[Dict[str, Any]]:
    #     endpoint = 'genres'
    #     return self._make_request(endpoint, params=kwargs)
    #
    # def get_countries(self, **kwargs: Any) -> Optional[Dict[str, Any]]:
    #     endpoint = 'countries'
    #     return self._make_request(endpoint, params=kwargs)
