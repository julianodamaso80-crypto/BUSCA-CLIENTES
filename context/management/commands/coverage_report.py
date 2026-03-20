"""
Django management command to generate context coverage report.

Usage:
    python manage.py coverage_report
    python manage.py coverage_report --json
    python manage.py coverage_report --detect-conflicts
"""

import json

from django.core.management.base import BaseCommand

from context.managers import ContextManager, ConflictDetector


class Command(BaseCommand):
    help = 'Generate context coverage report'

    def add_arguments(self, parser):
        parser.add_argument(
            '--json',
            action='store_true',
            help='Output as JSON'
        )
        parser.add_argument(
            '--stats',
            action='store_true',
            help='Show detailed statistics'
        )
        parser.add_argument(
            '--detect-conflicts',
            action='store_true',
            help='Also run conflict detection'
        )
        parser.add_argument(
            '--index',
            action='store_true',
            help='Show knowledge index'
        )

    def handle(self, *args, **options):
        manager = ContextManager()

        if options['json']:
            self._output_json(manager, options)
            return

        # Header
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("  CONTEXT COVERAGE REPORT")
        self.stdout.write("=" * 60 + "\n")

        # Generate report
        report = manager.get_coverage_report()

        # Summary
        self.stdout.write(f"Generated: {report['generated_at']}")
        self.stdout.write(f"Health Score: {self._health_bar(report['health_score'])}")
        self.stdout.write("")

        # Statistics
        self.stdout.write("STATISTICS")
        self.stdout.write("-" * 40)
        self.stdout.write(f"  Total Documents: {report['total_documents']}")
        self.stdout.write(f"  Total Chunks: {report['total_chunks']}")
        self.stdout.write(f"  Total Tokens: {report['total_tokens']:,}")
        self.stdout.write(f"  Avg Chunk Size: {report['avg_chunk_size']} words")
        self.stdout.write("")

        # Coverage by Domain
        self.stdout.write("COVERAGE BY DOMAIN")
        self.stdout.write("-" * 40)

        domains = report['coverage_by_domain']
        if domains:
            for domain, stats in domains.items():
                self.stdout.write(
                    f"  {domain:15} | "
                    f"Docs: {stats['documents']:3} | "
                    f"Chunks: {stats['chunks']:5} | "
                    f"Words: {stats['words']:,}"
                )
        else:
            self.stdout.write("  No domains found")
        self.stdout.write("")

        # Missing Domains
        if report['missing_domains']:
            self.stdout.write(self.style.WARNING("MISSING DOMAINS"))
            self.stdout.write("-" * 40)
            for domain in report['missing_domains']:
                self.stdout.write(f"  - {domain}")
            self.stdout.write("")

        # Outdated Documents
        if report['outdated_documents']:
            self.stdout.write(self.style.WARNING("OUTDATED DOCUMENTS (>30 days)"))
            self.stdout.write("-" * 40)
            for doc in report['outdated_documents'][:10]:
                self.stdout.write(f"  - {doc}")
            if len(report['outdated_documents']) > 10:
                self.stdout.write(f"  ... and {len(report['outdated_documents']) - 10} more")
            self.stdout.write("")

        # Conflicts
        if report['unresolved_conflicts'] > 0:
            self.stdout.write(self.style.ERROR(
                f"UNRESOLVED CONFLICTS: {report['unresolved_conflicts']}"
            ))
            self.stdout.write("-" * 40)

        # Run conflict detection if requested
        if options['detect_conflicts']:
            self._run_conflict_detection()

        # Show index if requested
        if options['index']:
            self._show_index(manager)

        # Show detailed stats if requested
        if options['stats']:
            self._show_stats(manager)

        self.stdout.write("")
        self.stdout.write("=" * 60)

    def _health_bar(self, score: int) -> str:
        """Generate a visual health bar."""
        filled = int(score / 10)
        empty = 10 - filled

        if score >= 80:
            color = self.style.SUCCESS
        elif score >= 50:
            color = self.style.WARNING
        else:
            color = self.style.ERROR

        bar = color("[" + "=" * filled + "-" * empty + f"] {score}/100")
        return bar

    def _run_conflict_detection(self):
        """Run conflict detection and display results."""
        self.stdout.write("\nDETECTING CONFLICTS...")
        self.stdout.write("-" * 40)

        detector = ConflictDetector()
        conflicts = detector.detect_all_conflicts()

        if conflicts:
            self.stdout.write(self.style.WARNING(f"Found {len(conflicts)} conflicts:"))
            for conflict in conflicts[:5]:
                self.stdout.write(
                    f"  [{conflict['type']}] {conflict['term']}: {conflict['description']}"
                )
            if len(conflicts) > 5:
                self.stdout.write(f"  ... and {len(conflicts) - 5} more")
        else:
            self.stdout.write(self.style.SUCCESS("No conflicts detected!"))

    def _show_index(self, manager: ContextManager):
        """Show the knowledge index."""
        self.stdout.write("\nKNOWLEDGE INDEX")
        self.stdout.write("-" * 40)

        index = manager.get_index()

        for domain, data in index['domains'].items():
            self.stdout.write(f"\n  [{domain.upper()}]")
            for doc in data['documents'][:5]:
                self.stdout.write(f"    - {doc['title']} ({doc['chunks']} chunks)")
            if len(data['documents']) > 5:
                self.stdout.write(f"    ... and {len(data['documents']) - 5} more")

    def _show_stats(self, manager: ContextManager):
        """Show detailed statistics."""
        self.stdout.write("\nDETAILED STATISTICS")
        self.stdout.write("-" * 40)

        stats = manager.get_stats()

        self.stdout.write(f"  Documents:")
        self.stdout.write(f"    Total: {stats['documents']['total']}")
        self.stdout.write(f"    Words: {stats['documents']['total_words']:,}")
        self.stdout.write(f"    Characters: {stats['documents']['total_chars']:,}")

        self.stdout.write(f"  Chunks:")
        self.stdout.write(f"    Total: {stats['chunks']['total']}")
        self.stdout.write(f"    Tokens: {stats['chunks']['total_tokens']:,}")

        self.stdout.write(f"  Vector Store:")
        self.stdout.write(f"    Collection: {stats['vector_store']['collection_name']}")
        self.stdout.write(f"    Vectors: {stats['vector_store']['total_chunks']}")

        self.stdout.write(f"  Activity (Last 7 days):")
        self.stdout.write(f"    Ingestions: {stats['activity']['ingestions_7d']}")
        self.stdout.write(f"    Queries: {stats['activity']['queries_7d']}")

    def _output_json(self, manager: ContextManager, options: dict):
        """Output report as JSON."""
        data = {
            'report': manager.get_coverage_report(),
            'stats': manager.get_stats() if options['stats'] else None,
            'index': manager.get_index() if options['index'] else None
        }

        if options['detect_conflicts']:
            detector = ConflictDetector()
            data['conflicts'] = detector.get_unresolved_conflicts()

        self.stdout.write(json.dumps(data, indent=2, default=str))
