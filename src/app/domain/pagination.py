from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import ceil
from typing import TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class Page:
    items: list[T]
    page: int
    total_pages: int
    has_prev: bool
    has_next: bool


def paginate(items: Sequence[T], page: int, page_size: int) -> Page:
    if page_size <= 0:
        raise ValueError("page_size must be greater than zero")

    total_pages = max(1, ceil(len(items) / page_size))
    clamped_page = min(max(page, 0), total_pages - 1)
    start = clamped_page * page_size
    end = start + page_size
    return Page(
        items=list(items[start:end]),
        page=clamped_page,
        total_pages=total_pages,
        has_prev=clamped_page > 0,
        has_next=clamped_page < total_pages - 1,
    )
