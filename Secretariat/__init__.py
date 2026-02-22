"""Secretariat app creation."""  # noqa: N999

from __future__ import annotations

import os
import pathlib
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import flask
from flask.typing import ResponseReturnValue
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from Secretariat.app import Secretariat
from Secretariat.controllers.auth import AUTH, SCOPES
from Secretariat.google_calendar.google_calendar import GoogleCalendar

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

# Simulated busy templates for deterministic availability demos.
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

HOME_MONTH_WEEKDAYS: tuple[str, ...] = (
    "Mon",
    "Tue",
    "Wed",
    "Thu",
    "Fri",
    "Sat",
    "Sun",
)

DEFAULT_SCHEDULE_TIMEZONE = "America/Los_Angeles"
SLOT_REASON_LABELS: dict[str, str] = {
    "available": "Available (both free)",
    "user_busy": "Unavailable - You are busy",
    "business_busy": "Unavailable - Business is busy",
    "both_busy": "Unavailable - Both busy",
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


def _schedule_timezone_name() -> str:
    """Return timezone identifier used by schedule and bookings."""
    return os.environ.get("SCHEDULE_TIMEZONE", DEFAULT_SCHEDULE_TIMEZONE)


def _schedule_timezone() -> ZoneInfo:
    """Resolve the scheduler timezone with UTC fallback."""
    timezone_name = _schedule_timezone_name()
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def _google_busy_interval(
    event: dict[str, Any],
    local_timezone: ZoneInfo,
) -> tuple[datetime, datetime] | None:
    """Return a local naive busy interval for a Google event."""
    start_info = event.get("start", {})
    end_info = event.get("end", {})
    if not isinstance(start_info, dict) or not isinstance(end_info, dict):
        return None

    start_datetime = _parse_google_datetime(
        _string_or_none(start_info.get("dateTime"))
    )
    end_datetime = _parse_google_datetime(
        _string_or_none(end_info.get("dateTime"))
    )
    if start_datetime and end_datetime:
        if start_datetime.tzinfo is None:
            start_local = start_datetime.replace(tzinfo=local_timezone)
        else:
            start_local = start_datetime.astimezone(local_timezone)

        if end_datetime.tzinfo is None:
            end_local = end_datetime.replace(tzinfo=local_timezone)
        else:
            end_local = end_datetime.astimezone(local_timezone)

        return (
            start_local.replace(tzinfo=None),
            end_local.replace(tzinfo=None),
        )

    all_day_start = _string_or_none(start_info.get("date"))
    all_day_end = _string_or_none(end_info.get("date"))
    if all_day_start and all_day_end:
        try:
            start_day = datetime.strptime(all_day_start, "%Y-%m-%d").date()
            end_day = datetime.strptime(all_day_end, "%Y-%m-%d").date()
        except ValueError:
            return None

        return (
            datetime.combine(start_day, time.min),
            datetime.combine(end_day, time.min),
        )

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


def _google_event_day_and_slot(
    event: dict[str, Any],
) -> tuple[str | None, str, int]:
    """Return event day and a slot label for week-column rendering."""
    start_info = event.get("start", {})
    end_info = event.get("end", {})
    if not isinstance(start_info, dict) or not isinstance(end_info, dict):
        return None, "Time unavailable", 1440

    start_datetime = _parse_google_datetime(
        _string_or_none(start_info.get("dateTime"))
    )
    end_datetime = _parse_google_datetime(
        _string_or_none(end_info.get("dateTime"))
    )
    if start_datetime and end_datetime:
        sort_key = (start_datetime.hour * 60) + start_datetime.minute
        slot_label = (
            f"{_datetime_clock_label(start_datetime)} - "
            f"{_datetime_clock_label(end_datetime)}"
        )
        return start_datetime.date().isoformat(), slot_label, sort_key

    all_day_value = _string_or_none(start_info.get("date"))
    if all_day_value:
        try:
            all_day_date = datetime.strptime(all_day_value, "%Y-%m-%d").date()
            return all_day_date.isoformat(), "All day", -1
        except ValueError:
            return None, "All day", -1

    return None, "Time unavailable", 1440


def _google_events_in_range(
    credentials: Credentials,
    range_start: date,
    range_end_exclusive: date,
) -> list[dict[str, Any]]:
    """Read events from Google Calendar for a date range."""
    range_start_utc = datetime.combine(
        range_start,
        time.min,
        tzinfo=timezone.utc,
    )
    range_end_utc = datetime.combine(
        range_end_exclusive,
        time.min,
        tzinfo=timezone.utc,
    )
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
            timeMin=range_start_utc.isoformat(),
            timeMax=range_end_utc.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=250,
        )
        .execute()
    )
    raw_items = response.get("items", [])
    if not isinstance(raw_items, list):
        return []

    events: list[dict[str, Any]] = []
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            continue

        title = _string_or_none(raw_item.get("summary")) or "Untitled Event"
        location = _string_or_none(raw_item.get("location")) or ""
        day_iso, slot_label, sort_key = _google_event_day_and_slot(raw_item)
        events.append(
            {
                "title": title,
                "time_label": _google_event_time_label(raw_item),
                "location": location,
                "day_iso": day_iso or "",
                "slot_label": slot_label,
                "sort_key": sort_key,
            }
        )

    return events


def _google_user_busy_periods_for_window(
    credentials: Credentials,
    window_start: datetime,
    window_end: datetime,
) -> list[tuple[datetime, datetime]]:
    """Load busy time windows for the user primary calendar."""
    local_timezone = _schedule_timezone()
    request_start = (window_start - timedelta(days=1)).replace(
        tzinfo=local_timezone
    )
    request_end = (window_end + timedelta(days=1)).replace(
        tzinfo=local_timezone
    )
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
            timeMin=request_start.isoformat(),
            timeMax=request_end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=500,
        )
        .execute()
    )
    raw_items = response.get("items", [])
    if not isinstance(raw_items, list):
        return []

    busy_periods: list[tuple[datetime, datetime]] = []
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            continue

        if _string_or_none(raw_item.get("status")) == "cancelled":
            continue

        if _string_or_none(raw_item.get("transparency")) == "transparent":
            continue

        busy_interval = _google_busy_interval(raw_item, local_timezone)
        if busy_interval is None:
            continue

        busy_start, busy_end = busy_interval
        if busy_start >= busy_end:
            continue

        if busy_start < window_end and busy_end > window_start:
            busy_periods.append((busy_start, busy_end))

    return busy_periods


def _create_google_primary_event(
    credentials: Credentials,
    business: dict[str, Any],
    service: dict[str, Any],
    start_at: datetime,
    end_at: datetime,
) -> dict[str, Any]:
    """Create an appointment event on the signed-in user's calendar."""
    timezone_name = _schedule_timezone_name()
    local_timezone = _schedule_timezone()
    start_at_local = start_at.replace(tzinfo=local_timezone)
    end_at_local = end_at.replace(tzinfo=local_timezone)

    service_name = _string_or_none(service.get("name")) or "Appointment"
    business_name = _string_or_none(business.get("name")) or "Business"
    business_location = _string_or_none(business.get("location")) or ""

    event_body = {
        "summary": f"{service_name} at {business_name}",
        "description": (
            "Booked with Secretariat.\n"
            f"Business: {business_name}\n"
            f"Service: {service_name}"
        ),
        "location": business_location,
        "start": {
            "dateTime": start_at_local.isoformat(),
            "timeZone": timezone_name,
        },
        "end": {
            "dateTime": end_at_local.isoformat(),
            "timeZone": timezone_name,
        },
    }

    google_service = build(
        "calendar",
        "v3",
        credentials=credentials,
        cache_discovery=False,
    )
    result = (
        google_service.events()
        .insert(calendarId="primary", body=event_body)
        .execute()
    )
    if isinstance(result, dict):
        return result
    return {}


def _mock_user_events_in_range(
    range_start: date,
    range_end_exclusive: date,
) -> list[dict[str, Any]]:
    """Build deterministic fallback events for home calendar ranges."""
    templates: list[tuple[str, int, int, int, int, str]] = [
        ("Study Group", 0, 9, 30, 60, "Holland Library"),
        ("Office Hours", 1, 13, 0, 45, "Spark 223"),
        ("Gym Session", 2, 18, 0, 90, "Student Rec Center"),
        ("Team Sync", 3, 15, 30, 30, "Zoom"),
        ("Dinner with Friends", 5, 19, 0, 120, "Downtown Pullman"),
    ]
    events: list[dict[str, Any]] = []

    current_day = range_start
    while current_day < range_end_exclusive:
        for (
            title,
            weekday,
            hour,
            minute,
            duration,
            location,
        ) in templates:
            if current_day.weekday() != weekday:
                continue

            start_time = datetime.combine(
                current_day,
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
                    "day_iso": start_time.date().isoformat(),
                    "slot_label": (
                        f"{_datetime_clock_label(start_time)} - "
                        f"{_datetime_clock_label(end_time)}"
                    ),
                    "sort_key": (start_time.hour * 60) + start_time.minute,
                }
            )

        current_day += timedelta(days=1)

    return events


def _load_user_events(
    range_start: date,
    range_end_exclusive: date,
) -> tuple[list[dict[str, Any]], str]:
    """Load user events for a requested range with fallback data."""
    credentials = _init_google_credentials()
    if credentials is None:
        return (
            _mock_user_events_in_range(range_start, range_end_exclusive),
            "Mock Calendar",
        )

    try:
        return (
            _google_events_in_range(
                credentials,
                range_start,
                range_end_exclusive,
            ),
            "Google Calendar",
        )
    except Exception:
        flask.flash(
            "Unable to read Google Calendar right now. Showing mock events.",
            "error",
        )
        return (
            _mock_user_events_in_range(range_start, range_end_exclusive),
            "Mock Calendar",
        )


def _load_user_busy_periods_for_window(
    window_start: datetime,
    window_end: datetime,
) -> list[tuple[datetime, datetime]]:
    """Load user busy windows for scheduling conflict checks."""
    credentials = _init_google_credentials()
    if credentials is None:
        return []

    try:
        return _google_user_busy_periods_for_window(
            credentials,
            window_start,
            window_end,
        )
    except Exception:
        flask.flash(
            "Unable to check Google Calendar conflicts right now.",
            "error",
        )
        return []


def _busy_periods_for_day(
    busy_periods: list[tuple[datetime, datetime]],
    chosen_date: date,
) -> list[tuple[datetime, datetime]]:
    """Return the subset of busy periods that overlap a single day."""
    day_start = datetime.combine(chosen_date, time.min)
    day_end = day_start + timedelta(days=1)
    day_periods: list[tuple[datetime, datetime]] = []

    for busy_start, busy_end in busy_periods:
        if busy_start < day_end and busy_end > day_start:
            day_periods.append(
                (
                    max(day_start, busy_start),
                    min(day_end, busy_end),
                )
            )

    return day_periods


def _week_start_for(raw_date: date) -> date:
    """Normalize a date to the Monday of its week."""
    return raw_date - timedelta(days=raw_date.weekday())


def _month_start_for(raw_date: date) -> date:
    """Normalize a date to the first of its month."""
    return raw_date.replace(day=1)


def _home_calendar_view(raw_view: str | None) -> str:
    """Return the supported home calendar view."""
    return raw_view if raw_view in {"week", "month"} else "week"


def _parse_iso_date_or_none(raw_date: str | None) -> date | None:
    """Parse an ISO date string when valid."""
    if not raw_date:
        return None

    try:
        return datetime.strptime(raw_date, "%Y-%m-%d").date()
    except ValueError:
        return None


def _home_period_start(raw_start: str | None, view: str, today: date) -> date:
    """Resolve and normalize the calendar period start date."""
    parsed_start = _parse_iso_date_or_none(raw_start)
    anchor = parsed_start if parsed_start is not None else today
    if view == "month":
        return _month_start_for(anchor)
    return _week_start_for(anchor)


def _shift_month(month_start: date, month_delta: int) -> date:
    """Shift a month-first date by a number of months."""
    month_index = (month_start.year * 12) + (month_start.month - 1)
    shifted_index = month_index + month_delta
    shifted_year, shifted_month_zero = divmod(shifted_index, 12)
    return date(shifted_year, shifted_month_zero + 1, 1)


def _home_period_end_exclusive(view: str, period_start: date) -> date:
    """Return exclusive end date for home calendar view windows."""
    if view == "month":
        return _shift_month(period_start, 1)
    return period_start + timedelta(days=7)


def _home_neighbor_start(view: str, period_start: date, step: int) -> date:
    """Return period start for previous/next navigation."""
    if view == "month":
        return _shift_month(period_start, step)
    return period_start + timedelta(days=7 * step)


def _home_events_by_day(
    events: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Group events by day with stable in-day sorting."""
    events_by_day: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        day_iso = _string_or_none(event.get("day_iso"))
        if day_iso is None:
            continue

        raw_sort_key = event.get("sort_key")
        sort_key = raw_sort_key if isinstance(raw_sort_key, int) else 9999
        slot_label = _string_or_none(event.get("slot_label"))
        if slot_label is None:
            slot_label = (
                _string_or_none(event.get("time_label")) or "Time unavailable"
            )

        day_events = events_by_day.setdefault(day_iso, [])
        day_events.append(
            {
                "title": _string_or_none(event.get("title"))
                or "Untitled Event",
                "slot_label": slot_label,
                "location": _string_or_none(event.get("location")) or "",
                "sort_key": sort_key,
            }
        )

    for day_events in events_by_day.values():
        day_events.sort(
            key=lambda event: (
                event["sort_key"],
                str(event["title"]).lower(),
            )
        )

    return events_by_day


def _home_week_columns(
    week_start: date,
    today: date,
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build Monday-Sunday columns and place events under each day."""
    events_by_day = _home_events_by_day(events)
    columns: list[dict[str, Any]] = []

    for day_offset in range(7):
        current_day = week_start + timedelta(days=day_offset)
        day_iso = current_day.isoformat()
        columns.append(
            {
                "day_iso": day_iso,
                "weekday": current_day.strftime("%A"),
                "month_day": current_day.strftime("%b %d"),
                "is_today": current_day == today,
                "events": events_by_day.get(day_iso, []),
            }
        )

    return columns


def _home_month_cells(
    month_start: date,
    today: date,
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build month cells including adjacent days to complete week rows."""
    events_by_day = _home_events_by_day(events)
    month_end_exclusive = _shift_month(month_start, 1)
    month_last_day = month_end_exclusive - timedelta(days=1)

    first_grid_day = _week_start_for(month_start)
    last_grid_day = month_last_day + timedelta(
        days=(6 - month_last_day.weekday())
    )

    cells: list[dict[str, Any]] = []
    current_day = first_grid_day
    while current_day <= last_grid_day:
        day_iso = current_day.isoformat()
        day_events = events_by_day.get(day_iso, [])
        cells.append(
            {
                "day_iso": day_iso,
                "day_number": current_day.day,
                "is_today": current_day == today,
                "is_in_month": current_day.month == month_start.month,
                "events": day_events[:3],
                "extra_count": max(0, len(day_events) - 3),
            }
        )
        current_day += timedelta(days=1)

    return cells


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
    parsed_date = _parse_iso_date_or_none(raw_date)
    if parsed_date is None:
        return date.today()
    return parsed_date


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


def _schedule_query_for_selection(
    business: dict[str, Any],
    service: dict[str, Any],
    selected_date: date,
) -> dict[str, str]:
    """Build schedule query params for redirects and links."""
    return {
        "business_id": str(business["id"]),
        "service_id": str(service["id"]),
        "date": selected_date.isoformat(),
    }


def _schedule_url_for_query(schedule_query: dict[str, str]) -> str:
    """Build the canonical schedule URL from selected query params."""
    return flask.url_for(
        "schedule",
        business_id=schedule_query["business_id"],
        service_id=schedule_query["service_id"],
        date=schedule_query["date"],
    )


def _slot_reason_label(reason: str) -> str:
    """Return the friendly label for a slot reason code."""
    return SLOT_REASON_LABELS.get(reason, "Unavailable")


def _next_bookable_slots_in_week(
    business: dict[str, Any],
    service: dict[str, Any],
    selected_date: date,
    user_busy_periods: list[tuple[datetime, datetime]],
    limit: int = 3,
) -> list[dict[str, str]]:
    """Return up to ``limit`` upcoming intersection-available slots."""
    week_end_exclusive = _week_start_for(selected_date) + timedelta(days=7)
    current_date = selected_date
    suggestions: list[dict[str, str]] = []

    while current_date < week_end_exclusive and len(suggestions) < limit:
        current_day_busy = _busy_periods_for_day(
            user_busy_periods, current_date
        )
        day_slots = _build_business_day_slots(
            business,
            service,
            current_date,
            user_busy_periods=current_day_busy,
        )

        for slot in day_slots:
            if not bool(slot.get("bookable")):
                continue

            suggestions.append(
                {
                    "day_label": current_date.strftime("%a, %b %d"),
                    "time_label": str(slot["label"]),
                    "start_time": str(slot["start_time"]),
                    "date": current_date.isoformat(),
                }
            )
            if len(suggestions) >= limit:
                break

        current_date += timedelta(days=1)

    return suggestions


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
    user_busy_periods: list[tuple[datetime, datetime]] | None = None,
) -> list[dict[str, Any]]:
    """Generate available/unavailable slots for a business service and day."""
    open_weekdays = set(business["open_weekdays"])
    if chosen_date.weekday() not in open_weekdays:
        return []

    time_range = service["time_range"]
    opening = datetime.combine(chosen_date, _parse_clock(time_range["start"]))
    closing = datetime.combine(chosen_date, _parse_clock(time_range["end"]))
    business_busy_periods = _mock_busy_periods(str(business["id"]), chosen_date)
    user_periods = user_busy_periods if user_busy_periods else []

    duration = timedelta(minutes=int(service["duration"]))
    step = timedelta(minutes=15)
    current = opening
    slots: list[dict[str, Any]] = []

    while current + duration <= closing:
        slot_end = current + duration
        has_business_conflict = any(
            current < busy_end and slot_end > busy_start
            for busy_start, busy_end in business_busy_periods
        )
        has_user_conflict = any(
            current < busy_end and slot_end > busy_start
            for busy_start, busy_end in user_periods
        )
        if has_business_conflict and has_user_conflict:
            reason = "both_busy"
        elif has_business_conflict:
            reason = "business_busy"
        elif has_user_conflict:
            reason = "user_busy"
        else:
            reason = "available"
        bookable = reason == "available"

        slots.append(
            {
                "label": (
                    f"{current.strftime('%I:%M %p').lstrip('0')} - "
                    f"{slot_end.strftime('%I:%M %p').lstrip('0')}"
                ),
                "start_time": current.strftime("%H:%M"),
                "end_time": slot_end.strftime("%H:%M"),
                "business_free": not has_business_conflict,
                "user_free": not has_user_conflict,
                "bookable": bookable,
                "available": bookable,
                "reason": reason,
                "status_label": _slot_reason_label(reason),
                "status": _slot_reason_label(reason),
            }
        )
        current += step

    return slots


def _build_week_preview(
    business: dict[str, Any],
    service: dict[str, Any],
    selected_date: date,
    user_busy_periods: list[tuple[datetime, datetime]] | None = None,
) -> list[dict[str, Any]]:
    """Build a one-week status strip around the selected date."""
    week_start = selected_date - timedelta(days=selected_date.weekday())
    open_weekdays = set(business["open_weekdays"])
    weekly_busy_periods = user_busy_periods if user_busy_periods else []
    week_days: list[dict[str, Any]] = []

    for offset in range(7):
        current_date = week_start + timedelta(days=offset)
        current_day_busy = _busy_periods_for_day(
            weekly_busy_periods,
            current_date,
        )
        day_slots = _build_business_day_slots(
            business,
            service,
            current_date,
            user_busy_periods=current_day_busy,
        )
        available_count = sum(1 for slot in day_slots if slot["bookable"])

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


def _schedule_view_context(
    business_id: str | None,
    service_id: str | None,
    raw_date: str | None,
) -> dict[str, Any]:
    """Build shared schedule view data for HTML and JSON responses."""
    selected_business = _selected_business(business_id)
    selected_service = _selected_business_service(selected_business, service_id)
    selected_date_value = _parse_iso_date(raw_date)

    week_start = _week_start_for(selected_date_value)
    week_end_exclusive = week_start + timedelta(days=7)
    user_busy_periods = _load_user_busy_periods_for_window(
        datetime.combine(week_start, time.min),
        datetime.combine(week_end_exclusive, time.min),
    )
    week_days = _build_week_preview(
        selected_business,
        selected_service,
        selected_date_value,
        user_busy_periods=user_busy_periods,
    )
    selected_day_busy = _busy_periods_for_day(
        user_busy_periods,
        selected_date_value,
    )
    day_slots = _build_business_day_slots(
        selected_business,
        selected_service,
        selected_date_value,
        user_busy_periods=selected_day_busy,
    )
    available_count = sum(1 for slot in day_slots if slot["bookable"])
    unavailable_count = len(day_slots) - available_count
    next_available_slots = _next_bookable_slots_in_week(
        selected_business,
        selected_service,
        selected_date_value,
        user_busy_periods,
    )

    return {
        "selected_business": selected_business,
        "selected_service": selected_service,
        "selected_date": selected_date_value.isoformat(),
        "selected_date_human": selected_date_value.strftime("%A, %B %d, %Y"),
        "selected_time_range": _service_time_range_label(selected_service),
        "week_days": week_days,
        "day_slots": day_slots,
        "available_count": available_count,
        "unavailable_count": unavailable_count,
        "next_available_slots": next_available_slots,
    }


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

    cal_ids = {
        ("zuriel", "zurielhernandez04@gmail.com"),
        (
            "test",
            "7400e98d2ffd7844bc8925b0753fc023a4d8876ec190205d73429e0dffd0db55@group.calendar.google.com",
        ),
    }
    app.calendars = {
        alias: GoogleCalendar(calendar_id) for alias, calendar_id in cal_ids
    }

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

        request_values = flask.request.args
        today = date.today()
        selected_view = _home_calendar_view(request_values.get("view"))
        period_start = _home_period_start(
            request_values.get("start"),
            selected_view,
            today,
        )
        period_end_exclusive = _home_period_end_exclusive(
            selected_view,
            period_start,
        )
        period_end = period_end_exclusive - timedelta(days=1)

        calendar_events, calendar_source = _load_user_events(
            period_start,
            period_end_exclusive,
        )

        week_columns: list[dict[str, Any]] = []
        month_cells: list[dict[str, Any]] = []
        if selected_view == "month":
            month_cells = _home_month_cells(
                period_start,
                today,
                calendar_events,
            )
        else:
            week_columns = _home_week_columns(
                period_start,
                today,
                calendar_events,
            )

        today_start = _home_period_start(
            today.isoformat(),
            selected_view,
            today,
        )
        prev_start = _home_neighbor_start(selected_view, period_start, -1)
        next_start = _home_neighbor_start(selected_view, period_start, 1)

        return flask.render_template(
            "home.html",
            title="Home",
            selected_view=selected_view,
            range_start=period_start.strftime("%B %d, %Y"),
            range_end=period_end.strftime("%B %d, %Y"),
            month_label=period_start.strftime("%B %Y"),
            week_view_start=_week_start_for(period_start).isoformat(),
            month_view_start=_month_start_for(period_start).isoformat(),
            prev_start=prev_start.isoformat(),
            next_start=next_start.isoformat(),
            today_start=today_start.isoformat(),
            month_weekdays=HOME_MONTH_WEEKDAYS,
            calendar_source=calendar_source,
            upcoming_events=calendar_events,
            week_columns=week_columns,
            month_cells=month_cells,
        )

    @app.route("/schedule")
    @app.route("/availability")
    def schedule() -> ResponseReturnValue:
        """Render the appointment scheduling page."""
        sign_in_redirect = _require_signed_in()
        if sign_in_redirect is not None:
            return sign_in_redirect

        request_values = flask.request.args
        schedule_context = _schedule_view_context(
            request_values.get("business_id"),
            request_values.get("service_id"),
            request_values.get("date"),
        )

        return flask.render_template(
            "availability.html",
            title="Schedule",
            today=date.today().isoformat(),
            businesses=PULLMAN_BUSINESSES,
            **schedule_context,
        )

    @app.get("/schedule/data")
    def schedule_data() -> ResponseReturnValue:
        """Return schedule view data without a full page reload."""
        sign_in_redirect = _require_signed_in()
        if sign_in_redirect is not None:
            return sign_in_redirect

        request_values = flask.request.args
        schedule_context = _schedule_view_context(
            request_values.get("business_id"),
            request_values.get("service_id"),
            request_values.get("date"),
        )
        return flask.jsonify(
            {
                "today": date.today().isoformat(),
                "businesses": PULLMAN_BUSINESSES,
                **schedule_context,
            }
        )

    @app.post("/appointments")
    def book_appointment() -> ResponseReturnValue:
        """Book a selected appointment slot to the user's calendar."""
        sign_in_redirect = _require_signed_in()
        if sign_in_redirect is not None:
            return sign_in_redirect

        form_values = flask.request.form
        selected_business = _selected_business(form_values.get("business_id"))
        selected_service = _selected_business_service(
            selected_business,
            form_values.get("service_id"),
        )
        selected_date = _parse_iso_date(form_values.get("date"))
        schedule_query = _schedule_query_for_selection(
            selected_business,
            selected_service,
            selected_date,
        )

        slot_start_raw = _string_or_none(form_values.get("slot_start"))
        if slot_start_raw is None:
            flask.flash("Please choose a valid time slot.", "error")
            return flask.redirect(
                _schedule_url_for_query(schedule_query),
            )

        try:
            slot_start = datetime.combine(
                selected_date,
                _parse_clock(slot_start_raw),
            )
        except ValueError:
            flask.flash("Please choose a valid time slot.", "error")
            return flask.redirect(
                _schedule_url_for_query(schedule_query),
            )

        slot_end = slot_start + timedelta(
            minutes=int(selected_service["duration"]),
        )

        week_start = _week_start_for(selected_date)
        week_end_exclusive = week_start + timedelta(days=7)
        user_busy_periods = _load_user_busy_periods_for_window(
            datetime.combine(week_start, time.min),
            datetime.combine(week_end_exclusive, time.min),
        )
        selected_day_busy = _busy_periods_for_day(
            user_busy_periods,
            selected_date,
        )
        day_slots = _build_business_day_slots(
            selected_business,
            selected_service,
            selected_date,
            user_busy_periods=selected_day_busy,
        )
        chosen_slot = next(
            (
                slot
                for slot in day_slots
                if slot.get("start_time") == slot_start_raw
            ),
            None,
        )
        if chosen_slot is None:
            flask.flash(
                "Selected slot is invalid for the chosen service.",
                "error",
            )
            return flask.redirect(
                _schedule_url_for_query(schedule_query),
            )

        if not bool(chosen_slot.get("bookable")):
            flask.flash(
                "Selected slot is no longer available. Pick another time.",
                "error",
            )
            return flask.redirect(
                _schedule_url_for_query(schedule_query),
            )

        credentials = _init_google_credentials()
        if credentials is None:
            flask.flash(
                "Google session expired. Please sign in again.",
                "error",
            )
            return flask.redirect(flask.url_for("index"))

        try:
            _create_google_primary_event(
                credentials,
                selected_business,
                selected_service,
                slot_start,
                slot_end,
            )
        except Exception as error:
            flask.current_app.logger.exception(
                "Unable to create Google Calendar appointment: %s",
                error,
            )
            flask.flash(
                "Could not create Google Calendar appointment. Try again.",
                "error",
            )
            return flask.redirect(
                _schedule_url_for_query(schedule_query),
            )

        booked_day = selected_date.strftime("%a, %b %d")
        booked_time = slot_start.strftime("%I:%M %p").lstrip("0")
        service_name = (
            _string_or_none(selected_service.get("name")) or "Service"
        )
        flask.flash(
            f"Booked {service_name} on {booked_day} at {booked_time}.",
            "success",
        )
        return flask.redirect(flask.url_for("home"))

    return app
