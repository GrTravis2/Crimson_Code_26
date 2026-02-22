"""Calendar class to be used for scheduling."""

from datetime import datetime
from typing import Self

from googleapiclient.discovery import build

type CalEvent = tuple[float, float]
type Appointment = None


class GoogleCalendar:
    """Calendar Class which contains a persons booked events."""

    def __init__(self, creds) -> None:
        """Create a Calendar Object from google api credentials."""
        self.service = build("Calendar", "V3", credentials=creds)

    def get_available_times(self, start_time, end_time) -> list:
        """Given a datetime range return all available times."""
        raise NotImplementedError

    def _get_booked_times(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> list:
        """Given a datetime range return all booked times."""
        events_result = (
            self.service.events()
            .list(
                calendarId="primary",
                timeMin=start_time.isoformat(),
                timeMax=end_time.isoformat(),
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = events_result.get("items", [])
        return events

    def schedule_appt(self, appt: Appointment, server: Self) -> list[CalEvent]:
        """Schedule the optimal appt time against a businesses calendar."""
        raise NotImplementedError

    def _scheduler_helper(
        self, client: list[CalEvent], server: list[CalEvent]
    ) -> list[CalEvent]:
        """Find compatible times between the two available dates."""
        raise NotImplementedError

    # may need to add more helper methods for interacting with Google Calendar
