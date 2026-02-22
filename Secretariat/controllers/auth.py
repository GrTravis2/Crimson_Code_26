"""Google OAuth flow for Calendar access."""

from __future__ import annotations

import functools
import json
import os
import pathlib
from typing import Callable
from urllib.parse import urlparse

import flask
from flask.typing import ResponseReturnValue
from google_auth_oauthlib.flow import Flow

AUTH = flask.Blueprint(
    name="auth",
    import_name=__name__,
    url_prefix="/",
)

SCOPES = [
    "https://www.googleapis.com/auth/drive.metadata.readonly",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly",
]
CLIENT_SECRETS_FILE = pathlib.Path("credentials_web.json")
# Local Flask development uses ``http://127.0.0.1`` callback URLs.
os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")


def _default_redirect_target() -> str:
    """Return the default post-login destination."""
    return flask.url_for("home")


def _safe_redirect_target(raw_target: str | None) -> str:
    """Allow only same-site path redirects to avoid open redirects."""
    if not raw_target:
        return _default_redirect_target()

    parsed = urlparse(raw_target)
    if parsed.scheme or parsed.netloc or not raw_target.startswith("/"):
        return _default_redirect_target()

    return raw_target


def _env_redirect_uri() -> str | None:
    """Return explicit callback URI when configured."""
    raw_uri = os.environ.get("GOOGLE_OAUTH_REDIRECT_URI")
    if not raw_uri:
        return None
    return raw_uri.strip() or None


def _client_redirect_uris() -> list[str]:
    """Load redirect URIs from OAuth client secrets file."""
    try:
        raw_data = CLIENT_SECRETS_FILE.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []

    try:
        payload = json.loads(raw_data)
    except json.JSONDecodeError:
        return []

    web_config = payload.get("web")
    if not isinstance(web_config, dict):
        return []

    redirect_values = web_config.get("redirect_uris")
    if not isinstance(redirect_values, list):
        return []

    return [value for value in redirect_values if isinstance(value, str)]


def _oauth_redirect_uri() -> str:
    """Resolve callback URI for Google OAuth."""
    if (explicit_uri := _env_redirect_uri()) is not None:
        return explicit_uri

    generated_uri = flask.url_for("auth.oauth2callback", _external=True)
    if generated_uri in _client_redirect_uris():
        return generated_uri

    configured_uris = _client_redirect_uris()
    if configured_uris:
        return configured_uris[0]

    return generated_uri


def _credential_string(credentials: object, field_name: str) -> str | None:
    """Safely read an optional string field from credentials."""
    raw_value = getattr(credentials, field_name, None)
    return raw_value if isinstance(raw_value, str) else None


def _credential_scopes(credentials: object) -> list[str]:
    """Safely read scope list from credentials."""
    raw_scopes = getattr(credentials, "scopes", None)
    if raw_scopes is None:
        return []

    return [scope for scope in raw_scopes if isinstance(scope, str)]


def refresh(
    func: Callable[..., ResponseReturnValue],
) -> Callable[..., ResponseReturnValue]:
    """Redirect to login when Google credentials are missing from session."""

    @functools.wraps(func)
    def wrapper(*args: object, **kwargs: object) -> ResponseReturnValue:
        if "credentials" not in flask.session:
            return flask.redirect(location=flask.url_for("auth.login"))
        return func(*args, **kwargs)

    return wrapper


@AUTH.route("/login", methods=["GET", "POST"])
def login() -> ResponseReturnValue:
    """Start OAuth by redirecting users to Google sign-in."""
    # redirect_target = _safe_redirect_target(flask.request.values.get("next"))
    # flask.session["post_auth_redirect"] = redirect_target

    # try:
    flow = Flow.from_client_secrets_file(
        str(CLIENT_SECRETS_FILE),
        scopes=SCOPES,
    )
    """
    except FileNotFoundError:
        flask.flash(
            "Google OAuth is not configured. Missing credentials_web.json.",
            "error",
        )
        return flask.redirect(redirect_target)
    """

    # oauth_redirect_uri = _oauth_redirect_uri()
    # flow.redirect_uri = flask.url_for("auth.oauth2callback")
    flow.redirect_uri = "http://127.0.0.1:5000/auth/oauth2callback"
    # flask.session["oauth_redirect_uri"] = oauth_redirect_uri

    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )

    flask.session["state"] = state
    return flask.redirect(authorization_url)


@AUTH.route("/oauth2callback", methods=["GET", "POST"])
def oauth2callback() -> ResponseReturnValue:
    """Handle OAuth callback and persist token data in the session."""
    """
    redirect_target = _safe_redirect_target(
        flask.session.pop("post_auth_redirect", _default_redirect_target())
    )
    oauth_error = flask.request.args.get("error")
    if oauth_error:
        flask.flash(f"Google authentication failed: {oauth_error}.", "error")
        return flask.redirect(redirect_target)
    """
    redirect_uri = "http://127.0.0.1:5000/home"
    oauth_state = flask.session.get("state")
    if oauth_state is None:
        flask.flash(
            "OAuth session expired. Please try signing in again.",
            "error",
        )
        return flask.redirect(flask.url_for("auth.login"))

    try:
        flow = Flow.from_client_secrets_file(
            str(CLIENT_SECRETS_FILE),
            scopes=SCOPES,
            state=oauth_state,
        )
    except FileNotFoundError:
        flask.flash(
            "Google OAuth is not configured. Missing credentials_web.json.",
            "error",
        )
        return flask.redirect(redirect_uri)

    """
    stored_redirect_uri = flask.session.get("oauth_redirect_uri")
    redirect_uri = (
        stored_redirect_uri
        if isinstance(stored_redirect_uri, str) and stored_redirect_uri
        else _oauth_redirect_uri()
    )
    """
    flow.redirect_uri = redirect_uri

    try:
        flow.fetch_token(authorization_response=flask.request.url)
    except Exception as error:
        flask.current_app.logger.exception(
            "Google OAuth token exchange failed: %s",
            error,
        )
        detail = str(error).strip()
        detail_text = f" Details: {detail}" if detail else ""
        flask.flash(
            "Unable to complete Google authentication. "
            f"Verify redirect URI ({redirect_uri}) and try again."
            f"{detail_text}",
            "error",
        )
        return flask.redirect(redirect_uri)

    credentials = flow.credentials
    """
    flask.session["credentials"] = {
        "token": _credential_string(credentials, "token"),
        "refresh_token": _credential_string(credentials, "refresh_token"),
        "token_uri": _credential_string(credentials, "token_uri"),
        "client_id": _credential_string(credentials, "client_id"),
        "client_secret": _credential_string(credentials, "client_secret"),
        "scopes": _credential_scopes(credentials),
    }
    """
    flask.session["credentials"] = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "granted_scopes": credentials.granted_scopes,  # type: ignore
    }
    # flask.session.pop("state", None)
    # flask.session.pop("oauth_redirect_uri", None)
    flask.flash("Google Calendar connected.", "success")

    return flask.redirect(redirect_uri)


# added log out part
@AUTH.route("/logout", methods=["POST"])
def logout() -> ResponseReturnValue:
    """Clear auth state and return users to landing page."""
    flask.session.pop("credentials", None)
    flask.session.pop("state", None)
    flask.session.pop("post_auth_redirect", None)
    flask.session.pop("oauth_redirect_uri", None)
    flask.flash("Signed out.", "success")
    return flask.redirect(flask.url_for("index"))
