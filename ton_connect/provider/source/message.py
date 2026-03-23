from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class EventMessage:
    """Parsed SSE event message."""

    event: str = "message"
    """Event type name."""
    data: str | None = None
    """Event payload, or ``None``."""
    event_id: str | None = None
    """Event identifier, or ``None``."""

    @classmethod
    def parse(cls, raw: str) -> EventMessage:
        """Parse a raw SSE event block into an ``EventMessage``.

        :param raw: Raw SSE text block (lines separated by newlines).
        :return: Parsed event message.
        """
        event: str = "message"
        data_parts: list[str] = []
        event_id: str | None = None

        for line in raw.splitlines():
            if not line or line.startswith(":"):
                continue

            field, sep, value = line.partition(":")
            if not sep:
                continue

            if value.startswith(" "):
                value = value[1:]

            if field == "data":
                data_parts.append(value)
            elif field == "event":
                event = value or "message"
            elif field == "id":
                event_id = value or None

        data = "\n".join(data_parts) if data_parts else None
        return cls(event=event, data=data, event_id=event_id)
