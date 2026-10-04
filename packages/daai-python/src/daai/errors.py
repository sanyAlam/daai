from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class DaaiError(Exception):
    message: str
    status_code: int | None = None
    body: Any | None = None

    def __str__(self) -> str:
        if self.status_code is None:
            return self.message
        return f"{self.status_code}: {self.message}"


class DaaiUnauthorizedError(DaaiError):
    """401 errors."""


class DaaiNotFoundError(DaaiError):
    """404 errors."""


class DaaiConflictError(DaaiError):
    """409 errors."""


class DaaiValidationError(DaaiError):
    """422 errors."""


class DaaiApiError(DaaiError):
    """Other non-success API responses."""
