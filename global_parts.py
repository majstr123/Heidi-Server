"""
Heidi Server — Global Parts Library endpoints

Provides table creation / existence checks and CRUD for the global_parts table.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from database import get_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/global-parts", tags=["global-parts"])

# ---------------------------------------------------------------------------
# SQL for table creation
# ---------------------------------------------------------------------------

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS `global_parts` (
    `id`              INT NOT NULL AUTO_INCREMENT,
    `name`            VARCHAR(255) NOT NULL,
    `customer`        VARCHAR(255) NOT NULL DEFAULT '',
    `material`        VARCHAR(100) NOT NULL DEFAULT '',
    `thickness`       DOUBLE NOT NULL DEFAULT 0,
    `project`         VARCHAR(100) NOT NULL DEFAULT '',
    `geometry_hash`   CHAR(64) NOT NULL DEFAULT '',
    `bbox_width`      DOUBLE NOT NULL DEFAULT 0,
    `bbox_height`     DOUBLE NOT NULL DEFAULT 0,
    `entity_count`    INT NOT NULL DEFAULT 0,
    `source_path`     VARCHAR(1024) NOT NULL DEFAULT '',
    `hprt_path`       VARCHAR(1024) NOT NULL DEFAULT '',
    `created_at`      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at`      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    INDEX `idx_customer`       (`customer`),
    INDEX `idx_geometry_hash`  (`geometry_hash`),
    INDEX `idx_name`           (`name`),
    FULLTEXT INDEX `idx_search` (`name`, `customer`, `material`, `project`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""


# ---------------------------------------------------------------------------
# Table management endpoints
# ---------------------------------------------------------------------------

@router.get("/table-exists")
def check_table_exists():
    """Check whether the global_parts table exists in the database."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = DATABASE() AND table_name = 'global_parts'"
        )
        count = cursor.fetchone()[0]
        cursor.close()
    finally:
        conn.close()
    return {"exists": count > 0}


@router.post("/create-table")
def create_table():
    """Create the global_parts table if it does not already exist.

    Returns {"created": true} if a new table was made,
            {"created": false, "exists": true} if it already existed.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()

        # Check first
        cursor.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = DATABASE() AND table_name = 'global_parts'"
        )
        already = cursor.fetchone()[0] > 0

        if already:
            cursor.close()
            return {"created": False, "exists": True}

        cursor.execute(_CREATE_TABLE_SQL)
        conn.commit()
        cursor.close()
    finally:
        conn.close()

    logger.info("[global-parts] Created global_parts table")
    return {"created": True, "exists": True}


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class GlobalPartIn(BaseModel):
    name: str
    customer: str = ""
    material: str = ""
    thickness: float = 0
    project: str = ""
    geometry_hash: str = ""
    bbox_width: float = 0
    bbox_height: float = 0
    entity_count: int = 0
    source_path: str = ""
    hprt_path: str = ""


class GlobalPartUpdate(BaseModel):
    name: str | None = None
    customer: str | None = None
    material: str | None = None
    thickness: float | None = None
    project: str | None = None
    geometry_hash: str | None = None
    bbox_width: float | None = None
    bbox_height: float | None = None
    entity_count: int | None = None
    source_path: str | None = None
    hprt_path: str | None = None


# ---------------------------------------------------------------------------
# CRUD endpoints
# ---------------------------------------------------------------------------

@router.get("/")
def list_global_parts():
    """Return every row in the global_parts table."""
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM `global_parts` ORDER BY `name`")
        rows = cursor.fetchall()
        cursor.close()
    finally:
        conn.close()
    return rows


@router.post("/")
def insert_global_part(part: GlobalPartIn):
    """Insert a new row into the global_parts table and return the new id."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO `global_parts` "
            "(`name`, `customer`, `material`, `thickness`, `project`, "
            " `geometry_hash`, `bbox_width`, `bbox_height`, `entity_count`, "
            " `source_path`, `hprt_path`) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                part.name,
                part.customer,
                part.material,
                part.thickness,
                part.project,
                part.geometry_hash,
                part.bbox_width,
                part.bbox_height,
                part.entity_count,
                part.source_path,
                part.hprt_path,
            ),
        )
        conn.commit()
        new_id = cursor.lastrowid
        cursor.close()
    finally:
        conn.close()
    logger.info("[global-parts] Inserted global part id=%d name=%s", new_id, part.name)
    return {"id": new_id}


@router.put("/{part_id}")
def update_global_part(part_id: int, updates: GlobalPartUpdate):
    """Update an existing global part row.  Only non-None fields are changed."""
    fields = {k: v for k, v in updates.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_clause = ", ".join(f"`{k}` = %s" for k in fields)
    values = list(fields.values()) + [part_id]

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE `global_parts` SET {set_clause} WHERE `id` = %s",
            values,
        )
        conn.commit()
        if cursor.rowcount == 0:
            cursor.close()
            raise HTTPException(status_code=404, detail="Part not found")
        cursor.close()
    finally:
        conn.close()

    logger.info("[global-parts] Updated global part id=%d fields=%s", part_id, list(fields.keys()))
    return {"updated": True}


@router.delete("/{part_id}")
def delete_global_part(part_id: int):
    """Delete a global part row by id."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM `global_parts` WHERE `id` = %s", (part_id,))
        conn.commit()
        if cursor.rowcount == 0:
            cursor.close()
            raise HTTPException(status_code=404, detail="Part not found")
        cursor.close()
    finally:
        conn.close()

    logger.info("[global-parts] Deleted global part id=%d", part_id)
    return {"deleted": True}
