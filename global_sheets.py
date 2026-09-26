"""
Heidi Server — Global Sheets Library endpoints

Provides table creation / existence checks and CRUD for the global_sheets table.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from database import get_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/global-sheets", tags=["global-sheets"])

# ---------------------------------------------------------------------------
# SQL for table creation
# ---------------------------------------------------------------------------

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS `global_sheets` (
    `id`              INT NOT NULL AUTO_INCREMENT,
    `name`            VARCHAR(255) NOT NULL,
    `material`        VARCHAR(100) NOT NULL DEFAULT '',
    `thickness`       DOUBLE NOT NULL DEFAULT 0,
    `sheet_width`     DOUBLE NOT NULL DEFAULT 0,
    `sheet_height`    DOUBLE NOT NULL DEFAULT 0,
    `part_count`      INT NOT NULL DEFAULT 0,
    `qty`             INT NOT NULL DEFAULT 1,
    `is_custom`       TINYINT(1) NOT NULL DEFAULT 0,
    `rel_path`        VARCHAR(1024) NOT NULL DEFAULT '',
    `created_at`      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at`      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    INDEX `idx_material`  (`material`),
    INDEX `idx_name`      (`name`),
    FULLTEXT INDEX `idx_search` (`name`, `material`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""

# Per-(material, thickness) sequence counter for the "Library Automatic"
# save naming convention (Material_S{thickness}_{WxH}_{id}) — a separate
# 1, 2, 3... sequence per distinct material+thickness pair, instead of
# sharing global_sheets' own single auto-increment `id` column across every
# sheet regardless of material/thickness.
_CREATE_COUNTER_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS `sheet_id_counters` (
    `material`   VARCHAR(100) NOT NULL,
    `thickness`  DOUBLE NOT NULL,
    `next_id`    INT NOT NULL DEFAULT 0,
    PRIMARY KEY (`material`, `thickness`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""


# ---------------------------------------------------------------------------
# Table management endpoints
# ---------------------------------------------------------------------------

@router.get("/table-exists")
def check_table_exists():
    """Check whether the global_sheets table exists in the database."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = DATABASE() AND table_name = 'global_sheets'"
        )
        count = cursor.fetchone()[0]
        cursor.close()
    finally:
        conn.close()
    return {"exists": count > 0}


@router.post("/create-table")
def create_table():
    """Create the global_sheets table if it does not already exist.

    Returns {"created": true} if a new table was made,
            {"created": false, "exists": true} if it already existed.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = DATABASE() AND table_name = 'global_sheets'"
        )
        already = cursor.fetchone()[0] > 0

        if already:
            # Migration: ensure qty column exists on legacy tables
            cursor.execute(
                "SELECT COUNT(*) FROM information_schema.columns "
                "WHERE table_schema = DATABASE() "
                "AND table_name = 'global_sheets' AND column_name = 'qty'"
            )
            has_qty = cursor.fetchone()[0] > 0
            if not has_qty:
                cursor.execute(
                    "ALTER TABLE `global_sheets` "
                    "ADD COLUMN `qty` INT NOT NULL DEFAULT 1 AFTER `part_count`"
                )
                conn.commit()
                logger.info("[global-sheets] Migration: added qty column")
            cursor.close()
            return {"created": False, "exists": True}

        cursor.execute(_CREATE_TABLE_SQL)
        conn.commit()
        cursor.close()
    finally:
        conn.close()

    logger.info("[global-sheets] Created global_sheets table")
    return {"created": True, "exists": True}


def ensure_qty_column() -> None:
    """Idempotent migration: add `qty` column to global_sheets if missing.

    Safe to call on every server start; no-op when column already exists or
    when the table itself does not exist yet.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = DATABASE() AND table_name = 'global_sheets'"
        )
        if cursor.fetchone()[0] == 0:
            cursor.close()
            return
        cursor.execute(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = DATABASE() "
            "AND table_name = 'global_sheets' AND column_name = 'qty'"
        )
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                "ALTER TABLE `global_sheets` "
                "ADD COLUMN `qty` INT NOT NULL DEFAULT 1 AFTER `part_count`"
            )
            conn.commit()
            logger.info("[global-sheets] Migration: added qty column")
        cursor.close()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class GlobalSheetIn(BaseModel):
    name: str
    material: str = ""
    thickness: float = 0
    sheet_width: float = 0
    sheet_height: float = 0
    part_count: int = 0
    qty: int = 1
    is_custom: bool = False
    rel_path: str = ""


class GlobalSheetUpdate(BaseModel):
    name: str | None = None
    material: str | None = None
    thickness: float | None = None
    sheet_width: float | None = None
    sheet_height: float | None = None
    part_count: int | None = None
    qty: int | None = None
    is_custom: bool | None = None
    rel_path: str | None = None


# ---------------------------------------------------------------------------
# CRUD endpoints
# ---------------------------------------------------------------------------

@router.get("/")
def list_global_sheets():
    """Return every row in the global_sheets table."""
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM `global_sheets` ORDER BY `name`")
        rows = cursor.fetchall()
        cursor.close()
    finally:
        conn.close()
    return rows


@router.get("/search")
def search_global_sheets(q: str = ""):
    """Full-text search on name and material."""
    if not q.strip():
        return list_global_sheets()
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM `global_sheets` "
            "WHERE MATCH(`name`, `material`) AGAINST (%s IN NATURAL LANGUAGE MODE) "
            "ORDER BY `name`",
            (q,),
        )
        rows = cursor.fetchall()
        cursor.close()
    finally:
        conn.close()
    return rows


@router.post("/")
def insert_global_sheet(sheet: GlobalSheetIn):
    """Insert a new row into the global_sheets table and return the new id."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO `global_sheets` "
            "(`name`, `material`, `thickness`, `sheet_width`, `sheet_height`, "
            " `part_count`, `qty`, `is_custom`, `rel_path`) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                sheet.name,
                sheet.material,
                sheet.thickness,
                sheet.sheet_width,
                sheet.sheet_height,
                sheet.part_count,
                sheet.qty,
                int(sheet.is_custom),
                sheet.rel_path,
            ),
        )
        conn.commit()
        new_id = cursor.lastrowid
        cursor.close()
    finally:
        conn.close()
    logger.info("[global-sheets] Inserted global sheet id=%d name=%s", new_id, sheet.name)
    return {"id": new_id}


@router.get("/counter-state")
def sheet_counter_state(material: str = Query(...), thickness: float = Query(...)):
    """
    Read-only peek at the current per-(material, thickness) sheet-id
    counter, without advancing it. Used by SaveSheetDialog's "Force ID"
    checkbox: a combo with no counter row yet (never auto-saved before)
    allows forcing any id; one that already has a row only allows forcing
    something greater than current+1 (see next_sheet_id()'s own comment).
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = DATABASE() AND table_name = 'sheet_id_counters'"
        )
        if cursor.fetchone()[0] == 0:
            cursor.close()
            return {"exists": False, "current": 0}
        cursor.execute(
            "SELECT `next_id` FROM `sheet_id_counters` WHERE `material` = %s AND `thickness` = %s",
            (material, thickness),
        )
        row = cursor.fetchone()
        cursor.close()
    finally:
        conn.close()
    if row is None:
        return {"exists": False, "current": 0}
    return {"exists": True, "current": row[0]}


@router.post("/next-id")
def next_sheet_id(
    material: str = Query(...),
    thickness: float = Query(...),
    forced_id: Optional[int] = Query(None, description="Manually assign this id instead of auto-incrementing"),
):
    """
    Atomically returns the next sequence id (1, 2, 3...) for this exact
    (material, thickness) pair, creating the counter table/row on first use.
    Used by the "Library Automatic" save naming convention
    (Material_S{thickness}_{WxH}_{id}) so every distinct material+thickness
    combination gets its own counter instead of sharing global_sheets' own
    global auto-increment id.

    Safe under concurrent callers from different client machines: the
    INSERT ... ON DUPLICATE KEY UPDATE next_id = LAST_INSERT_ID(...) idiom
    (auto path) and the conditional UPDATE/INSERT pair (forced_id path)
    below are each a single atomic statement — MySQL serializes concurrent
    writers on the same (material, thickness) row, so no two callers can
    ever be handed the same id, unlike a client-side "read current, then
    write current+1" pattern which would race.

    forced_id (optional): manually assign a specific id ("Force ID" in
    SaveSheetDialog) instead of taking the next automatic one. Only two
    cases are accepted:
      - This (material, thickness) has never been auto-saved before (no
        counter row exists yet) — any forced_id >= 1 is allowed, since
        nothing has been issued yet to collide with.
      - A counter row already exists — forced_id must be STRICTLY GREATER
        than current next_id + 1 (i.e. it must skip at least the value
        that would have been issued automatically next), so Force can
        never reuse, go backward past, or silently duplicate an
        already-issued id. Raises 409 (with the current value in the
        detail message) if forced_id doesn't satisfy this.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(_CREATE_COUNTER_TABLE_SQL)

        if forced_id is not None:
            if forced_id < 1:
                cursor.close()
                raise HTTPException(status_code=400, detail="forced_id must be >= 1")

            # Try the "row already exists" path first: a single atomic
            # conditional UPDATE that only takes effect if forced_id truly
            # skips past the natural next value — this is what stops two
            # concurrent Force saves (or a Force racing an auto save) from
            # ever landing on the same id, without needing a separate
            # lock/transaction dance.
            cursor.execute(
                "UPDATE `sheet_id_counters` SET `next_id` = %s "
                "WHERE `material` = %s AND `thickness` = %s AND `next_id` + 1 < %s",
                (forced_id, material, thickness, forced_id),
            )
            conn.commit()
            if cursor.rowcount == 1:
                new_id = forced_id
            else:
                # Either no row exists yet (first save for this combo —
                # try the insert below) or one exists but forced_id didn't
                # satisfy the "> current + 1" rule (report the current
                # value so the client can show a useful message).
                cursor.execute(
                    "SELECT `next_id` FROM `sheet_id_counters` WHERE `material` = %s AND `thickness` = %s",
                    (material, thickness),
                )
                row = cursor.fetchone()
                if row is not None:
                    cursor.close()
                    raise HTTPException(
                        status_code=409,
                        detail=f"forced_id must be greater than {row[0] + 1} for this material/thickness",
                    )
                try:
                    cursor.execute(
                        "INSERT INTO `sheet_id_counters` (`material`, `thickness`, `next_id`) "
                        "VALUES (%s, %s, %s)",
                        (material, thickness, forced_id),
                    )
                    conn.commit()
                    new_id = forced_id
                except Exception:
                    # Lost a race against another first-ever save/force for
                    # this exact combo landing between the SELECT above and
                    # this INSERT — vanishingly rare, but fail cleanly
                    # rather than silently colliding.
                    conn.rollback()
                    cursor.close()
                    raise HTTPException(
                        status_code=409,
                        detail="Another sheet was just saved for this material/thickness — try again",
                    )
            cursor.close()
        else:
            # Seed a brand-new (material, thickness) counter from however
            # many sheets of that exact combination already exist in
            # global_sheets — almost all of them saved before this
            # per-(material,thickness) counter existed, under the old
            # shared-global-id naming, so they don't carry a counter row of
            # their own. Continuing from that count instead of always
            # restarting at 1 avoids a brand-new automatic save looking
            # like a duplicate of (or lower-numbered than) sheets already
            # sitting in the library for that same material+thickness.
            # Only ever actually used on the row's first-ever insert below
            # — an existing counter row always increments from its own
            # next_id instead, ignoring this.
            cursor.execute(
                "SELECT COUNT(*) FROM `global_sheets` WHERE `material` = %s AND `thickness` = %s",
                (material, thickness),
            )
            seed = cursor.fetchone()[0] + 1

            cursor.execute(
                "INSERT INTO `sheet_id_counters` (`material`, `thickness`, `next_id`) "
                "VALUES (%s, %s, LAST_INSERT_ID(%s)) "
                "ON DUPLICATE KEY UPDATE `next_id` = LAST_INSERT_ID(`next_id` + 1)",
                (material, thickness, seed),
            )
            conn.commit()
            new_id = cursor.lastrowid
            cursor.close()
    finally:
        conn.close()
    logger.info("[global-sheets] Next id for material=%s thickness=%s -> %d", material, thickness, new_id)
    return {"id": new_id}


@router.put("/{sheet_id}")
def update_global_sheet(sheet_id: int, updates: GlobalSheetUpdate):
    """Update an existing global sheet row.  Only non-None fields are changed."""
    fields = {k: v for k, v in updates.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    # Convert bool to int for MySQL
    if "is_custom" in fields:
        fields["is_custom"] = int(fields["is_custom"])

    set_clause = ", ".join(f"`{k}` = %s" for k in fields)
    values = list(fields.values()) + [sheet_id]

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE `global_sheets` SET {set_clause} WHERE `id` = %s",
            values,
        )
        conn.commit()
        if cursor.rowcount == 0:
            cursor.close()
            raise HTTPException(status_code=404, detail="Sheet not found")
        cursor.close()
    finally:
        conn.close()

    logger.info("[global-sheets] Updated global sheet id=%d fields=%s", sheet_id, list(fields.keys()))
    return {"updated": True}


@router.delete("/{sheet_id}")
def delete_global_sheet(sheet_id: int):
    """Delete a global sheet row by id."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM `global_sheets` WHERE `id` = %s", (sheet_id,))
        conn.commit()
        if cursor.rowcount == 0:
            cursor.close()
            raise HTTPException(status_code=404, detail="Sheet not found")
        cursor.close()
    finally:
        conn.close()
    logger.info("[global-sheets] Deleted global sheet id=%d", sheet_id)
    return {"deleted": True}
