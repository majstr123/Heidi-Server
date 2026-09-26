"""
Heidi Server — Project Explorer: Projects & Tags endpoints

Provides REST access to the projects, tags and related data used by
ProjectExplorer.  Queries mirror exactly what the Qt client does in:
  - mainwindow.cpp (setupProjectTree, refreshProjects, filter, status, fingerprint, pending icons)
  - newprojectdialog.cpp (insert project, GenerateProjectCode)
  - projecteditdialog.cpp (load/update project, stale snapshot)
  - projectpickerdialog.cpp (filtered project list)
  - settingsdialog.cpp (tags CRUD)
"""

from __future__ import annotations

import datetime
import logging
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from database import get_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["projects"])


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def ensure_project_order_items_columns():
    """Idempotent migration: adds project_order_items.source_file_path if
    missing — same try/ALTER-TABLE/except pattern as
    sheet_technology.py's ensure_tables() and main.py's
    ensure_material_price_density_ref()."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "ALTER TABLE `project_order_items` ADD COLUMN `source_file_path` VARCHAR(500) DEFAULT NULL"
            )
            conn.commit()
        except Exception:
            pass  # column already exists
        cursor.close()
    finally:
        conn.close()


def _row_to_dict(columns: list[str], row: tuple) -> dict:
    """Convert a raw DB row tuple into a JSON-safe dict."""
    d = {}
    for col, val in zip(columns, row):
        if isinstance(val, (bytes, bytearray)):
            # BINARY(1) columns like Status_Display → bool
            d[col] = any(b != 0 for b in val) if val else None
        elif isinstance(val, (datetime.date, datetime.datetime)):
            d[col] = val.isoformat()
        else:
            d[col] = val
    return d


def _get_order_item_by_id(item_id: int) -> ProjectOrderItem:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM project_order_items WHERE Id = %s", [item_id])
        columns = [desc[0] for desc in cursor.description]
        row = cursor.fetchone()
        cursor.close()
    finally:
        conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail=f"Order item {item_id} not found")
    return ProjectOrderItem(**_row_to_dict(columns, row))


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ProjectRow(BaseModel):
    Id: int
    project_title: Optional[str] = None
    subproject_title: Optional[str] = None
    customer_id: Optional[int] = None
    project_technical_path: Optional[str] = None
    project_administration_path: Optional[str] = None
    project_ticket_paths: Optional[str] = None
    created: Optional[str] = None
    last_edit: Optional[str] = None
    is_deleted: Optional[int] = None
    deleted_at: Optional[str] = None
    project_code: Optional[str] = None
    display_year: Optional[str] = None
    status: Optional[str] = None


class ProjectFull(BaseModel):
    """Project joined with customer data — used by projecteditdialog."""
    Id: int
    project_title: Optional[str] = None
    subproject_title: Optional[str] = None
    project_code: Optional[str] = None
    project_administration_path: Optional[str] = None
    project_technical_path: Optional[str] = None
    project_ticket_paths: Optional[str] = None
    status: Optional[str] = None
    display_year: Optional[str] = None
    customer_id: Optional[int] = None
    customer_title: Optional[str] = None
    customer_alias: Optional[str] = None
    customer_title_short: Optional[str] = None


class ProjectCreate(BaseModel):
    """Body for POST /projects — insert a new project."""
    project_title: str
    customer_id: int
    project_administration_path: Optional[str] = None
    project_technical_path: Optional[str] = None
    project_ticket_paths: Optional[str] = None
    subproject_title: Optional[str] = None
    project_code: str
    display_year: Optional[str] = None


class ProjectUpdate(BaseModel):
    """Body for PATCH /projects/{id} — update project fields."""
    project_title: Optional[str] = None
    subproject_title: Optional[str] = None
    customer_id: Optional[int] = None
    project_administration_path: Optional[str] = None
    project_technical_path: Optional[str] = None
    project_code: Optional[str] = None
    display_year: Optional[str] = None
    old_path: Optional[str] = None
    last_edit: Optional[str] = None


class StaleSnapshotCreate(BaseModel):
    """Body for POST /projects/stale-snapshot — archive old project data."""
    project_title: Optional[str] = None
    subproject_title: Optional[str] = None
    customer_id: int
    project_technical_path: Optional[str] = None
    project_administration_path: Optional[str] = None
    project_ticket_paths: Optional[str] = None
    project_code: str
    display_year: Optional[str] = None
    status: Optional[str] = None


class StatusBody(BaseModel):
    """Body for PATCH /projects/{id}/status."""
    status: Optional[str] = None  # None or empty string → clear status


class TagRow(BaseModel):
    tag: Optional[str] = None
    color: Optional[str] = None
    Status_Display: Optional[bool] = None


class TagsReplace(BaseModel):
    """Body for PUT /project-tags — replace all tags."""
    tags: list[TagRow]


class TreeProject(BaseModel):
    Id: int
    project_title: str
    project_code: Optional[str] = None
    status: Optional[str] = None
    created: Optional[str] = None
    last_edit: Optional[str] = None


class TreeCustomer(BaseModel):
    title: str
    customer_id: int
    alias: Optional[str] = None
    title_short: Optional[str] = None
    projects: list[TreeProject] = []


class TreeYear(BaseModel):
    year: str
    customers: list[TreeCustomer] = []


class FilteredProjectRow(BaseModel):
    """One row in the filtered project list."""
    year: str
    customer_title: str
    project_title: str
    project_id: int
    customer_id: Optional[int] = None
    status: Optional[str] = None
    customer_alias: Optional[str] = None
    customer_title_short: Optional[str] = None
    created: Optional[str] = None
    last_edit: Optional[str] = None


class ProjectOrderItem(BaseModel):
    Id: int
    project_id: Optional[int] = None
    item: Optional[str] = None
    material: Optional[str] = None
    type: Optional[str] = None
    qty_value: Optional[float] = None
    qty_unit: Optional[str] = None
    unit_price_value: Optional[float] = None
    unit_price_unit: Optional[str] = None
    total_price_value: Optional[float] = None
    total_price_unit: Optional[str] = None
    order_flag: Optional[int] = None
    delivery_flag: Optional[int] = None
    order_mode: Optional[str] = None
    source_material_id: Optional[int] = None
    sheet_mode: Optional[str] = None
    sheet_count: Optional[float] = None
    sheet_width_mm: Optional[float] = None
    sheet_height_mm: Optional[float] = None
    sheet_waste_percent: Optional[float] = None
    sheet_size: Optional[str] = None
    # Path to the source DXF for a type='part' row (added via Heidi-PE's
    # "Add to Material Assignment" ticket button) — lets MaterialAssignDialog
    # render a thumbnail on load instead of storing one.
    source_file_path: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    ordered_at: Optional[str] = None
    delivered_at: Optional[str] = None


class ProjectOrderItemCreate(BaseModel):
    item: Optional[str] = None
    material: Optional[str] = None
    type: Optional[str] = None
    qty_value: Optional[float] = None
    qty_unit: Optional[str] = None
    unit_price_value: Optional[float] = None
    unit_price_unit: Optional[str] = None
    total_price_value: Optional[float] = None
    total_price_unit: Optional[str] = None
    order_flag: Optional[int] = None
    delivery_flag: Optional[int] = None
    order_mode: Optional[str] = None
    source_material_id: Optional[int] = None
    sheet_mode: Optional[str] = None
    sheet_count: Optional[float] = None
    sheet_width_mm: Optional[float] = None
    sheet_height_mm: Optional[float] = None
    sheet_waste_percent: Optional[float] = None
    sheet_size: Optional[str] = None
    source_file_path: Optional[str] = None


class ProjectOrderItemUpdate(BaseModel):
    item: Optional[str] = None
    material: Optional[str] = None
    type: Optional[str] = None
    qty_value: Optional[float] = None
    qty_unit: Optional[str] = None
    unit_price_value: Optional[float] = None
    unit_price_unit: Optional[str] = None
    total_price_value: Optional[float] = None
    total_price_unit: Optional[str] = None
    order_flag: Optional[int] = None
    delivery_flag: Optional[int] = None
    order_mode: Optional[str] = None
    source_material_id: Optional[int] = None
    sheet_mode: Optional[str] = None
    sheet_count: Optional[float] = None
    sheet_width_mm: Optional[float] = None
    sheet_height_mm: Optional[float] = None
    sheet_waste_percent: Optional[float] = None
    sheet_size: Optional[str] = None
    source_file_path: Optional[str] = None


class PendingOrderRow(BaseModel):
    order_id: int
    project_id: int
    project: str
    item: Optional[str] = None
    material: Optional[str] = None
    type: Optional[str] = None
    stock_qty_text: Optional[str] = None
    qty_text: Optional[str] = None
    sheet_size_text: Optional[str] = None
    unit_price_text: Optional[str] = None
    total_price_text: Optional[str] = None
    order_flag: Optional[int] = None
    delivery_flag: Optional[int] = None


# ---------------------------------------------------------------------------
# Project tree (for setupProjectTree)
# ---------------------------------------------------------------------------

@router.get("/tree", response_model=list[TreeYear])
def get_project_tree():
    """
    Return the full project tree: years → customers → projects.
    Combines the three queries from mainwindow.cpp setupProjectTree.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()

        # 1) Get distinct years
        cursor.execute(
            "SELECT DISTINCT IFNULL(display_year, 'Unassigned') AS yr "
            "FROM projects WHERE is_deleted = 0 ORDER BY yr DESC"
        )
        years = [row[0] for row in cursor.fetchall()]

        result: list[TreeYear] = []
        for yr in years:
            # 2) Customers in this year
            cursor.execute(
                "SELECT DISTINCT c.title, c.id, c.alias, c.title_short "
                "FROM projects p JOIN customer_data c ON p.customer_id = c.id "
                "WHERE IFNULL(p.display_year, 'Unassigned') = %s AND p.is_deleted = 0",
                [yr],
            )
            customers_raw = cursor.fetchall()

            tree_customers: list[TreeCustomer] = []
            for cust_title, cust_id, cust_alias, cust_title_short in customers_raw:
                # 3) Projects for this customer + year
                cursor.execute(
                    "SELECT Id, project_title, project_code, status, created, last_edit "
                    "FROM projects "
                    "WHERE customer_id = (SELECT id FROM customer_data WHERE title = %s) "
                    "  AND IFNULL(display_year, 'Unassigned') = %s "
                    "  AND is_deleted = 0 "
                    "ORDER BY created",
                    [cust_title, yr],
                )
                projects = [
                    TreeProject(Id=r[0], project_title=r[1], project_code=r[2], status=r[3],
                                created=str(r[4]) if r[4] else None,
                                last_edit=str(r[5]) if r[5] else None)
                    for r in cursor.fetchall()
                ]
                tree_customers.append(
                    TreeCustomer(title=cust_title, customer_id=cust_id,
                                 alias=cust_alias, title_short=cust_title_short,
                                 projects=projects)
                )

            result.append(TreeYear(year=yr, customers=tree_customers))

        cursor.close()
    finally:
        conn.close()

    return result


# ---------------------------------------------------------------------------
# Filtered project list (for onProjectFilterChanged / projectpickerdialog)
# ---------------------------------------------------------------------------

@router.get("/filtered", response_model=list[FilteredProjectRow])
def get_projects_filtered(
    filter: Optional[str] = Query(None, description="Text filter applied across all fields. Pipe-separated terms are AND-combined."),
):
    """
    Return a flat filtered list of projects with year, customer, project info.
    Used by onProjectFilterChanged and projectpickerdialog.

    Supports pipe-separated multi-term filtering: "term1|term2" means
    each term must match at least one searchable field (AND logic).
    """
    LIKE_FIELDS = [
        "c.title", "c.address", "c.city", "c.country",
        "c.postal_code", "c.post", "c.social_security_number",
        "c.vat_number", "c.alias", "c.title_short",
        "c.phone", "c.mail",
        "p.project_title", "p.subproject_title",
        "p.project_code", "p.display_year", "p.status",
    ]

    conn = get_connection()
    try:
        cursor = conn.cursor()

        base_sql = (
            "SELECT DISTINCT "
            "  IFNULL(p.display_year, 'Unassigned') AS yr, "
            "  c.title AS cust_title, "
            "  p.project_title AS proj_title, "
            "  p.Id AS proj_id, "
            "  c.id AS cust_id, "
            "  p.status, "
            "  c.alias AS cust_alias, "
            "  c.title_short AS cust_title_short, "
            "  p.created, "
            "  p.last_edit "
            "FROM projects p "
            "JOIN customer_data c ON p.customer_id = c.id "
            "WHERE p.is_deleted = 0"
        )

        params = []
        if filter and filter.strip():
            # Split on pipe, each term must match at least one field
            terms = [t.strip() for t in filter.split("|") if t.strip()]
            if not terms:
                terms = [filter.strip()]

            term_clauses = []
            for term in terms:
                like = f"%{term}%"
                field_ors = " OR ".join(f"{f} LIKE %s" for f in LIKE_FIELDS)
                term_clauses.append(f"({field_ors})")
                params.extend([like] * len(LIKE_FIELDS))

            base_sql += " AND " + " AND ".join(term_clauses)

        base_sql += " ORDER BY yr DESC, cust_title, proj_title"

        cursor.execute(base_sql, params)

        rows = []
        for r in cursor.fetchall():
            rows.append(FilteredProjectRow(
                year=r[0], customer_title=r[1], project_title=r[2],
                project_id=r[3], customer_id=r[4], status=r[5],
                customer_alias=r[6], customer_title_short=r[7],
                created=str(r[8]) if r[8] else None,
                last_edit=str(r[9]) if r[9] else None,
            ))
        cursor.close()
    finally:
        conn.close()

    return rows


# ---------------------------------------------------------------------------
# Data fingerprint (for cache invalidation)
# ---------------------------------------------------------------------------

@router.get("/fingerprint")
def get_project_fingerprint():
    """
    Return a combined fingerprint of projects + customer_data + tags.
    Used by buildProjectDataFingerprint in mainwindow.cpp to detect changes.
    """
    query = (
        "SELECT CONCAT_WS('#', "
        "  COALESCE((SELECT CONCAT(COUNT(*), ':', "
        "    COALESCE(MAX(UNIX_TIMESTAMP(last_edit)), 0), ':', "
        "    COALESCE(BIT_XOR(CRC32(CONCAT_WS('|', Id, project_title, customer_id, "
        "      COALESCE(display_year, ''), COALESCE(status, ''), is_deleted, "
        "      UNIX_TIMESTAMP(last_edit) ))), 0)) "
        "   FROM projects), '0:0:0'), "
        "  COALESCE((SELECT CONCAT(COUNT(*), ':', "
        "    COALESCE(BIT_XOR(CRC32(CONCAT_WS('|', id, title, COALESCE(alias, ''), "
        "      COALESCE(title_short, ''), COALESCE(mail, ''), COALESCE(phone, '') ))), 0)) "
        "   FROM customer_data), '0:0'), "
        "  COALESCE((SELECT CONCAT(COUNT(*), ':', "
        "    COALESCE(BIT_XOR(CRC32(CONCAT_WS('|', Id, COALESCE(tag, ''), "
        "      COALESCE(color, ''), COALESCE(Status_Display, '') ))), 0)) "
        "   FROM tags), '0:0') "
        ") AS fingerprint"
    )
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query)
        row = cursor.fetchone()
        cursor.close()
    finally:
        conn.close()

    return {"fingerprint": row[0] if row else ""}


# ---------------------------------------------------------------------------
# Single project (by ID)
# ---------------------------------------------------------------------------

@router.get("/{project_id}", response_model=ProjectRow)
def get_project(project_id: int):
    """Fetch a single project by Id."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM projects WHERE Id = %s", [project_id])
        columns = [desc[0] for desc in cursor.description]
        row = cursor.fetchone()
        cursor.close()
    finally:
        conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    return ProjectRow(**_row_to_dict(columns, row))


# ---------------------------------------------------------------------------
# Project with customer data (for projecteditdialog)
# ---------------------------------------------------------------------------

@router.get("/{project_id}/full", response_model=ProjectFull)
def get_project_full(project_id: int):
    """
    Fetch project joined with customer data.
    Mirrors loadCurrentProjectData in projecteditdialog.cpp.
    """
    query = (
        "SELECT p.project_title, p.subproject_title, p.project_code, "
        "  p.project_administration_path, p.project_technical_path, "
        "  p.project_ticket_paths, p.status, p.display_year AS proj_year, "
        "  p.customer_id, c.title, c.alias, c.title_short, p.Id "
        "FROM projects p "
        "JOIN customer_data c ON p.customer_id = c.id "
        "WHERE p.Id = %s AND p.is_deleted = 0"
    )
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query, [project_id])
        row = cursor.fetchone()
        cursor.close()
    finally:
        conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    return ProjectFull(
        Id=row[12],
        project_title=row[0],
        subproject_title=row[1],
        project_code=row[2],
        project_administration_path=row[3],
        project_technical_path=row[4],
        project_ticket_paths=row[5],
        status=row[6],
        display_year=row[7],
        customer_id=row[8],
        customer_title=row[9],
        customer_alias=row[10],
        customer_title_short=row[11],
    )


# ---------------------------------------------------------------------------
# Project paths lookup (for attach documents, file import, nestings)
# ---------------------------------------------------------------------------

@router.get("/lookup/paths")
def get_project_paths(
    project: str = Query(..., description="project_title"),
    customer: str = Query(..., description="customer title"),
    year: str = Query(..., description="display_year or 'Unassigned'"),
):
    """
    Return project_administration_path, project_technical_path (and old_path)
    for a given project+customer+year triple.
    Used by on_actionattach_documents / on_actionImport_File / on_actionNestings.
    """
    query = (
        "SELECT p.project_title, p.project_administration_path, p.project_technical_path, "
        "  p.project_ticket_paths, p.old_path "
        "FROM projects p "
        "JOIN customer_data c ON p.customer_id = c.id "
        "WHERE p.project_title = %s AND c.title = %s "
        "  AND COALESCE(CAST(p.display_year AS CHAR), "
        "      CASE WHEN p.project_code REGEXP '^[0-9]{4}' THEN LEFT(p.project_code, 4) "
        "           ELSE 'Unassigned' END) = %s "
        "  AND p.is_deleted = 0"
    )
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query, [project, customer, year])
        row = cursor.fetchone()
        cursor.close()
    finally:
        conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return {
        "project_title": row[0],
        "project_administration_path": row[1],
        "project_technical_path": row[2],
        "project_ticket_paths": row[3],
        "old_path": row[4],
    }


# ---------------------------------------------------------------------------
# Find project ID by title (for material assign)
# ---------------------------------------------------------------------------

@router.get("/lookup/by-title")
def get_project_id_by_title(
    title: str = Query(..., description="project_title"),
):
    """
    Return the project Id for a given project_title.
    Used by on_actionMaterial_Assign to get project Id.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT Id FROM projects WHERE project_title = %s AND is_deleted = 0",
            [title],
        )
        row = cursor.fetchone()
        cursor.close()
    finally:
        conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail=f"Project '{title}' not found")
    return {"Id": row[0]}


# ---------------------------------------------------------------------------
# Create project
# ---------------------------------------------------------------------------

@router.post("/", response_model=ProjectRow, status_code=201)
def create_project(body: ProjectCreate):
    """
    Insert a new project.
    Mirrors insertProject in newprojectdialog.cpp.
    """
    query = (
        "INSERT INTO projects "
        "  (project_title, customer_id, project_administration_path, project_technical_path, "
        "   project_ticket_paths, subproject_title, project_code, display_year) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
    )
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query, [
            body.project_title, body.customer_id,
            body.project_administration_path, body.project_technical_path,
            body.project_ticket_paths, body.subproject_title,
            body.project_code, body.display_year,
        ])
        conn.commit()
        new_id = cursor.lastrowid
        cursor.close()
    finally:
        conn.close()

    return get_project(new_id)


# ---------------------------------------------------------------------------
# Update project
# ---------------------------------------------------------------------------

@router.patch("/{project_id}", response_model=ProjectRow)
def update_project(project_id: int, body: ProjectUpdate):
    """
    Update one or more fields on an existing project.
    Mirrors onAccept in projecteditdialog.cpp.
    """
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(status_code=400, detail="No fields provided")

    set_clause = ", ".join(f"`{c}` = %s" for c in fields)
    values = list(fields.values()) + [project_id]

    query = f"UPDATE projects SET {set_clause} WHERE Id = %s"
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
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    return get_project(project_id)


# ---------------------------------------------------------------------------
# Soft-delete & undelete
# ---------------------------------------------------------------------------

@router.delete("/{project_id}")
def soft_delete_project(project_id: int):
    """Soft-delete a project (set is_deleted=1)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE projects SET is_deleted = 1, deleted_at = CURRENT_TIMESTAMP "
            "WHERE Id = %s AND is_deleted = 0",
            [project_id],
        )
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
    finally:
        conn.close()

    if affected == 0:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found or already deleted")
    return {"ok": True, "id": project_id}


@router.patch("/{project_id}/undelete")
def undelete_project(project_id: int):
    """Undo soft-delete of a project."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE projects SET is_deleted = 0, deleted_at = NULL, last_edit = CURRENT_TIMESTAMP "
            "WHERE Id = %s",
            [project_id],
        )
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
    finally:
        conn.close()

    if affected == 0:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    return {"ok": True, "id": project_id}


# ---------------------------------------------------------------------------
# Project status
# ---------------------------------------------------------------------------

@router.get("/{project_id}/status")
def get_project_status(project_id: int):
    """Get the current status tag of a project."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM projects WHERE Id = %s", [project_id])
        row = cursor.fetchone()
        cursor.close()
    finally:
        conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    return {"Id": project_id, "status": row[0]}


@router.patch("/{project_id}/status")
def set_project_status(project_id: int, body: StatusBody):
    """Set or clear the status tag of a project."""
    if body.status:
        query = "UPDATE projects SET status = %s, last_edit = CURRENT_TIMESTAMP WHERE Id = %s"
        params = [body.status, project_id]
    else:
        query = "UPDATE projects SET status = NULL, last_edit = CURRENT_TIMESTAMP WHERE Id = %s"
        params = [project_id]

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
    finally:
        conn.close()

    if affected == 0:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    return {"ok": True, "id": project_id, "status": body.status}


# ---------------------------------------------------------------------------
# Pending order icons
# ---------------------------------------------------------------------------

@router.get("/pending/customers", response_model=list[int])
def get_pending_order_customers():
    """
    Return customer IDs that have pending (ordered but not delivered) items.
    Used by updatePendingCustomerIcons.
    """
    query = (
        "SELECT DISTINCT p.customer_id "
        "FROM project_order_items poi "
        "JOIN projects p ON poi.project_id = p.Id "
        "WHERE poi.order_flag = 1 AND poi.delivery_flag = 0 AND p.is_deleted = 0"
    )
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query)
        ids = [row[0] for row in cursor.fetchall()]
        cursor.close()
    finally:
        conn.close()

    return ids


@router.get("/pending/projects", response_model=list[int])
def get_pending_order_projects():
    """
    Return project IDs that have pending (ordered but not delivered) items.
    Used by updatePendingProjectIcons.
    """
    query = (
        "SELECT DISTINCT poi.project_id "
        "FROM project_order_items poi "
        "JOIN projects p ON poi.project_id = p.Id "
        "WHERE poi.order_flag = 1 AND poi.delivery_flag = 0 AND p.is_deleted = 0"
    )
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query)
        ids = [row[0] for row in cursor.fetchall()]
        cursor.close()
    finally:
        conn.close()

    return ids


# ---------------------------------------------------------------------------
# Project order items (material assignments)
# ---------------------------------------------------------------------------

@router.get("/{project_id}/order-items", response_model=list[ProjectOrderItem])
def get_project_order_items(project_id: int):
    """Return all order items for a project."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM project_order_items WHERE project_id = %s ORDER BY Id", [project_id])
        columns = [desc[0] for desc in cursor.description]
        rows = [ProjectOrderItem(**_row_to_dict(columns, row)) for row in cursor.fetchall()]
        cursor.close()
    finally:
        conn.close()

    return rows


@router.post("/{project_id}/order-items", response_model=ProjectOrderItem, status_code=201)
def create_project_order_item(project_id: int, body: ProjectOrderItemCreate):
    """Insert a new order item for a project."""
    fields = body.model_dump(exclude_unset=True)
    fields["project_id"] = project_id

    columns = list(fields.keys())
    values = [fields[c] for c in columns]

    if not columns:
        raise HTTPException(status_code=400, detail="No fields provided")

    placeholders = ",".join(["%s"] * len(columns))
    col_sql = ",".join(columns)
    query = f"INSERT INTO project_order_items ({col_sql}) VALUES ({placeholders})"

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query, values)
        conn.commit()
        new_id = cursor.lastrowid
        cursor.close()
    finally:
        conn.close()

    return _get_order_item_by_id(new_id)


@router.patch("/order-items/{item_id}", response_model=ProjectOrderItem)
def update_project_order_item(item_id: int, body: ProjectOrderItemUpdate):
    """Update fields on an order item."""
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields provided")

    set_clauses = []
    values = []
    for key, value in fields.items():
        set_clauses.append(f"{key} = %s")
        values.append(value)

    query = f"UPDATE project_order_items SET {', '.join(set_clauses)} WHERE Id = %s"
    values.append(item_id)

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
        raise HTTPException(status_code=404, detail=f"Order item {item_id} not found")

    return _get_order_item_by_id(item_id)


@router.delete("/order-items/{item_id}")
def delete_project_order_item(item_id: int):
    """Delete an order item."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM project_order_items WHERE Id = %s", [item_id])
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
    finally:
        conn.close()

    if affected == 0:
        raise HTTPException(status_code=404, detail=f"Order item {item_id} not found")
    return {"ok": True, "deleted_id": item_id}


@router.get("/orders/pending", response_model=list[PendingOrderRow])
def get_pending_order_items():
    """Return pending order items (ordered but not delivered)."""
    query = (
        "SELECT poi.Id AS order_id, "
        "       poi.project_id, "
        "       CONCAT(c.title, ' - ', p.project_code, ' - ', p.project_title) AS project, "
        "       poi.item, "
        "       poi.material, "
        "       poi.type, "
        "       CASE "
        "           WHEN poi.sheet_count IS NULL THEN '' "
        "           WHEN ABS(COALESCE(poi.sheet_count, 0)) < 0.0000001 THEN '' "
        "           ELSE TRIM(TRAILING '.00' FROM TRIM(TRAILING '0' FROM CAST(poi.sheet_count AS CHAR))) "
        "       END AS stock_qty_text, "
        "       CONCAT(COALESCE(poi.qty_value, 0), ' ', COALESCE(poi.qty_unit, '')) AS qty_text, "
        "       CASE "
        "           WHEN TRIM(COALESCE(poi.sheet_size, '')) <> '' THEN poi.sheet_size "
        "           WHEN COALESCE(poi.sheet_width_mm, 0) > 0 AND COALESCE(poi.sheet_height_mm, 0) > 0 "
        "                THEN CONCAT(TRIM(TRAILING '.00' FROM TRIM(TRAILING '0' FROM CAST(poi.sheet_width_mm AS CHAR))), ' x ', TRIM(TRAILING '.00' FROM TRIM(TRAILING '0' FROM CAST(poi.sheet_height_mm AS CHAR)))) "
        "           ELSE '' "
        "       END AS sheet_size_text, "
        "       CONCAT(COALESCE(poi.unit_price_value, 0), ' ', COALESCE(poi.unit_price_unit, '')) AS unit_price_text, "
        "       CONCAT(COALESCE(poi.total_price_value, 0), ' ', COALESCE(poi.total_price_unit, 'EUR')) AS total_price_text, "
        "       poi.order_flag, "
        "       poi.delivery_flag "
        "FROM project_order_items poi "
        "JOIN projects p ON poi.project_id = p.Id "
        "JOIN customer_data c ON p.customer_id = c.id "
        "WHERE poi.order_flag = 1 "
        "  AND poi.delivery_flag = 0 "
        "  AND p.is_deleted = 0 "
        "ORDER BY p.project_code, poi.item"
    )

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query)
        columns = [desc[0] for desc in cursor.description]
        rows = [PendingOrderRow(**_row_to_dict(columns, row)) for row in cursor.fetchall()]
        cursor.close()
    finally:
        conn.close()

    return rows


# ---------------------------------------------------------------------------
# Generate project code (stored procedure)
# ---------------------------------------------------------------------------

@router.post("/generate-code")
def generate_project_code(year: str = Query(..., description="Year for code generation")):
    """
    Call the GenerateProjectCode stored procedure.
    Returns the generated project code.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("CALL GenerateProjectCode(%s, @code)", [year])
        cursor.execute("SELECT @code AS code")
        row = cursor.fetchone()
        conn.commit()
        cursor.close()
    finally:
        conn.close()

    if row is None or row[0] is None:
        raise HTTPException(status_code=500, detail="Failed to generate project code")
    return {"code": row[0]}


# ---------------------------------------------------------------------------
# Stale project snapshot (archival copy before edit)
# ---------------------------------------------------------------------------

@router.post("/stale-snapshot", status_code=201)
def create_stale_snapshot(body: StaleSnapshotCreate):
    """
    Insert a stale (archived) copy of a project before editing.
    Mirrors insertStaleProjectSnapshot in projecteditdialog.cpp.
    is_deleted = 2, deleted_at = NOW().
    """
    query = (
        "INSERT INTO projects "
        "  (project_title, subproject_title, customer_id, project_technical_path, "
        "   project_administration_path, project_ticket_paths, "
        "   is_deleted, deleted_at, project_code, display_year, status) "
        "VALUES (%s, %s, %s, %s, %s, %s, 2, NOW(), %s, %s, %s)"
    )
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query, [
            body.project_title, body.subproject_title, body.customer_id,
            body.project_technical_path, body.project_administration_path,
            body.project_ticket_paths,
            body.project_code, body.display_year, body.status,
        ])
        conn.commit()
        new_id = cursor.lastrowid
        cursor.close()
    finally:
        conn.close()

    return {"ok": True, "id": new_id}


# ---------------------------------------------------------------------------
# Project tags (settings)
# ---------------------------------------------------------------------------

tags_router = APIRouter(prefix="/project-tags", tags=["project-tags"])


@tags_router.get("/", response_model=list[TagRow])
def get_project_tags():
    """
    Fetch all project tags.
    Used by loadProjectTags and loadProjectTagsFromDatabase.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT tag, color, Status_Display FROM tags WHERE tag IS NOT NULL ORDER BY Id"
        )
        columns = [desc[0] for desc in cursor.description]
        rows = [TagRow(**_row_to_dict(columns, r)) for r in cursor.fetchall()]
        cursor.close()
    finally:
        conn.close()

    return rows


@tags_router.put("/")
def replace_project_tags(body: TagsReplace):
    """
    Replace ALL project tags (delete + re-insert).
    Mirrors saveProjectTagsToDatabase in settingsdialog.cpp.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tags")
        for t in body.tags:
            sd_val = b'\x01' if t.Status_Display else None
            cursor.execute(
                "INSERT INTO tags (tag, color, Status_Display) VALUES (%s, %s, %s)",
                [t.tag, t.color, sd_val],
            )
        conn.commit()
        cursor.close()
    finally:
        conn.close()

    return {"ok": True, "count": len(body.tags)}
