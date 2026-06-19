import asyncio

from app.repositories.regions import RegionsRepository


def test_regions_repository_lists_active_provinces_in_query_order() -> None:
    pool = _FakePool(
        provinces=[{"province": "DKI Jakarta"}, {"province": "Jawa Barat"}],
        cities=[],
    )
    repository = RegionsRepository(pool)

    result = asyncio.run(repository.list_provinces("Aktif"))

    assert result == ["DKI Jakarta", "Jawa Barat"]
    assert pool.calls[0]["args"] == ("Aktif",)
    assert "SELECT DISTINCT province" in pool.calls[0]["query"]
    assert "ORDER BY province" in pool.calls[0]["query"]


def test_regions_repository_lists_active_cities_for_province_in_query_order() -> None:
    pool = _FakePool(
        provinces=[],
        cities=[{"city": "Kota Bandung"}, {"city": "Kota Bogor"}],
    )
    repository = RegionsRepository(pool)

    result = asyncio.run(repository.list_cities("Jawa Barat", "Aktif"))

    assert result == ["Kota Bandung", "Kota Bogor"]
    assert pool.calls[0]["args"] == ("Jawa Barat", "Aktif")
    assert "WHERE province = $1" in pool.calls[0]["query"]
    assert "ORDER BY city" in pool.calls[0]["query"]


class _FakePool:
    def __init__(self, provinces: list[dict[str, str]], cities: list[dict[str, str]]) -> None:
        self.provinces = provinces
        self.cities = cities
        self.calls: list[dict[str, object]] = []

    async def fetch(self, query: str, *args: object) -> list[dict[str, str]]:
        self.calls.append({"query": query, "args": args})
        if "SELECT DISTINCT province" in query:
            return self.provinces
        return self.cities
