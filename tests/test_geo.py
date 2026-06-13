from app.domain.geo import haversine_meters


def test_haversine_same_point_is_zero() -> None:
    assert haversine_meters(-6.272245364, 106.8422682, -6.272245364, 106.8422682) == 0


def test_haversine_one_degree_longitude_at_equator() -> None:
    assert haversine_meters(0, 0, 0, 1) == pytest_approx_meter(111_195)


def pytest_approx_meter(value: float):
    from pytest import approx

    return approx(value, rel=0.001)
