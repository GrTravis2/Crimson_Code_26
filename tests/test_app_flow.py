"""Tests for auth flow, route protection, and time formatting."""

from __future__ import annotations

import unittest
from datetime import date, datetime
from unittest.mock import patch

from Secretariat import (
    _build_business_day_slots,
    _google_event_time_label,
    _home_week_columns,
    _parse_google_datetime,
    _selected_business,
    _selected_business_service,
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


class SlotIntersectionTests(unittest.TestCase):
    """Validate business/user availability intersection slot modeling."""

    def setUp(self) -> None:
        """Load one business/service pair used across slot tests."""
        self.business = _selected_business("crimson-cuts")
        self.service = _selected_business_service(self.business, "fade-cut")
        self.chosen_date = date(2026, 2, 23)

    def _slot(
        self,
        start_time: str,
        user_busy: list[tuple[datetime, datetime]],
    ) -> dict[str, object]:
        """Return one slot from generated day slots."""
        day_slots = _build_business_day_slots(
            self.business,
            self.service,
            self.chosen_date,
            user_busy_periods=user_busy,
        )
        return next(
            slot for slot in day_slots if slot["start_time"] == start_time
        )

    def test_slot_marks_user_busy_reason(self) -> None:
        """Mark slot unavailable when only the user is busy."""
        slot = self._slot(
            "11:00",
            [
                (
                    datetime(2026, 2, 23, 11, 0),
                    datetime(2026, 2, 23, 11, 30),
                )
            ],
        )

        self.assertTrue(slot["business_free"])
        self.assertFalse(slot["user_free"])
        self.assertFalse(slot["bookable"])
        self.assertEqual(slot["reason"], "user_busy")
        self.assertEqual(slot["status_label"], "Unavailable - You are busy")

    def test_slot_marks_business_busy_reason(self) -> None:
        """Mark slot unavailable when only mock business is busy."""
        slot = self._slot("10:00", [])

        self.assertFalse(slot["business_free"])
        self.assertTrue(slot["user_free"])
        self.assertFalse(slot["bookable"])
        self.assertEqual(slot["reason"], "business_busy")
        self.assertEqual(
            slot["status_label"],
            "Unavailable - Business is busy",
        )

    def test_slot_marks_both_busy_reason(self) -> None:
        """Mark slot unavailable as both-busy when both sides conflict."""
        slot = self._slot(
            "10:00",
            [
                (
                    datetime(2026, 2, 23, 10, 0),
                    datetime(2026, 2, 23, 10, 30),
                )
            ],
        )

        self.assertFalse(slot["business_free"])
        self.assertFalse(slot["user_free"])
        self.assertFalse(slot["bookable"])
        self.assertEqual(slot["reason"], "both_busy")
        self.assertEqual(slot["status_label"], "Unavailable - Both busy")

    def test_slot_marks_available_as_bookable(self) -> None:
        """Keep slot bookable when user and business are both free."""
        slot = self._slot("11:00", [])

        self.assertTrue(slot["business_free"])
        self.assertTrue(slot["user_free"])
        self.assertTrue(slot["bookable"])
        self.assertEqual(slot["reason"], "available")
        self.assertEqual(slot["status_label"], "Available (both free)")


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

    def test_schedule_data_returns_json_payload(self) -> None:
        """Expose async schedule payload for client-side updates."""
        self._seed_signed_in_session()
        with patch(
            "Secretariat._load_user_busy_periods_for_window",
            return_value=[],
        ):
            response = self.client.get(
                "/schedule/data?business_id=crimson-cuts&"
                "service_id=fade-cut&date=2026-02-23",
                follow_redirects=False,
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsInstance(payload, dict)
        if not isinstance(payload, dict):
            return
        self.assertIn("day_slots", payload)
        self.assertIn("week_days", payload)
        self.assertIn("selected_business", payload)
        self.assertEqual(payload["selected_business"]["id"], "crimson-cuts")

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

    def test_schedule_shows_intersection_overlay_labels(self) -> None:
        """Render schedule overlay labels and next-slot guidance text."""
        self._seed_signed_in_session()
        with patch(
            "Secretariat._load_user_busy_periods_for_window",
            return_value=[],
        ):
            response = self.client.get(
                "/schedule?business_id=crimson-cuts&service_id=fade-cut"
                "&date=2026-02-23",
                follow_redirects=False,
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Availability Overlay", response.data)
        self.assertIn(b"Next 3 available times", response.data)
        self.assertIn(b"Unavailable - Business is busy", response.data)

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

    def test_book_appointment_creates_google_event(self) -> None:
        """Book an available slot and redirect back to home."""
        self._seed_signed_in_session()
        payload = {
            "business_id": "crimson-cuts",
            "service_id": "fade-cut",
            "date": "2026-02-23",
            "slot_start": "09:00",
        }
        with (
            patch(
                "Secretariat._load_user_busy_periods_for_window",
                return_value=[],
            ),
            patch(
                "Secretariat._create_google_primary_event",
                return_value={"id": "event-1"},
            ) as mock_create_event,
        ):
            response = self.client.post(
                "/appointments",
                data=payload,
                follow_redirects=False,
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers.get("Location"), "/home")
        mock_create_event.assert_called_once()

    def test_book_appointment_rejects_stale_slot_conflict(self) -> None:
        """Reject stale booking attempts when the slot is no longer free."""
        self._seed_signed_in_session()
        payload = {
            "business_id": "crimson-cuts",
            "service_id": "fade-cut",
            "date": "2026-02-23",
            "slot_start": "09:00",
        }
        busy_periods = [
            (
                datetime(2026, 2, 23, 9, 0),
                datetime(2026, 2, 23, 9, 30),
            )
        ]
        with (
            patch(
                "Secretariat._load_user_busy_periods_for_window",
                return_value=busy_periods,
            ),
            patch(
                "Secretariat._create_google_primary_event"
            ) as mock_create_event,
        ):
            response = self.client.post(
                "/appointments",
                data=payload,
                follow_redirects=True,
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            b"Selected slot is no longer available. Pick another time.",
            response.data,
        )
        mock_create_event.assert_not_called()

    def test_book_appointment_rejects_invalid_slot_value(self) -> None:
        """Reject malformed slot values before calendar insertion."""
        self._seed_signed_in_session()
        payload = {
            "business_id": "crimson-cuts",
            "service_id": "fade-cut",
            "date": "2026-02-23",
            "slot_start": "not-a-clock",
        }
        with (
            patch(
                "Secretariat._load_user_busy_periods_for_window",
                return_value=[],
            ),
            patch(
                "Secretariat._create_google_primary_event"
            ) as mock_create_event,
        ):
            response = self.client.post(
                "/appointments",
                data=payload,
                follow_redirects=True,
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Please choose a valid time slot.", response.data)
        mock_create_event.assert_not_called()


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
