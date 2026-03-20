"""
Text processing utilities for the Context System.

Handles text cleaning, normalization, and analysis.
"""

import re
import unicodedata
from typing import List, Tuple


class TextProcessor:
    """
    Utility class for text processing operations.

    Provides methods for cleaning, normalizing, and analyzing text.
    """

    # Common Portuguese stop words
    STOP_WORDS_PT = {
        'a', 'ao', 'aos', 'as', 'com', 'como', 'da', 'das', 'de', 'do', 'dos',
        'e', 'em', 'era', 'essa', 'essas', 'esse', 'esses', 'esta', 'estas',
        'este', 'estes', 'foi', 'for', 'isso', 'isto', 'ja', 'la', 'lhe',
        'mais', 'mas', 'me', 'muito', 'na', 'nas', 'nao', 'nem', 'no', 'nos',
        'o', 'os', 'ou', 'para', 'pela', 'pelas', 'pelo', 'pelos', 'por',
        'qual', 'quando', 'que', 'se', 'sem', 'sera', 'seu', 'seus', 'so',
        'sua', 'suas', 'tambem', 'te', 'tem', 'ter', 'tinha', 'um', 'uma',
        'umas', 'uns', 'voce', 'voces'
    }

    # Common English stop words
    STOP_WORDS_EN = {
        'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from', 'has',
        'he', 'in', 'is', 'it', 'its', 'of', 'on', 'or', 'that', 'the', 'to',
        'was', 'were', 'will', 'with', 'the', 'this', 'but', 'they', 'have',
        'had', 'what', 'when', 'where', 'who', 'which', 'why', 'how'
    }

    # Combined stop words
    STOP_WORDS = STOP_WORDS_PT | STOP_WORDS_EN

    @staticmethod
    def clean_text(text: str) -> str:
        """
        Clean text by removing extra whitespace and normalizing.

        Args:
            text: Raw text to clean

        Returns:
            Cleaned text
        """
        # Normalize unicode characters
        text = unicodedata.normalize('NFKC', text)

        # Replace multiple newlines with double newline
        text = re.sub(r'\n{3,}', '\n\n', text)

        # Replace multiple spaces with single space
        text = re.sub(r' {2,}', ' ', text)

        # Remove leading/trailing whitespace from lines
        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join(lines)

        return text.strip()

    @staticmethod
    def normalize_text(text: str, lowercase: bool = True) -> str:
        """
        Normalize text for comparison and indexing.

        Args:
            text: Text to normalize
            lowercase: Whether to convert to lowercase

        Returns:
            Normalized text
        """
        # Remove diacritics
        text = ''.join(
            c for c in unicodedata.normalize('NFD', text)
            if unicodedata.category(c) != 'Mn'
        )

        if lowercase:
            text = text.lower()

        # Remove punctuation except hyphens in compound words
        text = re.sub(r'[^\w\s-]', ' ', text)

        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)

        return text.strip()

    @staticmethod
    def extract_keywords(
        text: str,
        max_keywords: int = 10,
        min_word_length: int = 3
    ) -> List[str]:
        """
        Extract important keywords from text.

        Args:
            text: Text to analyze
            max_keywords: Maximum number of keywords to return
            min_word_length: Minimum word length to consider

        Returns:
            List of keywords
        """
        # Normalize and tokenize
        normalized = TextProcessor.normalize_text(text)
        words = normalized.split()

        # Filter stop words and short words
        filtered = [
            word for word in words
            if word not in TextProcessor.STOP_WORDS
            and len(word) >= min_word_length
        ]

        # Count frequencies
        freq: dict[str, int] = {}
        for word in filtered:
            freq[word] = freq.get(word, 0) + 1

        # Sort by frequency and return top keywords
        sorted_words = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        return [word for word, _ in sorted_words[:max_keywords]]

    @staticmethod
    def count_words(text: str) -> int:
        """Count words in text."""
        words = text.split()
        return len(words)

    @staticmethod
    def count_tokens_approx(text: str) -> int:
        """
        Approximate token count (roughly 4 chars per token for English).

        For more accurate counts, use tiktoken.
        """
        return len(text) // 4

    @staticmethod
    def extract_code_blocks(text: str) -> List[Tuple[str, str, int, int]]:
        """
        Extract code blocks from markdown text.

        Args:
            text: Markdown text

        Returns:
            List of (language, code, start_line, end_line) tuples
        """
        pattern = r'```(\w*)\n(.*?)```'
        blocks = []

        for match in re.finditer(pattern, text, re.DOTALL):
            language = match.group(1) or 'text'
            code = match.group(2)
            start = text[:match.start()].count('\n') + 1
            end = text[:match.end()].count('\n') + 1
            blocks.append((language, code.strip(), start, end))

        return blocks

    @staticmethod
    def extract_headings(text: str) -> List[Tuple[int, str, int]]:
        """
        Extract markdown headings.

        Args:
            text: Markdown text

        Returns:
            List of (level, heading_text, line_number) tuples
        """
        headings = []
        lines = text.split('\n')

        for i, line in enumerate(lines, 1):
            match = re.match(r'^(#{1,6})\s+(.+)$', line.strip())
            if match:
                level = len(match.group(1))
                heading = match.group(2).strip()
                headings.append((level, heading, i))

        return headings

    @staticmethod
    def extract_links(text: str) -> List[Tuple[str, str]]:
        """
        Extract markdown links.

        Args:
            text: Markdown text

        Returns:
            List of (text, url) tuples
        """
        pattern = r'\[([^\]]+)\]\(([^)]+)\)'
        return re.findall(pattern, text)

    @staticmethod
    def split_into_sentences(text: str) -> List[str]:
        """
        Split text into sentences.

        Args:
            text: Text to split

        Returns:
            List of sentences
        """
        # Simple sentence splitting (handles common cases)
        pattern = r'(?<=[.!?])\s+(?=[A-Z])'
        sentences = re.split(pattern, text)
        return [s.strip() for s in sentences if s.strip()]

    @staticmethod
    def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
        """
        Truncate text to max length, preserving word boundaries.

        Args:
            text: Text to truncate
            max_length: Maximum length
            suffix: Suffix to add if truncated

        Returns:
            Truncated text
        """
        if len(text) <= max_length:
            return text

        truncated = text[:max_length - len(suffix)]

        # Try to break at word boundary
        last_space = truncated.rfind(' ')
        if last_space > max_length // 2:
            truncated = truncated[:last_space]

        return truncated + suffix

    @staticmethod
    def remove_markdown_formatting(text: str) -> str:
        """
        Remove markdown formatting, keeping plain text.

        Args:
            text: Markdown text

        Returns:
            Plain text
        """
        # Remove code blocks
        text = re.sub(r'```[\s\S]*?```', '', text)
        text = re.sub(r'`[^`]+`', '', text)

        # Remove headers markers
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)

        # Remove bold/italic
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
        text = re.sub(r'\*([^*]+)\*', r'\1', text)
        text = re.sub(r'__([^_]+)__', r'\1', text)
        text = re.sub(r'_([^_]+)_', r'\1', text)

        # Remove links, keep text
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)

        # Remove images
        text = re.sub(r'!\[([^\]]*)\]\([^)]+\)', '', text)

        # Remove blockquotes
        text = re.sub(r'^>\s+', '', text, flags=re.MULTILINE)

        # Remove horizontal rules
        text = re.sub(r'^-{3,}$', '', text, flags=re.MULTILINE)
        text = re.sub(r'^\*{3,}$', '', text, flags=re.MULTILINE)

        return TextProcessor.clean_text(text)
