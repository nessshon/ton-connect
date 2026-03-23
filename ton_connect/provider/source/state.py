from enum import Enum


class ReadyState(int, Enum):
    """SSE connection state."""

    CONNECTING = 0
    """Connection in progress (0)."""
    OPEN = 1
    """Connected and receiving events (1)."""
    CLOSED = 2
    """Connection closed (2)."""
