import pytest

from app.domain.pagination import paginate


def test_paginate_empty_list() -> None:
    page = paginate([], 0, 6)

    assert page.items == []
    assert page.page == 0
    assert page.total_pages == 1
    assert page.has_prev is False
    assert page.has_next is False


def test_paginate_single_page() -> None:
    page = paginate([1, 2, 3], 0, 6)

    assert page.items == [1, 2, 3]
    assert page.total_pages == 1
    assert page.has_prev is False
    assert page.has_next is False


def test_paginate_last_page() -> None:
    page = paginate(list(range(13)), 2, 6)

    assert page.items == [12]
    assert page.page == 2
    assert page.total_pages == 3
    assert page.has_prev is True
    assert page.has_next is False


def test_paginate_clamps_out_of_range_page() -> None:
    low = paginate(list(range(8)), -2, 6)
    high = paginate(list(range(8)), 20, 6)

    assert low.page == 0
    assert low.items == [0, 1, 2, 3, 4, 5]
    assert high.page == 1
    assert high.items == [6, 7]


def test_paginate_exact_multiple_of_six() -> None:
    page = paginate(list(range(12)), 1, 6)

    assert page.items == [6, 7, 8, 9, 10, 11]
    assert page.total_pages == 2


def test_paginate_rejects_non_positive_page_size() -> None:
    with pytest.raises(ValueError):
        paginate([1], 0, 0)
