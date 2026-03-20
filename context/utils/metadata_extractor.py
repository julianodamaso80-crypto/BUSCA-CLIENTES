"""
Metadata extraction utilities for the Context System.

Extracts structured metadata from markdown documents.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional

import frontmatter

from .text_processing import TextProcessor


@dataclass
class DocumentMetadata:
    """Structured metadata for a document."""
    title: str = ""
    description: str = ""
    domain: str = "other"
    authors: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    created_date: Optional[datetime] = None
    modified_date: Optional[datetime] = None
    version: str = ""
    status: str = ""
    custom: dict[str, Any] = field(default_factory=dict)


@dataclass
class SectionMetadata:
    """Metadata for a document section."""
    level: int
    title: str
    line_start: int
    line_end: int
    content: str
    subsections: List['SectionMetadata'] = field(default_factory=list)


class MetadataExtractor:
    """
    Extracts metadata from markdown documents.

    Handles frontmatter, headings, and content-based extraction.
    """

    # Domain detection keywords
    DOMAIN_KEYWORDS = {
        'business': ['pricing', 'planos', 'regras', 'politica', 'policy', 'termos', 'business'],
        'technical': ['api', 'endpoint', 'database', 'schema', 'migration', 'deploy', 'config'],
        'features': ['feature', 'funcionalidade', 'recurso', 'botao', 'tela', 'interface'],
        'flows': ['fluxo', 'flow', 'jornada', 'journey', 'processo', 'etapa', 'step'],
        'integrations': ['integracao', 'integration', 'api', 'webhook', 'oauth', 'external'],
        'architecture': ['arquitetura', 'architecture', 'sistema', 'system', 'design', 'pattern'],
        'glossary': ['glossario', 'glossary', 'termo', 'definicao', 'definition'],
    }

    @staticmethod
    def extract_from_file(file_path: Path) -> DocumentMetadata:
        """
        Extract metadata from a markdown file.

        Args:
            file_path: Path to the markdown file

        Returns:
            DocumentMetadata object
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        return MetadataExtractor.extract_from_content(content, file_path)

    @staticmethod
    def extract_from_content(
        content: str,
        file_path: Optional[Path] = None
    ) -> DocumentMetadata:
        """
        Extract metadata from markdown content.

        Args:
            content: Markdown content
            file_path: Optional file path for context

        Returns:
            DocumentMetadata object
        """
        metadata = DocumentMetadata()

        # Try to parse frontmatter
        try:
            post = frontmatter.loads(content)
            fm = post.metadata

            metadata.title = fm.get('title', '')
            metadata.description = fm.get('description', '')
            metadata.authors = fm.get('authors', fm.get('author', []))
            if isinstance(metadata.authors, str):
                metadata.authors = [metadata.authors]
            metadata.tags = fm.get('tags', [])
            metadata.version = str(fm.get('version', ''))
            metadata.status = fm.get('status', '')
            metadata.domain = fm.get('domain', '')

            # Parse dates
            if 'created' in fm:
                metadata.created_date = MetadataExtractor._parse_date(fm['created'])
            if 'modified' in fm or 'updated' in fm:
                date_str = fm.get('modified', fm.get('updated'))
                metadata.modified_date = MetadataExtractor._parse_date(date_str)

            # Store any extra custom fields
            known_fields = {
                'title', 'description', 'authors', 'author', 'tags',
                'version', 'status', 'domain', 'created', 'modified', 'updated'
            }
            metadata.custom = {k: v for k, v in fm.items() if k not in known_fields}

            content = post.content  # Content without frontmatter

        except Exception:
            pass  # No frontmatter or parsing error

        # Extract title from first H1 if not in frontmatter
        if not metadata.title:
            metadata.title = MetadataExtractor._extract_title(content)

        # Extract description from first paragraph if not in frontmatter
        if not metadata.description:
            metadata.description = MetadataExtractor._extract_description(content)

        # Detect domain if not specified
        if not metadata.domain or metadata.domain == 'other':
            metadata.domain = MetadataExtractor._detect_domain(content, file_path)

        # Extract tags from content if none specified
        if not metadata.tags:
            metadata.tags = MetadataExtractor._extract_tags(content)

        return metadata

    @staticmethod
    def extract_sections(content: str) -> List[SectionMetadata]:
        """
        Extract section hierarchy from markdown content.

        Args:
            content: Markdown content

        Returns:
            List of top-level sections with nested subsections
        """
        lines = content.split('\n')
        headings = TextProcessor.extract_headings(content)

        if not headings:
            return []

        sections: List[SectionMetadata] = []
        section_stack: List[SectionMetadata] = []

        for i, (level, title, line_num) in enumerate(headings):
            # Find end of section (next heading of same or higher level, or end)
            line_end = len(lines)
            for next_level, _, next_line in headings[i + 1:]:
                if next_level <= level:
                    line_end = next_line - 1
                    break

            # Extract section content
            section_lines = lines[line_num:line_end]
            content = '\n'.join(section_lines).strip()

            section = SectionMetadata(
                level=level,
                title=title,
                line_start=line_num,
                line_end=line_end,
                content=content
            )

            # Place in hierarchy
            while section_stack and section_stack[-1].level >= level:
                section_stack.pop()

            if section_stack:
                section_stack[-1].subsections.append(section)
            else:
                sections.append(section)

            section_stack.append(section)

        return sections

    @staticmethod
    def extract_entities(content: str) -> List[str]:
        """
        Extract named entities from content.

        Args:
            content: Text content

        Returns:
            List of identified entities
        """
        entities = set()

        # Extract capitalized terms (potential proper nouns)
        pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b'
        matches = re.findall(pattern, content)
        entities.update(matches)

        # Extract quoted terms
        quoted_pattern = r'"([^"]+)"|\'([^\']+)\''
        for match in re.finditer(quoted_pattern, content):
            term = match.group(1) or match.group(2)
            if term and len(term) > 2:
                entities.add(term)

        # Extract backtick terms (likely technical terms)
        code_pattern = r'`([^`]+)`'
        for match in re.finditer(code_pattern, content):
            term = match.group(1)
            if term and len(term) > 2 and ' ' not in term:
                entities.add(term)

        return list(entities)

    @staticmethod
    def extract_topics(content: str, max_topics: int = 5) -> List[str]:
        """
        Extract main topics from content.

        Args:
            content: Text content
            max_topics: Maximum number of topics to return

        Returns:
            List of identified topics
        """
        # Use keywords as topics
        keywords = TextProcessor.extract_keywords(content, max_keywords=max_topics * 2)

        # Also consider heading text as topics
        headings = TextProcessor.extract_headings(content)
        heading_keywords = []
        for _, title, _ in headings:
            words = TextProcessor.extract_keywords(title, max_keywords=2)
            heading_keywords.extend(words)

        # Combine and deduplicate
        all_topics = keywords + heading_keywords
        seen = set()
        unique_topics = []
        for topic in all_topics:
            if topic.lower() not in seen:
                seen.add(topic.lower())
                unique_topics.append(topic)

        return unique_topics[:max_topics]

    @staticmethod
    def _extract_title(content: str) -> str:
        """Extract title from first H1 heading."""
        match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if match:
            return match.group(1).strip()
        return ""

    @staticmethod
    def _extract_description(content: str) -> str:
        """Extract description from first paragraph."""
        # Remove frontmatter and headings
        clean = re.sub(r'^---[\s\S]*?---\n', '', content)
        clean = re.sub(r'^#.*$', '', clean, flags=re.MULTILINE)

        # Get first non-empty paragraph
        paragraphs = clean.strip().split('\n\n')
        for para in paragraphs:
            para = para.strip()
            if para and not para.startswith(('-', '*', '1.', '>')):
                return TextProcessor.truncate_text(para, 300)

        return ""

    @staticmethod
    def _detect_domain(content: str, file_path: Optional[Path] = None) -> str:
        """Detect document domain from content and path."""
        content_lower = content.lower()
        path_str = str(file_path).lower() if file_path else ""

        scores: dict[str, int] = {domain: 0 for domain in MetadataExtractor.DOMAIN_KEYWORDS}

        # Check path for domain hints
        for domain, keywords in MetadataExtractor.DOMAIN_KEYWORDS.items():
            for keyword in keywords:
                if keyword in path_str:
                    scores[domain] += 5  # Path matches are strong signals

        # Check content for domain keywords
        for domain, keywords in MetadataExtractor.DOMAIN_KEYWORDS.items():
            for keyword in keywords:
                count = content_lower.count(keyword)
                scores[domain] += count

        # Return domain with highest score
        best_domain = max(scores.items(), key=lambda x: x[1])
        if best_domain[1] > 0:
            return best_domain[0]

        return "other"

    @staticmethod
    def _extract_tags(content: str) -> List[str]:
        """Extract tags from content based on structure and keywords."""
        tags = []

        # Check for common tag indicators
        tag_pattern = r'(?:tags?|labels?|categories?|keywords?):\s*\[?([^\]\n]+)\]?'
        match = re.search(tag_pattern, content, re.IGNORECASE)
        if match:
            tag_str = match.group(1)
            tags = [t.strip().strip(',') for t in tag_str.split(',')]

        # If no explicit tags, use top keywords
        if not tags:
            tags = TextProcessor.extract_keywords(content, max_keywords=5)

        return tags

    @staticmethod
    def _parse_date(date_val: Any) -> Optional[datetime]:
        """Parse date from various formats."""
        if isinstance(date_val, datetime):
            return date_val

        if isinstance(date_val, str):
            formats = [
                '%Y-%m-%d',
                '%Y/%m/%d',
                '%d/%m/%Y',
                '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%dT%H:%M:%S',
            ]
            for fmt in formats:
                try:
                    return datetime.strptime(date_val, fmt)
                except ValueError:
                    continue

        return None
