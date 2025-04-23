# catalog/services/kodik_client.py
import httpx
from django.conf import settings
from urllib.parse import urljoin
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class KodikApiClient:
    DEFAULT_LIMIT = 50

    def __init__(self, base_url: str = settings.KODIK_API_BASE_URL, token: str = settings.KODIK_API_TOKEN,
                 timeout: int = 15):
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
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Kodik API request failed for {e.request.url!r}: Status {e.response.status_code} - {e.response.text}")
        except httpx.RequestError as e:
            logger.error(f"Kodik API request error for {e.request.url!r}: {e}")
        except Exception as e:
            logger.exception(
                f"An unexpected error occurred during Kodik API request to {url}: {e}")  # Use exception for traceback

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
            for key, value in kwargs.items():
                if isinstance(value, (list, tuple)):
                    params[key] = ','.join(map(str, value))
                elif value is not None:
                    params[key] = str(value)
            return self._make_request(endpoint, params=params)

    # --- NEW METHOD ---
    def get_translations(self, **kwargs: Any) -> Optional[Dict[str, Any]]:
        """
        Fetches a list of all available translations from the /translations/v2 endpoint.

        Args:
            **kwargs: Optional filter parameters as per Kodik docs (e.g., types, year).

        Returns:
            The parsed JSON response dictionary from the API, or None on failure.
            Expected keys: 'time', 'total', 'results' (list of dicts with 'id', 'title', 'count').
        """
        endpoint = 'translations/v2'
        return self._make_request(endpoint, params=kwargs)
    # --- END NEW METHOD ---

    # Add other methods like get_genres, get_countries, search_by_ids later
