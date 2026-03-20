"""
Django management command to reprocess context (force re-ingestion).

Usage:
    python manage.py reprocess_context
    python manage.py reprocess_context --file docs/feature.md
    python manage.py reprocess_context --reset
"""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from context.managers import ContextManager


class Command(BaseCommand):
    help = 'Reprocess all context documents (force re-ingestion)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            default=None,
            help='Reprocess a single file'
        )
        parser.add_argument(
            '--path',
            type=str,
            default=None,
            help='Path to docs directory'
        )
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Reset all context before reprocessing (DANGEROUS)'
        )
        parser.add_argument(
            '--confirm-reset',
            action='store_true',
            help='Confirm reset operation'
        )

    def handle(self, *args, **options):
        manager = ContextManager()

        # Reset mode
        if options['reset']:
            if not options['confirm_reset']:
                self.stdout.write(self.style.ERROR(
                    "Reset requires --confirm-reset flag. This will DELETE ALL indexed data!"
                ))
                return

            self.stdout.write(self.style.WARNING("Resetting all context data..."))
            manager.reset_all(confirm=True)
            self.stdout.write(self.style.SUCCESS("Context reset complete."))

        # Single file mode
        if options['file']:
            file_path = Path(options['file'])
            if not file_path.exists():
                raise CommandError(f"File not found: {file_path}")

            self.stdout.write(f"Reprocessing: {file_path}")
            result = manager.reprocess_document(str(file_path))

            if result['success']:
                self.stdout.write(self.style.SUCCESS(
                    f"Reprocessed successfully\n"
                    f"  Chunks: {result['chunks_created'] + result['chunks_updated']}\n"
                    f"  Time: {result['processing_time_ms']}ms"
                ))
            else:
                self.stdout.write(self.style.ERROR(f"Failed: {result['error']}"))
            return

        # Full reprocess
        docs_dir = options['path']
        if docs_dir:
            docs_dir = Path(docs_dir)
        else:
            docs_dir = Path(settings.BASE_DIR) / 'docs'

        if not docs_dir.exists():
            raise CommandError(f"Docs directory not found: {docs_dir}")

        self.stdout.write(f"Reprocessing all documents in: {docs_dir}")
        self.stdout.write(self.style.WARNING("This will regenerate all chunks and embeddings."))

        stats = manager.ingestion.ingest_directory(
            docs_dir,
            recursive=True,
            force=True  # Force reprocessing
        )

        self.stdout.write("\n" + "=" * 50)
        self.stdout.write("REPROCESS COMPLETE")
        self.stdout.write("=" * 50)
        self.stdout.write(f"Files reprocessed: {stats['processed']}")
        self.stdout.write(f"Errors: {stats['errors']}")
        self.stdout.write(f"Total chunks: {stats['total_chunks_created'] + stats['total_chunks_updated']}")
        self.stdout.write(f"Total time: {stats['total_time_ms']}ms")

        if stats['errors'] == 0:
            self.stdout.write(self.style.SUCCESS("\nAll files reprocessed successfully!"))
        else:
            self.stdout.write(self.style.WARNING(f"\n{stats['errors']} errors occurred."))
