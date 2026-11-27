import pytest

from graph import parse_depth


def test_parse_depth_default():
    assert parse_depth(None) == 3


def test_parse_depth_bounds():
    assert parse_depth("1") == 1
    assert parse_depth("10") == 10
    for bad in ("0", "11", "abc", "-1", "3.5"):
        with pytest.raises(ValueError):
            parse_depth(bad)