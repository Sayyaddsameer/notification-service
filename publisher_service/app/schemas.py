"""Pydantic v2 request / response schemas for the Publisher Service."""

from pydantic import BaseModel, Field


class EventPayload(BaseModel):
    """Incoming event that will be published to SNS.

    Attributes:
        eventType: Category of the event (e.g. ``order.created``).
        recipient: Target recipient identifier (email, user-id, etc.).
        data: Arbitrary payload data associated with the event.
    """

    eventType: str = Field(..., min_length=1, description="Non-empty event type identifier")
    recipient: str = Field(..., min_length=1, description="Non-empty recipient identifier")
    data: dict = Field(..., description="Arbitrary event payload data")


class EventResponse(BaseModel):
    """Successful publish acknowledgement."""

    message: str


class ErrorResponse(BaseModel):
    """Generic error envelope returned on failures."""

    detail: str
