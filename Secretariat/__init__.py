"""Secretariat app creation."""  # noqa: N999

from __future__ import annotations

import os
import pathlib
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

import flask
from flask.typing import ResponseReturnValue
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from Secretariat.app import Secretariat
from Secretariat.controllers.auth import AUTH, SCOPES

PULLMAN_BUSINESSES: list[dict[str, Any]] = [
    {
        "id": "crimson-cuts",
        "name": "Crimson Cuts Barbershop",
        "location": "Downtown Pullman",
        "description": (
            "Student-friendly barbershop offering fades, beard trims, and "
            "full grooming appointments."
        ),
        "open_weekdays": [0, 1, 2, 3, 4, 5],
        "services": [
            {
                "id": "fade-cut",
                "name": "Fade + Style",
                "duration": 30,
                "time_range": {"start": "09:00", "end": "17:00"},
            },
            {
                "id": "haircut-beard",
                "name": "Haircut + Beard Trim",
                "duration": 45,
                "time_range": {"start": "10:00", "end": "18:00"},
            },
            {
                "id": "full-groom",
                "name": "Full Grooming Session",
                "duration": 60,
                "time_range": {"start": "11:00", "end": "18:00"},
            },
        ],
    },
    {
        "id": "palouse-pt",
        "name": "Palouse Physical Therapy",
        "location": "Grand Avenue, Pullman",
        "description": (
            "Sports recovery and mobility sessions tailored for students, "
            "athletes, and local residents."
        ),
        "open_weekdays": [0, 1, 2, 3, 4],
        "services": [
            {
                "id": "initial-eval",
                "name": "Initial Evaluation",
                "duration": 60,
                "time_range": {"start": "08:30", "end": "16:30"},
            },
            {
                "id": "follow-up",
                "name": "Follow-up Session",
                "duration": 45,
                "time_range": {"start": "09:00", "end": "17:00"},
            },
            {
                "id": "mobility-reset",
                "name": "Mobility Reset",
                "duration": 30,
                "time_range": {"start": "10:00", "end": "15:30"},
            },
        ],
    },
    {
        "id": "sweet-serenity",
        "name": "Sweet Serenity Spa",
        "location": "Main Street, Pullman",
        "description": (
            "A calm downtown spa with facials and massage-focused appointments "
            "for quick or full-session self-care."
        ),
        "open_weekdays": [1, 2, 3, 4, 5, 6],
        "services": [
            {
                "id": "express-facial",
                "name": "Express Facial",
                "duration": 30,
                "time_range": {"start": "10:00", "end": "18:00"},
            },
            {
                "id": "custom-facial",
                "name": "Custom Facial",
                "duration": 60,
                "time_range": {"start": "10:00", "end": "17:00"},
            },
            {
                "id": "swedish-massage",
                "name": "Swedish Massage",
                "duration": 60,
                "time_range": {"start": "11:00", "end": "19:00"},
            },
        ],
    },
]

BUSINESS_BUSY_TEMPLATES: dict[str, dict[int, list[tuple[str, str]]]] = {
    "crimson-cuts": {
        0: [("09:45", "10:30"), ("12:00", "13:00"), ("15:30", "16:30")],
        1: [("10:15", "11:00"), ("13:30", "14:30"), ("16:00", "16:45")],
        2: [("09:30", "10:15"), ("12:45", "13:30"), ("15:00", "16:00")],
        3: [("10:00", "11:30"), ("14:15", "15:00"), ("17:00", "17:45")],
        4: [("09:00", "09:45"), ("12:15", "13:15"), ("15:45", "16:45")],
        5: [("10:30", "11:30"), ("13:00", "14:00"), ("16:15", "17:15")],
    },
    "palouse-pt": {
        0: [("09:00", "10:30"), ("11:45", "12:45"), ("14:30", "15:30")],
        1: [("08:30", "09:30"), ("11:00", "12:00"), ("15:00", "16:00")],
        2: [("09:15", "10:00"), ("12:30", "13:30"), ("14:45", "15:45")],
        3: [("08:45", "09:45"), ("11:30", "12:30"), ("13:45", "15:15")],
        4: [("09:30", "10:15"), ("12:00", "13:00"), ("15:15", "16:15")],
    },
    "sweet-serenity": {
        1: [("10:30", "11:30"), ("13:00", "14:00"), ("16:00", "17:00")],
        2: [("10:00", "11:00"), ("12:45", "13:45"), ("15:30", "16:30")],
        3: [("11:15", "12:15"), ("14:00", "15:00"), ("17:00", "18:00")],
        4: [("10:45", "11:45"), ("13:15", "14:15"), ("16:15", "17:15")],
        5: [("10:30", "11:30"), ("14:30", "15:30"), ("17:30", "18:30")],
        6: [("11:00", "12:00"), ("13:30", "14:30"), ("16:30", "17:30")],
    },
}


def _string_or_none(raw_value: object) -> str | None:
    """Return a string value when possible."""
    return raw_value if isinstance(raw_value, str) else None


def _has_google_session_credentials() -> bool:
    """Return whether a user has usable auth data in session."""
    raw_credentials = flask.session.get("credentials")
    if not isinstance(raw_credentials, dict):
        return False

    token = _string_or_none(raw_credentials.get("token"))
    return token is not None and bool(token)


def _init_google_credentials() -> Credentials | None:
    """Build Google credentials for API use from session state."""
    raw_credentials = flask.session.get("credentials")
    if not isinstance(raw_credentials, dict):
        return None

    token = _string_or_none(raw_credentials.get("token"))
    if token is None:
        return None

    refresh_token = _string_or_none(raw_credentials.get("refresh_token"))
    token_uri = _string_or_none(raw_credentials.get("token_uri"))
    client_id = _string_or_none(raw_credentials.get("client_id"))
    client_secret = _string_or_none(raw_credentials.get("client_secret"))

    raw_scopes = raw_credentials.get("scopes")
    scopes: list[str] = []
    if isinstance(raw_scopes, list):
        scopes = [scope for scope in raw_scopes if isinstance(scope, str)]
    if not scopes:
        scopes = SCOPES

    return Credentials(
        token=token,
        refresh_token=refresh_token,
        token_uri=token_uri,
        client_id=client_id,
        client_secret=client_secret,
        scopes=scopes,
    )


def _require_signed_in() -> ResponseReturnValue | None:
    """Redirect guests back to the landing page."""
    if _has_google_session_credentials():
        return None

    flask.flash("Sign in with Google to continue.", "error")
    return flask.redirect(flask.url_for("index"))


def _datetime_clock_label(clock: datetime) -> str:
    """Render a datetime as a simple human clock label."""
    return clock.strftime("%I:%M %p").lstrip("0")


# parses datetime strings from Calendar API
def _parse_google_datetime(raw_value: str | None) -> datetime | None:
    """Parse RFC3339-ish values returned by Google Calendar."""
    if raw_value is None:
        return None

    normalized = raw_value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


# builds time labels derived from Google Calendar event data after parsing
def _google_event_time_label(event: dict[str, Any]) -> str:
    """Build a readable time label for a Google Calendar event."""
    start_info = event.get("start", {})
    end_info = event.get("end", {})
    if not isinstance(start_info, dict) or not isinstance(end_info, dict):
        return "Time unavailable"

    start_datetime = _parse_google_datetime(
        _string_or_none(start_info.get("dateTime"))
    )
    end_datetime = _parse_google_datetime(
        _string_or_none(end_info.get("dateTime"))
    )
    if start_datetime and end_datetime:
        day_label = start_datetime.strftime("%a, %b %d")
        return (
            f"{day_label} · {_datetime_clock_label(start_datetime)} - "
            f"{_datetime_clock_label(end_datetime)}"
        )

    all_day_value = _string_or_none(start_info.get("date"))
    if all_day_value:
        try:
            parsed_day = datetime.strptime(all_day_value, "%Y-%m-%d")
            return f"{parsed_day.strftime('%a, %b %d')} · All day"
        except ValueError:
            return "All day"

    return "Time unavailable"


def _google_week_events(credentials: Credentials) -> list[dict[str, str]]:
    """Read the next seven days of events from Google Calendar."""
    now_utc = datetime.now(timezone.utc)
    one_week_from_now = now_utc + timedelta(days=7)
    service = build(
        "calendar",
        "v3",
        credentials=credentials,
        cache_discovery=False,
    )
    response = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=now_utc.isoformat(),
            timeMax=one_week_from_now.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=30,
        )
        .execute()
    )
    raw_items = response.get("items", [])
    if not isinstance(raw_items, list):
        return []

    events: list[dict[str, str]] = []
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            continue

        title = _string_or_none(raw_item.get("summary")) or "Untitled Event"
        location = _string_or_none(raw_item.get("location")) or ""
        events.append(
            {
                "title": title,
                "time_label": _google_event_time_label(raw_item),
                "location": location,
            }
        )

    return events


def _mock_user_week_events(today: date) -> list[dict[str, str]]:
    """Build deterministic fallback events for the user dashboard."""
    week_start = today - timedelta(days=today.weekday())
    templates = [
        ("Study Group", 0, 9, 30, 60, "Holland Library"),
        ("Office Hours", 1, 13, 0, 45, "Spark 223"),
        ("Gym Session", 2, 18, 0, 90, "Student Rec Center"),
        ("Team Sync", 3, 15, 30, 30, "Zoom"),
        ("Dinner with Friends", 5, 19, 0, 120, "Downtown Pullman"),
    ]
    events: list[dict[str, str]] = []

    for title, day_offset, hour, minute, duration, location in templates:
        start_time = datetime.combine(
            week_start + timedelta(days=day_offset),
            time(hour=hour, minute=minute),
        )
        end_time = start_time + timedelta(minutes=duration)
        events.append(
            {
                "title": title,
                "time_label": (
                    f"{start_time.strftime('%a, %b %d')} · "
                    f"{_datetime_clock_label(start_time)} - "
                    f"{_datetime_clock_label(end_time)}"
                ),
                "location": location,
            }
        )

    return events


def _load_user_week_events(today: date) -> tuple[list[dict[str, str]], str]:
    """Get user events from Google when possible, otherwise fallback mock."""
    credentials = _init_google_credentials()
    if credentials is None:
        return _mock_user_week_events(today), "Mock Calendar"

    try:
        return _google_week_events(credentials), "Google Calendar"
    except Exception:
        flask.flash(
            "Unable to read Google Calendar right now. Showing mock events.",
            "error",
        )
        return _mock_user_week_events(today), "Mock Calendar"


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


def _parse_clock(raw_clock: str) -> time:
    """Parse an ``HH:MM`` clock value into a ``time`` object."""
    return datetime.strptime(raw_clock, "%H:%M").time()


def _clock_label(raw_clock: str) -> str:
    """Render an ``HH:MM`` clock value in human-readable format."""
    parsed = datetime.strptime(raw_clock, "%H:%M")
    return parsed.strftime("%I:%M %p").lstrip("0")


def _selected_business(business_id: str | None) -> dict[str, Any]:
    """Return the chosen business or a default business."""
    for business in PULLMAN_BUSINESSES:
        if business["id"] == business_id:
            return business

    return PULLMAN_BUSINESSES[0]


def _selected_business_service(
    business: dict[str, Any],
    service_id: str | None,
) -> dict[str, Any]:
    """Return selected service for a business or fallback to the first one."""
    for service in business["services"]:
        if service["id"] == service_id:
            return service

    return business["services"][0]


def _mock_busy_periods(
    business_id: str,
    chosen_date: date,
) -> list[tuple[datetime, datetime]]:
    """Build deterministic busy blocks for a business on a given date."""
    templates = BUSINESS_BUSY_TEMPLATES.get(business_id, {})
    day_templates = templates.get(chosen_date.weekday(), [])
    periods: list[tuple[datetime, datetime]] = []

    for start_raw, end_raw in day_templates:
        periods.append(
            (
                datetime.combine(chosen_date, _parse_clock(start_raw)),
                datetime.combine(chosen_date, _parse_clock(end_raw)),
            )
        )

    return periods


def _build_business_day_slots(
    business: dict[str, Any],
    service: dict[str, Any],
    chosen_date: date,
) -> list[dict[str, Any]]:
    """Generate available/unavailable slots for a business service and day."""
    open_weekdays = set(business["open_weekdays"])
    if chosen_date.weekday() not in open_weekdays:
        return []

    time_range = service["time_range"]
    opening = datetime.combine(chosen_date, _parse_clock(time_range["start"]))
    closing = datetime.combine(chosen_date, _parse_clock(time_range["end"]))
    busy_periods = _mock_busy_periods(str(business["id"]), chosen_date)

    duration = timedelta(minutes=int(service["duration"]))
    step = timedelta(minutes=15)
    current = opening
    slots: list[dict[str, Any]] = []

    while current + duration <= closing:
        slot_end = current + duration
        has_conflict = any(
            current < busy_end and slot_end > busy_start
            for busy_start, busy_end in busy_periods
        )

        slots.append(
            {
                "label": (
                    f"{current.strftime('%I:%M %p').lstrip('0')} - "
                    f"{slot_end.strftime('%I:%M %p').lstrip('0')}"
                ),
                "available": not has_conflict,
                "status": "Available" if not has_conflict else "Unavailable",
            }
        )
        current += step

    return slots


def _build_week_preview(
    business: dict[str, Any],
    service: dict[str, Any],
    selected_date: date,
) -> list[dict[str, Any]]:
    """Build a one-week status strip around the selected date."""
    week_start = selected_date - timedelta(days=selected_date.weekday())
    open_weekdays = set(business["open_weekdays"])
    week_days: list[dict[str, Any]] = []

    for offset in range(7):
        current_date = week_start + timedelta(days=offset)
        day_slots = _build_business_day_slots(business, service, current_date)
        available_count = sum(1 for slot in day_slots if slot["available"])

        if current_date.weekday() not in open_weekdays:
            status = "closed"
            status_label = "Closed"
        elif available_count == 0:
            status = "full"
            status_label = "Full"
        elif available_count < 5:
            status = "limited"
            status_label = "Limited"
        else:
            status = "open"
            status_label = "Open"

        week_days.append(
            {
                "date": current_date.isoformat(),
                "weekday": current_date.strftime("%a"),
                "day_number": current_date.strftime("%d"),
                "status": status,
                "status_label": status_label,
                "available_count": available_count,
                "is_selected": current_date == selected_date,
            }
        )

    return week_days


def _service_time_range_label(service: dict[str, Any]) -> str:
    """Return a friendly time range label for a service."""
    time_range = service["time_range"]
    return (
        f"{_clock_label(time_range['start'])} - "
        f"{_clock_label(time_range['end'])}"
    )


def create_app() -> Secretariat:
    """Create and configure the Flask app."""
    app = Secretariat(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=_load_secret_key(),
        GOOG_AUTH="token.json",
    )
    app.register_blueprint(AUTH)

    @app.context_processor
    def inject_google_auth_state() -> dict[str, bool]:
        """Expose current Google auth state to all templates."""
        return {"google_authenticated": _has_google_session_credentials()}

    @app.route("/")
    def index() -> ResponseReturnValue:
        """Render landing page or redirect signed-in users home."""
        if _has_google_session_credentials():
            return flask.redirect(flask.url_for("home"))

        return flask.render_template("index.html", title="Landing")

    @app.route("/home")
    def home() -> ResponseReturnValue:
        """Render the authenticated user home page."""
        sign_in_redirect = _require_signed_in()
        if sign_in_redirect is not None:
            return sign_in_redirect

        today = date.today()
        upcoming_events, calendar_source = _load_user_week_events(today)
        return flask.render_template(
            "home.html",
            title="Home",
            range_start=today.strftime("%B %d, %Y"),
            range_end=(today + timedelta(days=7)).strftime("%B %d, %Y"),
            upcoming_events=upcoming_events,
            calendar_source=calendar_source,
        )

    @app.route("/schedule")
    @app.route("/availability")
    def schedule() -> ResponseReturnValue:
        """Render the appointment scheduling page."""
        sign_in_redirect = _require_signed_in()
        if sign_in_redirect is not None:
            return sign_in_redirect

        request_values = flask.request.args
        selected_business = _selected_business(
            request_values.get("business_id")
        )
        selected_service = _selected_business_service(
            selected_business,
            request_values.get("service_id"),
        )
        selected_date = _parse_iso_date(request_values.get("date"))
        week_days = _build_week_preview(
            selected_business,
            selected_service,
            selected_date,
        )
        day_slots = _build_business_day_slots(
            selected_business,
            selected_service,
            selected_date,
        )
        available_count = sum(1 for slot in day_slots if slot["available"])
        unavailable_count = len(day_slots) - available_count

        return flask.render_template(
            "availability.html",
            title="Schedule",
            today=date.today().isoformat(),
            businesses=PULLMAN_BUSINESSES,
            selected_business=selected_business,
            selected_service=selected_service,
            selected_date=selected_date.isoformat(),
            selected_date_human=selected_date.strftime("%A, %B %d, %Y"),
            selected_time_range=_service_time_range_label(selected_service),
            week_days=week_days,
            day_slots=day_slots,
            available_count=available_count,
            unavailable_count=unavailable_count,
        )

    return app
