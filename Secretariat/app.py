"""Entry point for doing flask things."""

from __future__ import annotations

import flask

from secretariat.google_calendar.google_calendar import GoogleCalendar


class Secretariat(flask.Flask):
    """Flask application entry point."""

    calendars: dict[str, GoogleCalendar]
