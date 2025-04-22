# catalog/services/kodik_client.py
import httpx
from django.conf import settings
from urllib.parse import urljoin
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class KodikApiClient:
    """
    Client for interacting with the Kodik API.
    Uses httpx for making synchronous HTTP requests.
    """
    DEFAULT_LIMIT = 50  # Default limit per page as per Kodik docs

    def __init__(self, base_url: str = settings.KODIK_API_BASE_URL, token: str = settings.KODIK_API_TOKEN,
                 timeout: int = 15):
        if not base_url or not token:
            raise ValueError("Kodik API base URL and token must be configured in settings.")
        self.base_url = base_url
        self.token = token
        self.timeout = timeout

    def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Internal method to make a GET request to the Kodik API.

        Args:
            endpoint: The API endpoint path (e.g., 'list').
            params: A dictionary of query parameters.

        Returns:
            A dictionary representing the parsed JSON response, or None if an error occurs.
        """
        if params is None:
            params = {}

        # Ensure the mandatory token is included
        params['token'] = self.token

        # Construct the full URL
        url = urljoin(self.base_url, endpoint)

        try:
            # Use httpx.Client for synchronous requests
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url, params=params)
                response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Kodik API request failed for {e.request.url!r}: Status {e.response.status_code} - {e.response.text}")
        except httpx.RequestError as e:
            logger.error(f"Kodik API request error for {e.request.url!r}: {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred during Kodik API request to {url}: {e}")

        return None

    def list_items(self, limit: int = DEFAULT_LIMIT, page_link: Optional[str] = None, **kwargs: Any) -> Optional[
        Dict[str, Any]]:
        """
        Fetches a list of media items from the /list endpoint.

        Args:
            limit: Number of items per page (1-100).
            page_link: The full URL for the next page (from 'next_page' in previous response).
                       If provided, other parameters might be ignored by the API.
            **kwargs: Additional filter/sort parameters (e.g., types, year, sort, order, with_material_data).
                      Values should be strings or types easily convertible to strings.
                      Lists/tuples will be joined by commas.

        Returns:
            The parsed JSON response dictionary from the API, or None on failure.
            Expected keys include 'total', 'prev_page', 'next_page', 'results'.
        """
        if page_link:
            # If a direct page link is given, use it directly.
            # Need to strip base_url if page_link includes it, or handle differently.
            # Assuming page_link is the full URL as seen in the example.
            # We make the request to the full URL, ignoring the endpoint path.
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    # Don't pass the token again if it's already in page_link (safer to just use it)
                    response = client.get(page_link)
                    response.raise_for_status()
                    return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"Kodik API request failed for {e.request.url!r}: Status {e.response.status_code} - {e.response.text}")
            except httpx.RequestError as e:
                logger.error(f"Kodik API request error for {e.request.url!r}: {e}")
            except Exception as e:
                logger.error(f"An unexpected error occurred during Kodik API request to {page_link}: {e}")
            return None
        else:
            # Build parameters for a new request
            endpoint = 'list'
            params = {'limit': min(max(limit, 1), 100)}  # Ensure limit is within 1-100

            for key, value in kwargs.items():
                if isinstance(value, (list, tuple)):
                    params[key] = ','.join(map(str, value))  # Join list items with comma
                elif value is not None:
                    # Only add parameter if value is not None
                    # API might treat empty string differently than missing param
                    params[key] = str(value)

            return self._make_request(endpoint, params=params)

    # --- Add methods for other potential Kodik API endpoints if needed ---
    # def get_translations(self, ...): ...
    # def get_qualities(self, ...): ...
