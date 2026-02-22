"""Secretariat app creation."""  # noqa: N999

from __future__ import annotations

import os
import pathlib
from datetime import date, datetime, time, timedelta
from typing import Any

import flask

from secretariat.app import Secretariat
from secretariat.controllers.auth import AUTH
from secretariat.controllers.home import HOME


from google.oauth2.credentials import Credentials

from Secretariat.app import Secretariat

SERVICE_OPTIONS: list[dict[str, Any]] = [
    {"id": "intro_call", "label": "Intro Call (30 min)", "duration": 30},
    {"id": "deep_dive", "label": "Deep Dive (60 min)", "duration": 60},
    {
        "id": "planning",
        "label": "Planning Session (90 min)",
        "duration": 90,
    },
]
 
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

    return os.environ.get("SECRET_KEY", "dev-only-secret-key")


def _parse_iso_date(raw_date: str | None) -> date:
    """Parse a date string from form/query values."""
    if not raw_date:
        return date.today()

    try:
        return datetime.strptime(raw_date, "%Y-%m-%d").date()
    except ValueError:
        return date.today()


def _selected_service(service_id: str | None) -> dict[str, Any]:
    """Return the selected service or default option."""
    for service in SERVICE_OPTIONS:
        if service["id"] == service_id:
            return service

    return SERVICE_OPTIONS[0]


def _build_demo_slots(
    chosen_date: date,
    duration_minutes: int,
) -> list[dict[str, str]]:
    """Generate deterministic availability for frontend scaffolding."""
    if chosen_date.weekday() >= 5:
        return []

    opening = datetime.combine(chosen_date, time(hour=9))
    closing = datetime.combine(chosen_date, time(hour=17))
    booked_periods = [
        (
            datetime.combine(chosen_date, time(hour=10, minute=0)),
            datetime.combine(chosen_date, time(hour=10, minute=30)),
        ),
        (
            datetime.combine(chosen_date, time(hour=12, minute=0)),
            datetime.combine(chosen_date, time(hour=13, minute=0)),
        ),
        (
            datetime.combine(chosen_date, time(hour=15, minute=30)),
            datetime.combine(chosen_date, time(hour=16, minute=0)),
        ),
    ]

    step = timedelta(minutes=15)
    duration = timedelta(minutes=duration_minutes)
    current = opening
    slots: list[dict[str, str]] = []

    while current + duration <= closing:
        slot_end = current + duration
        has_conflict = any(
            current < booked_end and slot_end > booked_start
            for booked_start, booked_end in booked_periods
        )

        if not has_conflict:
            start_label = current.strftime("%I:%M %p").lstrip("0")
            end_label = slot_end.strftime("%I:%M %p").lstrip("0")
            slots.append(
                {
                    "label": f"{start_label} - {end_label}",
                    "value": current.strftime("%Y-%m-%dT%H:%M"),
                }
            )

        current += step

    return slots


def create_app() -> Secretariat:
    """Create and configure the Flask app."""
    app = Secretariat(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=_load_secret_key(),
        GOOG_AUTH="token.json",
    )

    @app.route("/")
    def index() -> str:
        """Render the landing page."""
        return flask.render_template("index.html", title="Home")

    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"  # only for local testing
    app.register_blueprint(HOME)
    app.register_blueprint(AUTH)
    @app.route("/availability", methods=["GET", "POST"])
    def availability() -> str:
        """Render an availability UI with Jinja."""
        request_values = flask.request.values
        selected_date = _parse_iso_date(request_values.get("date"))
        selected_service = _selected_service(request_values.get("service_id"))
        duration = int(selected_service["duration"])
        slots = _build_demo_slots(selected_date, duration)

        selected_slot = ""
        if flask.request.method == "POST":
            selected_slot = flask.request.form.get("slot", "")
            slot_lookup = {slot["value"]: slot["label"] for slot in slots}
            slot_label = slot_lookup.get(selected_slot)

            if slot_label is None:
                flask.flash("Selected slot is no longer available.", "error")
            else:
                human_date = selected_date.strftime("%A, %B %d, %Y")
                flask.flash(
                    f"Demo hold created for {human_date} at {slot_label}.",
                    "success",
                )

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
        return flask.render_template(
            "availability.html",
            today=date.today().isoformat(),
            selected_date=selected_date.isoformat(),
            selected_date_human=selected_date.strftime("%A, %B %d, %Y"),
            services=SERVICE_OPTIONS,
            selected_service=selected_service,
            slots=slots,
            selected_slot=selected_slot,
        )
        return flask.redirect(oauth_url)

    return app
