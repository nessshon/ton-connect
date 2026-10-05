from codecs import getincrementaldecoder

from .message import EventMessage

_UTF8_DECODER = getincrementaldecoder("utf-8")


class EventDecoder:
    """Incremental SSE stream decoder."""

    def __init__(self) -> None:
        """Initialize decoder with empty buffer."""
        self._decoder = _UTF8_DECODER()
        self._buffer: str = ""

    def reset(self) -> None:
        """Reset decoder and buffer state."""
        self._decoder = _UTF8_DECODER()
        self._buffer = ""

    def feed(self, chunk: bytes) -> list[EventMessage]:
        """Decode a chunk and return any complete events.

        :param chunk: Raw bytes from the SSE stream.
        :return: List of parsed events (maybe empty).
        """
        text = self._decoder.decode(chunk)
        if not text:
            return []

        buf = (self._buffer + text).replace("\r\n", "\n")
        pending = "\r" if buf.endswith("\r") else ""
        buf = buf[: len(buf) - len(pending)].replace("\r", "\n")
        events: list[EventMessage] = []

        while True:
            sep = buf.find("\n\n")
            if sep == -1:
                break

            raw_event = buf[:sep]
            buf = buf[sep + 2 :]

            if raw_event.strip():
                events.append(EventMessage.parse(raw_event))

        self._buffer = buf + pending
        return events

    def flush(self) -> list[EventMessage]:
        """Discard an unterminated trailing event, as the SSE spec requires at end of stream.

        :return: Always an empty list.
        """
        self.reset()
        return []
