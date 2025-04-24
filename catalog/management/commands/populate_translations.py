# catalog/management/commands/populate_translations.py

import logging
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction
from catalog.models import Translation
from catalog.services.kodik_client import KodikApiClient

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Populates the Translation table with data from the Kodik API /translations/v2 endpoint.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing translations before populating.',
        )
        # Optional: Add arguments to pass filters to get_translations if needed
        # parser.add_argument('--types', type=str, help='Filter by media types.')

    def handle(self, *args, **options):
        self.verbosity = options['verbosity']
        self._log("Starting population of Kodik translations...", self.style.NOTICE)

        if options['clear']:
            self._log("Clearing existing translations...", self.style.WARNING)
            count, _ = Translation.objects.all().delete()
            self._log(f"Deleted {count} existing translations.", self.style.WARNING)

        try:
            client = KodikApiClient()
        except ValueError as e:
            raise CommandError(f"API Client initialization failed: {e}")

        # Optional: Pass filters from command line if implemented
        filter_params = {}
        # if options['types']: filter_params['types'] = options['types']

        response_data = client.get_translations(**filter_params)

        if response_data is None or 'results' not in response_data:
            raise CommandError("Failed to fetch translations from Kodik API. Check logs.")

        translations_api = response_data.get('results', [])
        api_total = len(translations_api)  # This endpoint doesn't seem to have pagination based on docs

        self._log(f"Fetched {api_total} translations from API. Processing...")

        created_count = 0
        updated_count = 0
        skipped_count = 0

        with transaction.atomic():  # Process all within one transaction
            for trans_data in translations_api:
                kodik_id = trans_data.get('id')
                title = trans_data.get('title')

                if not kodik_id or not title:
                    logger.warning(f"Skipping translation entry due to missing ID or title: {trans_data}")
                    skipped_count += 1
                    continue

                try:
                    # Use update_or_create to handle existing entries and update titles if they change
                    translation, created = Translation.objects.update_or_create(
                        kodik_id=kodik_id,
                        defaults={'title': title.strip()}  # Ensure title is stripped
                    )
                    if created:
                        created_count += 1
                        self._log(f"  Created: {translation}", verbosity=2)
                    else:
                        # Check if title actually changed before incrementing updated_count
                        if translation.title != title.strip():
                            # update_or_create already saved it
                            updated_count += 1
                            self._log(f"  Updated: {translation}", verbosity=2)
                        # else: # Log unchanged only at higher verbosity?
                        #    self._log(f"  Exists: {translation}", verbosity=3)

                except IntegrityError as e:  # Should not happen with update_or_create unless DB is inconsistent
                    logger.error(f"Integrity error processing translation ID {kodik_id}, Title '{title}': {e}")
                    skipped_count += 1
                except Exception as e:
                    logger.exception(f"Error processing translation ID {kodik_id}, Title '{title}': {e}")
                    skipped_count += 1

        self._log(f"\nProcessing finished.", self.style.SUCCESS)
        self._log(f"  Total from API: {api_total}", self.style.SUCCESS)
        self._log(f"  Created: {created_count}", self.style.SUCCESS)
        self._log(f"  Updated: {updated_count}", self.style.SUCCESS)
        self._log(f"  Skipped: {skipped_count}", self.style.WARNING if skipped_count else self.style.SUCCESS)

    def _log(self, message, style=None, verbosity=1):
        # Simple logger helper for commands
        if self.verbosity >= verbosity:
            styled_message = style(message) if style else message
            self.stdout.write(styled_message)
