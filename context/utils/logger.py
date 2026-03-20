"""
Structured logging for the Context System.

Provides rich, formatted logging with context tracking.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table


class ContextLogger:
    """
    Logger for the context processing pipeline.

    Provides structured logging with rich formatting and
    automatic log file management.
    """

    def __init__(
        self,
        name: str = "context",
        log_dir: Path | None = None,
        console_level: int = logging.INFO,
        file_level: int = logging.DEBUG
    ):
        self.name = name
        self.console = Console()
        self.log_dir = log_dir or Path("context_logs")
        self.log_dir.mkdir(exist_ok=True)

        # Create logger
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers = []  # Clear existing handlers

        # Console handler with rich formatting
        console_handler = RichHandler(
            console=self.console,
            show_time=True,
            show_path=False,
            rich_tracebacks=True
        )
        console_handler.setLevel(console_level)
        self.logger.addHandler(console_handler)

        # File handler
        log_file = self.log_dir / f"{name}_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(file_level)
        file_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)

    def info(self, message: str, **kwargs: Any) -> None:
        """Log info message."""
        extra = self._format_extra(kwargs)
        self.logger.info(f"{message}{extra}")

    def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message."""
        extra = self._format_extra(kwargs)
        self.logger.debug(f"{message}{extra}")

    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message."""
        extra = self._format_extra(kwargs)
        self.logger.warning(f"{message}{extra}")

    def error(self, message: str, **kwargs: Any) -> None:
        """Log error message."""
        extra = self._format_extra(kwargs)
        self.logger.error(f"{message}{extra}")

    def exception(self, message: str, **kwargs: Any) -> None:
        """Log exception with traceback."""
        extra = self._format_extra(kwargs)
        self.logger.exception(f"{message}{extra}")

    def _format_extra(self, kwargs: dict[str, Any]) -> str:
        """Format extra context for logging."""
        if not kwargs:
            return ""
        parts = [f"{k}={v}" for k, v in kwargs.items()]
        return f" | {' | '.join(parts)}"

    # === Pipeline-specific logging methods ===

    def log_ingestion_start(self, path: str) -> None:
        """Log start of document ingestion."""
        self.info(f"[bold blue]INGESTION START[/]", path=path)

    def log_ingestion_complete(
        self,
        path: str,
        chunks: int,
        time_ms: int
    ) -> None:
        """Log completion of document ingestion."""
        self.info(
            f"[bold green]INGESTION COMPLETE[/]",
            path=path,
            chunks=chunks,
            time_ms=time_ms
        )

    def log_ingestion_error(self, path: str, error: str) -> None:
        """Log ingestion error."""
        self.error(f"[bold red]INGESTION FAILED[/]", path=path, error=error)

    def log_chunk_created(
        self,
        chunk_id: str,
        chunk_type: str,
        tokens: int
    ) -> None:
        """Log chunk creation."""
        self.debug(
            "Chunk created",
            chunk_id=chunk_id[:8],
            type=chunk_type,
            tokens=tokens
        )

    def log_embedding_generated(
        self,
        chunk_id: str,
        model: str,
        time_ms: int
    ) -> None:
        """Log embedding generation."""
        self.debug(
            "Embedding generated",
            chunk_id=chunk_id[:8],
            model=model,
            time_ms=time_ms
        )

    def log_search_query(
        self,
        query: str,
        results: int,
        time_ms: int
    ) -> None:
        """Log search query."""
        self.info(
            "Search query",
            query=query[:50] + "..." if len(query) > 50 else query,
            results=results,
            time_ms=time_ms
        )

    def log_conflict_detected(
        self,
        term: str,
        conflict_type: str,
        source_a: str,
        source_b: str
    ) -> None:
        """Log conflict detection."""
        self.warning(
            f"[yellow]CONFLICT DETECTED[/]",
            term=term,
            type=conflict_type,
            source_a=source_a,
            source_b=source_b
        )

    # === Rich console output ===

    def print_stats_table(self, stats: dict[str, Any]) -> None:
        """Print a formatted stats table."""
        table = Table(title="Context Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        for key, value in stats.items():
            table.add_row(key, str(value))

        self.console.print(table)

    def print_panel(self, title: str, content: str, style: str = "blue") -> None:
        """Print a formatted panel."""
        self.console.print(Panel(content, title=title, border_style=style))

    def print_success(self, message: str) -> None:
        """Print success message."""
        self.console.print(f"[bold green]SUCCESS[/] {message}")

    def print_error(self, message: str) -> None:
        """Print error message."""
        self.console.print(f"[bold red]ERROR[/] {message}")


# Global logger instance
_logger: ContextLogger | None = None


def get_logger() -> ContextLogger:
    """Get or create the global context logger."""
    global _logger
    if _logger is None:
        _logger = ContextLogger()
    return _logger
