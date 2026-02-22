"""Calendar class to be used for scheduling."""

import itertools
from datetime import datetime, timedelta
from typing import Any, Self

from secretariat.google_calendar.calendar_event import CalendarEvent

type Appointment = None


class GoogleCalendar:
    """Calendar Class which contains a persons booked events."""

    def __init__(self, calendar_id: str) -> None:
        """Create a Calendar Object from google api credentials."""
        self.id = calendar_id

    def get_calendar_events(
        self,
        service: Any,
        start: datetime,
        end: datetime,
    ) -> list[CalendarEvent]:
        """Get your calendar events in ascending order from start to end."""
        events_result = (
            service.events()
            .list(
                calendarId=self.id,
                timeMin=start.isoformat(),
                timeMax=end.isoformat(),
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events: list[CalendarEvent] = events_result.get("items", [])
        return events

    def find_common_availability(
        self,
        client_events: list[CalendarEvent],
        server_events: list[CalendarEvent],
        start: datetime,
        end: datetime,
    ) -> set[datetime]:
        """Return shared availability for two calendars."""
        step = timedelta(minutes=15)
        current = start
        free_slots: set[datetime] = set()
        while current <= end:
            free_slots.add(current)
            current += step

        for e in itertools.chain(client_events, server_events):
            if (dt := e["start"]["datetime"]) in free_slots:
                free_slots.discard(dt)
            if (dt := e["end"]["datetime"]) in free_slots:
                free_slots.discard(dt)

        return free_slots

    def schedule_appt(
        self,
        appt: Appointment,
        server: Self,
    ) -> list[CalendarEvent]:
        """Schedule the optimal appt time against a businesses calendar."""
        raise NotImplementedError

    def _scheduler_helper(
        self, client: list[CalendarEvent], server: list[CalendarEvent]
    ) -> list[CalendarEvent]:
        """Find compatible times between the two available dates."""
        raise NotImplementedError

    # may need to add more helper methods for interacting with Google Calendar
