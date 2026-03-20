"""
Django management command to sync context from markdown files.

Usage:
    python manage.py sync_context
    python manage.py sync_context --path docs/
    python manage.py sync_context --force
"""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from context.managers import ContextManager


class Command(BaseCommand):
    help = 'Synchronize context from markdown documents'

    def add_arguments(self, parser):
        parser.add_argument(
            '--path',
            type=str,
            default=None,
            help='Path to docs directory (default: BASE_DIR/docs)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force reprocessing of all documents'
        )
        parser.add_argument(
            '--file',
            type=str,
            default=None,
            help='Process a single file instead of directory'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output'
        )

    def handle(self, *args, **options):
        manager = ContextManager()

        # Single file mode
        if options['file']:
            file_path = Path(options['file'])
            if not file_path.exists():
                raise CommandError(f"File not found: {file_path}")

            self.stdout.write(f"Processing file: {file_path}")

            result = manager.process_document(file_path, force=options['force'])

            if result['success']:
                self.stdout.write(self.style.SUCCESS(
                    f"Successfully processed {file_path}\n"
                    f"  Chunks created: {result['chunks_created']}\n"
                    f"  Chunks updated: {result['chunks_updated']}\n"
                    f"  Time: {result['processing_time_ms']}ms"
                ))
            else:
                self.stdout.write(self.style.ERROR(
                    f"Failed to process {file_path}: {result['error']}"
                ))
            return

        # Directory mode
        docs_dir = options['path']
        if docs_dir:
            docs_dir = Path(docs_dir)
        else:
            docs_dir = Path(settings.BASE_DIR) / 'docs'

        if not docs_dir.exists():
            self.stdout.write(self.style.WARNING(
                f"Docs directory does not exist: {docs_dir}"
            ))
            self.stdout.write("Creating directory...")
            docs_dir.mkdir(parents=True, exist_ok=True)
            self.stdout.write(self.style.SUCCESS("Directory created. Add .md files and run again."))
            return

        self.stdout.write(f"Syncing context from: {docs_dir}")

        if options['force']:
            self.stdout.write(self.style.WARNING("Force mode: all documents will be reprocessed"))

        # Run sync
        stats = manager.ingestion.ingest_directory(
            docs_dir,
            recursive=True,
            force=options['force']
        )

        # Display results
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write("SYNC COMPLETE")
        self.stdout.write("=" * 50)

        self.stdout.write(f"Total files found: {stats['total_files']}")
        self.stdout.write(f"Files processed: {stats['processed']}")
        self.stdout.write(f"Files skipped (unchanged): {stats['skipped']}")
        self.stdout.write(f"Errors: {stats['errors']}")
        self.stdout.write(f"Chunks created: {stats['total_chunks_created']}")
        self.stdout.write(f"Chunks updated: {stats['total_chunks_updated']}")
        self.stdout.write(f"Total time: {stats['total_time_ms']}ms")

        if stats['files_with_errors'] and options['verbose']:
            self.stdout.write("\nErrors:")
            for error in stats['files_with_errors']:
                self.stdout.write(self.style.ERROR(
                    f"  {error['file']}: {error['error']}"
                ))

        if stats['errors'] > 0:
            self.stdout.write(self.style.WARNING(
                f"\n{stats['errors']} file(s) had errors. Use --verbose for details."
            ))
        else:
            self.stdout.write(self.style.SUCCESS("\nAll files synced successfully!"))
