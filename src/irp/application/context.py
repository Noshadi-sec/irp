"""What a workflow needs from its caller: who is acting, and swappable I/O for tests."""

from __future__ import annotations

from dataclasses import dataclass, field

from irp.providers.intake.arxiv import Fetcher, HttpFetcher


@dataclass(frozen=True)
class OperationContext:
    actor: str  # "cli" or "mcp"; recorded on every evidence record
    fetcher: Fetcher = field(default_factory=HttpFetcher)
