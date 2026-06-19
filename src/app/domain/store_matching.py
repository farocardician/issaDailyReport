from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable

from app.domain.geo import haversine_meters

DEFAULT_RADIUS_METER = 100
ACTIVE_STATUS = "Aktif"


class MatchType(StrEnum):
    SINGLE = "SINGLE"
    MULTIPLE = "MULTIPLE"
    NONE = "NONE"


@dataclass(frozen=True)
class StoreLocation:
    store_id: str
    outlet: str
    branch: str
    city: str
    brand: str
    latitude: float | None
    longitude: float | None
    allowed_radius_meter: int | None
    status: str
    notes: str | None = None
    province: str | None = None
    brand_short: str | None = None
    outlet_short: str | None = None
    city_short: str | None = None


@dataclass(frozen=True)
class StoreCandidate:
    store: StoreLocation
    distance_meter: float
    effective_radius_meter: int
    in_range: bool


@dataclass(frozen=True)
class StoreMatch:
    match_type: MatchType
    candidates: list[StoreCandidate]


def match_stores(
    lat: float,
    lon: float,
    active_stores: Iterable[StoreLocation],
    default_radius_meter: int = DEFAULT_RADIUS_METER,
    active_status: str = ACTIVE_STATUS,
) -> StoreMatch:
    candidates: list[StoreCandidate] = []

    for store in active_stores:
        if store.status != active_status or store.latitude is None or store.longitude is None:
            continue

        effective_radius = store.allowed_radius_meter or default_radius_meter
        if effective_radius <= 0:
            effective_radius = default_radius_meter

        distance = haversine_meters(lat, lon, store.latitude, store.longitude)
        candidates.append(
            StoreCandidate(
                store=store,
                distance_meter=distance,
                effective_radius_meter=effective_radius,
                in_range=distance <= effective_radius,
            )
        )

    candidates.sort(key=lambda candidate: candidate.distance_meter)
    in_range = [candidate for candidate in candidates if candidate.in_range]

    if len(in_range) == 1:
        return StoreMatch(MatchType.SINGLE, in_range)
    if len(in_range) > 1:
        return StoreMatch(MatchType.MULTIPLE, in_range)
    return StoreMatch(MatchType.NONE, candidates)
