from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from app.domain.store_matching import StoreCandidate, StoreLocation


@dataclass(frozen=True)
class Brand:
    brand_id: str
    label: str
    short_code: str
    sort_order: int
    status: str


@dataclass(frozen=True)
class BrandOption:
    brand_id: str
    label: str
    short_code: str
    count: int


def brand_options(
    stores: Iterable[StoreLocation | StoreCandidate],
    brands_meta: Sequence[Brand],
) -> list[BrandOption]:
    store_labels = Counter(_store(item).brand for item in stores)
    meta_by_label = {brand.label: brand for brand in brands_meta}

    # Brands link to stores by exact label: stores.brand must match brands.label.
    # Unknown store labels remain selectable as raw labels and sort after known brands.
    options = [
        BrandOption(
            brand_id=meta_by_label[label].brand_id if label in meta_by_label else label,
            label=label,
            short_code=meta_by_label[label].short_code if label in meta_by_label else label,
            count=count,
        )
        for label, count in store_labels.items()
    ]
    options.sort(key=lambda option: _brand_sort_key(option, meta_by_label))
    return options


def filter_by_brand(
    stores: Iterable[StoreLocation | StoreCandidate],
    label: str,
) -> list[StoreLocation | StoreCandidate]:
    return [item for item in stores if _store(item).brand == label]


def _brand_sort_key(option: BrandOption, meta_by_label: dict[str, Brand]) -> tuple[int, int, str]:
    meta = meta_by_label.get(option.label)
    if meta is None:
        return (1, 0, option.label)
    return (0, meta.sort_order, meta.label)


def _store(item: StoreLocation | StoreCandidate) -> StoreLocation:
    if isinstance(item, StoreCandidate):
        return item.store
    return item
