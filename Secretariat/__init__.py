"""Secretariat app creation."""  # noqa: N999

from __future__ import annotations

import json
import os
import pathlib
from typing import TYPE_CHECKING

import flask

from secretariat.app import Secretariat
from secretariat.controllers.auth import AUTH
from secretariat.controllers.home import HOME
from secretariat.google_calendar.google_calendar import GoogleCalendar

if TYPE_CHECKING:
    from secretariat.app import Secretariat


def _get_client_id() -> str | None:
    """For setting up credendials to work with google api."""
    with pathlib.Path("credentials_web.json").open(encoding="utf-8") as f:
        raw: dict[str, str] = json.loads(f.read())
        return raw.get("client_id")


def _load_secret_key() -> str:
    """Load secret key from `.env`, then env var, then a dev fallback."""
    env_path = pathlib.Path("./.env")
    if env_path.exists():
        with env_path.open("r", encoding="utf-8") as env_file:
            secret_key = env_file.read().strip()
            if secret_key:
                return secret_key
    else:
        raise ValueError

    return os.environ.get("SECRET_KEY", "dev-only-secret-key")


def create_app() -> Secretariat:
    """Create and configure the Flask app."""
    app = Secretariat(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=_load_secret_key(),
        SESSION_COOKIE_SECURE=False,
    )

    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"  # only for local testing
    app.register_blueprint(HOME)
    app.register_blueprint(AUTH)

    cal_ids = {
        ("zuriel", "zurielhernandez04@gmail.com"),
        (
            "test",
            "7400e98d2ffd7844bc8925b0753fc023a4d8876ec190205d73429e0dffd0db55@group.calendar.google.com",
        ),
    }
    app.calendars = {alias: GoogleCalendar(id) for alias, id in cal_ids}

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
