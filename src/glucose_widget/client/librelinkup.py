"""Client for the unofficial LibreLinkUp API.

LibreLinkUp is Abbott's "follower" service: the sensor wearer's phone app
uploads readings to it, and a follower account (the one this client logs in
as) can poll it for the latest reading. There is no official public API or
documentation for this - the request/response shapes here are based on
community-documented behavior of the LibreLinkUp mobile app and may drift if
Abbott changes their backend. If this client starts failing, the response
shapes below are the first thing to re-check against a real request.

Everything the rest of the app needs is exposed through one method:
`get_latest_reading()`. It always returns a fully-formed GlucoseReading or
raises one of the errors in `client.errors` - callers never see raw HTTP or
JSON errors.
"""

import hashlib
from datetime import datetime, timedelta
from typing import Any

import requests

from glucose_widget.client.errors import AuthError, NetworkError, StaleDataError
from glucose_widget.domain.reading import GlucoseReading
from glucose_widget.domain.trend import TrendArrow

# Default entry point; a login response can redirect us to a region-specific
# host instead (e.g. api-eu.libreview.io), which we then remember.
DEFAULT_BASE_HOST = "api.libreview.io"

# LibreLinkUp's backend rejects requests that don't look like they came from
# the official mobile app, and version-gates the API: too low a version
# here gets a 403 with {"status": 920, "data": {"minimumVersion": "X"}}
# (confirmed live - 4.12.0 was rejected demanding 4.16.0). Bump this if that
# starts happening again.
_REQUEST_HEADERS = {
    "Content-Type": "application/json",
    "product": "llu.android",
    "version": "4.16.0",
}

# A reading older than this is treated as stale: the wearer's phone has
# likely stopped relaying data to LibreLinkUp.
_STALE_AFTER = timedelta(minutes=20)

# The token LibreLinkUp issues is short-lived; refresh a little before it
# actually expires rather than racing the clock.
_TOKEN_REFRESH_MARGIN = timedelta(minutes=1)


class LibreLinkUpClient:
    """Fetches the latest glucose reading for a single LibreLinkUp follower account."""

    def __init__(self, email: str, password: str, *, base_host: str | None = None):
        """Create a client. `base_host` can be a previously-cached region host
        (see `_login`) to skip the redirect round trip; if omitted, the
        default host is tried first."""
        self._email = email
        self._password = password
        self._base_host = base_host or DEFAULT_BASE_HOST
        self._session = requests.Session()
        self._token: str | None = None
        self._token_expires_at: datetime | None = None
        self._account_id_header: str | None = None

    @property
    def base_host(self) -> str:
        """The (possibly region-redirected) host currently in use, for callers
        that want to cache it in config and pass it back in next time."""
        return self._base_host

    def get_latest_reading(self) -> GlucoseReading:
        """Fetch the wearer's most recent glucose reading.

        Raises AuthError, NetworkError, or StaleDataError - never returns
        None and never lets a lower-level exception escape.
        """
        self._ensure_authenticated()
        connections = self._get_connections()
        return _parse_connections_response(connections)

    def _ensure_authenticated(self) -> None:
        """Log in if we don't yet have a token, or it's about to expire."""
        if self._token and self._token_expires_at:
            if datetime.now() < self._token_expires_at - _TOKEN_REFRESH_MARGIN:
                return
        self._login()

    def _login(self) -> None:
        """POST credentials to /llu/auth/login, following a region redirect once."""
        response_data = self._post_login(self._base_host)

        if response_data.get("redirect"):
            region = response_data.get("region")
            if not region:
                raise AuthError("LibreLinkUp requested a redirect but gave no region")
            self._base_host = f"api-{region}.libreview.io"
            response_data = self._post_login(self._base_host)

        try:
            ticket = response_data["authTicket"]
            self._token = ticket["token"]
            self._token_expires_at = datetime.fromtimestamp(ticket["expires"])
            # Abbott's backend requires this header on later calls; it's the
            # SHA-256 hex digest of the account's user id.
            user_id = response_data["user"]["id"]
            self._account_id_header = hashlib.sha256(user_id.encode("utf-8")).hexdigest()
        except (KeyError, TypeError) as exc:
            raise AuthError(f"Unexpected login response shape: {exc}") from exc

    def _post_login(self, host: str) -> dict[str, Any]:
        """Send the login request to the given host and return its `data` field."""
        try:
            resp = self._session.post(
                f"https://{host}/llu/auth/login",
                json={"email": self._email, "password": self._password},
                headers=_REQUEST_HEADERS,
                timeout=10,
            )
        except requests.RequestException as exc:
            raise NetworkError(f"Login request failed: {exc}") from exc

        body = _parse_json(resp, NetworkError)
        if resp.status_code == 401 or body.get("status") not in (0, None):
            raise AuthError(f"Login rejected: {_response_error_detail(resp, body)}")
        if resp.status_code != 200:
            detail = _response_error_detail(resp, body)
            raise NetworkError(f"Login returned unexpected HTTP {detail}")

        return body.get("data", {})

    def _get_connections(self) -> dict[str, Any]:
        """GET /llu/connections, which includes each connected patient's latest reading."""
        headers = dict(_REQUEST_HEADERS, Authorization=f"Bearer {self._token}")
        if self._account_id_header:
            headers["Account-Id"] = self._account_id_header

        try:
            resp = self._session.get(
                f"https://{self._base_host}/llu/connections",
                headers=headers,
                timeout=10,
            )
        except requests.RequestException as exc:
            raise NetworkError(f"Connections request failed: {exc}") from exc

        if resp.status_code == 401:
            # Token was rejected outright (e.g. revoked server-side); force a
            # fresh login on the next call rather than retrying here.
            self._token = None
            raise AuthError("Connections request was unauthorized")

        body = _parse_json(resp, NetworkError)
        if resp.status_code != 200:
            detail = _response_error_detail(resp, body)
            raise NetworkError(f"Connections returned unexpected HTTP {detail}")

        return body


def _response_error_detail(resp: requests.Response, body: dict[str, Any]) -> str:
    """Build a short diagnostic string for a non-2xx response: the status
    code plus whatever error info the body offers, so failures are
    debuggable from logs instead of just "HTTP 403" with no context."""
    return f"{resp.status_code} (body={body!r})"


def _parse_json(resp: requests.Response, on_error: type[Exception]) -> dict[str, Any]:
    """Decode a response body as JSON, wrapping decode failures in `on_error`."""
    try:
        return resp.json()
    except ValueError as exc:
        raise on_error(f"Response was not valid JSON: {exc}") from exc


def _parse_connections_response(body: dict[str, Any]) -> GlucoseReading:
    """Turn a /llu/connections response body into a GlucoseReading for the
    first connected patient (phase 1 assumes a single sensor wearer)."""
    connections = body.get("data") or []
    if not connections:
        raise StaleDataError("Follower account has no active connections")

    measurement = connections[0].get("glucoseMeasurement")
    if not measurement:
        raise StaleDataError("Connection has no glucose measurement yet")

    try:
        value_mgdl = int(measurement["Value"])
        timestamp = _parse_api_timestamp(measurement["Timestamp"])
        is_high = bool(measurement.get("isHigh", False))
        is_low = bool(measurement.get("isLow", False))
        trend = TrendArrow.from_api_value(measurement.get("TrendArrow"))
    except (KeyError, ValueError, TypeError) as exc:
        raise StaleDataError(f"Malformed glucose measurement: {exc}") from exc

    if datetime.now() - timestamp > _STALE_AFTER:
        raise StaleDataError(f"Latest reading is older than {_STALE_AFTER}")

    return GlucoseReading(
        value_mgdl=value_mgdl,
        trend=trend,
        timestamp=timestamp,
        is_high=is_high,
        is_low=is_low,
    )


def _parse_api_timestamp(raw: str) -> datetime:
    """Parse the API's timestamp format, e.g. '9/16/2026 3:04:12 PM'.

    The API does not include timezone info, so this is naive local time -
    consistent with `datetime.now()` as long as both run in the same
    timezone, which is fine for our staleness check.
    """
    return datetime.strptime(raw, "%m/%d/%Y %I:%M:%S %p")
