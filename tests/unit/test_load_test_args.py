"""06.11: load_test.py — разбор командной строки (адрес и уровни) и перцентиль."""
from load_test import DEFAULT_BASE_URL, DEFAULT_LEVELS, parse_args, percentile


def test_no_args_means_production_and_default_levels():
    assert parse_args([]) == (DEFAULT_BASE_URL, DEFAULT_LEVELS)


def test_url_and_levels_from_args():
    assert parse_args(["https://example.com/", "5", "10"]) == ("https://example.com", [5, 10])


def test_only_levels_keeps_production_url():
    assert parse_args(["1", "10"]) == (DEFAULT_BASE_URL, [1, 10])


def test_percentile_picks_from_sorted_values():
    values = [5.0, 1.0, 3.0, 2.0, 4.0]
    assert percentile(values, 0.50) == 3.0
    assert percentile(values, 0.95) == 5.0