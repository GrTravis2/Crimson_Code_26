"""Secretariat app creation."""  # noqa: N999

from __future__ import annotations

import pathlib

import flask

# from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from Secretariat.app import Secretariat

# from google_auth_oauthlib.flow import InstalledAppFlow
# from googleapiclient.discovery import build
# from googleapiclient.errors import HttpError


def _init_google_credentials() -> Credentials:
    """For setting up credendials to work with google api."""
    raise NotImplementedError


def create_app() -> Secretariat:
    """Entry point for flask app."""
    app = Secretariat(__name__, instance_relative_config=True)

    # get secret to save in config for session handling
    with pathlib.Path("./.env").open("r", encoding="utf-8") as env:
        super_secret_key = env.read().strip()

    # setup other env vars here, like api keys and stuff
    # creds = _init_google_credentials()

    # register close db to happen at clean up
    # app.teardown_appcontext(app.close_db)
    app.config.from_mapping(SECRET_KEY=super_secret_key, GOOG_AUTH="token.json")

    # create index page to start on
    @app.route("/")
    def index():
        return flask.render_template(
            "index.html",
            name="INDEX",
            title="HOMEPAGE",
        )

    return app
