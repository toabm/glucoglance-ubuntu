"""Exceptions raised by the LibreLinkUp client.

`LibreLinkUpClient.get_latest_reading()` only ever raises one of these three
types - it never lets a raw `requests` exception, `KeyError`, or JSON parsing
error escape - so callers (the poller) can handle failures uniformly without
knowing anything about the client's internals.
"""


class LibreLinkUpError(Exception):
    """Base class for all errors raised by the LibreLinkUp client."""


class AuthError(LibreLinkUpError):
    """Login failed: bad credentials, or the API rejected/expired our session."""


class NetworkError(LibreLinkUpError):
    """A network-level failure (timeout, DNS, connection refused, HTTP 5xx, ...)."""


class StaleDataError(LibreLinkUpError):
    """The request succeeded, but there's no usable reading.

    Raised when the follower account has no connections, or the latest
    reading's timestamp is too old - both indicate the sensor wearer's phone
    has stopped relaying data to LibreLinkUp, not a problem with our request.
    """
