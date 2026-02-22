"""Secretariat app creation."""  # noqa: N999

from __future__ import annotations

import json
import os
import pathlib

import flask

from secretariat.app import Secretariat
from secretariat.controllers.auth import AUTH
from secretariat.controllers.home import HOME


def _get_client_id() -> str | None:
    """For setting up credendials to work with google api."""
    with pathlib.Path("credentials_web.json").open(encoding="utf-8") as f:
        raw: dict[str, str] = json.loads(f.read())
        return raw.get("client_id")


def create_app() -> Secretariat:
    """Entry point for flask app."""
    app = Secretariat(__name__, instance_relative_config=True)

    # get secret to save in config for session handling
    with pathlib.Path("./.env").open("r", encoding="utf-8") as env:
        super_secret_key = env.read().strip()

    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"  # only for local testing
    app.register_blueprint(HOME)
    app.register_blueprint(AUTH)

    # register close db to happen at clean up
    # app.teardown_appcontext(app.close_db)
    app.config.from_mapping(SECRET_KEY=super_secret_key, GOOG_AUTH="token.json")

    # create index page to start on
    @app.route("/")
    def index():
        client_id = _get_client_id()
        oauth_url = (
            "https://accounts.google.com/o/oauth2/v2/auth?"
            f"client_id={client_id}"
            f"&redirect_uri={flask.url_for('auth.login')}"
            "&response_type=code"
            "&scope=https://www.googleapis.com/auth/calendar.readonly"
            "&access_type=offline"
            "&prompt=consent"
        )
        return flask.redirect(oauth_url)

    return app
