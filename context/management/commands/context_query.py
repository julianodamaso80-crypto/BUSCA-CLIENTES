"""
Django management command to query the context system.

Usage:
    python manage.py context_query "Como funciona o disparo de WhatsApp?"
    python manage.py context_query "limites anti-bloqueio" --top 10
    python manage.py context_query "API endpoints" --domain technical
"""

import json

from django.core.management.base import BaseCommand

from context.managers import ContextManager
from context.services import AgentInterface


class Command(BaseCommand):
    help = 'Query the context system'

    def add_arguments(self, parser):
        parser.add_argument(
            'query',
            type=str,
            help='Search query'
        )
        parser.add_argument(
            '--top',
            type=int,
            default=5,
            help='Number of results (default: 5)'
        )
        parser.add_argument(
            '--domain',
            type=str,
            default=None,
            help='Filter by domain'
        )
        parser.add_argument(
            '--type',
            type=str,
            default=None,
            help='Filter by chunk type'
        )
        parser.add_argument(
            '--json',
            action='store_true',
            help='Output as JSON'
        )
        parser.add_argument(
            '--context-only',
            action='store_true',
            help='Only show assembled context'
        )
        parser.add_argument(
            '--agent-prompt',
            action='store_true',
            help='Generate full agent prompt'
        )

    def handle(self, *args, **options):
        query = options['query']
        top_k = options['top']

        # Build filters
        filters = {}
        if options['domain']:
            filters['domain'] = options['domain']
        if options['type']:
            filters['chunk_type'] = options['type']

        manager = ContextManager()

        # Agent prompt mode
        if options['agent_prompt']:
            self._output_agent_prompt(query, top_k)
            return

        # Run search
        result = manager.search(query, top_k=top_k, filters=filters if filters else None)

        # JSON output
        if options['json']:
            self.stdout.write(json.dumps(result, indent=2, default=str))
            return

        # Context only mode
        if options['context_only']:
            self.stdout.write(result['context'])
            return

        # Normal output
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(f"  Query: {query}")
        self.stdout.write(f"  Results: {len(result['results'])} | Time: {result['search_time_ms']}ms")
        self.stdout.write("=" * 60 + "\n")

        if not result['results']:
            self.stdout.write(self.style.WARNING("No results found."))
            self.stdout.write("\nSuggestions:")
            self.stdout.write("  - Try broader search terms")
            self.stdout.write("  - Check if documents are indexed: python manage.py sync_context")
            return

        for i, r in enumerate(result['results'], 1):
            self.stdout.write(f"\n[{i}] Score: {r['score']:.2%}")
            self.stdout.write(f"    Source: {r['source']}")
            self.stdout.write(f"    Section: {r['section']}")
            self.stdout.write(f"    Lines: {r['lines']}")
            self.stdout.write("-" * 40)

            # Truncate content for display
            content = r['content']
            if len(content) > 500:
                content = content[:500] + "..."
            self.stdout.write(f"    {content}")
            self.stdout.write("")

        self.stdout.write("\n" + "-" * 60)
        self.stdout.write(f"Total tokens in context: {result['total_tokens']}")

    def _output_agent_prompt(self, query: str, top_k: int):
        """Generate and output a full agent prompt."""
        agent = AgentInterface()
        prompt, sources = agent.build_prompt(query, max_chunks=top_k)

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("  AGENT PROMPT")
        self.stdout.write("=" * 60 + "\n")

        self.stdout.write(prompt)

        self.stdout.write("\n" + "-" * 60)
        self.stdout.write(f"Sources: {len(sources)}")
        for s in sources:
            self.stdout.write(f"  [{s.id}] {s.file} ({s.section})")
