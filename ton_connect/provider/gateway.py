import asyncio
import base64
import logging
import random
import typing as t
from contextlib import suppress

import aiohttp
from yarl import URL

from ..exceptions import TonConnectError
from ..models import IncomingMessage
from ..utils import add_path_to_url
from .source import (
    EventMessage,
    EventSource,
    ReadyState,
)
from .storage import ProviderStorage

logger = logging.getLogger(__name__)


class Gateway:
    """SSE bridge gateway for a single TonConnect bridge connection."""

    SSE_PATH = "events"
    POST_PATH = "message"
    HEARTBEAT_MESSAGE = "heartbeat"

    RECONNECT_ATTEMPTS: int = 150
    RECONNECT_DELAY: float = 2.0
    SSE_READ_TIMEOUT: float = 90.0

    def __init__(
        self,
        *,
        session_id: str,
        bridge_url: str,
        storage: ProviderStorage,
        headers: dict[str, str] | None = None,
        on_gateway_message: t.Callable[[IncomingMessage, str], t.Awaitable[None]],
        on_gateway_error: t.Callable[[Exception], t.Awaitable[None]],
    ) -> None:
        """Initialize the gateway.

        :param session_id: SSE client identifier.
        :param bridge_url: Bridge base URL.
        :param storage: Provider storage.
        :param headers: Extra HTTP headers, or ``None``.
        :param on_gateway_message: Async callback for incoming messages.
        :param on_gateway_error: Async callback for errors.
        """
        self._session_id = session_id
        self._bridge_url = bridge_url
        self._storage = storage

        self._headers = headers or {}
        self._on_gateway_message = on_gateway_message
        self._on_gateway_error = on_gateway_error

        self._http_session: aiohttp.ClientSession | None = None
        self._event_source: EventSource | None = None

        self._connect_lock = asyncio.Lock()
        self._reconnect_task: asyncio.Task[None] | None = None
        self._reconnect_attempts = 0
        self._rejected: aiohttp.ClientResponseError | None = None

        self._closed = False
        self._paused = False

    @property
    def bridge_url(self) -> str:
        """Bridge URL this gateway is connected to."""
        return self._bridge_url

    @property
    def ready_state(self) -> ReadyState:
        """Current SSE connection state."""
        if self._closed:
            return ReadyState.CLOSED
        es = self._event_source
        if es is None:
            return ReadyState.CLOSED
        return es.ready_state

    async def register_session(self, timeout: float = 12.0) -> None:
        """Open an SSE session with the bridge.

        :param timeout: Connection timeout in seconds.
        :raises TonConnectError: If the gateway is closed.
        """
        self._reconnect_attempts = 0
        await self._register_session(timeout)

    async def _register_session(self, timeout: float = 12.0) -> None:
        """Open an SSE session without resetting the reconnect budget."""
        if self._closed:
            raise TonConnectError("Bridge is closed")
        if self._paused:
            return

        async with self._connect_lock:
            state = self.ready_state
            if state in (ReadyState.OPEN, ReadyState.CONNECTING):
                return

            await self._close_event_source()

            last_event_id = await self._storage.get_last_event_id()
            if self._closed or self._paused:  # race condition protection
                return  # type: ignore[unreachable]
            url = self._make_open_url(last_event_id)
            session = await self._ensure_session()
            es = EventSource(
                session=session,
                url=url,
                headers=self._headers,
                on_message=self._on_event_source_message,
                on_error=self._on_event_source_error,
            )
            self._event_source = es

            self._rejected = None
            try:
                await es.open(timeout)
            except BaseException as exc:
                await self._close_event_source()
                # A 4xx, like the Cloudflare or Akamai 403 in front of some bridges, answers every retry the same;
                # 429 is the bridge limit of streams per IP and frees up.
                if isinstance(exc, aiohttp.ClientResponseError) and exc.status < 500 and exc.status != 429:
                    self._rejected = exc
                raise

    async def send(
        self,
        message: bytes,
        receiver: str,
        topic: str,
        *,
        ttl: int = 300,
        attempts: int = 10,
        delay: float = 5.0,
    ) -> None:
        """Send an encrypted message to a wallet via the bridge.

        :param message: Encrypted message bytes.
        :param receiver: Hex-encoded wallet public key.
        :param topic: Bridge topic (RPC method name).
        :param ttl: Message time-to-live in seconds.
        :param attempts: Attempts for the HTTP POST; only network errors, 5xx and 429 are retried.
        :param delay: Delay between retries in seconds.
        :raises TonConnectError: If the gateway is closed, the bridge rejects the message or all attempts fail.
        """
        if self._closed:
            raise TonConnectError("Bridge is closed")

        url = self._make_send_url(
            receiver=receiver,
            topic=topic,
            ttl=ttl,
        )
        body = base64.b64encode(message).decode()

        error = TonConnectError("Bridge send failed")
        for attempt in range(attempts):
            if attempt:
                await asyncio.sleep(delay)
            session = await self._ensure_session()
            try:
                async with session.post(str(url), data=body) as resp:
                    if 200 <= resp.status < 300:
                        return
                    error = TonConnectError(f"Bridge send failed, status {resp.status}")
                    # The bridge answers 4xx to a message it will never take: bad params, ttl above 300, oversized body.
                    if resp.status < 500 and resp.status != 429:
                        raise error
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                if self._closed:
                    raise TonConnectError("Bridge is closed") from exc
                error = TonConnectError(f"Bridge send failed: {exc!r}")
                error.__cause__ = exc
        raise error

    async def pause(self) -> None:
        """Pause SSE listening and cancel any pending reconnect."""
        self._paused = True

        task, self._reconnect_task = self._reconnect_task, None
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await task

        await self._close_event_source()

    async def unpause(self) -> None:
        """Resume SSE listening after a pause."""
        if self._closed or not self._paused:
            return
        self._paused = False
        try:
            await self.register_session()
        except Exception:
            await self.reconnect()

    async def close(self) -> None:
        """Permanently close the gateway and release resources."""
        self._closed = True
        self._paused = True

        task, self._reconnect_task = self._reconnect_task, None
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await task

        await self._close_event_source()
        await self._close_session()

    async def reconnect(self) -> None:
        """Schedule a background reconnect within the attempt budget.

        Does nothing if the gateway is closed, paused or already reconnecting. A stream the bridge rejected with
        4xx other than 429 is not retried: the gateway reports it once.
        """
        if self._closed or self._paused:
            return

        task = self._reconnect_task
        if task is not None and not task.done():
            return

        async def _runner() -> None:
            await self._close_event_source()
            last_error: Exception | None = None
            while self._rejected is None and self._reconnect_attempts < self.RECONNECT_ATTEMPTS:
                self._reconnect_attempts += 1
                await asyncio.sleep(self.RECONNECT_DELAY * random.uniform(0.5, 1.5))
                if self._closed or self._paused:
                    return
                try:
                    await self._register_session()
                    return
                except Exception as exc:
                    last_error = exc

            if self._closed or self._paused:
                return
            if self._rejected is not None:
                message = f"Bridge rejected the stream: {self._rejected}"
            else:
                reason = last_error or "stream closed without events"
                message = f"Bridge reconnect failed after {self.RECONNECT_ATTEMPTS} attempts: {reason}"
            logger.warning("%s: %s", self._bridge_url, message)
            with suppress(Exception):
                await self._on_gateway_error(TonConnectError(message))

        task = asyncio.create_task(_runner())
        self._reconnect_task = task

    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Return the HTTP session, creating one if needed."""
        if self._closed:
            raise TonConnectError("Bridge is closed")
        if self._http_session is None or self._http_session.closed:
            self._http_session = aiohttp.ClientSession(
                headers=self._headers,
                timeout=aiohttp.ClientTimeout(
                    total=None,
                    sock_connect=30,
                    sock_read=self.SSE_READ_TIMEOUT,
                ),
            )
        return self._http_session

    async def _close_event_source(self) -> None:
        """Close and discard the current ``EventSource``."""
        es, self._event_source = self._event_source, None
        if es is None:
            return
        with suppress(Exception):
            await es.close()

    async def _close_session(self) -> None:
        """Close and discard the HTTP session."""
        session, self._http_session = self._http_session, None
        if session is None:
            return
        with suppress(Exception):
            await session.close()

    async def _on_event_source_error(self, exc: Exception) -> None:
        """Handle SSE-level errors, triggering reconnect as needed."""
        if self._closed or self._paused:
            return

        if self.ready_state in (ReadyState.OPEN, ReadyState.CONNECTING):
            with suppress(Exception):
                await self._on_gateway_error(exc)
            return

        await self.reconnect()

    async def _on_event_source_message(self, e: EventMessage) -> None:
        """Handle a raw SSE event, parsing and dispatching it."""
        if e.data is not None or e.event == self.HEARTBEAT_MESSAGE:
            self._reconnect_attempts = 0
        if e.data is None or e.data == self.HEARTBEAT_MESSAGE:
            return
        if self._closed or self._paused:
            return

        try:
            msg = IncomingMessage.model_validate_json(e.data)
        except Exception as exc:
            with suppress(Exception):
                err = TonConnectError(f"Bridge message parse failed, message: `{e.data}`, error: {exc}")
                await self._on_gateway_error(err)
        else:
            try:
                await self._on_gateway_message(msg, self._bridge_url)
            except Exception as exc:
                with suppress(Exception):
                    await self._on_gateway_error(exc)

        if e.event_id:
            await self._storage.store_last_event_id(e.event_id)

    def _make_open_url(self, last_event_id: str | None = None) -> URL:
        """Build the SSE endpoint URL."""
        query: dict[str, str] = {"client_id": self._session_id}
        if last_event_id:
            query["last_event_id"] = last_event_id
        base = add_path_to_url(self._bridge_url, self.SSE_PATH)
        return URL(base).with_query(query)

    def _make_send_url(self, receiver: str, topic: str, ttl: int) -> URL:
        """Build the POST endpoint URL for sending messages."""
        query: dict[str, str] = {
            "client_id": self._session_id,
            "to": receiver,
            "ttl": str(ttl),
            "topic": topic,
        }
        base = add_path_to_url(self._bridge_url, self.POST_PATH)
        return URL(base).with_query(query)
