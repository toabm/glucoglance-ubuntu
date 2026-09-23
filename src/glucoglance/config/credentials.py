"""LibreLinkUp password storage via the system keyring (GNOME Keyring on Ubuntu).

The account email is treated as a non-secret identifier and lives in
`config.settings`; only the password goes through here.
"""

import keyring

_SERVICE_NAME = "glucoglance"


def get_password(email: str) -> str | None:
    """Return the stored password for `email`, or None if none is stored."""
    return keyring.get_password(_SERVICE_NAME, email)


def set_password(email: str, password: str) -> None:
    """Store `password` for `email` in the system keyring."""
    keyring.set_password(_SERVICE_NAME, email, password)


def delete_password(email: str) -> None:
    """Remove the stored password for `email`, if any (used by "Log out")."""
    try:
        keyring.delete_password(_SERVICE_NAME, email)
    except keyring.errors.PasswordDeleteError:
        pass  # nothing was stored for this email - already effectively logged out
