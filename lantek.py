"""
Heidi Server — Lantek database endpoints

Provides REST access to the Lantek SQL Server (MSSQL via ODBC).
This replaces the direct QODBC connection that NestingReportWindow makes.

Queries mirror exactly what the Qt client does in:
  - fetchSheetData()
  - fetchPartsData()
  - fetchIntRefForMaterial()
  - part label queries
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from datetime import datetime as _dt
from typing import Optional, List, Union

logger = logging.getLogger(__name__)

import pyodbc
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from config import settings

router = APIRouter(prefix="/lantek", tags=["lantek"])


# ---------------------------------------------------------------------------
# Connection helper — with cooldown caching on failure
# ---------------------------------------------------------------------------

_last_connection_failure: float = 0.0          # timestamp of last failure
_CONNECTION_COOLDOWN_SECONDS: float = 30.0     # skip retries for this long


def _get_lantek_connection() -> pyodbc.Connection:
    """Open a connection to the Lantek SQL Server database.

    If the last connection attempt failed within the cooldown period, raises
    503 immediately instead of blocking for the ODBC timeout (~10 s).
    """
    global _last_connection_failure

    now = time.monotonic()
    if now - _last_connection_failure < _CONNECTION_COOLDOWN_SECONDS:
        raise HTTPException(
            status_code=503,
            detail="Lantek DB unavailable (cooldown — last failure was "
                   f"{now - _last_connection_failure:.0f}s ago, retry after "
                   f"{_CONNECTION_COOLDOWN_SECONDS:.0f}s)",
        )

    conn_str = (
        f"Driver={{SQL Server}};"
        f"Server={settings.lantek_server};"
        f"Database={settings.lantek_database};"
        f"Uid={settings.lantek_user};"
        f"Pwd={settings.lantek_password};"
    )
    try:
        return pyodbc.connect(conn_str, timeout=3)
    except pyodbc.Error as e:
        _last_connection_failure = time.monotonic()
        raise HTTPException(status_code=503, detail=f"Lantek DB connection failed: {e}")


@router.get("/status")
def lantek_status():
    """Quick health check — reports Lantek cooldown state.

    Does NOT attempt a connection.  Use any real endpoint to trigger a
    connection test (which will set the cooldown on failure).
    """
    now = time.monotonic()
    if _last_connection_failure == 0.0:
        return {"available": True, "reason": "no_failure_recorded"}
    elapsed = now - _last_connection_failure
    if elapsed < _CONNECTION_COOLDOWN_SECONDS:
        return {"available": False, "reason": "cooldown",
                "retry_in": round(_CONNECTION_COOLDOWN_SECONDS - elapsed)}
    return {"available": True, "reason": "cooldown_expired"}


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class SheetHeader(BaseModel):
    NstRef: Optional[str] = None
    RecID: Optional[int] = None
    ShtRef: Optional[str] = None
    MatRef: Optional[str] = None
    SLength: Optional[float] = None
    SWidth: Optional[float] = None
    SThickness: Optional[float] = None
    Quantity: Optional[int] = None
    CrtDate: Optional[str] = None


class PartRow(BaseModel):
    Thumbnail: Optional[str] = None
    Id: Optional[int] = None
    Code: Optional[str] = None
    PartName: Optional[str] = None
    Quantity: Optional[int] = None
    Customer: Optional[str] = None
    Project: Optional[str] = None
    Path: Optional[str] = None
    Length: Optional[float] = None
    Width: Optional[float] = None
    Weight: Optional[float] = None
    CuttingTime: Optional[str] = None
    CuttingTimeTotal: Optional[str] = None
    ExtWeight: Optional[float] = None
    RectWeight: Optional[float] = None
    Area: Optional[float] = None
    ExtArea: Optional[float] = None
    RectArea: Optional[float] = None
    CutPerim: Optional[float] = None
    MrkPerim: Optional[float] = None
    InternalPiercings: Optional[str] = None
    ExternalPiercings: Optional[str] = None
    Thickness: Optional[float] = None
    CostMaterial: Optional[float] = None
    CostMachining: Optional[float] = None
    Cost: Optional[float] = None
    MnORef: Optional[str] = None
    OprID: Optional[Union[str, int]] = None
    Image: Optional[str] = None
    DIS_CreationM: Optional[str] = None


class PartLabel(BaseModel):
    PrdRefDst: Optional[str] = None
    RecId: Optional[int] = None
    Project: Optional[str] = None


class MaterialMap(BaseModel):
    IntRef: Optional[str] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

def _sync_get_sheet_header(cnc_filename: str) -> Optional[SheetHeader]:
    conn = _get_lantek_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT NstRef, RecID, ShtRef, MatRef, SLength, SWidth, SThickness, Quantity, CrtDate "
            f"FROM {settings.lantek_sheet_header_table} WHERE CNC = ?",
            cnc_filename,
        )
        row = cursor.fetchone()
        if row is None:
            return None
        columns = [desc[0] for desc in cursor.description]
        data = dict(zip(columns, row))
        if data.get("CrtDate") is not None:
            data["CrtDate"] = str(data["CrtDate"])
        return SheetHeader(**data)
    finally:
        conn.close()


@router.get("/sheet", response_model=Optional[SheetHeader])
async def get_sheet_header(
    cnc_filename: str = Query(..., description="CNC filename, e.g. S235_s8_3000x1500_107.LXD"),
):
    """
    Fetch sheet header data from the Lantek nesting table.
    Mirrors: fetchSheetData() → SELECT NstRef, ShtRef, MatRef, SLength, SWidth, SThickness, Quantity, CrtDate
    """
    return await asyncio.to_thread(_sync_get_sheet_header, cnc_filename)


def _sync_get_parts(nst_ref: str, customer: Optional[str]) -> list[PartRow]:
    query = (
        f"SELECT "
        f"p.Image AS Thumbnail, "
        f"ROW_NUMBER() OVER (ORDER BY n.RecID) AS Id, "
        f"n.PrdRefDst AS Code, "
        f"p.PrdName AS PartName, "
        f"n.Quantity AS Quantity, "
        f"p.DIS_UData1_Prt AS Customer, "
        f"p.DIS_UData2_Prt AS Project, "
        f"p.DIS_Udata3_Prt AS Path, "
        f"p.DIS_Length AS Length, "
        f"p.DIS_Width AS Width, "
        f"p.Weight AS Weight, "
        f"NULL AS CuttingTime, "
        f"NULL AS CuttingTimeTotal, "
        f"p.DIS_ExtWeight AS ExtWeight, "
        f"p.DIS_RectWeight AS RectWeight, "
        f"p.DIS_Area AS Area, "
        f"p.DIS_ExtArea AS ExtArea, "
        f"p.DIS_RectArea AS RectArea, "
        f"p.DIS_CutPerim AS CutPerim, "
        f"p.DIS_MrkPerim AS MrkPerim, "
        f"NULL AS InternalPiercings, "
        f"NULL AS ExternalPiercings, "
        f"p.DIS_Thickness AS Thickness, "
        f"n.CostMat AS CostMaterial, "
        f"n.CostMachTime AS CostMachining, "
        f"p.StdCost AS Cost, "
        f"n.MnORef, "
        f"n.OprID, "
        f"p.Image, "
        f"p.DIS_CreationM "
        f"FROM {settings.lantek_sheet_parts_table} n "
        f"LEFT JOIN {settings.lantek_part_master_table} p ON n.PrdRefDst = p.PrdRef "
        f"WHERE n.NstRef = ?"
    )
    params = [nst_ref]

    if customer:
        query += " AND p.DIS_UData1_Prt = ?"
        params.append(customer)

    conn = _get_lantek_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        columns = [desc[0] for desc in cursor.description]
        rows = []
        for row in cursor.fetchall():
            data = {}
            for col, val in zip(columns, row):
                if val is not None and hasattr(val, "isoformat"):
                    data[col] = str(val)
                else:
                    data[col] = val
            rows.append(PartRow(**data))
        return rows
    finally:
        conn.close()


@router.get("/parts", response_model=list[PartRow])
async def get_parts(
    nst_ref: str = Query(..., description="NstRef from sheet header"),
    customer: Optional[str] = Query(None, description="Optional customer filter"),
):
    """
    Fetch parts data for a given NstRef.
    Mirrors: fetchPartsData() — the big 30-column SELECT.
    """
    return await asyncio.to_thread(_sync_get_parts, nst_ref, customer)


def _sync_get_part_labels(nst_ref: str, customer: Optional[str]) -> list[PartLabel]:
    query = (
        f"SELECT n.PrdRefDst, ROW_NUMBER() OVER (ORDER BY n.RecID) AS RecId, "
        f"p.DIS_UData2_Prt AS Project "
        f"FROM {settings.lantek_sheet_parts_table} n "
        f"LEFT JOIN {settings.lantek_part_master_table} p ON n.PrdRefDst = p.PrdRef "
        f"WHERE n.NstRef = ?"
    )
    params = [nst_ref]

    if customer:
        query += " AND p.DIS_UData1_Prt = ?"
        params.append(customer)

    conn = _get_lantek_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        columns = [desc[0] for desc in cursor.description]
        rows = []
        for row in cursor.fetchall():
            data = dict(zip(columns, row))
            rows.append(PartLabel(**data))
        return rows
    finally:
        conn.close()


@router.get("/part-labels", response_model=list[PartLabel])
async def get_part_labels(
    nst_ref: str = Query(..., description="NstRef from sheet header"),
    customer: Optional[str] = Query(None, description="Optional customer filter"),
):
    """
    Fetch part label mappings (PrdRefDst → RecId, Project).
    Used by NestingReportWindow to label parts on the sheet image.
    """
    return await asyncio.to_thread(_sync_get_part_labels, nst_ref, customer)


def _sync_get_material_map(mat_ref: str) -> Optional[MaterialMap]:
    conn = _get_lantek_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT IntRef FROM {settings.lantek_material_map_table} WHERE MatRef = ?",
            mat_ref,
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return MaterialMap(IntRef=row[0])
    finally:
        conn.close()


@router.get("/material-map", response_model=Optional[MaterialMap])
async def get_material_map(
    mat_ref: str = Query(..., description="MatRef from the sheet header"),
):
    """
    Look up IntRef for a given MatRef.
    Mirrors: fetchIntRefForMaterial().
    """
    return await asyncio.to_thread(_sync_get_material_map, mat_ref)


# ---------------------------------------------------------------------------
# Background cache for recent sheets (LXD) and NCEX files
# ---------------------------------------------------------------------------

_LXD_REFRESH_INTERVAL = 15   # seconds between Lantek DB polls
_NCEX_REFRESH_INTERVAL = 15  # seconds between CNC folder scans
_LXD_MAX_ROWS = 2000         # max rows to cache from DB


class _RecentCache:
    """Thread-safe in-memory cache refreshed by a background loop."""

    def __init__(self):
        self._lock = threading.Lock()
        self._lxd_rows: List[RecentSheet] = []
        self._lxd_ts: float = 0.0          # time.monotonic() of last refresh
        self._ncex_rows: List[RecentNcexFile] = []
        self._ncex_ts: float = 0.0

    # -- LXD --
    def get_lxd(self) -> tuple:
        with self._lock:
            return list(self._lxd_rows), self._lxd_ts

    def set_lxd(self, rows: List[RecentSheet]):
        with self._lock:
            self._lxd_rows = rows
            self._lxd_ts = time.monotonic()

    # -- NCEX --
    def get_ncex(self) -> tuple:
        with self._lock:
            return list(self._ncex_rows), self._ncex_ts

    def set_ncex(self, rows: List[RecentNcexFile]):
        with self._lock:
            self._ncex_rows = rows
            self._ncex_ts = time.monotonic()


_cache = _RecentCache()


def _int_or_zero(s: str) -> int:
    try:
        return int(s)
    except (ValueError, TypeError):
        return 0


def _sort_recent_sheets(rows: List[RecentSheet], sort_column: str, sort_dir: str) -> List[RecentSheet]:
    """Sort cached LXD rows to match the original SQL ORDER BY behaviour."""
    reverse = sort_dir == "DESC"
    if sort_column == "cnc":
        # SQL: ORDER BY n.CNC {dir}, n.RecID DESC  (stable sort: secondary first)
        work = sorted(rows, key=lambda r: _int_or_zero(r.RecID), reverse=True)
        work = sorted(work, key=lambda r: r.CNC, reverse=reverse)
    else:
        # SQL: ORDER BY n.LastDate {dir}, n.CNC ASC
        work = sorted(rows, key=lambda r: r.CNC)
        work = sorted(work, key=lambda r: r.LastDate or "", reverse=reverse)
    return work


def _fetch_all_recent_sheets() -> List[RecentSheet]:
    """Fetch up to _LXD_MAX_ROWS recent sheets from Lantek MSSQL."""
    conn = _get_lantek_connection()
    try:
        cursor = conn.cursor()
        sql = f"""
            SELECT TOP {_LXD_MAX_ROWS}
                n.RecID, n.NstRef, n.CNC, n.LastDate,
                ISNULL(CAST(n.Quantity AS NVARCHAR(50)), '') AS Quantity,
                ISNULL(CAST(n.SLength AS NVARCHAR(50)), '') AS SLength,
                ISNULL(CAST(n.SWidth  AS NVARCHAR(50)), '') AS SWidth,
                ISNULL(CAST(n.SThickness AS NVARCHAR(50)), '') AS SThickness,
                ISNULL(n.MatRef, '') AS MatRef,
                COALESCE(s.FFName, '') AS CNCPath
            FROM {settings.lantek_sheet_header_table} n
            OUTER APPLY (
                SELECT TOP 1 FFName
                FROM {settings.lantek_owned_files_table}
                WHERE TblRef = '{settings.lantek_sheet_header_table}'
                  AND FFType = 'CNC'
                  AND RecordID = n.RecID
                ORDER BY LastDate DESC
            ) s
            WHERE ISNULL(LTRIM(RTRIM(n.CNC)), '') <> ''
            ORDER BY n.LastDate DESC, n.CNC ASC
        """
        cursor.execute(sql)
        results: List[RecentSheet] = []
        for row in cursor.fetchall():
            rec_id = str(row[0]) if row[0] is not None else ""
            nst_ref = str(row[1]) if row[1] is not None else ""
            cnc = str(row[2]) if row[2] is not None else ""
            last_date = row[3].strftime("%Y-%m-%d %H:%M") if row[3] else ""
            quantity = str(row[4]) if row[4] is not None else ""
            s_length = str(row[5]) if row[5] is not None else ""
            s_width = str(row[6]) if row[6] is not None else ""
            s_thickness = str(row[7]) if row[7] is not None else ""
            mat_ref = str(row[8]) if row[8] is not None else ""
            cnc_path = str(row[9]) if row[9] is not None else ""

            cnc_file_missing = not cnc_path or not os.path.isfile(cnc_path)

            results.append(RecentSheet(
                CNC=cnc, LastDate=last_date, CNCPath=cnc_path,
                NstRef=nst_ref, RecID=rec_id, Quantity=quantity,
                SLength=s_length, SWidth=s_width, SThickness=s_thickness,
                MatRef=mat_ref, CNCFileMissing=cnc_file_missing,
            ))
        logger.info("[cache] LXD fetched %d rows from DB", len(results))
        return results
    finally:
        conn.close()


def _scan_all_ncex_files() -> List[RecentNcexFile]:
    """Scan CNC_PATH folders for .ncex files (sorted by mtime descending)."""
    cnc_path = settings.cnc_path
    if not cnc_path:
        return []

    folders = [f.strip() for f in cnc_path.split(",") if f.strip()]
    all_files: list[tuple[str, float, str]] = []   # (name, mtime, abspath)
    for folder in folders:
        if not os.path.isdir(folder):
            continue
        for entry in os.scandir(folder):
            if entry.is_file() and entry.name.lower().endswith(".ncex"):
                stat = entry.stat()
                all_files.append((entry.name, stat.st_mtime, entry.path))

    all_files.sort(key=lambda x: x[1], reverse=True)

    results: List[RecentNcexFile] = []
    for name, mtime, path in all_files:
        modified = _dt.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
        results.append(RecentNcexFile(FileName=name, Modified=modified, FilePath=path))
    logger.info("[cache] NCEX scanned %d files across %d folders", len(results), len(folders))
    return results


def _cache_refresh_lxd():
    rows = _fetch_all_recent_sheets()
    _cache.set_lxd(rows)


def _cache_refresh_ncex():
    rows = _scan_all_ncex_files()
    _cache.set_ncex(rows)


async def background_cache_loop():
    """Continuously refresh LXD and NCEX caches.  Started from app lifespan."""
    logger.info("[cache] Background cache loop starting "
                "(LXD every %ds, NCEX every %ds)",
                _LXD_REFRESH_INTERVAL, _NCEX_REFRESH_INTERVAL)

    # --- initial load ---
    try:
        await asyncio.to_thread(_cache_refresh_lxd)
    except Exception as e:
        logger.warning("[cache] Initial LXD refresh failed: %s", e)
    try:
        await asyncio.to_thread(_cache_refresh_ncex)
    except Exception as e:
        logger.warning("[cache] Initial NCEX refresh failed: %s", e)

    # --- periodic refresh ---
    while True:
        await asyncio.sleep(_LXD_REFRESH_INTERVAL)
        try:
            await asyncio.to_thread(_cache_refresh_lxd)
        except Exception as e:
            logger.warning("[cache] LXD refresh failed: %s", e)
        try:
            await asyncio.to_thread(_cache_refresh_ncex)
        except Exception as e:
            logger.warning("[cache] NCEX refresh failed: %s", e)


# ---------------------------------------------------------------------------
# Recent sheets (LXD tab)
# ---------------------------------------------------------------------------

class RecentSheet(BaseModel):
    CNC: str
    LastDate: Optional[str] = None
    CNCPath: str = ""
    NstRef: str = ""
    RecID: str = ""
    Quantity: str = ""
    SLength: str = ""
    SWidth: str = ""
    SThickness: str = ""
    MatRef: str = ""
    CNCFileMissing: bool = False


def _sync_get_recent_sheets(
    sort_column: str,
    sort_dir: str,
    limit: int,
) -> List[RecentSheet]:
    """Legacy on-demand fetch — only used as fallback if cache is empty."""
    rows = _fetch_all_recent_sheets()
    sorted_rows = _sort_recent_sheets(rows, sort_column, sort_dir)
    return sorted_rows[:limit]


# ---------------------------------------------------------------------------
# Sheet customers/projects (for populateCustomerProjectFromDatabase)
# ---------------------------------------------------------------------------

class SheetCustomer(BaseModel):
    Customer: str = ""
    Project: str = ""


def _sync_get_sheet_customers(
    nst_ref: Optional[str],
    cnc: Optional[str],
) -> List[SheetCustomer]:
    conn = _get_lantek_connection()
    try:
        cursor = conn.cursor()
        parts_table = settings.lantek_sheet_parts_table
        master_table = settings.lantek_part_master_table
        header_table = settings.lantek_sheet_header_table

        if nst_ref:
            sql = (
                f"SELECT DISTINCT "
                f"ISNULL(p.DIS_UData1_Prt, '') AS Customer, "
                f"ISNULL(p.DIS_UData2_Prt, '') AS Project "
                f"FROM {parts_table} n "
                f"LEFT JOIN {master_table} p ON n.PrdRefDst = p.PrdRef "
                f"WHERE n.NstRef = ?"
            )
            cursor.execute(sql, nst_ref)
        else:
            sql = (
                f"SELECT DISTINCT "
                f"ISNULL(p.DIS_UData1_Prt, '') AS Customer, "
                f"ISNULL(p.DIS_UData2_Prt, '') AS Project "
                f"FROM {parts_table} n "
                f"LEFT JOIN {master_table} p ON n.PrdRefDst = p.PrdRef "
                f"WHERE n.NstRef = ("
                f"  SELECT TOP 1 NstRef FROM {header_table} WHERE CNC = ? ORDER BY LastDate DESC"
                f")"
            )
            cursor.execute(sql, cnc)

        results: List[SheetCustomer] = []
        for row in cursor.fetchall():
            results.append(SheetCustomer(
                Customer=str(row[0]) if row[0] else "",
                Project=str(row[1]) if row[1] else "",
            ))
        logger.info("[sheet-customers] nst_ref=%r cnc=%r => %d rows", nst_ref, cnc, len(results))
        return results
    finally:
        conn.close()


@router.get("/sheet-customers", response_model=List[SheetCustomer])
async def get_sheet_customers(
    nst_ref: Optional[str] = Query(None, description="NstRef from sheet header"),
    cnc: Optional[str] = Query(None, description="CNC filename (fallback if nst_ref not given)"),
):
    """
    Get distinct customer/project pairs for a sheet.
    Mirrors: populateCustomerProjectFromDatabase() in QueueEntryDialog.
    """
    if not nst_ref and not cnc:
        raise HTTPException(status_code=400, detail="Provide either nst_ref or cnc")
    return await asyncio.to_thread(_sync_get_sheet_customers, nst_ref, cnc)


@router.get("/recent-sheets", response_model=List[RecentSheet])
async def get_recent_sheets(
    sort_column: str = Query("date", description="Sort column: 'cnc' or 'date'"),
    sort_dir: str = Query("DESC", description="Sort direction: 'ASC' or 'DESC'"),
    limit: int = Query(1000, description="Max rows to return"),
    force_refresh: bool = Query(False, description="Force a fresh DB query, ignoring cache"),
):
    """
    Fetch the most recent Lantek sheet nestings.
    Returns data from the background cache (refreshed every ~15 s).
    Mirrors: reloadRecentLxdFiles() in QueueEntryDialog.
    """
    # Sanitise inputs
    if sort_column not in ("cnc", "date"):
        sort_column = "date"
    if sort_dir.upper() not in ("ASC", "DESC"):
        sort_dir = "DESC"
    limit = max(1, min(limit, 5000))

    if force_refresh:
        await asyncio.to_thread(_cache_refresh_lxd)

    rows, ts = _cache.get_lxd()
    if not rows and ts == 0.0:
        # Cache never loaded yet — do an on-demand fetch
        await asyncio.to_thread(_cache_refresh_lxd)
        rows, ts = _cache.get_lxd()

    sorted_rows = _sort_recent_sheets(rows, sort_column, sort_dir.upper())
    return sorted_rows[:limit]


# ---------------------------------------------------------------------------
# Recent NCEX files
# ---------------------------------------------------------------------------

class RecentNcexFile(BaseModel):
    FileName: str
    Modified: str
    FilePath: str


def _sync_get_recent_ncex(limit: int) -> List[RecentNcexFile]:
    """Legacy on-demand scan — only used as fallback if cache is empty."""
    rows = _scan_all_ncex_files()
    return rows[:limit]


@router.get("/recent-ncex", response_model=List[RecentNcexFile])
async def get_recent_ncex(
    limit: int = Query(500, description="Max files to return"),
    force_refresh: bool = Query(False, description="Force a fresh folder scan, ignoring cache"),
):
    """
    List recent .ncex files from the CNC path.
    Returns data from the background cache (refreshed every ~15 s).
    Mirrors: reloadRecentNcexFiles() in QueueEntryDialog.
    """
    limit = max(1, min(limit, 5000))

    if force_refresh:
        await asyncio.to_thread(_cache_refresh_ncex)

    rows, ts = _cache.get_ncex()
    if not rows and ts == 0.0:
        # Cache never loaded yet — do an on-demand scan
        await asyncio.to_thread(_cache_refresh_ncex)
        rows, ts = _cache.get_ncex()

    return rows[:limit]


# ---------------------------------------------------------------------------
# Cutting speed (CT1 file parsing)
# ---------------------------------------------------------------------------

def _parse_ct1_file(ct1_path: str, int_ref: str, thickness: float) -> float:
    """Parse the Lantek PSTFSC01.CT1 file to find cutting speed for material + thickness."""
    import pathlib
    p = pathlib.Path(ct1_path)
    if not p.is_file():
        logger.warning("[cutting-speed] CT1 file not found: %s", ct1_path)
        return 0.0

    mat_ref = ""
    min_thickness = 0.0
    max_thickness = 0.0
    cutting_speed = 0.0

    with open(p, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if line.startswith("Z000"):
                parts = line.split('"')
                mat_ref = parts[1] if len(parts) > 1 else ""
            elif mat_ref == int_ref and line.startswith("Z001"):
                tokens = line.split()
                min_thickness = float(tokens[1]) if len(tokens) > 1 else 0.0
            elif mat_ref == int_ref and line.startswith("Z002"):
                tokens = line.split()
                max_thickness = float(tokens[1]) if len(tokens) > 1 else 0.0
            elif mat_ref == int_ref and line.startswith("Z016"):
                tokens = line.split()
                cutting_speed = float(tokens[1]) if len(tokens) > 1 else 0.0
            elif line.startswith("Z999"):
                if mat_ref == int_ref and min_thickness <= thickness <= max_thickness:
                    logger.info("[cutting-speed] Found speed=%.2f for IntRef=%s thickness=%.2f",
                                cutting_speed, int_ref, thickness)
                    return cutting_speed
                mat_ref = ""
                min_thickness = max_thickness = cutting_speed = 0.0

    logger.info("[cutting-speed] No speed found for IntRef=%s thickness=%.2f", int_ref, thickness)
    return 0.0


def _sync_get_cutting_speed(mat_ref: str, thickness: float) -> dict:
    """Fetch IntRef via DB, then parse CT1 file to get cutting speed."""
    # Step 1: get IntRef for the material
    mat = _sync_get_material_map(mat_ref)
    int_ref = mat.IntRef if mat and mat.IntRef else ""
    if not int_ref:
        return {"cutting_speed": 0.0, "int_ref": ""}

    # Step 2: parse CT1 file
    import os
    ct1_path = os.path.join(settings.lantek_files_root, "FilesCfg", "PSTFSC01.CT1")
    speed = _parse_ct1_file(ct1_path, int_ref, thickness)
    return {"cutting_speed": speed, "int_ref": int_ref}


@router.get("/cutting-speed")
async def get_cutting_speed(
    mat_ref: str = Query(..., description="MatRef from the sheet header"),
    thickness: float = Query(..., description="Sheet thickness in mm"),
):
    """
    Return the cutting speed for a given material and thickness.
    Mirrors: fetchIntRef() + parseCt1File() in NestingReportWindow.
    """
    return await asyncio.to_thread(_sync_get_cutting_speed, mat_ref, thickness)


# ---------------------------------------------------------------------------
# Nestings-by-project (used by ProjectExplorer NestingsByProjectWindow)
# ---------------------------------------------------------------------------

class NestingByProject(BaseModel):
    nst_ref: str
    cnc: Optional[str] = None


@router.get("/nestings-by-project", response_model=List[NestingByProject])
def nestings_by_project(
    project_path: str = Query(..., description="Normalized project path (forward slashes, lowercase)"),
    old_path: Optional[str] = Query(None, description="Old project path (optional)"),
):
    """
    Return all NstRef values whose parts belong to a given project path.
    Mirrors the query in NestingsByProjectWindow::loadNestings().
    """
    parts_table = settings.lantek_sheet_parts_table   # DIS_NEST_NEST_00000500
    master_table = settings.lantek_part_master_table   # PPRR_PPRR_00000100
    header_table = settings.lantek_sheet_header_table  # DIS_NEST_NEST_00000100

    project_path = project_path.strip().lower().replace("\\\\", "/")
    project_path_bs = project_path.replace("/", "\\")

    path_clauses = []
    params = []

    if project_path:
        path_clauses.append(
            "(LOWER(REPLACE(p.DIS_Udata3_Prt, '\\', '/')) = ? "
            "OR LOWER(REPLACE(p.DIS_Udata3_Prt, '\\', '/')) LIKE ? "
            "OR LOWER(p.DIS_Udata3_Prt) = ? "
            "OR LOWER(p.DIS_Udata3_Prt) LIKE ?)"
        )
        params += [project_path, project_path + "/%", project_path_bs, project_path_bs + "\\%"]

    if old_path:
        old_path = old_path.strip().lower().replace("\\\\", "/")
        old_path_bs = old_path.replace("/", "\\")
        path_clauses.append(
            "(LOWER(REPLACE(p.DIS_Udata3_Prt, '\\', '/')) = ? "
            "OR LOWER(REPLACE(p.DIS_Udata3_Prt, '\\', '/')) LIKE ? "
            "OR LOWER(p.DIS_Udata3_Prt) = ? "
            "OR LOWER(p.DIS_Udata3_Prt) LIKE ?)"
        )
        params += [old_path, old_path + "/%", old_path_bs, old_path_bs + "\\%"]

    if not path_clauses:
        return []

    where = " OR ".join(path_clauses)
    sql = (
        f"SELECT n.NstRef, MAX(s.CNC) AS CNC "
        f"FROM {parts_table} n "
        f"LEFT JOIN {master_table} p ON n.PrdRefDst = p.PrdRef "
        f"LEFT JOIN {header_table} s ON s.NstRef = n.NstRef "
        f"WHERE p.DIS_Udata3_Prt IS NOT NULL "
        f"  AND LTRIM(RTRIM(p.DIS_Udata3_Prt)) <> '' "
        f"  AND ({where}) "
        f"GROUP BY n.NstRef "
        f"ORDER BY n.NstRef DESC"
    )

    conn = _get_lantek_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        rows = cursor.fetchall()
    finally:
        conn.close()

    return [NestingByProject(nst_ref=row[0], cnc=row[1]) for row in rows]


@router.get("/nesting-cnc")
def nesting_cnc(
    nst_ref: str = Query(..., description="NstRef to look up"),
):
    """
    Return the CNC filename for a given NstRef.
    Mirrors the query in NestingsByProjectWindow::loadPreviewForNesting().
    """
    header_table = settings.lantek_sheet_header_table
    conn = _get_lantek_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT TOP 1 CNC FROM {header_table} WHERE NstRef = ? ORDER BY CrtDate DESC",
            [nst_ref],
        )
        row = cursor.fetchone()
    finally:
        conn.close()

    if row is None:
        return {"cnc": None}
    return {"cnc": row[0]}
