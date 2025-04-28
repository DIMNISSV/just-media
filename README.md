# Just Media

A Django CMS-based project for browsing and viewing media content, utilizing the Kodik API for data sourcing.

## Key Features

*   **Media Catalog:** Browse movies, TV shows, anime series, and more.
*   **Kodik API Integration:** Parses media details, seasons, episodes, and player links from Kodik.
*   **Dynamic Player:** Select different translations and episodes directly on the watch page.
*   **User Layout Preferences:** Choose how episodes are displayed relative to the player (below, right side, or player only). Preference saved locally.
*   **Search & Filtering:** Basic navbar search and advanced filtering by title, year, type, and genre.
*   **Django CMS:** Leverages Django CMS for basic site structure and potential content management via plugins (future).
*   **Theme Switcher:** Toggle between light and dark modes (Bootstrap 5).

## Technology Stack

*   Python
*   Django & Django CMS
*   Bootstrap 5
*   Kodik API
*   SQLite (for development)
*   `python-dotenv` for environment variables

## Basic Setup & Running

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/DIMNISSV/just-media
    cd just_media
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.in
    ```

4.  **Configure environment variables:**
    *   Create a `.env` file in the project root (where `manage.py` is).
    *   Add the following variables:
        ```dotenv
        SECRET_KEY='your-strong-random-secret-key'
        KODIK_API_TOKEN='your_kodik_api_token'
        DEBUG=True # Set to False for production
        ```
    *   You can use this command: `python -c "import secrets; print(secrets.token_urlsafe(64))"`
5.  **Apply database migrations:**
    ```bash
    python manage.py migrate
    ```

6.  **Create a superuser (for admin access):**
    ```bash
    python manage.py createsuperuser
    ```

7.  **Populate initial data from Kodik:**
    *   Fetch available translations:
        ```bash
        python manage.py populate_translations
        ```
    *   Parse core media item data (this might take time):
        ```bash
        python manage.py parse_kodik --with-material-data
        ```
    *   Fetch episode/link details for some items:
        ```bash
        python manage.py update_translations --all --limit 50 # Process 50 random items
        ```
        *(Or specify specific PKs with `--pk 1 2 3`)*

8.  **Run the development server:**
    ```bash
    python manage.py runserver
    ```

9.  **Access the site:**
    *   Frontend: `http://127.0.0.1:8000/`
    *   Admin: `http://127.0.0.1:8000/admin/`

## Licenses
* **Base:** GPL-3 in `LICENSE`
* **DjangoCMS:** BSD-3 Clause in `licenses/DjangoCMS`