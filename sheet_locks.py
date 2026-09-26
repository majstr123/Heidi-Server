"""
Heidi Server — Sheet Locks (soft advisory locks)

Per-sheet lock used to coordinate concurrent edits across users / clients.
Heartbeat-based: a lock dies if no heartbeat is received within
``STALE_AFTER_SECONDS``.  The /heartbeat endpoint also reports any
release-request initiated by another user.

Endpoints (prefix /sheet-locks):
  GET    /{sheet_id}            -> current lock info or {"locked": false}
  POST   /{sheet_id}/acquire    -> body: {user_name, client_id, workspace_id?}
                                    returns {ok, holder?, since?}
  POST   /{sheet_id}/heartbeat  -> body: {client_id}
                                    returns {ok, release_requested_by?}
  POST   /{sheet_id}/release    -> body: {client_id}
  POST   /{sheet_id}/request-release -> body: {requester}
  POST   /{sheet_id}/take-over  -> body: {user_name, client_id, workspace_id?}
                                    forcibly grabs the lock; returns previous holder
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import Optional, Any

from database import get_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sheet-locks", tags=["sheet-locks"])


# --- pub/sub broker --------------------------------------------------------

class LockEventBroker:
    """Per-sheet pub/sub used by the WebSocket endpoint.

    publish() is callable from sync code (REST handlers run in a thread
    pool) and is thread-safe via loop.call_soon_threadsafe.
    """
    def __init__(self) -> None:
        self._subs: dict[int, set[asyncio.Queue]] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def subscribe(self, sheet_id: int) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subs.setdefault(sheet_id, set()).add(q)
        return q

    def unsubscribe(self, sheet_id: int, q: asyncio.Queue) -> None:
        s = self._subs.get(sheet_id)
        if s is not None:
            s.discard(q)
            if not s:
                self._subs.pop(sheet_id, None)

    def publish(self, sheet_id: int, event: dict[str, Any]) -> None:
        if not self._loop:
            return
        subs = self._subs.get(sheet_id)
        if not subs:
            return
        for q in list(subs):
            try:
                self._loop.call_soon_threadsafe(q.put_nowait, event)
            except RuntimeError:
                pass


broker = LockEventBroker()

# --- tunables --------------------------------------------------------------

HEARTBEAT_SECONDS    = 10
STALE_AFTER_SECONDS  = 60   # 6 missed heartbeats

# --- schema ----------------------------------------------------------------

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS `sheet_locks` (
    `sheet_id`              INT NOT NULL,
    `user_name`             VARCHAR(64) NOT NULL,
    `workspace_id`          INT NULL,
    `client_id`             VARCHAR(64) NOT NULL,
    `acquired_at`           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `heartbeat_at`          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `release_requested_by`  VARCHAR(64) NULL,
    `release_requested_at`  DATETIME NULL,
    PRIMARY KEY (`sheet_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""


def ensure_table() -> None:
    """Create the sheet_locks table if it does not exist."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(_CREATE_TABLE_SQL)
        conn.commit()
        cursor.close()
    finally:
        conn.close()


def _purge_stale(cursor) -> None:
    """Delete locks whose heartbeat is older than STALE_AFTER_SECONDS."""
    cursor.execute(
        "DELETE FROM sheet_locks "
        "WHERE heartbeat_at < (NOW() - INTERVAL %s SECOND)",
        (STALE_AFTER_SECONDS,),
    )


# --- models ----------------------------------------------------------------

class AcquireIn(BaseModel):
    user_name: str
    client_id: str
    workspace_id: Optional[int] = None


class HeartbeatIn(BaseModel):
    client_id: str


class ReleaseIn(BaseModel):
    client_id: str


class RequestReleaseIn(BaseModel):
    requester: str


# --- endpoints -------------------------------------------------------------

@router.get("/{sheet_id}")
def get_lock(sheet_id: int):
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        _purge_stale(cursor)
        conn.commit()
        cursor.execute(
            "SELECT * FROM sheet_locks WHERE sheet_id = %s",
            (sheet_id,),
        )
        row = cursor.fetchone()
        cursor.close()
    finally:
        conn.close()
    if not row:
        return {"locked": False}
    return {"locked": True, **{k: (v.isoformat() if hasattr(v, "isoformat") else v)
                                for k, v in row.items()}}


@router.post("/{sheet_id}/acquire")
def acquire(sheet_id: int, body: AcquireIn):
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        _purge_stale(cursor)
        cursor.execute(
            "SELECT * FROM sheet_locks WHERE sheet_id = %s",
            (sheet_id,),
        )
        row = cursor.fetchone()
        if row and row["client_id"] != body.client_id:
            cursor.close()
            return {
                "ok": False,
                "holder": {
                    "user_name":     row["user_name"],
                    "client_id":     row["client_id"],
                    "workspace_id":  row["workspace_id"],
                    "acquired_at":   row["acquired_at"].isoformat(),
                    "heartbeat_at":  row["heartbeat_at"].isoformat(),
                },
            }
        # Either no lock, or we already hold it -> upsert + refresh heartbeat
        cursor.execute(
            """
            INSERT INTO sheet_locks
                (sheet_id, user_name, workspace_id, client_id,
                 acquired_at, heartbeat_at)
            VALUES (%s, %s, %s, %s, NOW(), NOW())
            ON DUPLICATE KEY UPDATE
                user_name = VALUES(user_name),
                workspace_id = VALUES(workspace_id),
                client_id = VALUES(client_id),
                heartbeat_at = NOW(),
                release_requested_by = NULL,
                release_requested_at = NULL
            """,
            (sheet_id, body.user_name, body.workspace_id, body.client_id),
        )
        conn.commit()
        cursor.close()
    finally:
        conn.close()
    broker.publish(sheet_id, {
        "type": "acquired",
        "user_name": body.user_name,
        "client_id": body.client_id,
    })
    return {"ok": True}


@router.post("/{sheet_id}/heartbeat")
def heartbeat(sheet_id: int, body: HeartbeatIn):
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM sheet_locks "
            "WHERE sheet_id = %s AND client_id = %s",
            (sheet_id, body.client_id),
        )
        row = cursor.fetchone()
        if not row:
            cursor.close()
            return {"ok": False, "lost": True}
        cursor.execute(
            "UPDATE sheet_locks SET heartbeat_at = NOW() "
            "WHERE sheet_id = %s AND client_id = %s",
            (sheet_id, body.client_id),
        )
        conn.commit()
        cursor.close()
    finally:
        conn.close()
    out = {"ok": True}
    if row.get("release_requested_by"):
        out["release_requested_by"] = row["release_requested_by"]
        out["release_requested_at"] = row["release_requested_at"].isoformat()
    return out


@router.post("/{sheet_id}/release")
def release(sheet_id: int, body: ReleaseIn):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM sheet_locks "
            "WHERE sheet_id = %s AND client_id = %s",
            (sheet_id, body.client_id),
        )
        conn.commit()
        cursor.close()
    finally:
        conn.close()
    broker.publish(sheet_id, {
        "type": "released",
        "client_id": body.client_id,
    })
    return {"ok": True}


@router.post("/{sheet_id}/request-release")
def request_release(sheet_id: int, body: RequestReleaseIn):
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT user_name FROM sheet_locks WHERE sheet_id = %s",
            (sheet_id,),
        )
        row = cursor.fetchone()
        if not row:
            cursor.close()
            return {"ok": False, "reason": "not_locked"}
        cursor.execute(
            "UPDATE sheet_locks "
            "SET release_requested_by = %s, release_requested_at = NOW() "
            "WHERE sheet_id = %s",
            (body.requester, sheet_id),
        )
        conn.commit()
        cursor.close()
    finally:
        conn.close()
    broker.publish(sheet_id, {
        "type": "release_requested",
        "by": body.requester,
    })
    return {"ok": True, "holder": row["user_name"]}


@router.post("/{sheet_id}/take-over")
def take_over(sheet_id: int, body: AcquireIn):
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT user_name, client_id FROM sheet_locks WHERE sheet_id = %s",
            (sheet_id,),
        )
        prev = cursor.fetchone()
        cursor.execute(
            """
            INSERT INTO sheet_locks
                (sheet_id, user_name, workspace_id, client_id,
                 acquired_at, heartbeat_at)
            VALUES (%s, %s, %s, %s, NOW(), NOW())
            ON DUPLICATE KEY UPDATE
                user_name = VALUES(user_name),
                workspace_id = VALUES(workspace_id),
                client_id = VALUES(client_id),
                acquired_at = NOW(),
                heartbeat_at = NOW(),
                release_requested_by = NULL,
                release_requested_at = NULL
            """,
            (sheet_id, body.user_name, body.workspace_id, body.client_id),
        )
        conn.commit()
        cursor.close()
    finally:
        conn.close()
    broker.publish(sheet_id, {
        "type": "taken_over",
        "user_name": body.user_name,
        "client_id": body.client_id,
        "previous_client_id": prev["client_id"] if prev else None,
    })
    return {
        "ok": True,
        "previous_holder": prev["user_name"] if prev else None,
        "previous_client_id": prev["client_id"] if prev else None,
    }


# --- WebSocket endpoint ----------------------------------------------------

@router.websocket("/{sheet_id}/events")
async def lock_events(ws: WebSocket, sheet_id: int):
    """Push lock-state changes for `sheet_id` to subscribed clients.

    Events:
      * {"type": "acquired",          "user_name", "client_id"}
      * {"type": "released",          "client_id"}
      * {"type": "release_requested", "by"}
      * {"type": "taken_over",        "user_name", "client_id",
                                       "previous_client_id"}

    Heartbeats remain the source of truth; this channel is purely an
    instant-notification optimisation.
    """
    await ws.accept()
    q = broker.subscribe(sheet_id)
    try:
        while True:
            event = await q.get()
            await ws.send_json(event)
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.warning("[sheet_locks] WS for %s closed: %s", sheet_id, exc)
    finally:
        broker.unsubscribe(sheet_id, q)
