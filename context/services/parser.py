"""
Markdown Parser Service.

Parses markdown documents into structured format for processing.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

from markdown_it import MarkdownIt

from ..utils.text_processing import TextProcessor
from ..utils.metadata_extractor import MetadataExtractor, DocumentMetadata, SectionMetadata


@dataclass
class ParsedBlock:
    """A parsed block from the markdown document."""
    block_type: str  # 'heading', 'paragraph', 'code', 'list', 'table', 'blockquote'
    content: str
    raw_content: str
    level: int = 0  # For headings
    language: str = ""  # For code blocks
    line_start: int = 0
    line_end: int = 0
    metadata: dict = field(default_factory=dict)


@dataclass
class ParsedDocument:
    """A fully parsed markdown document."""
    path: str
    filename: str
    content: str
    metadata: DocumentMetadata
    blocks: List[ParsedBlock]
    sections: List[SectionMetadata]
    word_count: int
    char_count: int
    line_count: int


class MarkdownParser:
    """
    Parses markdown documents into structured format.

    Uses markdown-it for parsing and extracts:
    - Document metadata (frontmatter, title, etc.)
    - Hierarchical sections
    - Content blocks (paragraphs, code, lists, etc.)
    """

    def __init__(self):
        self.md = MarkdownIt('commonmark')

    def parse_file(self, file_path: Path) -> ParsedDocument:
        """
        Parse a markdown file.

        Args:
            file_path: Path to the markdown file

        Returns:
            ParsedDocument with all extracted information
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        return self.parse_content(content, file_path)

    def parse_content(
        self,
        content: str,
        file_path: Optional[Path] = None
    ) -> ParsedDocument:
        """
        Parse markdown content.

        Args:
            content: Raw markdown content
            file_path: Optional file path for context

        Returns:
            ParsedDocument with all extracted information
        """
        # Clean content
        clean_content = self._strip_frontmatter(content)

        # Extract metadata
        metadata = MetadataExtractor.extract_from_content(content, file_path)

        # Extract sections
        sections = MetadataExtractor.extract_sections(clean_content)

        # Parse blocks
        blocks = self._parse_blocks(clean_content)

        # Calculate stats
        word_count = TextProcessor.count_words(clean_content)
        char_count = len(clean_content)
        line_count = clean_content.count('\n') + 1

        return ParsedDocument(
            path=str(file_path) if file_path else "",
            filename=file_path.name if file_path else "",
            content=clean_content,
            metadata=metadata,
            blocks=blocks,
            sections=sections,
            word_count=word_count,
            char_count=char_count,
            line_count=line_count
        )

    def _strip_frontmatter(self, content: str) -> str:
        """Remove YAML frontmatter from content."""
        if content.startswith('---'):
            match = re.match(r'^---\n[\s\S]*?\n---\n', content)
            if match:
                return content[match.end():]
        return content

    def _parse_blocks(self, content: str) -> List[ParsedBlock]:
        """
        Parse content into blocks.

        Args:
            content: Markdown content without frontmatter

        Returns:
            List of ParsedBlock objects
        """
        blocks: List[ParsedBlock] = []
        lines = content.split('\n')
        current_line = 0

        i = 0
        while i < len(lines):
            line = lines[i]

            # Skip empty lines
            if not line.strip():
                i += 1
                current_line += 1
                continue

            # Check for heading
            heading_match = re.match(r'^(#{1,6})\s+(.+)$', line)
            if heading_match:
                level = len(heading_match.group(1))
                text = heading_match.group(2).strip()
                blocks.append(ParsedBlock(
                    block_type='heading',
                    content=text,
                    raw_content=line,
                    level=level,
                    line_start=current_line + 1,
                    line_end=current_line + 1
                ))
                i += 1
                current_line += 1
                continue

            # Check for code block
            if line.startswith('```'):
                code_block, end_i = self._parse_code_block(lines, i)
                if code_block:
                    code_block.line_start = current_line + 1
                    code_block.line_end = current_line + (end_i - i) + 1
                    blocks.append(code_block)
                    current_line += end_i - i + 1
                    i = end_i + 1
                    continue

            # Check for blockquote
            if line.startswith('>'):
                quote_block, end_i = self._parse_blockquote(lines, i)
                quote_block.line_start = current_line + 1
                quote_block.line_end = current_line + (end_i - i)
                blocks.append(quote_block)
                current_line += end_i - i
                i = end_i
                continue

            # Check for list
            if re.match(r'^[\s]*[-*+]\s|^[\s]*\d+\.\s', line):
                list_block, end_i = self._parse_list(lines, i)
                list_block.line_start = current_line + 1
                list_block.line_end = current_line + (end_i - i)
                blocks.append(list_block)
                current_line += end_i - i
                i = end_i
                continue

            # Check for table
            if '|' in line and i + 1 < len(lines) and re.match(r'^[\s]*\|?[\s]*[-:]+', lines[i + 1]):
                table_block, end_i = self._parse_table(lines, i)
                table_block.line_start = current_line + 1
                table_block.line_end = current_line + (end_i - i)
                blocks.append(table_block)
                current_line += end_i - i
                i = end_i
                continue

            # Default: paragraph
            para_block, end_i = self._parse_paragraph(lines, i)
            para_block.line_start = current_line + 1
            para_block.line_end = current_line + (end_i - i)
            blocks.append(para_block)
            current_line += end_i - i
            i = end_i

        return blocks

    def _parse_code_block(
        self,
        lines: List[str],
        start: int
    ) -> Tuple[Optional[ParsedBlock], int]:
        """Parse a fenced code block."""
        first_line = lines[start]
        lang_match = re.match(r'^```(\w*)$', first_line)
        language = lang_match.group(1) if lang_match else ""

        code_lines = []
        i = start + 1

        while i < len(lines):
            if lines[i].startswith('```'):
                break
            code_lines.append(lines[i])
            i += 1

        content = '\n'.join(code_lines)
        raw_content = '\n'.join(lines[start:i + 1])

        return ParsedBlock(
            block_type='code',
            content=content,
            raw_content=raw_content,
            language=language
        ), i

    def _parse_blockquote(
        self,
        lines: List[str],
        start: int
    ) -> Tuple[ParsedBlock, int]:
        """Parse a blockquote."""
        quote_lines = []
        i = start

        while i < len(lines) and lines[i].startswith('>'):
            # Remove the '>' prefix
            quote_lines.append(re.sub(r'^>\s?', '', lines[i]))
            i += 1

        content = '\n'.join(quote_lines)
        raw_content = '\n'.join(lines[start:i])

        return ParsedBlock(
            block_type='blockquote',
            content=content,
            raw_content=raw_content
        ), i

    def _parse_list(
        self,
        lines: List[str],
        start: int
    ) -> Tuple[ParsedBlock, int]:
        """Parse a list (ordered or unordered)."""
        list_lines = []
        i = start

        while i < len(lines):
            line = lines[i]
            # Check if line is part of list
            if re.match(r'^[\s]*[-*+]\s|^[\s]*\d+\.\s', line) or \
               (line.startswith('  ') and list_lines):
                list_lines.append(line)
                i += 1
            elif not line.strip():
                # Empty line might continue list if next is list item
                if i + 1 < len(lines) and re.match(r'^[\s]*[-*+]\s|^[\s]*\d+\.\s', lines[i + 1]):
                    list_lines.append(line)
                    i += 1
                else:
                    break
            else:
                break

        content = '\n'.join(list_lines)
        raw_content = content

        return ParsedBlock(
            block_type='list',
            content=content,
            raw_content=raw_content
        ), i

    def _parse_table(
        self,
        lines: List[str],
        start: int
    ) -> Tuple[ParsedBlock, int]:
        """Parse a markdown table."""
        table_lines = []
        i = start

        while i < len(lines):
            line = lines[i]
            if '|' in line or re.match(r'^[\s]*[-:]+[\s]*$', line):
                table_lines.append(line)
                i += 1
            else:
                break

        content = '\n'.join(table_lines)
        raw_content = content

        return ParsedBlock(
            block_type='table',
            content=content,
            raw_content=raw_content
        ), i

    def _parse_paragraph(
        self,
        lines: List[str],
        start: int
    ) -> Tuple[ParsedBlock, int]:
        """Parse a paragraph."""
        para_lines = []
        i = start

        while i < len(lines):
            line = lines[i]
            # Stop at empty line or special block
            if not line.strip():
                break
            if line.startswith('#') or line.startswith('```') or \
               line.startswith('>') or line.startswith('|') or \
               re.match(r'^[\s]*[-*+]\s|^[\s]*\d+\.\s', line):
                break

            para_lines.append(line)
            i += 1

        content = ' '.join(para_lines)
        raw_content = '\n'.join(para_lines)

        return ParsedBlock(
            block_type='paragraph',
            content=content,
            raw_content=raw_content
        ), i
