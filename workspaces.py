"""
Heidi Server — Workspaces

A Workspace is a logical grouping of sheets + parts used to coordinate a
nesting effort across users:
  * `material` — everything in the workspace is the same material/thickness
                 (typical batch nesting use case).
  * `project`  — bound to a Project; mixed materials allowed.
  * `quote`    — quotation-only; can be promoted to project later.

Three tables back the feature:
  * workspaces        — registry row + path to .hwsp file
  * workspace_sheets  — references to global_sheets rows that belong here
  * workspace_parts   — parts roster (needed quantities per part)

The actual sheet payloads live inside the .hwsp ZIP on disk; the database
only stores references and metadata.
"""

from __future__ import annotations

import logging
from typing import Optional, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database import get_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


# --- schema ----------------------------------------------------------------

WorkspaceType = Literal["material", "project", "quote"]

_CREATE_WORKSPACES_SQL = """
CREATE TABLE IF NOT EXISTS `workspaces` (
    `id`           INT NOT NULL AUTO_INCREMENT,
    `name`         VARCHAR(255) NOT NULL,
    `type`         ENUM('material','project','quote') NOT NULL DEFAULT 'material',
    `material`     VARCHAR(100) NOT NULL DEFAULT '',
    `thickness`    DOUBLE NOT NULL DEFAULT 0,
    `project_id`   INT NULL,
    `customer_id`  INT NULL,
    `hwsp_path`    VARCHAR(1024) NOT NULL DEFAULT '',
    `owner`        VARCHAR(64) NOT NULL DEFAULT '',
    `notes`        TEXT NULL,
    `created_at`   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at`   TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    INDEX `idx_type`     (`type`),
    INDEX `idx_material` (`material`),
    INDEX `idx_project`  (`project_id`),
    INDEX `idx_owner`    (`owner`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""

_CREATE_SHEETS_SQL = """
CREATE TABLE IF NOT EXISTS `workspace_sheets` (
    `workspace_id`  INT NOT NULL,
    `sheet_id`      INT NOT NULL,
    `ordering`      INT NOT NULL DEFAULT 0,
    `is_draft`      TINYINT(1) NOT NULL DEFAULT 1,
    `created_at`    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`workspace_id`, `sheet_id`),
    INDEX `idx_workspace` (`workspace_id`),
    INDEX `idx_sheet`     (`sheet_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""

_CREATE_PARTS_SQL = """
CREATE TABLE IF NOT EXISTS `workspace_parts` (
    `workspace_id`  INT NOT NULL,
    `part_id`       INT NOT NULL,
    `needed_qty`    INT NOT NULL DEFAULT 1,
    `ordering`      INT NOT NULL DEFAULT 0,
    `created_at`    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`workspace_id`, `part_id`),
    INDEX `idx_workspace` (`workspace_id`),
    INDEX `idx_part`      (`part_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""


def ensure_tables() -> None:
    """Create the workspaces / workspace_sheets / workspace_parts tables."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(_CREATE_WORKSPACES_SQL)
        cursor.execute(_CREATE_SHEETS_SQL)
        cursor.execute(_CREATE_PARTS_SQL)
        conn.commit()
        cursor.close()
    finally:
        conn.close()


# --- models ----------------------------------------------------------------

class WorkspaceIn(BaseModel):
    name: str
    type: WorkspaceType = "material"
    material: str = ""
    thickness: float = 0
    project_id: Optional[int] = None
    customer_id: Optional[int] = None
    hwsp_path: str = ""
    owner: str = ""
    notes: Optional[str] = None


class WorkspaceUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[WorkspaceType] = None
    material: Optional[str] = None
    thickness: Optional[float] = None
    project_id: Optional[int] = None
    customer_id: Optional[int] = None
    hwsp_path: Optional[str] = None
    owner: Optional[str] = None
    notes: Optional[str] = None


class SheetRefIn(BaseModel):
    sheet_id: int
    ordering: int = 0
    is_draft: bool = True


class PartRefIn(BaseModel):
    part_id: int
    needed_qty: int = 1
    ordering: int = 0


# --- helpers ---------------------------------------------------------------

def _row_to_dict(row: dict) -> dict:
    """Stringify timestamps for JSON-friendly output."""
    return {
        k: (v.isoformat() if hasattr(v, "isoformat") else v)
        for k, v in row.items()
    }


# --- workspace CRUD --------------------------------------------------------

@router.get("/")
def list_workspaces(type: Optional[WorkspaceType] = None,
                    owner: Optional[str] = None):
    """List workspaces, optionally filtered by type or owner."""
    sql = "SELECT * FROM `workspaces`"
    where = []
    params: list = []
    if type:
        where.append("`type` = %s")
        params.append(type)
    if owner:
        where.append("`owner` = %s")
        params.append(owner)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY `updated_at` DESC"
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        cursor.close()
    finally:
        conn.close()
    return [_row_to_dict(r) for r in rows]


@router.get("/{workspace_id}")
def get_workspace(workspace_id: int):
    """Return one workspace row plus its sheets + parts rosters."""
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM `workspaces` WHERE `id` = %s", (workspace_id,))
        row = cursor.fetchone()
        if not row:
            cursor.close()
            raise HTTPException(status_code=404, detail="Workspace not found")
        cursor.execute(
            "SELECT ws.*, gs.`name` AS `sheet_name`, "
            "       gs.`material` AS `sheet_material`, "
            "       gs.`thickness` AS `sheet_thickness` "
            "FROM `workspace_sheets` ws "
            "LEFT JOIN `global_sheets` gs ON gs.`id` = ws.`sheet_id` "
            "WHERE ws.`workspace_id` = %s "
            "ORDER BY ws.`ordering`, ws.`sheet_id`",
            (workspace_id,),
        )
        sheets = cursor.fetchall()
        cursor.execute(
            "SELECT wp.*, gp.`name` AS `part_name`, "
            "       gp.`material` AS `part_material`, "
            "       gp.`thickness` AS `part_thickness` "
            "FROM `workspace_parts` wp "
            "LEFT JOIN `global_parts` gp ON gp.`id` = wp.`part_id` "
            "WHERE wp.`workspace_id` = %s "
            "ORDER BY wp.`ordering`, wp.`part_id`",
            (workspace_id,),
        )
        parts = cursor.fetchall()
        cursor.close()
    finally:
        conn.close()
    return {
        **_row_to_dict(row),
        "sheets": [_row_to_dict(s) for s in sheets],
        "parts":  [_row_to_dict(p) for p in parts],
    }


@router.post("/")
def create_workspace(body: WorkspaceIn):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO `workspaces`
                (`name`, `type`, `material`, `thickness`,
                 `project_id`, `customer_id`, `hwsp_path`, `owner`, `notes`)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (body.name, body.type, body.material, body.thickness,
             body.project_id, body.customer_id, body.hwsp_path,
             body.owner, body.notes),
        )
        conn.commit()
        new_id = cursor.lastrowid
        cursor.close()
    finally:
        conn.close()
    logger.info("[workspaces] Created workspace id=%d name=%s", new_id, body.name)
    return {"id": new_id}


@router.put("/{workspace_id}")
def update_workspace(workspace_id: int, body: WorkspaceUpdate):
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    set_clause = ", ".join(f"`{k}` = %s" for k in fields)
    values = list(fields.values()) + [workspace_id]
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE `workspaces` SET {set_clause} WHERE `id` = %s",
            values,
        )
        conn.commit()
        if cursor.rowcount == 0:
            cursor.close()
            raise HTTPException(status_code=404, detail="Workspace not found")
        cursor.close()
    finally:
        conn.close()
    return {"updated": True}


@router.delete("/{workspace_id}")
def delete_workspace(workspace_id: int):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM `workspace_sheets` WHERE `workspace_id` = %s",
                       (workspace_id,))
        cursor.execute("DELETE FROM `workspace_parts`  WHERE `workspace_id` = %s",
                       (workspace_id,))
        cursor.execute("DELETE FROM `workspaces`       WHERE `id` = %s",
                       (workspace_id,))
        conn.commit()
        if cursor.rowcount == 0:
            cursor.close()
            raise HTTPException(status_code=404, detail="Workspace not found")
        cursor.close()
    finally:
        conn.close()
    logger.info("[workspaces] Deleted workspace id=%d", workspace_id)
    return {"deleted": True}


# --- sheet roster ----------------------------------------------------------

@router.put("/{workspace_id}/sheets")
def replace_sheets(workspace_id: int, sheets: list[SheetRefIn]):
    """Replace the entire sheet roster for a workspace (transactional).

    Idempotent: callers compute the desired list and POST it whole.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM `workspace_sheets` WHERE `workspace_id` = %s",
                       (workspace_id,))
        for s in sheets:
            cursor.execute(
                "INSERT INTO `workspace_sheets` "
                "(`workspace_id`, `sheet_id`, `ordering`, `is_draft`) "
                "VALUES (%s, %s, %s, %s)",
                (workspace_id, s.sheet_id, s.ordering, int(s.is_draft)),
            )
        conn.commit()
        cursor.close()
    finally:
        conn.close()
    return {"ok": True, "count": len(sheets)}


@router.post("/{workspace_id}/sheets")
def add_sheet(workspace_id: int, body: SheetRefIn):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO `workspace_sheets` "
            "(`workspace_id`, `sheet_id`, `ordering`, `is_draft`) "
            "VALUES (%s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE "
            "`ordering` = VALUES(`ordering`), `is_draft` = VALUES(`is_draft`)",
            (workspace_id, body.sheet_id, body.ordering, int(body.is_draft)),
        )
        conn.commit()
        cursor.close()
    finally:
        conn.close()
    return {"ok": True}


@router.delete("/{workspace_id}/sheets/{sheet_id}")
def remove_sheet(workspace_id: int, sheet_id: int):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM `workspace_sheets` "
            "WHERE `workspace_id` = %s AND `sheet_id` = %s",
            (workspace_id, sheet_id),
        )
        conn.commit()
        cursor.close()
    finally:
        conn.close()
    return {"ok": True}


# --- part roster -----------------------------------------------------------

@router.put("/{workspace_id}/parts")
def replace_parts(workspace_id: int, parts: list[PartRefIn]):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM `workspace_parts` WHERE `workspace_id` = %s",
                       (workspace_id,))
        for p in parts:
            cursor.execute(
                "INSERT INTO `workspace_parts` "
                "(`workspace_id`, `part_id`, `needed_qty`, `ordering`) "
                "VALUES (%s, %s, %s, %s)",
                (workspace_id, p.part_id, p.needed_qty, p.ordering),
            )
        conn.commit()
        cursor.close()
    finally:
        conn.close()
    return {"ok": True, "count": len(parts)}


@router.post("/{workspace_id}/parts")
def add_part(workspace_id: int, body: PartRefIn):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO `workspace_parts` "
            "(`workspace_id`, `part_id`, `needed_qty`, `ordering`) "
            "VALUES (%s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE "
            "`needed_qty` = VALUES(`needed_qty`), `ordering` = VALUES(`ordering`)",
            (workspace_id, body.part_id, body.needed_qty, body.ordering),
        )
        conn.commit()
        cursor.close()
    finally:
        conn.close()
    return {"ok": True}


@router.delete("/{workspace_id}/parts/{part_id}")
def remove_part(workspace_id: int, part_id: int):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM `workspace_parts` "
            "WHERE `workspace_id` = %s AND `part_id` = %s",
            (workspace_id, part_id),
        )
        conn.commit()
        cursor.close()
    finally:
        conn.close()
    return {"ok": True}
