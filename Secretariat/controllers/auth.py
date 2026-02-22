"""Google OAuth flow for Calendar access."""

from __future__ import annotations

import os
import pathlib
from urllib.parse import urlparse

import flask
from flask.typing import ResponseReturnValue
from google_auth_oauthlib.flow import Flow

AUTH = flask.Blueprint(
    name="auth",
    import_name=__name__,
    url_prefix="/",
)

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
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


@AUTH.route("/login", methods=["GET", "POST"])
def login() -> ResponseReturnValue:
    """Start OAuth by redirecting users to Google sign-in."""
    redirect_target = _safe_redirect_target(flask.request.values.get("next"))
    flask.session["post_auth_redirect"] = redirect_target

    try:
        flow = Flow.from_client_secrets_file(
            str(CLIENT_SECRETS_FILE),
            scopes=SCOPES,
        )
    except FileNotFoundError:
        flask.flash(
            "Google OAuth is not configured. Missing credentials_web.json.",
            "error",
        )
        return flask.redirect(redirect_target)

    flow.redirect_uri = flask.url_for("auth.oauth2callback", _external=True)

    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )

    flask.session["state"] = state
    return flask.redirect(authorization_url)


@AUTH.route("/oauth2callback")
def oauth2callback() -> ResponseReturnValue:
    """Handle OAuth callback and persist token data in the session."""
    redirect_target = _safe_redirect_target(
        flask.session.pop("post_auth_redirect", _default_redirect_target())
    )
    oauth_error = flask.request.args.get("error")
    if oauth_error:
        flask.flash(f"Google authentication failed: {oauth_error}.", "error")
        return flask.redirect(redirect_target)

    oauth_state = flask.session.get("state")
    if oauth_state is None:
        flask.flash(
            "OAuth session expired. Please try signing in again.",
            "error",
        )
        return flask.redirect(redirect_target)

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
        return flask.redirect(redirect_target)

    flow.redirect_uri = flask.url_for("auth.oauth2callback", _external=True)

    try:
        flow.fetch_token(authorization_response=flask.request.url)
    except Exception as error:
        flask.current_app.logger.exception(
            "Google OAuth token exchange failed: %s",
            error,
        )
        flask.flash(
            "Unable to complete Google authentication. "
            "Verify your redirect URI and try again.",
            "error",
        )
        return flask.redirect(redirect_target)

    credentials = flow.credentials
    flask.session["credentials"] = {
        "token": _credential_string(credentials, "token"),
        "refresh_token": _credential_string(credentials, "refresh_token"),
        "token_uri": _credential_string(credentials, "token_uri"),
        "client_id": _credential_string(credentials, "client_id"),
        "client_secret": _credential_string(credentials, "client_secret"),
        "scopes": _credential_scopes(credentials),
    }
    flask.session.pop("state", None)
    flask.flash("Google Calendar connected.", "success")

    return flask.redirect(redirect_target)


# added log out part
@AUTH.route("/logout", methods=["POST"])
def logout() -> ResponseReturnValue:
    """Clear auth state and return users to landing page."""
    flask.session.pop("credentials", None)
    flask.session.pop("state", None)
    flask.session.pop("post_auth_redirect", None)
    flask.flash("Signed out.", "success")
    return flask.redirect(flask.url_for("index"))
