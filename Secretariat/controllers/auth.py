"""Auth stuff."""

import flask
from google_auth_oauthlib.flow import Flow

AUTH = flask.Blueprint(
    name="auth",
    import_name=__name__,
    url_prefix="/",
)

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


@AUTH.route("/login", methods=["GET"])
def login() -> flask.Response:
    """Do access code stuff after login."""
    flow = Flow.from_client_secrets_file("credentials_web.json", scopes=SCOPES)
    flow.redirect_uri = flask.url_for("auth.oauth2callback", _external=True)

    authorization_url, state = flow.authorization_url(
        access_type="offline", prompt="consent"
    )

    flask.session["state"] = state
    return flask.redirect(authorization_url)  # type: ignore


@AUTH.route("/oauth2callback")
def oauth2callback():
    """Handle session stuff after oauth redirect."""
    flow = Flow.from_client_secrets_file(
        "credentials_web.json", scopes=SCOPES, state=flask.session["state"]
    )
    flow.redirect_uri = flask.url_for("auth.oauth2callback", _external=True)

    flow.fetch_token(authorization_response=flask.request.url)

    flask.session["credentials"] = flow.credentials

    return flask.redirect(flask.url_for("home"))
