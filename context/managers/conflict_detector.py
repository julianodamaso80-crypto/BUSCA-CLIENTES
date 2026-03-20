"""
Conflict Detector.

Detects conflicts and inconsistencies between documents.
"""

import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from django.utils import timezone

from ..services.query_engine import QueryEngine
from ..utils.text_processing import TextProcessor
from ..utils.logger import get_logger


class ConflictDetector:
    """
    Detects conflicts between documents in the context.

    Identifies:
    - Conflicting definitions
    - Contradictory values
    - Terminology mismatches
    - Outdated information
    """

    # Patterns that indicate definitions
    DEFINITION_PATTERNS = [
        r'(?:e|eh|sao|significa|define-se como|consiste em)\s+["\']?([^"\'\.]+)["\']?',
        r'([^:]+):\s*(?:e|eh|significa|consiste)',
        r'(?:definicao|conceito)(?:\s+de)?\s+([^:]+):',
    ]

    # Patterns that indicate values/rules
    VALUE_PATTERNS = [
        r'(\d+)\s*(?:mensagens?|msg|dias?|horas?|minutos?|segundos?)',
        r'(?:limite|maximo|minimo)\s*(?:de|:)?\s*(\d+)',
        r'(\d+(?:,\d+)?)\s*(?:reais|R\$|\$|%)',
    ]

    def __init__(self, query_engine: Optional[QueryEngine] = None):
        """Initialize the conflict detector."""
        self.logger = get_logger()
        self.query_engine = query_engine or QueryEngine()

    def detect_all_conflicts(self) -> List[Dict[str, Any]]:
        """
        Run all conflict detection methods.

        Returns:
            List of detected conflicts
        """
        conflicts = []

        # Detect definition conflicts
        definition_conflicts = self.detect_definition_conflicts()
        conflicts.extend(definition_conflicts)

        # Detect value conflicts
        value_conflicts = self.detect_value_conflicts()
        conflicts.extend(value_conflicts)

        # Detect terminology mismatches
        terminology_conflicts = self.detect_terminology_mismatches()
        conflicts.extend(terminology_conflicts)

        # Save conflicts to database
        for conflict in conflicts:
            self._save_conflict(conflict)

        self.logger.info(f"Detected {len(conflicts)} conflicts")

        return conflicts

    def detect_definition_conflicts(self) -> List[Dict[str, Any]]:
        """
        Detect conflicting definitions of the same term.

        Returns:
            List of definition conflicts
        """
        from ..models import Chunk

        conflicts = []
        definitions: Dict[str, List[Tuple[str, str, str]]] = defaultdict(list)

        # Extract definitions from all chunks
        chunks = Chunk.objects.all()

        for chunk in chunks:
            extracted = self._extract_definitions(chunk.content)

            for term, definition in extracted:
                normalized_term = TextProcessor.normalize_text(term)
                if len(normalized_term) > 2:
                    definitions[normalized_term].append((
                        term,
                        definition,
                        str(chunk.id)
                    ))

        # Find terms with multiple different definitions
        for normalized_term, defs in definitions.items():
            if len(defs) < 2:
                continue

            # Check if definitions are actually different
            unique_defs = {}
            for term, definition, chunk_id in defs:
                def_normalized = TextProcessor.normalize_text(definition)
                if def_normalized not in unique_defs:
                    unique_defs[def_normalized] = (term, definition, chunk_id)

            if len(unique_defs) > 1:
                # We have conflicting definitions
                items = list(unique_defs.values())
                for i in range(len(items)):
                    for j in range(i + 1, len(items)):
                        conflicts.append({
                            'type': 'definition',
                            'term': items[i][0],
                            'severity': 'high',
                            'source_a': {
                                'chunk_id': items[i][2],
                                'snippet': items[i][1]
                            },
                            'source_b': {
                                'chunk_id': items[j][2],
                                'snippet': items[j][1]
                            },
                            'description': f"Definicoes conflitantes para '{items[i][0]}'"
                        })

        return conflicts

    def detect_value_conflicts(self) -> List[Dict[str, Any]]:
        """
        Detect conflicting values (numbers, limits, etc.).

        Returns:
            List of value conflicts
        """
        from ..models import Chunk

        conflicts = []
        values: Dict[str, List[Tuple[str, str, str]]] = defaultdict(list)

        chunks = Chunk.objects.all()

        for chunk in chunks:
            extracted = self._extract_values(chunk.content)

            for context, value in extracted:
                context_normalized = TextProcessor.normalize_text(context)
                # Create a key from the context (what the value refers to)
                context_key = context_normalized[:50]
                values[context_key].append((
                    value,
                    chunk.content[:200],
                    str(chunk.id)
                ))

        # Find contexts with different values
        for context_key, vals in values.items():
            if len(vals) < 2:
                continue

            # Check for different values
            unique_values = {}
            for value, snippet, chunk_id in vals:
                if value not in unique_values:
                    unique_values[value] = (snippet, chunk_id)

            if len(unique_values) > 1:
                items = list(unique_values.items())
                for i in range(len(items)):
                    for j in range(i + 1, len(items)):
                        val_a, (snip_a, chunk_a) = items[i]
                        val_b, (snip_b, chunk_b) = items[j]

                        conflicts.append({
                            'type': 'value',
                            'term': context_key,
                            'severity': 'medium',
                            'source_a': {
                                'chunk_id': chunk_a,
                                'snippet': f"Valor: {val_a} - {snip_a[:100]}"
                            },
                            'source_b': {
                                'chunk_id': chunk_b,
                                'snippet': f"Valor: {val_b} - {snip_b[:100]}"
                            },
                            'description': f"Valores diferentes: {val_a} vs {val_b}"
                        })

        return conflicts

    def detect_terminology_mismatches(self) -> List[Dict[str, Any]]:
        """
        Detect terminology inconsistencies (same concept, different names).

        Returns:
            List of terminology conflicts
        """
        from ..models import DomainTerm

        conflicts = []

        # Get all terms
        terms = DomainTerm.objects.all()

        # Group by normalized form
        normalized_groups: Dict[str, List[DomainTerm]] = defaultdict(list)

        for term in terms:
            normalized_groups[term.normalized_term].append(term)

        # Check for similar terms (Levenshtein distance)
        term_list = list(terms)

        for i, term_a in enumerate(term_list):
            for term_b in term_list[i + 1:]:
                # Skip if same normalized form
                if term_a.normalized_term == term_b.normalized_term:
                    continue

                # Check similarity
                similarity = self._calculate_similarity(
                    term_a.normalized_term,
                    term_b.normalized_term
                )

                if similarity > 0.8:  # Very similar but different
                    conflicts.append({
                        'type': 'terminology',
                        'term': f"{term_a.term} / {term_b.term}",
                        'severity': 'low',
                        'source_a': {
                            'term_id': str(term_a.id),
                            'snippet': term_a.definition or term_a.term
                        },
                        'source_b': {
                            'term_id': str(term_b.id),
                            'snippet': term_b.definition or term_b.term
                        },
                        'description': f"Termos similares podem referir ao mesmo conceito (similaridade: {similarity:.0%})"
                    })

        return conflicts

    def check_document_consistency(self, doc_path: str) -> List[Dict[str, Any]]:
        """
        Check a specific document for internal consistency.

        Args:
            doc_path: Path to the document

        Returns:
            List of issues found
        """
        from ..models import Document, Chunk

        issues = []

        try:
            doc = Document.objects.get(path=doc_path)
        except Document.DoesNotExist:
            return [{'error': 'Document not found'}]

        chunks = Chunk.objects.filter(document=doc).order_by('chunk_index')

        # Check for internal value conflicts
        values_in_doc: Dict[str, List[str]] = defaultdict(list)

        for chunk in chunks:
            extracted = self._extract_values(chunk.content)
            for context, value in extracted:
                context_key = TextProcessor.normalize_text(context)[:30]
                values_in_doc[context_key].append(value)

        for context, vals in values_in_doc.items():
            unique_vals = set(vals)
            if len(unique_vals) > 1:
                issues.append({
                    'type': 'internal_value_conflict',
                    'context': context,
                    'values': list(unique_vals),
                    'severity': 'medium'
                })

        # Check for broken internal references
        # (e.g., "see section X" where X doesn't exist)
        all_sections = set()
        references = []

        for chunk in chunks:
            if chunk.section:
                all_sections.add(chunk.section.lower())
            if chunk.subsection:
                all_sections.add(chunk.subsection.lower())

            # Find references
            ref_patterns = [
                r'(?:veja|ver|confira|consulte)\s+(?:a\s+)?secao\s+["\']?([^"\'\.]+)["\']?',
                r'(?:descrito|explicado)\s+(?:na\s+)?secao\s+["\']?([^"\'\.]+)["\']?',
            ]

            for pattern in ref_patterns:
                matches = re.findall(pattern, chunk.content, re.IGNORECASE)
                references.extend(matches)

        for ref in references:
            ref_normalized = ref.lower().strip()
            if ref_normalized and ref_normalized not in all_sections:
                issues.append({
                    'type': 'broken_reference',
                    'reference': ref,
                    'severity': 'low'
                })

        return issues

    def _extract_definitions(self, text: str) -> List[Tuple[str, str]]:
        """Extract term-definition pairs from text."""
        definitions = []

        for pattern in self.DEFINITION_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    term = match[0].strip()
                    definition = match[1].strip() if len(match) > 1 else ""
                else:
                    term = match.strip()
                    definition = ""

                if term and len(term) > 2:
                    # Get surrounding context as definition
                    idx = text.lower().find(term.lower())
                    if idx >= 0:
                        definition = text[idx:idx + 200]

                    definitions.append((term, definition))

        return definitions

    def _extract_values(self, text: str) -> List[Tuple[str, str]]:
        """Extract context-value pairs from text."""
        values = []

        for pattern in self.VALUE_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                value = match.group(1)

                # Get context (text before the match)
                start = max(0, match.start() - 50)
                context = text[start:match.start()].strip()

                # Clean up context
                context = re.sub(r'^\W+', '', context)
                context = context.split('\n')[-1]  # Get last line

                if context and value:
                    values.append((context, value))

        return values

    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """Calculate similarity between two strings (Jaccard)."""
        set1 = set(str1.lower())
        set2 = set(str2.lower())

        intersection = len(set1 & set2)
        union = len(set1 | set2)

        if union == 0:
            return 0

        return intersection / union

    def _save_conflict(self, conflict: Dict[str, Any]) -> None:
        """Save a conflict to the database."""
        from ..models import Chunk, ConflictLog

        try:
            source_a_id = conflict['source_a'].get('chunk_id')
            source_b_id = conflict['source_b'].get('chunk_id')

            if not source_a_id or not source_b_id:
                return

            chunk_a = Chunk.objects.get(id=source_a_id)
            chunk_b = Chunk.objects.get(id=source_b_id)

            # Check if conflict already exists
            existing = ConflictLog.objects.filter(
                term=conflict['term'],
                source_a=chunk_a,
                source_b=chunk_b,
                resolved=False
            ).exists()

            if existing:
                return

            ConflictLog.objects.create(
                term=conflict['term'],
                conflict_type=conflict['type'],
                severity=conflict.get('severity', 'medium'),
                description=conflict['description'],
                source_a=chunk_a,
                source_b=chunk_b,
                snippet_a=conflict['source_a']['snippet'][:500],
                snippet_b=conflict['source_b']['snippet'][:500]
            )

            self.logger.log_conflict_detected(
                term=conflict['term'],
                conflict_type=conflict['type'],
                source_a=source_a_id,
                source_b=source_b_id
            )

        except Chunk.DoesNotExist:
            pass  # Chunk might have been deleted

    def resolve_conflict(
        self,
        conflict_id: str,
        resolution_note: str,
        user=None
    ) -> bool:
        """
        Mark a conflict as resolved.

        Args:
            conflict_id: ID of the conflict
            resolution_note: Explanation of resolution
            user: User resolving the conflict

        Returns:
            True if resolved
        """
        from ..models import ConflictLog

        try:
            conflict = ConflictLog.objects.get(id=conflict_id)
            conflict.resolved = True
            conflict.resolution_note = resolution_note
            conflict.resolved_at = timezone.now()
            conflict.resolved_by = user
            conflict.save()

            self.logger.info(f"Conflict resolved", conflict_id=conflict_id)
            return True

        except ConflictLog.DoesNotExist:
            return False

    def get_unresolved_conflicts(self) -> List[Dict[str, Any]]:
        """Get all unresolved conflicts."""
        from ..models import ConflictLog

        conflicts = ConflictLog.objects.filter(resolved=False).order_by('-detected_at')

        return [
            {
                'id': str(c.id),
                'term': c.term,
                'type': c.conflict_type,
                'severity': c.severity,
                'description': c.description,
                'source_a': c.snippet_a,
                'source_b': c.snippet_b,
                'detected_at': c.detected_at.isoformat()
            }
            for c in conflicts
        ]
