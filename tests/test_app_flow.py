"""Tests for auth flow, route protection, and time formatting."""

from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

from Secretariat import (
    _google_event_time_label,
    _home_week_columns,
    _parse_google_datetime,
    create_app,
)


class TimestampFormattingTests(unittest.TestCase):
    """Validate timestamp parsing and label formatting."""

    def test_parse_google_datetime_z_suffix(self) -> None:
        """Parse Google Zulu datetime values into aware datetimes."""
        parsed = _parse_google_datetime("2026-02-22T17:30:00Z")

        self.assertIsNotNone(parsed)
        if parsed is None:
            return
        self.assertEqual(parsed.isoformat(), "2026-02-22T17:30:00+00:00")

    def test_google_event_time_label_for_timed_event(self) -> None:
        """Render a timed event label in 12-hour format."""
        event = {
            "start": {"dateTime": "2026-02-22T09:05:00-08:00"},
            "end": {"dateTime": "2026-02-22T10:15:00-08:00"},
        }

        label = _google_event_time_label(event)

        self.assertEqual(label, "Sun, Feb 22 · 9:05 AM - 10:15 AM")

    def test_google_event_time_label_for_all_day_event(self) -> None:
        """Render all-day events with date and all-day text."""
        event = {
            "start": {"date": "2026-02-23"},
            "end": {"date": "2026-02-24"},
        }

        label = _google_event_time_label(event)

        self.assertEqual(label, "Mon, Feb 23 · All day")


class RouteFlowTests(unittest.TestCase):
    """Validate route behavior for signed-out and signed-in sessions."""

    def setUp(self) -> None:
        """Create an application instance and test client."""
        self.app = create_app()
        self.app.config.update(TESTING=True)
        self.client = self.app.test_client()

    def _seed_signed_in_session(self) -> None:
        """Set minimal credentials in the test session."""
        with self.client.session_transaction() as session:
            session["credentials"] = {"token": "test-token"}

    def test_schedule_requires_sign_in(self) -> None:
        """Redirect guests to landing and show sign-in flash message."""
        response = self.client.get("/schedule", follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Sign in with Google to continue.", response.data)

    def test_index_redirects_to_home_when_signed_in(self) -> None:
        """Redirect signed-in users away from landing page."""
        self._seed_signed_in_session()

        response = self.client.get("/", follow_redirects=False)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers.get("Location"), "/home")

    def test_home_renders_for_signed_in_user(self) -> None:
        """Render home page tabs when the session is authenticated."""
        self._seed_signed_in_session()
        fake_events = [
            {
                "title": "Mock Event",
                "time_label": "Mon, Feb 23 · 9:00 AM - 10:00 AM",
                "location": "Pullman",
                "day_iso": "2026-02-23",
                "slot_label": "9:00 AM - 10:00 AM",
                "sort_key": 540,
            }
        ]
        with patch(
            "Secretariat._load_user_events",
            return_value=(fake_events, "Mock Calendar"),
        ):
            response = self.client.get("/home", follow_redirects=False)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Your Calendar", response.data)
        self.assertIn(b"Set Up Appointment", response.data)

    def test_home_month_view_renders_label_and_controls(self) -> None:
        """Render month view when requested through query parameters."""
        self._seed_signed_in_session()
        with patch(
            "Secretariat._load_user_events",
            return_value=([], "Mock Calendar"),
        ):
            response = self.client.get(
                "/home?view=month&start=2026-02-01",
                follow_redirects=False,
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"February 2026", response.data)
        self.assertIn(b"Prev", response.data)
        self.assertIn(b"Next", response.data)

    def test_oauth_callback_missing_state_shows_error(self) -> None:
        """Display an OAuth error when callback state is unavailable."""
        response = self.client.get("/oauth2callback", follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            b"OAuth session expired. Please try signing in again.",
            response.data,
        )

    def test_logout_clears_session_and_redirects_to_landing(self) -> None:
        """Drop credentials and send users back to landing on logout."""
        self._seed_signed_in_session()

        response = self.client.post("/logout", follow_redirects=False)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers.get("Location"), "/")
        with self.client.session_transaction() as session:
            self.assertNotIn("credentials", session)


class HomeWeekColumnsTests(unittest.TestCase):
    """Validate mapping events into Monday-Sunday home columns."""

    def test_home_week_columns_places_events_in_matching_day(self) -> None:
        """Keep events under the correct weekday with sorted times."""
        columns = _home_week_columns(
            week_start=date(2026, 2, 16),
            today=date(2026, 2, 22),
            events=[
                {
                    "title": "Late Event",
                    "day_iso": "2026-02-18",
                    "slot_label": "5:00 PM - 6:00 PM",
                    "location": "Gym",
                    "sort_key": 1020,
                },
                {
                    "title": "Early Event",
                    "day_iso": "2026-02-18",
                    "slot_label": "9:00 AM - 10:00 AM",
                    "location": "Library",
                    "sort_key": 540,
                },
            ],
        )

        self.assertEqual(len(columns), 7)
        wednesday = next(
            column for column in columns if column["day_iso"] == "2026-02-18"
        )
        self.assertEqual(len(wednesday["events"]), 2)
        self.assertEqual(wednesday["events"][0]["title"], "Early Event")
        self.assertEqual(wednesday["events"][1]["title"], "Late Event")


if __name__ == "__main__":
    unittest.main()
