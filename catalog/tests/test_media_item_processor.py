# catalog/tests/test_media_item_processor.py

from datetime import timedelta

# Используем Django TestCase для управления БД
from django.test import TestCase
from django.utils import timezone as django_timezone  # Используем для now() в тестах

from catalog.models import MediaItem, Genre, Country, Source, MediaItemSourceMetadata
from catalog.services.media_item_processor import MediaItemProcessor


# Используем pytest.mark.django_db, если используем pytest,
# или наследуемся от Django TestCase
# @pytest.mark.django_db
class MediaItemProcessorTests(TestCase):
    """Tests for the MediaItemProcessor service."""

    @classmethod
    def setUpTestData(cls):
        """Set up non-modified objects used by all test methods."""
        cls.source_kodik = Source.objects.create(name='Kodik', slug='kodik')
        cls.genre1 = Genre.objects.create(name='Action')
        cls.genre2 = Genre.objects.create(name='Comedy')
        cls.country1 = Country.objects.create(name='USA')

    def setUp(self):
        """Set up fresh processor instance for each test."""
        # Reset processor for each test to avoid state issues if it becomes stateful
        # Verbosity 0 to avoid log noise during tests unless debugging
        self.processor = MediaItemProcessor(kodik_source=self.source_kodik, verbosity=0)
        self.processor_fill = MediaItemProcessor(kodik_source=self.source_kodik, fill_empty_fields=True, verbosity=0)

        # Common API data structure elements
        self.now = django_timezone.now()
        self.past_time = self.now - timedelta(days=1)
        self.future_time = self.now + timedelta(days=1)

        self.base_api_item_data = {
            'media_item_data': {
                'title': 'Test Movie',
                'original_title': 'Test Movie Orig',
                'media_type': MediaItem.MediaType.MOVIE,
                'release_year': 2023,
                'description': 'Test description',
                'poster_url': 'http://example.com/poster.jpg',
                'kinopoisk_id': '12345',
                'imdb_id': 'tt12345',
                'shikimori_id': None,  # Explicitly None
                'mydramalist_id': None,
            },
            'genres': ['Action', 'Comedy'],
            'countries': ['USA'],
        }

    # --- Test Cases ---

    def test_create_new_item(self):
        """Test creating a new item when no match exists."""
        api_data = self.base_api_item_data
        item, status = self.processor.process_api_item(api_data, self.now)

        self.assertEqual(status, 'created')
        self.assertIsNotNone(item)
        self.assertEqual(item.title, 'Test Movie')
        self.assertEqual(item.kinopoisk_id, '12345')
        self.assertEqual(item.imdb_id, 'tt12345')
        self.assertIsNone(item.shikimori_id)
        self.assertEqual(item.genres.count(), 2)
        self.assertIn(self.genre1, item.genres.all())
        self.assertIn(self.genre2, item.genres.all())
        self.assertEqual(item.countries.count(), 1)
        self.assertIn(self.country1, item.countries.all())

        # Check metadata
        meta = MediaItemSourceMetadata.objects.get(media_item=item, source=self.source_kodik)
        self.assertEqual(meta.source_last_updated_at, self.now)

    def test_exact_match_no_update_needed(self):
        """Test finding an exact match but skipping update (API data not newer)."""
        # 1. Create initial item
        initial_item, _ = self.processor.process_api_item(self.base_api_item_data, self.past_time)
        initial_updated_at = initial_item.updated_at  # Store initial Django timestamp

        # 2. Process the same data with the same (or older) API timestamp
        # Use a slightly modified description to see if it updates
        api_data_same_time = self.base_api_item_data.copy()
        api_data_same_time['media_item_data'] = api_data_same_time['media_item_data'].copy()
        api_data_same_time['media_item_data']['description'] = 'New Description - Should Not Update'

        item, status = self.processor.process_api_item(api_data_same_time, self.past_time)

        # 3. Assertions
        self.assertEqual(status, 'skipped')  # Should be skipped as API time <= DB time
        self.assertEqual(item.pk, initial_item.pk)
        self.assertEqual(item.description, 'Test description')  # Description should NOT have updated
        self.assertEqual(MediaItem.objects.count(), 1)  # No new item created

        # Check metadata timestamp wasn't updated
        meta = MediaItemSourceMetadata.objects.get(media_item=item, source=self.source_kodik)
        self.assertEqual(meta.source_last_updated_at, self.past_time)

        # Check Django's updated_at didn't change unnecessarily
        item.refresh_from_db()
        self.assertEqual(item.updated_at, initial_updated_at)

    def test_exact_match_update_newer_api_data(self):
        """Test finding an exact match and updating because API data is newer."""
        # 1. Create initial item
        initial_item, _ = self.processor.process_api_item(self.base_api_item_data, self.past_time)

        # 2. Process the same data with a *newer* API timestamp and changed data
        api_data_newer = self.base_api_item_data.copy()
        api_data_newer['media_item_data'] = api_data_newer['media_item_data'].copy()
        api_data_newer['media_item_data']['description'] = 'New Description - Should Update'
        api_data_newer['media_item_data']['release_year'] = 2024
        # Remove a genre to test M2M update
        api_data_newer['genres'] = ['Action']

        item, status = self.processor.process_api_item(api_data_newer, self.future_time)

        # 3. Assertions
        self.assertEqual(status, 'updated')
        self.assertEqual(item.pk, initial_item.pk)
        self.assertEqual(item.description, 'New Description - Should Update')  # Description updated
        self.assertEqual(item.release_year, 2024)  # Year updated
        self.assertEqual(item.genres.count(), 1)  # Genre removed
        self.assertIn(self.genre1, item.genres.all())
        self.assertNotIn(self.genre2, item.genres.all())
        self.assertEqual(MediaItem.objects.count(), 1)

        # Check metadata timestamp WAS updated
        meta = MediaItemSourceMetadata.objects.get(media_item=item, source=self.source_kodik)
        self.assertEqual(meta.source_last_updated_at, self.future_time)

    def test_exact_match_fill_empty_fields(self):
        """Test updating empty fields when fill_empty_fields is True, even if API data is not newer."""
        # 1. Create initial item with an empty description and old timestamp
        initial_data = self.base_api_item_data.copy()
        initial_data['media_item_data'] = initial_data['media_item_data'].copy()
        initial_data['media_item_data']['description'] = None  # Start with empty description
        initial_item, _ = self.processor.process_api_item(initial_data, self.past_time)
        self.assertIsNone(initial_item.description)

        # 2. Process data with a description but the *same* old API timestamp, using processor_fill
        api_data_fill = self.base_api_item_data.copy()  # Has description 'Test description'
        item, status = self.processor_fill.process_api_item(api_data_fill, self.past_time)

        # 3. Assertions
        self.assertEqual(status, 'updated')  # Should update because fill_empty_fields=True
        self.assertEqual(item.pk, initial_item.pk)
        self.assertEqual(item.description, 'Test description')  # Description should be filled
        self.assertEqual(MediaItem.objects.count(), 1)

        # Check metadata timestamp wasn't updated (since should_update_main_data was false)
        meta = MediaItemSourceMetadata.objects.get(media_item=item, source=self.source_kodik)
        self.assertEqual(meta.source_last_updated_at, self.past_time)

    def test_subset_match_update_ids(self):
        """Test finding a subset match and updating it with new IDs and data."""
        # 1. Create initial item with only KP ID and old timestamp
        initial_data = {
            'media_item_data': {
                'title': 'Old Title',
                'media_type': MediaItem.MediaType.MOVIE,
                'release_year': 2020,
                'kinopoisk_id': '12345',  # Only KP ID
                'imdb_id': None,
                'shikimori_id': None,
                'mydramalist_id': None,
            },
            'genres': ['Action'],
            'countries': [],
        }
        initial_item, _ = self.processor.process_api_item(initial_data, self.past_time)
        self.assertEqual(initial_item.title, 'Old Title')
        self.assertIsNone(initial_item.imdb_id)
        self.assertEqual(initial_item.genres.count(), 1)

        # 2. Process new data for the same item, but now with IMDb ID added and other data changed
        api_data_subset = {
            'media_item_data': {
                'title': 'New Title',  # Changed title
                'media_type': MediaItem.MediaType.MOVIE,
                'release_year': 2020,
                'kinopoisk_id': '12345',  # Same KP ID
                'imdb_id': 'tt99999',  # <-- New IMDb ID
                'shikimori_id': None,
                'mydramalist_id': None,
                'description': 'Subset Description',  # New description
            },
            'genres': ['Action', 'Comedy'],  # Added genre
            'countries': ['USA'],  # Added country
        }
        # Use future time to ensure update would happen anyway, focus is on ID merge
        item, status = self.processor.process_api_item(api_data_subset, self.future_time)

        # 3. Assertions
        self.assertEqual(status, 'updated')  # Status should be updated (due to subset match)
        self.assertEqual(item.pk, initial_item.pk)  # Should update the existing item
        self.assertEqual(MediaItem.objects.count(), 1)  # No new item created
        self.assertEqual(item.title, 'New Title')  # Title updated
        self.assertEqual(item.description, 'Subset Description')  # Description updated
        self.assertEqual(item.kinopoisk_id, '12345')  # KP ID remains
        self.assertEqual(item.imdb_id, 'tt99999')  # <-- IMDb ID was added
        self.assertEqual(item.genres.count(), 2)  # Comedy genre added
        self.assertIn(self.genre2, item.genres.all())
        self.assertEqual(item.countries.count(), 1)  # USA added
        self.assertIn(self.country1, item.countries.all())

        # Check metadata timestamp WAS updated
        meta = MediaItemSourceMetadata.objects.get(media_item=item, source=self.source_kodik)
        self.assertEqual(meta.source_last_updated_at, self.future_time)

    def test_no_external_ids_skipped(self):
        """Test that an item with no external IDs is skipped."""
        api_data_no_ids = {
            'media_item_data': {
                'title': 'No ID Movie',
                'media_type': MediaItem.MediaType.MOVIE,
                'release_year': 2023,
                'kinopoisk_id': None,  # All IDs None
                'imdb_id': None,
                'shikimori_id': None,
                'mydramalist_id': None,
            },
            'genres': [], 'countries': [],
        }
        item, status = self.processor.process_api_item(api_data_no_ids, self.now)
        self.assertEqual(status, 'skipped_no_ids')
        self.assertIsNone(item)
        self.assertEqual(MediaItem.objects.count(), 0)

    def test_mapping_failed_skipped(self):
        """Test that status reflects skipped mapping."""
        # Simulate processor receiving None as mapped_data
        item, status = self.processor.process_api_item(None, self.now)
        self.assertEqual(status, 'skipped_mapping_failed')
        self.assertIsNone(item)

    def test_missing_title_skipped(self):
        """Test skipping when title is missing after mapping."""
        api_data_no_title = {
            'media_item_data': {'kinopoisk_id': '111'},  # No title
            'genres': [], 'countries': [],
        }
        item, status = self.processor.process_api_item(api_data_no_title, self.now)
        self.assertEqual(status, 'skipped_missing_title')
        self.assertIsNone(item)

    # Test for MultipleObjectsReturned might require more complex setup
    # to actually create duplicate conflicting items in the DB before running the processor.
    # It might be better tested manually or with integration tests.
