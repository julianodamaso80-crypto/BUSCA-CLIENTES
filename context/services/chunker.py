"""
Semantic Chunking Service.

Splits documents into semantically coherent chunks for embedding.
"""

import hashlib
import uuid
from dataclasses import dataclass, field
from typing import List, Optional

from .parser import ParsedDocument, ParsedBlock
from ..utils.text_processing import TextProcessor


@dataclass
class ChunkConfig:
    """Configuration for chunking."""
    max_chunk_size: int = 1000  # Maximum characters per chunk
    min_chunk_size: int = 100  # Minimum to create a chunk
    overlap_size: int = 150  # Overlap between chunks
    preserve_hierarchy: bool = True  # Maintain heading structure
    include_parent_context: bool = True  # Add parent heading context
    parent_context_chars: int = 200  # Characters from parent
    code_block_as_single: bool = True  # Keep code blocks together
    table_as_single: bool = True  # Keep tables together
    list_group_threshold: int = 5  # Group lists smaller than this


@dataclass
class Chunk:
    """A semantic chunk ready for embedding."""
    id: str
    content: str
    content_hash: str
    chunk_type: str
    chunk_index: int

    # Hierarchy
    section: str = ""
    subsection: str = ""
    hierarchy_path: List[str] = field(default_factory=list)
    heading_level: int = 0

    # Position
    line_start: int = 0
    line_end: int = 0
    char_start: int = 0
    char_end: int = 0

    # Metadata
    topics: List[str] = field(default_factory=list)
    entities: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)

    # Stats
    word_count: int = 0
    token_count_approx: int = 0

    # Context
    parent_context: str = ""


class SemanticChunker:
    """
    Splits documents into semantic chunks.

    Uses a hierarchical approach that respects document structure
    while maintaining chunk size constraints.
    """

    def __init__(self, config: Optional[ChunkConfig] = None):
        self.config = config or ChunkConfig()

    def chunk_document(self, doc: ParsedDocument) -> List[Chunk]:
        """
        Chunk a parsed document.

        Args:
            doc: ParsedDocument from the parser

        Returns:
            List of Chunk objects
        """
        chunks: List[Chunk] = []
        current_hierarchy: List[str] = []
        current_section = ""
        current_subsection = ""
        chunk_index = 0

        # Track content position
        char_offset = 0

        # Process blocks
        i = 0
        while i < len(doc.blocks):
            block = doc.blocks[i]

            # Update hierarchy for headings
            if block.block_type == 'heading':
                self._update_hierarchy(
                    current_hierarchy,
                    block.level,
                    block.content
                )

                if block.level <= 2:
                    current_section = block.content
                    current_subsection = ""
                else:
                    current_subsection = block.content

                # Create heading chunk
                heading_chunk = self._create_chunk(
                    content=block.content,
                    chunk_type='section' if block.level <= 2 else 'subsection',
                    chunk_index=chunk_index,
                    section=current_section,
                    subsection=current_subsection,
                    hierarchy_path=list(current_hierarchy),
                    heading_level=block.level,
                    line_start=block.line_start,
                    line_end=block.line_end,
                    char_start=char_offset,
                    char_end=char_offset + len(block.raw_content)
                )

                # Add parent context if available
                if self.config.include_parent_context and len(current_hierarchy) > 1:
                    heading_chunk.parent_context = " > ".join(current_hierarchy[:-1])

                chunks.append(heading_chunk)
                chunk_index += 1
                char_offset += len(block.raw_content) + 1
                i += 1
                continue

            # Handle code blocks
            if block.block_type == 'code' and self.config.code_block_as_single:
                code_chunk = self._create_chunk(
                    content=f"```{block.language}\n{block.content}\n```",
                    chunk_type='code',
                    chunk_index=chunk_index,
                    section=current_section,
                    subsection=current_subsection,
                    hierarchy_path=list(current_hierarchy),
                    line_start=block.line_start,
                    line_end=block.line_end,
                    char_start=char_offset,
                    char_end=char_offset + len(block.raw_content)
                )
                code_chunk.keywords = [block.language] if block.language else []
                chunks.append(code_chunk)
                chunk_index += 1
                char_offset += len(block.raw_content) + 1
                i += 1
                continue

            # Handle tables
            if block.block_type == 'table' and self.config.table_as_single:
                table_chunk = self._create_chunk(
                    content=block.content,
                    chunk_type='table',
                    chunk_index=chunk_index,
                    section=current_section,
                    subsection=current_subsection,
                    hierarchy_path=list(current_hierarchy),
                    line_start=block.line_start,
                    line_end=block.line_end,
                    char_start=char_offset,
                    char_end=char_offset + len(block.raw_content)
                )
                chunks.append(table_chunk)
                chunk_index += 1
                char_offset += len(block.raw_content) + 1
                i += 1
                continue

            # Handle lists
            if block.block_type == 'list':
                list_items = block.content.count('\n') + 1
                if list_items <= self.config.list_group_threshold:
                    list_chunk = self._create_chunk(
                        content=block.content,
                        chunk_type='list',
                        chunk_index=chunk_index,
                        section=current_section,
                        subsection=current_subsection,
                        hierarchy_path=list(current_hierarchy),
                        line_start=block.line_start,
                        line_end=block.line_end,
                        char_start=char_offset,
                        char_end=char_offset + len(block.raw_content)
                    )
                    chunks.append(list_chunk)
                    chunk_index += 1
                else:
                    # Split large lists
                    list_chunks = self._split_large_content(
                        content=block.content,
                        chunk_type='list',
                        chunk_index=chunk_index,
                        section=current_section,
                        subsection=current_subsection,
                        hierarchy_path=list(current_hierarchy),
                        line_start=block.line_start,
                        line_end=block.line_end,
                        char_offset=char_offset
                    )
                    chunks.extend(list_chunks)
                    chunk_index += len(list_chunks)

                char_offset += len(block.raw_content) + 1
                i += 1
                continue

            # Handle paragraphs and other content
            # Collect consecutive paragraphs/blockquotes
            collected_content = []
            collected_start = block.line_start
            collected_end = block.line_end
            collected_char_start = char_offset

            while i < len(doc.blocks):
                block = doc.blocks[i]
                if block.block_type in ('heading', 'code', 'table'):
                    break

                collected_content.append(block.content)
                collected_end = block.line_end
                char_offset += len(block.raw_content) + 1
                i += 1

                # Check if we've collected enough
                combined = '\n\n'.join(collected_content)
                if len(combined) >= self.config.max_chunk_size:
                    break

            # Create chunk(s) from collected content
            combined_content = '\n\n'.join(collected_content)

            if len(combined_content) <= self.config.max_chunk_size:
                para_chunk = self._create_chunk(
                    content=combined_content,
                    chunk_type='paragraph',
                    chunk_index=chunk_index,
                    section=current_section,
                    subsection=current_subsection,
                    hierarchy_path=list(current_hierarchy),
                    line_start=collected_start,
                    line_end=collected_end,
                    char_start=collected_char_start,
                    char_end=char_offset
                )

                if self.config.include_parent_context and current_hierarchy:
                    para_chunk.parent_context = " > ".join(current_hierarchy)

                chunks.append(para_chunk)
                chunk_index += 1
            else:
                # Split large content
                split_chunks = self._split_large_content(
                    content=combined_content,
                    chunk_type='paragraph',
                    chunk_index=chunk_index,
                    section=current_section,
                    subsection=current_subsection,
                    hierarchy_path=list(current_hierarchy),
                    line_start=collected_start,
                    line_end=collected_end,
                    char_offset=collected_char_start
                )
                chunks.extend(split_chunks)
                chunk_index += len(split_chunks)

        # Add document summary chunk at the beginning
        if chunks:
            summary_content = self._create_summary(doc, chunks[:5])
            summary_chunk = self._create_chunk(
                content=summary_content,
                chunk_type='document_summary',
                chunk_index=0,
                section="",
                subsection="",
                hierarchy_path=[doc.metadata.title or doc.filename],
                line_start=1,
                line_end=min(20, doc.line_count),
                char_start=0,
                char_end=len(summary_content)
            )
            chunks.insert(0, summary_chunk)

            # Reindex
            for idx, chunk in enumerate(chunks):
                chunk.chunk_index = idx

        return chunks

    def _create_chunk(
        self,
        content: str,
        chunk_type: str,
        chunk_index: int,
        section: str,
        subsection: str,
        hierarchy_path: List[str],
        line_start: int,
        line_end: int,
        char_start: int,
        char_end: int,
        heading_level: int = 0
    ) -> Chunk:
        """Create a chunk with all metadata."""
        chunk_id = str(uuid.uuid4())
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

        # Extract metadata
        keywords = TextProcessor.extract_keywords(content, max_keywords=5)
        word_count = TextProcessor.count_words(content)
        token_count = TextProcessor.count_tokens_approx(content)

        return Chunk(
            id=chunk_id,
            content=content,
            content_hash=content_hash,
            chunk_type=chunk_type,
            chunk_index=chunk_index,
            section=section,
            subsection=subsection,
            hierarchy_path=hierarchy_path,
            heading_level=heading_level,
            line_start=line_start,
            line_end=line_end,
            char_start=char_start,
            char_end=char_end,
            keywords=keywords,
            word_count=word_count,
            token_count_approx=token_count
        )

    def _update_hierarchy(
        self,
        hierarchy: List[str],
        level: int,
        title: str
    ) -> None:
        """Update the heading hierarchy."""
        # Remove headings at same or lower level
        while len(hierarchy) >= level:
            hierarchy.pop()
        hierarchy.append(title)

    def _split_large_content(
        self,
        content: str,
        chunk_type: str,
        chunk_index: int,
        section: str,
        subsection: str,
        hierarchy_path: List[str],
        line_start: int,
        line_end: int,
        char_offset: int
    ) -> List[Chunk]:
        """Split large content into smaller chunks with overlap."""
        chunks = []
        max_size = self.config.max_chunk_size
        overlap = self.config.overlap_size

        # Split by paragraphs first
        paragraphs = content.split('\n\n')
        current_chunk_content = []
        current_size = 0

        for para in paragraphs:
            para_size = len(para)

            if current_size + para_size > max_size and current_chunk_content:
                # Create chunk from current content
                chunk_content = '\n\n'.join(current_chunk_content)
                chunk = self._create_chunk(
                    content=chunk_content,
                    chunk_type=chunk_type,
                    chunk_index=chunk_index + len(chunks),
                    section=section,
                    subsection=subsection,
                    hierarchy_path=hierarchy_path,
                    line_start=line_start,
                    line_end=line_end,
                    char_start=char_offset,
                    char_end=char_offset + len(chunk_content)
                )
                chunks.append(chunk)
                char_offset += len(chunk_content)

                # Keep overlap
                overlap_paras = []
                overlap_size = 0
                for p in reversed(current_chunk_content):
                    if overlap_size + len(p) <= overlap:
                        overlap_paras.insert(0, p)
                        overlap_size += len(p)
                    else:
                        break

                current_chunk_content = overlap_paras
                current_size = overlap_size

            current_chunk_content.append(para)
            current_size += para_size

        # Don't forget the last chunk
        if current_chunk_content:
            chunk_content = '\n\n'.join(current_chunk_content)
            if len(chunk_content) >= self.config.min_chunk_size:
                chunk = self._create_chunk(
                    content=chunk_content,
                    chunk_type=chunk_type,
                    chunk_index=chunk_index + len(chunks),
                    section=section,
                    subsection=subsection,
                    hierarchy_path=hierarchy_path,
                    line_start=line_start,
                    line_end=line_end,
                    char_start=char_offset,
                    char_end=char_offset + len(chunk_content)
                )
                chunks.append(chunk)

        return chunks

    def _create_summary(self, doc: ParsedDocument, first_chunks: List[Chunk]) -> str:
        """Create a document summary chunk."""
        parts = []

        # Title
        if doc.metadata.title:
            parts.append(f"# {doc.metadata.title}")

        # Description
        if doc.metadata.description:
            parts.append(doc.metadata.description)

        # Domain
        if doc.metadata.domain:
            parts.append(f"Domain: {doc.metadata.domain}")

        # Tags
        if doc.metadata.tags:
            parts.append(f"Tags: {', '.join(doc.metadata.tags)}")

        # First section titles
        section_titles = [
            c.section for c in first_chunks
            if c.section and c.chunk_type in ('section', 'subsection')
        ]
        if section_titles:
            unique_sections = list(dict.fromkeys(section_titles))[:5]
            parts.append(f"Sections: {', '.join(unique_sections)}")

        return '\n\n'.join(parts)
