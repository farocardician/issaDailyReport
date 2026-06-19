from app.domain.brands import Brand, brand_options, filter_by_brand
from app.domain.store_matching import StoreLocation


def test_brand_options_orders_by_active_brand_meta_and_falls_back_last() -> None:
    stores = [
        _store("S1", "Unknown"),
        _store("S2", "Mayyech"),
        _store("S3", "VIVI ZUBEDI"),
        _store("S4", "VIVI ZUBEDI"),
    ]
    brands = [
        Brand("VZ", "VIVI ZUBEDI", "VZ", 1, "Aktif"),
        Brand("MYC", "Mayyech", "MYC", 2, "Aktif"),
    ]

    options = brand_options(stores, brands)

    assert [(option.brand_id, option.label, option.short_code, option.count) for option in options] == [
        ("VZ", "VIVI ZUBEDI", "VZ", 2),
        ("MYC", "Mayyech", "MYC", 1),
        ("Unknown", "Unknown", "Unknown", 1),
    ]


def test_filter_by_brand_keeps_only_matching_store_label() -> None:
    stores = [
        _store("S1", "VIVI ZUBEDI"),
        _store("S2", "Mayyech"),
    ]

    assert [store.store_id for store in filter_by_brand(stores, "Mayyech")] == ["S2"]


def _store(store_id: str, brand: str) -> StoreLocation:
    return StoreLocation(
        store_id=store_id,
        outlet="Sogo",
        branch=store_id,
        city="Jakarta",
        brand=brand,
        latitude=-6.2,
        longitude=106.8,
        allowed_radius_meter=100,
        status="Aktif",
    )
