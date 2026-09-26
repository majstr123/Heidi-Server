"""
Heidi Server — Main Application

A REST API that exposes the cutting_tickets queue data.

Run with:
    python main.py
Or:
    uvicorn main:app --host 0.0.0.0 --port 8080 --reload

API docs are auto-generated at:
    http://localhost:8080/docs   (Swagger UI — interactive)
    http://localhost:8080/redoc  (ReDoc — read-only)
"""

from __future__ import annotations

import asyncio
import datetime
import logging
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from config import settings
from database import get_connection
from files import router as files_router
from lantek import router as lantek_router, background_cache_loop
from projects import router as projects_router, tags_router, ensure_project_order_items_columns
from customers import router as customers_router, postal_router
from global_parts import router as global_parts_router
from global_sheets import router as global_sheets_router, ensure_qty_column as ensure_global_sheets_qty_column
from sheet_technology import router as sheet_technology_router, ensure_tables as ensure_sheet_tech_tables, backfill_technology_xml
from sheet_locks import router as sheet_locks_router, ensure_table as ensure_sheet_locks_table, broker as sheet_locks_broker
from workspaces import router as workspaces_router, ensure_tables as ensure_workspaces_tables
from cut_list import router as cut_list_router, ensure_tables as ensure_cut_list_tables

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan — start / stop background tasks
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("[main] Starting background cache loop …")
    try:
        ensure_global_sheets_qty_column()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[main] global_sheets qty migration skipped: %s", exc)
    sheet_locks_broker.set_loop(asyncio.get_running_loop())
    cache_task = asyncio.create_task(background_cache_loop())
    yield
    logger.info("[main] Shutting down background cache loop …")
    cache_task.cancel()
    try:
        await cache_task
    except asyncio.CancelledError:
        pass


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Heidi Server",
    version="1.0.0",
    description="REST API for Heidi cutting queue and file serving",
    lifespan=lifespan,
)

# Mount endpoint routers
app.include_router(files_router)
app.include_router(lantek_router)
app.include_router(projects_router)
app.include_router(tags_router)
app.include_router(customers_router)
app.include_router(postal_router)
app.include_router(global_parts_router)
app.include_router(global_sheets_router)
app.include_router(sheet_technology_router)
app.include_router(sheet_locks_router)
app.include_router(workspaces_router)
app.include_router(cut_list_router)

# Ensure sheet_material_thickness table exists (merged — includes bundle columns)
ensure_sheet_tech_tables()
backfill_technology_xml()
ensure_sheet_locks_table()
ensure_cut_list_tables()
ensure_workspaces_tables()
ensure_project_order_items_columns()
# ensure_material_price_density_ref() is defined further down in this file
# (near _table_exists()) and called immediately after its own definition,
# since it isn't defined yet at this point in the module.


# ---------------------------------------------------------------------------
# Version endpoint (for client update checks)
# ---------------------------------------------------------------------------

@app.get("/version")
def get_version(app: str = Query("sm", description="App identifier: 'sm', 'pe', or 'nest'")):
    """Return the current application version advertised by the server.

    Clients poll this periodically and show a notification when
    their local version is older.

    Use ?app=sm for Sheet Manager, ?app=pe for Project Explorer,
    ?app=nest for Heidi-Nest.
    """
    if app.lower() == "pe":
        ver = settings.pe_version
    elif app.lower() == "nest":
        ver = settings.nest_version
    else:
        ver = settings.sm_version
    return {
        "version": ver,
        "download_hint": settings.app_download_hint,
    }


# ---------------------------------------------------------------------------
# Server paths (so clients can discover shared roots)
# ---------------------------------------------------------------------------

@app.get("/settings/paths")
def get_paths():
    """Return the server-configured shared directory paths.

    Clients use these to:
    - resolve project documentation / administration roots
    - know if direct filesystem access is possible (compare local vs server path)
    """
    return {
        "projects_root": settings.projects_root,
        "projects_documentation_root": settings.projects_documentation_root,
        "report_dir": settings.report_dir,
        "cnc_path": settings.cnc_path,
        "lantek_files_root": settings.lantek_files_root,
    }


# ---------------------------------------------------------------------------
# Pydantic models  (define the shape of request/response JSON)
# ---------------------------------------------------------------------------
class QueueRow(BaseModel):
    """One row from cutting_tickets, returned as JSON.

    Field order matches the DB column order:
      0:Id  1:Sheet  2:Qty  3:Customer  4:Machine  5:Create_Date
      6:Completion_Time  7:Project  8:CNC  9:Report
      10:Completed_Flag  11:ReportData  12:Remanant_scrapped
    """
    Id: int
    Sheet: Optional[str] = None
    Qty: Optional[str] = None
    Customer: Optional[str] = None
    Machine: Optional[str] = None
    Create_Date: Optional[str] = None
    Completion_Time: Optional[str] = None
    Project: Optional[str] = None
    CNC: Optional[str] = None
    Report: Optional[str] = None
    Completed_Flag: Optional[str] = None
    ReportData: Optional[str] = None
    Remanant_scrapped: Optional[bool] = None


class QueueResponse(BaseModel):
    """Wrapper returned by GET /queue."""
    total: int
    rows: list[QueueRow]


class ScrappedUpdate(BaseModel):
    """Body for PATCH /queue/{id}/scrapped."""
    scrapped: bool


class StatusUpdate(BaseModel):
    """Body for PATCH /queue/{id}/status."""
    status_tag: str


class QueueCreate(BaseModel):
    """Body for POST /queue — insert a new queue row."""
    Sheet: Optional[str] = None
    Qty: Optional[str] = None
    Customer: Optional[str] = None
    Machine: Optional[str] = None
    Completion_Time: Optional[str] = None
    Project: Optional[str] = None
    CNC: Optional[str] = None
    Report: Optional[str] = None
    Completed_Flag: Optional[str] = None
    ReportData: Optional[str] = None


class QueueUpdate(BaseModel):
    """Body for PATCH /queue/{id} — update arbitrary fields."""
    Sheet: Optional[str] = None
    Qty: Optional[str] = None
    Customer: Optional[str] = None
    Machine: Optional[str] = None
    Completion_Time: Optional[str] = None
    Project: Optional[str] = None
    CNC: Optional[str] = None
    Report: Optional[str] = None
    Completed_Flag: Optional[str] = None
    ReportData: Optional[str] = None


# ---------------------------------------------------------------------------
# Helper: build WHERE clause from filter parameters
# ---------------------------------------------------------------------------
def _build_filter(
    sheet: str | None,
    customer: str | None,
    project: str | None,
    date: str | None,
    machine: str | None,
    unfinished: bool,
    limit: int | None,
) -> tuple[str, list]:
    """Return (where_clause, params) for the queue query."""
    conditions: list[str] = []
    params: list = []

    if sheet:
        conditions.append("`Sheet` LIKE %s")
        params.append(f"%{sheet}%")
    if customer:
        conditions.append("`Customer` LIKE %s")
        params.append(f"%{customer}%")
    if project:
        conditions.append("`Project` LIKE %s")
        params.append(f"%{project}%")
    if date:
        conditions.append("CAST(`Create_Date` AS CHAR) LIKE %s")
        params.append(f"%{date}%")
    if machine:
        conditions.append("`Machine` LIKE %s")
        params.append(f"%{machine}%")
    if unfinished:
        conditions.append("(`Completion_Time` IS NULL OR `Completion_Time` = '')")

    # Limit to last N rows (same logic as the Qt client)
    if limit and limit > 0:
        conditions.append(
            f"`Id` >= (SELECT MAX(`Id`) FROM `{settings.db_table}`) - %s + 1"
        )
        params.append(limit)

    where = " AND ".join(conditions)
    if where:
        where = "WHERE " + where
    return where, params


def _row_to_dict(columns: list[str], row: tuple) -> dict:
    """Convert a raw DB row tuple into a dict, handling special types."""
    d = {}
    for col, val in zip(columns, row):
        if col in ("Create_Date", "Completion_Time") and val is not None:
            if isinstance(val, (datetime.date, datetime.datetime)):
                d[col] = val.isoformat()
            else:
                d[col] = str(val)
            continue
        if col == "Remanant_scrapped":
            # BINARY column → convert to bool (non-null non-zero = True)
            if val is None:
                d[col] = None
            elif isinstance(val, (bytes, bytearray)):
                d[col] = any(b != 0 for b in val)
            else:
                d[col] = bool(val)
        elif isinstance(val, (datetime.date, datetime.datetime)):
            d[col] = val.isoformat()
        elif isinstance(val, bytes):
            d[col] = val.decode("utf-8", errors="replace")
        else:
            d[col] = val
    return d


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/")
def root():
    """Health check."""
    return {"status": "ok", "service": "Heidi Server"}


@app.get("/queue", response_model=QueueResponse)
def get_queue(
    sheet: Optional[str] = Query(None, description="Filter by Sheet name"),
    customer: Optional[str] = Query(None, description="Filter by Customer"),
    project: Optional[str] = Query(None, description="Filter by Project"),
    date: Optional[str] = Query(None, description="Filter by Create_Date"),
    machine: Optional[str] = Query(None, description="Filter by Machine"),
    unfinished: bool = Query(False, description="Only show unfinished tickets"),
    limit: Optional[int] = Query(None, description="Show last N rows", ge=1),
):
    """
    Fetch queue rows from cutting_tickets.

    All filter parameters are optional.  Without any filters, returns all rows.
    Mirrors exactly the same filtering the Qt client does locally.

    Example:
        GET /queue?limit=100&unfinished=true&machine=Laser1
    """
    where, params = _build_filter(sheet, customer, project, date, machine, unfinished, limit)
    query = f"SELECT * FROM `{settings.db_table}` {where} ORDER BY `Id` ASC"

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        columns = [desc[0] for desc in cursor.description]
        raw_rows = cursor.fetchall()
        cursor.close()
    finally:
        conn.close()

    rows = [QueueRow(**_row_to_dict(columns, r)) for r in raw_rows]
    return QueueResponse(total=len(rows), rows=rows)


@app.get("/queue/{row_id}", response_model=QueueRow)
def get_queue_row(row_id: int):
    """Fetch a single queue row by Id."""
    query = f"SELECT * FROM `{settings.db_table}` WHERE `Id` = %s"
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query, [row_id])
        columns = [desc[0] for desc in cursor.description]
        row = cursor.fetchone()
        cursor.close()
    finally:
        conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail=f"Row {row_id} not found")
    return QueueRow(**_row_to_dict(columns, row))


@app.patch("/queue/{row_id}/scrapped")
def update_scrapped(row_id: int, body: ScrappedUpdate):
    """
    Mark or unmark a row's Remanant_scrapped flag.

    Body: {"scrapped": true}  or  {"scrapped": false}
    """
    if body.scrapped:
        query = f"UPDATE `{settings.db_table}` SET `Remanant_scrapped` = 1 WHERE `Id` = %s"
    else:
        query = f"UPDATE `{settings.db_table}` SET `Remanant_scrapped` = NULL WHERE `Id` = %s"

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query, [row_id])
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
    finally:
        conn.close()

    if affected == 0:
        raise HTTPException(status_code=404, detail=f"Row {row_id} not found")
    return {"ok": True, "id": row_id, "scrapped": body.scrapped}


@app.patch("/queue/{row_id}/status")
def update_status(row_id: int, body: StatusUpdate):
    """
    Update the status tag (Completed_Flag) of a queue row.

    Body: {"status_tag": "Finished"}  or  {"status_tag": ""}
    """
    query = f"UPDATE `{settings.db_table}` SET `Completed_Flag` = %s WHERE `Id` = %s"
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query, [body.status_tag, row_id])
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
    finally:
        conn.close()

    if affected == 0:
        raise HTTPException(status_code=404, detail=f"Row {row_id} not found")
    return {"ok": True, "id": row_id, "status_tag": body.status_tag}


@app.post("/queue", response_model=QueueRow, status_code=201)
def create_queue_row(body: QueueCreate):
    """
    Insert a new row into the queue.

    Only non-null fields from the body are inserted; the DB auto-generates the Id.
    Returns the newly created row.
    """
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(status_code=400, detail="No fields provided")

    columns = ", ".join(f"`{c}`" for c in fields)
    placeholders = ", ".join(["%s"] * len(fields))
    values = list(fields.values())

    insert_sql = f"INSERT INTO `{settings.db_table}` ({columns}) VALUES ({placeholders})"
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(insert_sql, values)
        conn.commit()
        new_id = cursor.lastrowid
        cursor.close()
    finally:
        conn.close()

    return get_queue_row(new_id)


@app.patch("/queue/{row_id}", response_model=QueueRow)
def update_queue_row(row_id: int, body: QueueUpdate):
    """
    Update one or more fields on an existing queue row.

    Only non-null fields in the body are updated.
    Returns the updated row.
    """
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(status_code=400, detail="No fields provided")

    set_clause = ", ".join(f"`{c}` = %s" for c in fields)
    values = list(fields.values()) + [row_id]

    query = f"UPDATE `{settings.db_table}` SET {set_clause} WHERE `Id` = %s"
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query, values)
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
    finally:
        conn.close()

    if affected == 0:
        raise HTTPException(status_code=404, detail=f"Row {row_id} not found")
    return get_queue_row(row_id)


@app.delete("/queue/{row_id}")
def delete_queue_row(row_id: int):
    """Delete a single queue row by Id."""
    query = f"DELETE FROM `{settings.db_table}` WHERE `Id` = %s"
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query, [row_id])
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
    finally:
        conn.close()

    if affected == 0:
        raise HTTPException(status_code=404, detail=f"Row {row_id} not found")
    return {"ok": True, "deleted_id": row_id}


@app.delete("/queue")
def delete_queue_rows(ids: list[int] = Query(..., description="List of Ids to delete")):
    """
    Delete multiple queue rows.

    Example: DELETE /queue?ids=100&ids=101&ids=102
    """
    if not ids:
        raise HTTPException(status_code=400, detail="No IDs provided")

    placeholders = ",".join(["%s"] * len(ids))
    query = f"DELETE FROM `{settings.db_table}` WHERE `Id` IN ({placeholders})"
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query, ids)
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
    finally:
        conn.close()

    return {"ok": True, "deleted_count": affected}


# ---------------------------------------------------------------------------
# Tags endpoint
# ---------------------------------------------------------------------------

@app.get("/tags", response_model=list[str])
def get_tags():
    """
    Fetch all distinct status tags from ticket_tags.
    Used by the context menu "Set status tag" action.
    """
    query = "SELECT DISTINCT `Tag` FROM `ticket_tags` ORDER BY `Tag`"
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query)
        tags = [row[0].strip() for row in cursor.fetchall() if row[0] and row[0].strip()]
        cursor.close()
    finally:
        conn.close()
    return tags


# ---------------------------------------------------------------------------
# Material price endpoints (MySQL — same DB as queue)
# ---------------------------------------------------------------------------

class MaterialPrice(BaseModel):
    Material: Optional[str] = None
    Price: Optional[float] = None
    density: Optional[float] = None


def _sanitize_material_row(d: dict) -> dict:
    """Convert European comma-decimal strings (e.g. '1,2') to proper floats."""
    for key in ("Price", "density"):
        val = d.get(key)
        if isinstance(val, str):
            try:
                d[key] = float(val.replace(",", "."))
            except (ValueError, AttributeError):
                d[key] = None
    return d


def _row_to_dict(columns: list[str], row: tuple) -> dict:
    """Convert a raw DB row tuple into a dict, handling special types."""
    d = {}
    for col, val in zip(columns, row):
        if col in ("Create_Date", "Completion_Time") and val is not None:
            if isinstance(val, (datetime.date, datetime.datetime)):
                d[col] = val.isoformat()
            else:
                d[col] = str(val)
            continue
        if col == "Remanant_scrapped":
            if val is None:
                d[col] = None
            elif isinstance(val, (bytes, bytearray)):
                d[col] = any(b != 0 for b in val)
            else:
                d[col] = bool(val)
        elif isinstance(val, (datetime.date, datetime.datetime)):
            d[col] = val.isoformat()
        elif isinstance(val, bytes):
            d[col] = val.decode("utf-8", errors="replace")
        else:
            d[col] = val
    return d


def _table_exists(table_name: str) -> bool:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SHOW TABLES LIKE %s", [table_name])
        row = cursor.fetchone()
        cursor.close()
    finally:
        conn.close()
    return row is not None


def ensure_material_price_density_ref():
    """Idempotent migration: adds material_price.density_ref if missing —
    a self-referencing name (another row's Material) a variant can point to
    instead of repeating the same density per family member, e.g.
    AISI316_Pol/AISI316_Br/AISI316_Reb all -> "AISI316". Same
    try/ALTER-TABLE/except pattern as sheet_technology.py's ensure_tables()."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "ALTER TABLE `material_price` ADD COLUMN `density_ref` VARCHAR(50) DEFAULT NULL"
            )
            conn.commit()
        except Exception:
            pass  # column already exists
        cursor.close()
    finally:
        conn.close()


ensure_material_price_density_ref()


@app.get("/materials", response_model=list[MaterialPrice])
def get_materials():
    """
    List all sheet materials with prices and densities.
    Used by NestingReportWindow's material price combo box.
    """
    query = (
        f"SELECT Material, Price, density "
        f"FROM `{settings.db_material_table}` "
        f"WHERE LOWER(TRIM(`Type`)) = 'sheet' "
        f"ORDER BY Material"
    )
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query)
        columns = [desc[0] for desc in cursor.description]
        rows = []
        seen = set()
        for row in cursor.fetchall():
            d = _sanitize_material_row(dict(zip(columns, row)))
            key = (d.get("Material") or "").upper().strip()
            if key in seen:
                continue
            seen.add(key)
            rows.append(MaterialPrice(**d))
        cursor.close()
    finally:
        conn.close()
    return rows


@app.get("/materials/lookup", response_model=Optional[MaterialPrice])
def lookup_material(
    material: str = Query(..., description="Material name to look up"),
):
    """
    Look up price and density for a specific material name.
    Used by NestingReportWindow to auto-set price when material is detected.
    """
    query = (
        f"SELECT Material, Price, density "
        f"FROM `{settings.db_material_table}` "
        f"WHERE UPPER(TRIM(Material)) = UPPER(TRIM(%s)) "
        f"ORDER BY CASE WHEN LOWER(TRIM(`Type`)) = 'sheet' THEN 0 ELSE 1 END "
        f"LIMIT 1"
    )
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query, [material])
        columns = [desc[0] for desc in cursor.description]
        row = cursor.fetchone()
        cursor.close()
    finally:
        conn.close()
    if row is None:
        return None
    return MaterialPrice(**_sanitize_material_row(dict(zip(columns, row))))


@app.get("/materials/items")
def get_material_items(
    category: str = Query(..., description="profile|sheet|items|fasteners|services|2d_cut"),
):
    """Return distinct item/material names for autocomplete lists."""
    cat = category.strip().lower()
    conn = get_connection()
    source = "material"
    try:
        cursor = conn.cursor()
        if cat == "profile":
            cursor.execute(
                "SELECT DISTINCT Item FROM material "
                "WHERE LOWER(COALESCE(Type, '')) LIKE '%profile%' "
                "ORDER BY Item"
            )
            items = [r[0] for r in cursor.fetchall() if r[0]]
        elif cat == "sheet":
            cursor.execute(
                "SELECT DISTINCT Item FROM material "
                "WHERE LOWER(COALESCE(Type, '')) LIKE '%sheet%' "
                "ORDER BY Item"
            )
            items = [r[0] for r in cursor.fetchall() if r[0]]
        elif cat == "items":
            cursor.execute(
                "SELECT DISTINCT Item FROM material "
                "WHERE Item IS NOT NULL AND Item <> '' "
                "AND (LOWER(COALESCE(Type, '')) = 'item' OR LOWER(COALESCE(Type, '')) = 'items') "
                "ORDER BY Item"
            )
            items = [r[0] for r in cursor.fetchall() if r[0]]
        elif cat == "profile-materials":
            source = "material_price"
            cursor.execute(
                "SELECT DISTINCT Material FROM material_price "
                "WHERE Material IS NOT NULL AND Material <> '' "
                "AND LOWER(COALESCE(Type, '')) = 'profile' "
                "ORDER BY Material"
            )
            items = [r[0] for r in cursor.fetchall() if r[0]]
        elif cat == "sheet-materials":
            source = "material_price"
            cursor.execute(
                "SELECT DISTINCT Material FROM material_price "
                "WHERE Material IS NOT NULL AND Material <> '' "
                "AND LOWER(COALESCE(Type, '')) LIKE '%sheet%' "
                "ORDER BY Material"
            )
            items = [r[0] for r in cursor.fetchall() if r[0]]
        elif cat == "fasteners":
            if _table_exists("fasteners"):
                source = "fasteners"
                cursor.execute(
                    "SELECT DISTINCT name FROM fasteners "
                    "WHERE name IS NOT NULL AND name <> '' "
                    "AND COALESCE(is_active, 1) = 1 "
                    "ORDER BY name"
                )
                items = [r[0] for r in cursor.fetchall() if r[0]]
            else:
                cursor.execute(
                    "SELECT DISTINCT Item FROM material "
                    "WHERE Item IS NOT NULL AND Item <> '' "
                    "AND (LOWER(COALESCE(Type, '')) = 'fastener' "
                    "     OR LOWER(COALESCE(Type, '')) = 'fasner' "
                    "     OR LOWER(COALESCE(Type, '')) = 'fastners') "
                    "ORDER BY Item"
                )
                items = [r[0] for r in cursor.fetchall() if r[0]]
        elif cat == "services":
            # Single source of truth: the `material` table's Type='service'
            # rows, editable via "Edit Material Database" — NOT the old
            # dedicated `services` table (left in place, unused, for now).
            cursor.execute(
                "SELECT DISTINCT Item FROM material "
                "WHERE Item IS NOT NULL AND Item <> '' "
                "AND LOWER(COALESCE(Type, '')) = 'service' "
                "ORDER BY Item"
            )
            items = [r[0] for r in cursor.fetchall() if r[0]]
        elif cat == "2d_cut":
            # 2D cutting machine rates (e.g. "razrez - laser N2/O2") — a
            # distinct Type from generic 'service' rows so a shop with
            # multiple 2D cutting machines can list/select among just these.
            cursor.execute(
                "SELECT DISTINCT Item FROM material "
                "WHERE Item IS NOT NULL AND Item <> '' "
                "AND LOWER(COALESCE(Type, '')) = '2d_cut' "
                "ORDER BY Item"
            )
            items = [r[0] for r in cursor.fetchall() if r[0]]
        else:
            raise HTTPException(status_code=400, detail="Invalid category")
        cursor.close()
    finally:
        conn.close()

    return {"source": source, "items": items}


@app.get("/materials/by-item")
def get_material_by_item(
    item: str = Query(..., description="Item name to look up"),
):
    """Return material row details for a given Item."""
    query = (
        "SELECT Id, Material, Type, `Measure-Quantity`, Unit, Em, orderUnit, Price, `CrossSection-Thickness` "
        "FROM material WHERE Item = %s LIMIT 1"
    )
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query, [item])
        columns = [desc[0] for desc in cursor.description]
        row = cursor.fetchone()
        cursor.close()
    finally:
        conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail=f"Item '{item}' not found")
    return _row_to_dict(columns, row)


@app.get("/materials/price")
def get_material_price(
    material: str = Query(..., description="Material name"),
    type: str = Query(..., description="profile|sheet|service"),
):
    """Return price/unit (and density for sheet) for a material.

    density resolution: a row's own `density` wins if set; otherwise, if
    `density_ref` names another material_price row (e.g. "AISI316_Pol" ->
    "AISI316" for a surface-finish variant of the same base alloy), that
    row's density is used instead — avoids re-entering the same density for
    every family member. Always returned under the plain `density` key so
    existing clients don't need to know about density_ref at all.
    """
    t = type.strip().lower()
    if t == "sheet":
        type_clause = "LOWER(COALESCE(Type, '')) LIKE %s"
        params = [material, "%sheet%"]
    elif t == "profile":
        type_clause = "LOWER(COALESCE(Type, '')) = 'profile'"
        params = [material]
    elif t == "service":
        type_clause = "LOWER(COALESCE(Type, '')) = 'service'"
        params = [material]
    else:
        raise HTTPException(status_code=400, detail="Invalid type")

    query = (
        "SELECT Price, Unit, density, density_ref FROM material_price "
        "WHERE Material = %s AND " + type_clause + " ORDER BY Id ASC LIMIT 1"
    )
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        columns = [desc[0] for desc in cursor.description]
        row = cursor.fetchone()

        if row is not None:
            result = _row_to_dict(columns, row)
            if not result.get("density") and result.get("density_ref"):
                cursor.execute(
                    "SELECT density FROM material_price WHERE Material = %s "
                    "ORDER BY Id ASC LIMIT 1",
                    [result["density_ref"]],
                )
                ref_row = cursor.fetchone()
                if ref_row is not None:
                    result["density"] = ref_row[0]
            result.pop("density_ref", None)
        else:
            result = None
        cursor.close()
    finally:
        conn.close()

    if result is None:
        return {}
    return _sanitize_material_row(result)


@app.get("/fasteners/lookup")
def get_fastener_by_name(
    name: str = Query(..., description="Fastener name"),
):
    """Return fastener price details and source table."""
    if _table_exists("fasteners"):
        query = (
            "SELECT Id, price, price_unit, pack_qty FROM fasteners "
            "WHERE name = %s AND COALESCE(is_active, 1) = 1 "
            "ORDER BY Id DESC LIMIT 1"
        )
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, [name])
            columns = [desc[0] for desc in cursor.description]
            row = cursor.fetchone()
            cursor.close()
        finally:
            conn.close()
        if row is None:
            return {"source": "fasteners"}
        data = _row_to_dict(columns, row)
        data["source"] = "fasteners"
        return data

    query = (
        "SELECT Price FROM material "
        "WHERE Item = %s AND (LOWER(COALESCE(Type, '')) = 'fastener' "
        " OR LOWER(COALESCE(Type, '')) = 'fasner' OR LOWER(COALESCE(Type, '')) = 'fastners') "
        "ORDER BY Id DESC LIMIT 1"
    )
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query, [name])
        columns = [desc[0] for desc in cursor.description]
        row = cursor.fetchone()
        cursor.close()
    finally:
        conn.close()
    if row is None:
        return {"source": "material"}
    data = _row_to_dict(columns, row)
    data["source"] = "material"
    return data


@app.patch("/fasteners/{fastener_id}/price")
def update_fastener_price(
    fastener_id: int,
    price: float = Query(..., description="Price per piece"),
    unit: str = Query("€/pc", description="Price unit"),
):
    if not _table_exists("fasteners"):
        raise HTTPException(status_code=400, detail="Fasteners table not available")
    query = "UPDATE fasteners SET price = %s, price_unit = %s WHERE Id = %s"
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query, [price, unit, fastener_id])
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
    finally:
        conn.close()
    if affected == 0:
        raise HTTPException(status_code=404, detail=f"Fastener {fastener_id} not found")
    return {"ok": True, "updated_id": fastener_id}


@app.get("/services/lookup")
def get_service_by_name(
    name: str = Query(..., description="Service name"),
):
    """Return service price details from the `material` table (Item, Type='service')."""
    query = (
        "SELECT Price, Unit FROM material "
        "WHERE Item = %s AND LOWER(COALESCE(Type, '')) = 'service' "
        "ORDER BY Id DESC LIMIT 1"
    )
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query, [name])
        columns = [desc[0] for desc in cursor.description]
        row = cursor.fetchone()
        cursor.close()
    finally:
        conn.close()
    if row is None:
        return {"source": "material"}
    data = _row_to_dict(columns, row)
    data["source"] = "material"
    return data


@app.post("/materials/items/price")
def upsert_item_price(
    item: str = Query(..., description="Item name"),
    price: float = Query(..., description="Unit price"),
):
    """Insert or update a material item price (Type=item)."""
    query_find = (
        "SELECT Id, Price FROM material "
        "WHERE Item = %s AND (LOWER(COALESCE(Type, '')) = 'item' OR LOWER(COALESCE(Type, '')) = 'items') "
        "ORDER BY Id DESC LIMIT 1"
    )
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query_find, [item])
        row = cursor.fetchone()
        if row:
            existing_id = row[0]
            cursor.execute(
                "UPDATE material SET Price = %s, Em = %s, Type = %s WHERE Id = %s",
                [price, "€/pc", "item", existing_id],
            )
            conn.commit()
            cursor.close()
            return {"ok": True, "updated_id": existing_id}
        cursor.execute(
            "INSERT INTO material (Item, Material, `Measure-Quantity`, Unit, Price, Em, Type, orderUnit) "
            "VALUES (%s, NULL, %s, NULL, %s, %s, %s, NULL)",
            [item, 0.0, price, "€/pc", "item"],
        )
        conn.commit()
        new_id = cursor.lastrowid
        cursor.close()
    finally:
        conn.close()

    return {"ok": True, "created_id": new_id}


# ---------------------------------------------------------------------------
# Material database editor (ProjectExplorer's "Edit Material Database")
# Full CRUD on the raw `material` table — every column, every row. Distinct
# from the narrower /materials/* endpoints above (price lookups, per-item
# fetches), which only ever return a curated subset for a specific purpose.
# ---------------------------------------------------------------------------

_MATERIAL_ROW_COLUMNS = (
    "Id, Item, Material, `Measure-Quantity`, Unit, Price, Em, "
    "`CrossSection-Thickness`, SolidWorksKey, Type, orderUnit"
)


class MaterialRowBody(BaseModel):
    # Field names match the real (hyphenated) DB columns via alias, since
    # Python identifiers can't contain hyphens.
    Item: str
    Material: Optional[str] = None
    MeasureQuantity: float = Field(default=0.0, alias="Measure-Quantity")
    Unit: Optional[str] = None
    Price: Optional[float] = None
    Em: Optional[str] = None
    CrossSectionThickness: Optional[float] = Field(default=None, alias="CrossSection-Thickness")
    SolidWorksKey: Optional[str] = None
    Type: Optional[str] = None
    orderUnit: Optional[str] = None

    class Config:
        populate_by_name = True


@app.get("/materials/all", tags=["materials"])
def get_all_material_rows():
    """Full `material` table listing for the Edit Material Database dialog."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(f"SELECT {_MATERIAL_ROW_COLUMNS} FROM material ORDER BY Item")
        columns = [desc[0] for desc in cursor.description]
        rows = [_row_to_dict(columns, row) for row in cursor.fetchall()]
        cursor.close()
    finally:
        conn.close()
    return rows


@app.post("/materials/row", tags=["materials"])
def create_material_row(body: MaterialRowBody):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO material (Item, Material, `Measure-Quantity`, Unit, Price, Em, "
            "`CrossSection-Thickness`, SolidWorksKey, Type, orderUnit) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            [body.Item, body.Material, body.MeasureQuantity, body.Unit, body.Price,
             body.Em, body.CrossSectionThickness, body.SolidWorksKey, body.Type, body.orderUnit],
        )
        conn.commit()
        new_id = cursor.lastrowid
        cursor.close()
    finally:
        conn.close()
    return {"Id": new_id}


@app.put("/materials/row/{row_id}", tags=["materials"])
def update_material_row(row_id: int, body: MaterialRowBody):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE material SET Item=%s, Material=%s, `Measure-Quantity`=%s, Unit=%s, "
            "Price=%s, Em=%s, `CrossSection-Thickness`=%s, SolidWorksKey=%s, Type=%s, orderUnit=%s "
            "WHERE Id=%s",
            [body.Item, body.Material, body.MeasureQuantity, body.Unit, body.Price,
             body.Em, body.CrossSectionThickness, body.SolidWorksKey, body.Type, body.orderUnit, row_id],
        )
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
    finally:
        conn.close()
    if affected == 0:
        raise HTTPException(status_code=404, detail=f"Material row {row_id} not found")
    return {"ok": True}


@app.delete("/materials/row/{row_id}", tags=["materials"])
def delete_material_row(row_id: int):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM material WHERE Id=%s", [row_id])
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
    finally:
        conn.close()
    return {"deleted": affected > 0}


@app.post("/services/price")
def upsert_service_price(
    name: str = Query(..., description="Service name"),
    price: float = Query(..., description="Unit price"),
    unit: str = Query(..., description="Price unit"),
):
    """Insert or update a service price — a `material` row (Item=name, Type='service'),
    same convention as /materials/items/price uses for Type='item'."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT Id FROM material WHERE Item = %s AND LOWER(COALESCE(Type, '')) = 'service' "
            "ORDER BY Id DESC LIMIT 1",
            [name],
        )
        row = cursor.fetchone()
        if row:
            existing_id = row[0]
            cursor.execute(
                "UPDATE material SET Price = %s, Unit = %s WHERE Id = %s",
                [price, unit, existing_id],
            )
            conn.commit()
            cursor.close()
            return {"ok": True, "updated_id": existing_id}
        cursor.execute(
            "INSERT INTO material (Item, Material, `Measure-Quantity`, Unit, Price, Em, Type, orderUnit) "
            "VALUES (%s, NULL, %s, %s, %s, %s, 'service', %s)",
            [name, 0.0, unit, price, unit, unit],
        )
        conn.commit()
        new_id = cursor.lastrowid
        cursor.close()
        return {"ok": True, "created_id": new_id}
    finally:
        conn.close()



# Display order for the sheet_sizes picker (Settings ▸ Nesting ▸ Standard
# Sizes' Move Up/Down). Deliberately NOT a column added onto the legacy
# sheet_sizes table itself -- that table is shared with whatever external
# (Lantek-descended) process still owns it, and ALTERing it is a bigger risk
# than this whole feature is worth. A tiny separate keyed-by-value table
# instead, same "new table alongside the legacy one, don't touch it"
# precedent global_sheets.py already used for the sheet library. A size
# with no row here just sorts after every explicitly-ordered one, by its
# own Length/Width -- the same order the picker always used before this
# existed.
_CREATE_ORDER_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS `sheet_size_order` (
    `length`     DOUBLE NOT NULL,
    `width`      DOUBLE NOT NULL,
    `sort_order` INT NOT NULL,
    PRIMARY KEY (`length`, `width`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""


@app.get("/sheet-sizes")
def get_sheet_sizes(prefix: str = Query("", description="Optional prefix filter")):
    """Return distinct sheet sizes from sheet_sizes table, in their saved
    display order (sheet_size_order), falling back to Length/Width for
    anything never explicitly reordered."""
    if not _table_exists("sheet_sizes"):
        return {"items": []}

    prefix = (prefix or "").strip()
    where_clause = ""
    params: list[str] = []
    if prefix:
        where_clause = "WHERE CAST(s.`Length` AS CHAR) LIKE %s OR CAST(s.`Width` AS CHAR) LIKE %s"
        params = [f"{prefix}%", f"{prefix}%"]

    query = (
        "SELECT CAST(s.`Length` AS CHAR) AS len_txt, "
        "CAST(s.`Width` AS CHAR) AS wid_txt, "
        "CONCAT(CAST(s.`Length` AS CHAR), ' x ', CAST(s.`Width` AS CHAR)) AS dim "
        "FROM sheet_sizes s "
        "LEFT JOIN sheet_size_order o ON o.`length` = s.`Length` AND o.`width` = s.`Width` "
        f"{where_clause} "
        "GROUP BY s.`Length`, s.`Width` "
        "ORDER BY COALESCE(MIN(o.sort_order), 999999999), s.`Length`, s.`Width`"
    )
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(_CREATE_ORDER_TABLE_SQL)
        cursor.execute(query, params)
        items = []
        for row in cursor.fetchall():
            items.append({"len_txt": row[0], "wid_txt": row[1], "dim": row[2]})
        cursor.close()
    finally:
        conn.close()

    return {"items": items}


class SheetSizeIn(BaseModel):
    length: float
    width: float


@app.post("/sheet-sizes")
def add_sheet_size(size: SheetSizeIn):
    """Add a (Length, Width) row to sheet_sizes -- the Settings ▸ Nesting ▸
    Standard Sizes list writes here directly rather than keeping a separate
    Heidi-owned table, per the user's own call: one list, not two. Only
    sets Length/Width; any other column (e.g. Sheet type) is left to its
    own default/NULL."""
    if size.length <= 0 or size.width <= 0:
        raise HTTPException(status_code=400, detail="length and width must be > 0")
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO `sheet_sizes` (`Length`, `Width`) VALUES (%s, %s)",
            (size.length, size.width),
        )
        conn.commit()
        cursor.close()
    finally:
        conn.close()
    return {"ok": True}


@app.delete("/sheet-sizes")
def delete_sheet_size(length: float = Query(...), width: float = Query(...)):
    """Delete every sheet_sizes row matching this exact (Length, Width) pair
    -- the GET endpoint above already GROUPs BY (Length, Width), so the
    picker only ever shows one entry per pair even if duplicate rows (e.g.
    one per Sheet type) exist underneath; removing "this size" means
    removing all of them, not just one arbitrary row. Also drops its
    display-order row, if any, so a later re-add doesn't inherit a stale
    position."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM `sheet_sizes` WHERE `Length` = %s AND `Width` = %s",
            (length, width),
        )
        conn.commit()
        deleted = cursor.rowcount > 0
        cursor.execute(_CREATE_ORDER_TABLE_SQL)
        cursor.execute(
            "DELETE FROM `sheet_size_order` WHERE `length` = %s AND `width` = %s",
            (length, width),
        )
        conn.commit()
        cursor.close()
    finally:
        conn.close()
    if not deleted:
        raise HTTPException(status_code=404, detail="No such sheet size.")
    return {"ok": True}


class SheetSizeOrderEntry(BaseModel):
    length: float
    width: float


class SheetSizeOrderIn(BaseModel):
    sizes: list[SheetSizeOrderEntry]  # full list, in the desired display order


@app.put("/sheet-sizes/order")
def set_sheet_size_order(payload: SheetSizeOrderIn):
    """Replace the whole display order -- Settings ▸ Nesting ▸ Standard
    Sizes' Move Up/Down sends its entire current list on every move, so
    this always fully reflects what's on screen rather than trying to
    patch individual positions."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(_CREATE_ORDER_TABLE_SQL)
        cursor.execute("DELETE FROM `sheet_size_order`")
        for idx, entry in enumerate(payload.sizes):
            cursor.execute(
                "INSERT INTO `sheet_size_order` (`length`, `width`, `sort_order`) VALUES (%s, %s, %s)",
                (entry.length, entry.width, idx),
            )
        conn.commit()
        cursor.close()
    finally:
        conn.close()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Config — expose key server paths so the client can use them
# ---------------------------------------------------------------------------

@app.get("/config/paths", tags=["config"])
def get_config_paths():
    """Return key server-side paths so the client knows where to save reports, etc."""
    return {
        "report_dir": settings.report_dir,
        "cnc_path": settings.cnc_path,
        "lantek_files_root": settings.lantek_files_root,
    }


# ---------------------------------------------------------------------------
# Self-update — manifest + file download
# ---------------------------------------------------------------------------

import hashlib
import os
import pathlib
from fastapi.responses import FileResponse

# Files the client must NEVER overwrite (per-machine config)
_UPDATE_SKIP_FILES = {"heidi-sm.ini", "heidi-pe.ini"}


def _compute_file_hash(filepath: str, algo: str = "sha256") -> str:
    h = hashlib.new(algo)
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


@app.get("/update/manifest", tags=["update"])
def get_update_manifest(app: str = Query("sm", description="App identifier: 'sm' or 'pe'")):
    """Return a list of files in the deploy folder with their SHA256 hashes.

    The client compares these against its local files to decide what to
    download.
    """
    update_dir = settings.update_dir
    if not update_dir or not os.path.isdir(update_dir):
        raise HTTPException(status_code=503, detail="update_dir not configured or missing")

    base = pathlib.Path(update_dir)
    manifest = []
    for path in sorted(base.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(base).as_posix()  # forward slashes
        if rel in _UPDATE_SKIP_FILES:
            continue
        manifest.append({
            "path": rel,
            "sha256": _compute_file_hash(str(path)),
            "size": path.stat().st_size,
        })

    if app.lower() == "pe":
        version = settings.pe_version
    elif app.lower() == "nest":
        version = settings.nest_version
    else:
        version = settings.sm_version
    return {
        "version": version,
        "files": manifest,
    }


@app.get("/update/file", tags=["update"])
def get_update_file(
    path: str = Query(..., description="Relative path from the deploy folder, e.g. 'Heidi.exe'"),
):
    """Download a single file from the deploy folder."""
    update_dir = settings.update_dir
    if not update_dir or not os.path.isdir(update_dir):
        raise HTTPException(status_code=503, detail="update_dir not configured or missing")

    base = pathlib.Path(update_dir).resolve()
    requested = (base / path).resolve()

    # Security: prevent path traversal
    if not str(requested).startswith(str(base)):
        raise HTTPException(status_code=400, detail="Invalid path")
    if not requested.is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {path}")

    return FileResponse(str(requested), filename=requested.name,
                        media_type="application/octet-stream")


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print(f"Starting Heidi Server on {settings.server_host}:{settings.server_port}")
    print(f"Database: {settings.db_host}:{settings.db_port}/{settings.db_name}")
    print(f"Table:    {settings.db_table}")
    print(f"API docs: http://localhost:{settings.server_port}/docs")
    # HEIDI_SERVER_RELOAD=0 disables auto-reload — used by server_dashboard's
    # tray app, which launches this with no console in its own ancestry;
    # reload=True's WatchFiles supervisor spawns its actual worker via
    # multiprocessing with bound sockets passed across (Windows socket
    # sharing), and that handshake was confirmed to hang indefinitely in
    # that specific setup. Not needed there anyway — the dashboard's own
    # Restart button already covers "pick up code changes."
    reload_enabled = os.environ.get("HEIDI_SERVER_RELOAD", "1") != "0"
    uvicorn.run(
        "main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=reload_enabled,  # Auto-reloads when you edit .py files (dev mode)
    )
