"""Service class template for business appointment offerings."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4


def utc_now() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(timezone.utc)


class Service:
    """Service class shell used by appointment scheduling."""

    id: UUID
    business_id: str | UUID
    name: str
    description: str | None
    service_duration_in_minutes: int
    buffer_before_minutes: int
    buffer_after_minutes: int
    time_step_minutes: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    def __init__(
        self,
        business_id: str | UUID,
        name: str,
        service_duration_in_minutes: int,
        description: str | None = None,
        buffer_before_minutes: int = 0,
        buffer_after_minutes: int = 0,
        time_step_minutes: int = 15,
        is_active: bool = True,
        service_id: UUID | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        """Initialize service shell with basic fields only."""
        self.id = service_id if service_id is not None else uuid4()
        self.business_id = business_id
        self.name = name
        self.description = description
        self.service_duration_in_minutes = service_duration_in_minutes
        self.buffer_before_minutes = buffer_before_minutes
        self.buffer_after_minutes = buffer_after_minutes
        self.time_step_minutes = time_step_minutes
        self.is_active = is_active
        self.created_at = created_at if created_at is not None else utc_now()
        self.updated_at = updated_at if updated_at is not None else utc_now()

    @property
    def total_duration_minutes(self) -> int:
        """Return total time block (buffer + service + buffer)."""
        raise NotImplementedError

    def validate(self) -> None:
        """Validate field values before save/scheduling."""
        raise NotImplementedError

    def to_dict(self) -> dict[str, Any]:
        """Serialize service shell into a JSON-compatible dictionary."""
        raise NotImplementedError

    def update(self, **kwargs: Any) -> None:
        """Update mutable service fields and refresh ``updated_at``."""
        raise NotImplementedError


# Backward-compatible, Service/Services
Services = Service
