"""
Heidi Server — Cut List

A shared, multi-user list of parts (.cut.dxf files) waiting to be nested and
cut. Rows store a file path only (no embedded geometry) — the client that
places a row onto a sheet is responsible for handling a missing/unreachable
path, see MainWindow::placeCutListItemsOnCanvas().
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database import get_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cut-list", tags=["cut-list"])

TABLE = "cut_list_items"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class CutListItem(BaseModel):
    id: int
    name: str
    material: Optional[str] = None
    thickness: Optional[float] = None
    qty: int
    customer: str = ""
    project: str = ""
    source_path: str
    added_at: Optional[str] = None


class CutListItemAdd(BaseModel):
    """Body for POST /cut-list/items. Adding an item that already matches an
    existing row (same source_path + customer + project) increments that
    row's qty instead of creating a duplicate — see the upsert in add_item()."""
    name: str
    material: Optional[str] = None
    thickness: Optional[float] = None
    qty: int = 1
    customer: str = ""
    project: str = ""
    source_path: str


class CutListItemUpdate(BaseModel):
    """Body for PUT /cut-list/items/{id} — partial update, only fields
    present (non-None) are changed. Covers Edit Qty, Edit Material/
    Thickness, and Reassign Customer/Project from the same endpoint, since
    all three are just "change some fields on an existing row." Changing
    customer/project can collide with another row's (source_path, customer,
    project) — see update_item()'s merge-on-conflict handling."""
    material: Optional[str] = None
    thickness: Optional[float] = None
    qty: Optional[int] = None
    customer: Optional[str] = None
    project: Optional[str] = None


class CutListDecrement(BaseModel):
    amount: int = 1


class CutListDecrementResult(BaseModel):
    id: int
    deleted: bool
    removed: int          # how much was actually removed (may be less than
                           # requested if another user already took some)
    remaining_qty: int = 0


# ---------------------------------------------------------------------------
# Ensure table exists
# ---------------------------------------------------------------------------

def ensure_tables():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS `{TABLE}` (
                `id`          INT UNSIGNED NOT NULL AUTO_INCREMENT,
                `name`        VARCHAR(255) NOT NULL,
                `material`    VARCHAR(100) DEFAULT NULL,
                `thickness`   DOUBLE DEFAULT NULL,
                `qty`         INT NOT NULL DEFAULT 1,
                `customer`    VARCHAR(255) NOT NULL DEFAULT '',
                `project`     VARCHAR(255) NOT NULL DEFAULT '',
                `source_path` VARCHAR(1024) NOT NULL,
                `added_at`    DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (`id`),
                -- Dedupe key: re-adding the same file under the same
                -- customer/project accumulates qty instead of duplicating a
                -- row. source_path is indexed at a prefix since VARCHAR(1024)
                -- exceeds MySQL's default max key-part length.
                UNIQUE KEY `uq_source_customer_project` (`source_path`(255), `customer`, `project`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        conn.commit()
        cursor.close()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/items", response_model=list[CutListItem])
def list_items():
    """Return every row, oldest first."""
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            f"SELECT id, name, material, thickness, qty, customer, project, "
            f"source_path, added_at FROM `{TABLE}` ORDER BY added_at"
        )
        rows = cursor.fetchall()
        cursor.close()
    finally:
        conn.close()
    for r in rows:
        r["added_at"] = r["added_at"].isoformat() if r.get("added_at") else None
    return [CutListItem(**r) for r in rows]


@router.post("/items", response_model=CutListItem)
def add_item(body: CutListItemAdd):
    """Add (or accumulate qty onto) one cut-list row."""
    if body.qty < 1:
        raise HTTPException(status_code=400, detail="qty must be at least 1")

    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            f"INSERT INTO `{TABLE}` "
            f"(name, material, thickness, qty, customer, project, source_path) "
            f"VALUES (%s, %s, %s, %s, %s, %s, %s) "
            f"ON DUPLICATE KEY UPDATE "
            f"qty = qty + VALUES(qty), "
            f"name = VALUES(name), "
            f"material = VALUES(material), "
            f"thickness = VALUES(thickness)",
            [body.name, body.material, body.thickness, body.qty,
             body.customer, body.project, body.source_path],
        )
        conn.commit()
        cursor.execute(
            f"SELECT id, name, material, thickness, qty, customer, project, "
            f"source_path, added_at FROM `{TABLE}` "
            f"WHERE source_path = %s AND customer = %s AND project = %s LIMIT 1",
            [body.source_path, body.customer, body.project],
        )
        row = cursor.fetchone()
        cursor.close()
    finally:
        conn.close()
    if row is None:
        raise HTTPException(status_code=500, detail="Insert succeeded but row not found")
    row["added_at"] = row["added_at"].isoformat() if row.get("added_at") else None
    return CutListItem(**row)


@router.put("/items/{item_id}", response_model=CutListItem)
def update_item(item_id: int, body: CutListItemUpdate):
    """Partial update — only the fields present (non-None) in the body are
    changed. If a customer/project change would collide with another row's
    (source_path, customer, project) — the table's own dedupe key — merges
    into that existing row instead of erroring: adds this row's qty onto
    the target row's, then deletes this one, mirroring the same "re-adding
    the same part accumulates qty" behavior POST /items already has."""
    fields = body.model_dump(exclude_none=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(f"SELECT * FROM `{TABLE}` WHERE id = %s FOR UPDATE", [item_id])
        row = cursor.fetchone()
        if row is None:
            conn.rollback()
            cursor.close()
            raise HTTPException(status_code=404, detail="Row not found")

        changing_key = "customer" in fields or "project" in fields
        if changing_key:
            new_customer = fields.get("customer", row["customer"])
            new_project = fields.get("project", row["project"])
            cursor.execute(
                f"SELECT id, qty FROM `{TABLE}` "
                f"WHERE source_path = %s AND customer = %s AND project = %s AND id != %s LIMIT 1",
                [row["source_path"], new_customer, new_project, item_id],
            )
            conflict = cursor.fetchone()
            if conflict is not None:
                merged_qty = conflict["qty"] + fields.get("qty", row["qty"])
                cursor.execute(f"UPDATE `{TABLE}` SET qty = %s WHERE id = %s",
                                [merged_qty, conflict["id"]])
                cursor.execute(f"DELETE FROM `{TABLE}` WHERE id = %s", [item_id])
                conn.commit()
                cursor.execute(
                    f"SELECT id, name, material, thickness, qty, customer, project, "
                    f"source_path, added_at FROM `{TABLE}` WHERE id = %s",
                    [conflict["id"]],
                )
                row = cursor.fetchone()
                cursor.close()
                row["added_at"] = row["added_at"].isoformat() if row.get("added_at") else None
                return CutListItem(**row)

        set_clause = ", ".join(f"`{k}` = %s" for k in fields)
        cursor.execute(f"UPDATE `{TABLE}` SET {set_clause} WHERE id = %s",
                        [*fields.values(), item_id])
        conn.commit()
        cursor.execute(
            f"SELECT id, name, material, thickness, qty, customer, project, "
            f"source_path, added_at FROM `{TABLE}` WHERE id = %s",
            [item_id],
        )
        row = cursor.fetchone()
        cursor.close()
    finally:
        conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Row not found")
    row["added_at"] = row["added_at"].isoformat() if row.get("added_at") else None
    return CutListItem(**row)


@router.put("/items/{item_id}/decrement", response_model=CutListDecrementResult)
def decrement_item(item_id: int, body: CutListDecrement):
    """Atomically remove up to `amount` from a row's qty. Removes fewer than
    requested (never negative) if another user already took some since the
    caller last saw this row. Deletes the row once qty reaches 0 — a fully
    picked-up entry drops off the list rather than lingering at 0."""
    if body.amount < 1:
        raise HTTPException(status_code=400, detail="amount must be at least 1")

    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(f"SELECT qty FROM `{TABLE}` WHERE id = %s FOR UPDATE", [item_id])
        row = cursor.fetchone()
        if row is None:
            conn.rollback()
            cursor.close()
            raise HTTPException(status_code=404, detail="Row not found")

        before = row["qty"]
        removed = min(before, body.amount)
        after = before - removed

        if after <= 0:
            cursor.execute(f"DELETE FROM `{TABLE}` WHERE id = %s", [item_id])
            conn.commit()
            cursor.close()
            return CutListDecrementResult(id=item_id, deleted=True, removed=removed, remaining_qty=0)

        cursor.execute(f"UPDATE `{TABLE}` SET qty = %s WHERE id = %s", [after, item_id])
        conn.commit()
        cursor.close()
        return CutListDecrementResult(id=item_id, deleted=False, removed=removed, remaining_qty=after)
    finally:
        conn.close()


@router.delete("/items/{item_id}")
def delete_item(item_id: int):
    """Manually remove a row outright (regardless of its qty)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM `{TABLE}` WHERE id = %s", [item_id])
        affected = cursor.rowcount
        conn.commit()
        cursor.close()
    finally:
        conn.close()
    if affected == 0:
        raise HTTPException(status_code=404, detail="Row not found")
    return {"deleted": item_id}
