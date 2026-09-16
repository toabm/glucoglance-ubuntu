"""Tests for the LibreLinkUp client: response parsing and the login/redirect
flow, all against fixture JSON and mocked HTTP - no real network calls.
"""

import json
from datetime import datetime
from pathlib import Path

import pytest
import responses

from glucose_widget.client.errors import StaleDataError
from glucose_widget.client.librelinkup import LibreLinkUpClient, _parse_connections_response
from glucose_widget.domain.trend import TrendArrow

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    """Load a fixture JSON file, substituting the __NOW__ placeholder (if
    present) with the current time in the API's timestamp format, so
    "fresh reading" fixtures don't go stale as time passes."""
    raw = (FIXTURES_DIR / name).read_text()
    now_text = datetime.now().strftime("%m/%d/%Y %I:%M:%S %p")
    raw = raw.replace("__NOW__", now_text)
    return json.loads(raw)


def test_parses_a_fresh_reading():
    reading = _parse_connections_response(load_fixture("connections_response.json"))
    assert reading.value_mgdl == 118
    assert reading.trend is TrendArrow.STABLE
    assert reading.is_high is False
    assert reading.is_low is False


def test_empty_connections_raises_stale_data_error():
    with pytest.raises(StaleDataError):
        _parse_connections_response(load_fixture("connections_empty.json"))


def test_old_timestamp_raises_stale_data_error():
    with pytest.raises(StaleDataError):
        _parse_connections_response(load_fixture("connections_stale.json"))


def test_missing_value_field_raises_stale_data_error():
    with pytest.raises(StaleDataError):
        _parse_connections_response(load_fixture("connections_malformed.json"))


@responses.activate
def test_login_follows_region_redirect_then_fetches_reading():
    """Simulates: default host redirects us to the EU host, then the EU
    host accepts login and returns a real connections response."""
    responses.add(
        responses.POST,
        "https://api.libreview.io/llu/auth/login",
        json=load_fixture("login_region_redirect.json"),
        status=200,
    )
    responses.add(
        responses.POST,
        "https://api-eu.libreview.io/llu/auth/login",
        json=load_fixture("login_success.json"),
        status=200,
    )
    responses.add(
        responses.GET,
        "https://api-eu.libreview.io/llu/connections",
        json=load_fixture("connections_response.json"),
        status=200,
    )

    client = LibreLinkUpClient(email="user@example.com", password="secret")
    reading = client.get_latest_reading()

    assert reading.value_mgdl == 118
    assert client.base_host == "api-eu.libreview.io"
