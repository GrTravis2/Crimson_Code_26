"""Appointment class template for scheduled service instances."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4


def utc_now() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(timezone.utc)


# similar to services in the sense that:
# appointment has a service_id field to link to the service being scheduled
#
class Appointment:
    """Appointment class shell used by scheduling and calendar adapters."""

    id: UUID
    business_id: str | UUID
    service_id: str | UUID
    user_id: str | UUID
    start_at: datetime
    end_at: datetime
    status: str
    notes: str | None
    external_event_id: str | None
    created_at: datetime
    updated_at: datetime

    def __init__(
        self,
        business_id: str | UUID,
        service_id: str | UUID,
        user_id: str | UUID,
        start_at: datetime,
        end_at: datetime,
        status: str = "pending",
        notes: str | None = None,
        external_event_id: str | None = None,
        appointment_id: UUID | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        """Initialize appointment shell with basic fields only."""
        self.id = appointment_id if appointment_id is not None else uuid4()
        self.business_id = business_id
        self.service_id = service_id
        self.user_id = user_id
        self.start_at = start_at
        self.end_at = end_at
        self.status = status
        self.notes = notes
        self.external_event_id = external_event_id
        self.created_at = created_at if created_at is not None else utc_now()
        self.updated_at = updated_at if updated_at is not None else utc_now()

    @property
    def duration_minutes(self) -> int:
        """Return scheduled appointment length in minutes."""
        raise NotImplementedError

    def validate(self) -> None:
        """Validate appointment fields before save/scheduling."""
        raise NotImplementedError

    def to_dict(self) -> dict[str, Any]:
        """Serialize appointment shell into a JSON-compatible dictionary."""
        raise NotImplementedError

    def update(self, **kwargs: Any) -> None:
        """Update mutable appointment fields and refresh ``updated_at``."""
        raise NotImplementedError

    def overlaps(self, other: Appointment) -> bool:
        """Check whether this appointment overlaps another."""
        raise NotImplementedError


# Backward-compatible, Appointment/Appointments
Appointments = Appointment
