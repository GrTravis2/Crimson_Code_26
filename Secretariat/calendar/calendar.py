"""Calendar class to be used for scheduling."""

from typing import Self

type CalEvent = tuple[float, float]
type Appointment = None


class Calendar:
    """Calendar Class which contains a persons booked events."""

    service: object  # Google API service object to make requests to

    def get_available_times(self, start_time, end_time) -> list[CalEvent]:
        """Given a datetime range return all available times."""
        raise NotImplementedError

    def _get_booked_times(self, start_time, end_time) -> list[CalEvent]:
        """Given a datetime range return all booked times."""
        raise NotImplementedError

    def schedule_appt(self, appt: Appointment, server: Self) -> list[CalEvent]:
        """Schedule the optimal appt time against a businesses calendar."""
        raise NotImplementedError

    def _scheduler_helper(
        self, client: list[CalEvent], server: list[CalEvent]
    ) -> list[CalEvent]:
        """Find compatible times between the two available dates."""
        raise NotImplementedError

    # may need to add more helper methods for interacting with Google Calendar
