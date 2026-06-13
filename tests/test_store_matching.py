from app.domain.store_matching import MatchType, StoreLocation, match_stores


def store(
    store_id: str,
    latitude: float | None,
    longitude: float | None,
    radius: int | None = 100,
    status: str = "Aktif",
) -> StoreLocation:
    return StoreLocation(
        store_id=store_id,
        department_store="Sogo",
        branch=store_id,
        city="Jakarta",
        brand="VIVI ZUBEDI",
        latitude=latitude,
        longitude=longitude,
        allowed_radius_meter=radius,
        status=status,
    )


def test_match_single_store_in_radius() -> None:
    result = match_stores(-6.272245364, 106.8422682, [store("A", -6.272245364, 106.8422682)])

    assert result.match_type == MatchType.SINGLE
    assert [candidate.store.store_id for candidate in result.candidates] == ["A"]


def test_match_multiple_stores_in_radius_for_identical_coordinates() -> None:
    stores = [
        store("A", -6.272245364, 106.8422682, 500),
        store("B", -6.272245364, 106.8422682, 500),
    ]

    result = match_stores(-6.272245364, 106.8422682, stores)

    assert result.match_type == MatchType.MULTIPLE
    assert [candidate.store.store_id for candidate in result.candidates] == ["A", "B"]


def test_match_none_returns_all_active_candidates_sorted_by_distance() -> None:
    stores = [
        store("far", 0, 2, 100),
        store("near", 0, 1, 100),
    ]

    result = match_stores(0, 0, stores)

    assert result.match_type == MatchType.NONE
    assert [candidate.store.store_id for candidate in result.candidates] == ["near", "far"]


def test_default_radius_applies_when_radius_is_null_or_non_positive() -> None:
    null_radius = match_stores(0, 0, [store("A", 0, 0.0005, None)], default_radius_meter=100)
    zero_radius = match_stores(0, 0, [store("A", 0, 0.0005, 0)], default_radius_meter=100)

    assert null_radius.match_type == MatchType.SINGLE
    assert zero_radius.match_type == MatchType.SINGLE


def test_inactive_and_invalid_coordinate_stores_are_ignored() -> None:
    stores = [
        store("inactive", 0, 0, status="Nonaktif"),
        store("missing", None, None),
    ]

    result = match_stores(0, 0, stores)

    assert result.match_type == MatchType.NONE
    assert result.candidates == []
