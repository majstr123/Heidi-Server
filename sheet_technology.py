"""
Heidi Server — Sheet Material/Thickness + Cutting Technology

Manages the `sheet_material_thickness` table that maps (material, thickness)
combinations to default cutting parameters (kerf, lead-in, lead-out, gap)
and per-combination Technology.xml blobs (bundle_data, hash, updated_at).
"""

from __future__ import annotations

import hashlib
import logging
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from database import get_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sheet-technology", tags=["sheet-technology"])

# ---------------------------------------------------------------------------
# Table names
# ---------------------------------------------------------------------------
TABLE = "sheet_material_thickness"

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class SheetMaterialThickness(BaseModel):
    id: Optional[int] = None
    material: str
    thickness: float
    kerf_width: float = 0.2
    # Split kerf by contour type — internal (hole) vs external (outer
    # profile) fit tolerance often differs. Both nullable/additive: a row
    # nobody has edited since this split was added has neither set, and
    # callers fall back to the legacy kerf_width above for both sides.
    kerf_width_internal: Optional[float] = None
    kerf_width_external: Optional[float] = None
    lead_in_length: float = 3.0
    lead_out_length: float = 0.0
    end_gap_length: float = 0.0
    layer_ref: Optional[str] = None
    # Richer lead-in/out defaults — additive/nullable, written one at a time
    # via PUT /sheet-technology/set-field (see FieldUpdate below) rather
    # than through the upsert body, so an older caller that only knows the
    # original 6 fields can never blank these out either. Unset until a
    # PE user explicitly clicks "Update Default" on that field.
    lead_in_type: Optional[str] = None
    lead_in_angle: Optional[float] = None
    lead_in_arc_radius: Optional[float] = None
    lead_in_arc_angle: Optional[float] = None
    lead_out_type: Optional[str] = None
    lead_out_angle: Optional[float] = None
    lead_out_arc_radius: Optional[float] = None
    lead_out_arc_angle: Optional[float] = None
    lead_out_overlap: Optional[float] = None
    # Laser dwell time at the start of each contour, before cutting motion
    # begins — consumed by PE's Cutting Simulation (see nestingsimulation.cpp)
    # for its time estimate. Additive/nullable like the lead-in/out fields
    # above, settable via PUT /sheet-technology/set-field.
    pierce_time_sec: Optional[float] = None


class SheetMaterialThicknessUpdate(BaseModel):
    """Body for upsert."""
    material: str
    thickness: float
    kerf_width: float = 0.2
    kerf_width_internal: Optional[float] = None
    kerf_width_external: Optional[float] = None
    lead_in_length: float = 3.0
    lead_out_length: float = 0.0
    end_gap_length: float = 0.0
    layer_ref: Optional[str] = None


class LayerRefUpdate(BaseModel):
    """Body for setting just the layer_ref field on an existing (material, thickness) row."""
    material: str
    thickness: float
    layer_ref: Optional[str] = None


# Columns settable one at a time via PUT /sheet-technology/set-field (see
# FieldUpdate/set_field below) — the "Update Default" buttons in PE's
# per-contour panel each push exactly one of these. Allowlisted so the
# `field` string from a request body can never reach the SQL as a raw,
# unchecked column name.
NUMERIC_SETTABLE_FIELDS = {
    "kerf_width_internal", "kerf_width_external",
    "lead_in_length", "lead_in_angle", "lead_in_arc_radius", "lead_in_arc_angle",
    "lead_out_length", "lead_out_angle", "lead_out_arc_radius", "lead_out_arc_angle",
    "lead_out_overlap", "end_gap_length", "pierce_time_sec",
}
STRING_SETTABLE_FIELDS = {"lead_in_type", "lead_out_type"}


class FieldUpdate(BaseModel):
    """Body for PUT /sheet-technology/set-field. Exactly one of value_num/
    value_str should be set, matching whether `field` is a numeric or
    string column (see NUMERIC_SETTABLE_FIELDS/STRING_SETTABLE_FIELDS)."""
    material: str
    thickness: float
    field: str
    value_num: Optional[float] = None
    value_str: Optional[str] = None


class TechnologyBundleInfo(BaseModel):
    material: str
    thickness: float
    hash: Optional[str] = None
    updated_at: Optional[str] = None


# ---------------------------------------------------------------------------
# Ensure tables exist  (merged — no separate technology_bundles table)
# ---------------------------------------------------------------------------

def ensure_tables():
    """Create the table if it doesn't exist, then add bundle columns."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        # Create the master table (sans bundle columns for existing installs)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS `{TABLE}` (
                `id`              INT UNSIGNED NOT NULL AUTO_INCREMENT,
                `material`        VARCHAR(100) NOT NULL,
                `thickness`       DOUBLE NOT NULL,
                `kerf_width`      DOUBLE NOT NULL DEFAULT 0.2,
                `lead_in_length`  DOUBLE NOT NULL DEFAULT 3.0,
                `lead_out_length` DOUBLE NOT NULL DEFAULT 0.0,
                `end_gap_length`  DOUBLE NOT NULL DEFAULT 0.0,
                `bundle_data`     LONGBLOB DEFAULT NULL,
                `hash`            VARCHAR(64) DEFAULT NULL,
                `updated_at`      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                PRIMARY KEY (`id`),
                UNIQUE KEY `uq_mat_thick` (`material`, `thickness`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        # Idempotent migration for existing installs that lack the new columns
        for col_def in (
            "ADD COLUMN `bundle_data` LONGBLOB DEFAULT NULL",
            "ADD COLUMN `hash` VARCHAR(64) DEFAULT NULL",
            "ADD COLUMN `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",
            # References a row in the Bodor cutting-speed library (imported
            # CSV, see ProjectExplorer's Cutting Speeds settings page) —
            # which laser "layer" technic to use for this material/thickness.
            "ADD COLUMN `layer_ref` VARCHAR(255) DEFAULT NULL",
            # Split kerf — internal (hole) vs external (outer profile).
            # Nullable: NULL means "not set, fall back to kerf_width".
            "ADD COLUMN `kerf_width_internal` DOUBLE DEFAULT NULL",
            "ADD COLUMN `kerf_width_external` DOUBLE DEFAULT NULL",
            # Richer lead-in/lead-out defaults, settable one field at a time
            # via PUT /sheet-technology/set-field — see NUMERIC_SETTABLE_FIELDS/
            # STRING_SETTABLE_FIELDS. All nullable: unset until a PE user
            # clicks "Update Default" on that specific field.
            "ADD COLUMN `lead_in_type` VARCHAR(20) DEFAULT NULL",
            "ADD COLUMN `lead_in_angle` DOUBLE DEFAULT NULL",
            "ADD COLUMN `lead_in_arc_radius` DOUBLE DEFAULT NULL",
            "ADD COLUMN `lead_in_arc_angle` DOUBLE DEFAULT NULL",
            "ADD COLUMN `lead_out_type` VARCHAR(20) DEFAULT NULL",
            "ADD COLUMN `lead_out_angle` DOUBLE DEFAULT NULL",
            "ADD COLUMN `lead_out_arc_radius` DOUBLE DEFAULT NULL",
            "ADD COLUMN `lead_out_arc_angle` DOUBLE DEFAULT NULL",
            "ADD COLUMN `lead_out_overlap` DOUBLE DEFAULT NULL",
            # Laser dwell time at the start of each contour cut, before
            # cutting motion begins — settable via PUT /sheet-technology/set-field.
            "ADD COLUMN `pierce_time_sec` DOUBLE DEFAULT NULL",
        ):
            try:
                cursor.execute(f"ALTER TABLE `{TABLE}` {col_def}")
            except Exception:
                pass  # column already exists
        conn.commit()

        # Drop the old separate table if it still exists
        cursor.execute("DROP TABLE IF EXISTS `technology_bundles`")
        conn.commit()
        cursor.close()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# One-time backfill: populate bundle_data from the template Technology.xml
# ---------------------------------------------------------------------------

def backfill_technology_xml():
    """
    For every row in sheet_material_thickness that has NULL bundle_data,
    fill in the default Technology.xml template and its SHA-256 hash.
    """
    xml_path = os.path.join(
        os.path.dirname(__file__), os.pardir,
        "HeidiNest", "example files",
        "testing123_ncex_extracted", "CAD", "Technology.xml",
    )
    xml_path = os.path.normpath(xml_path)
    if not os.path.isfile(xml_path):
        logger.warning("Technology.xml not found at %s — skipping backfill", xml_path)
        return

    with open(xml_path, "rb") as f:
        blob = f.read()
    blob_hash = hashlib.sha256(blob).hexdigest()

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE `{TABLE}` SET bundle_data = %s, hash = %s "
            f"WHERE bundle_data IS NULL",
            [blob, blob_hash],
        )
        affected = cursor.rowcount
        conn.commit()
        cursor.close()
        if affected:
            logger.info("Backfilled %d rows with Technology.xml (%s)", affected, blob_hash[:12])
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# sheet_material_thickness CRUD
# ---------------------------------------------------------------------------

@router.get("", response_model=list[SheetMaterialThickness])
def get_all():
    """Return all material/thickness rows with cutting parameters."""
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            f"SELECT id, material, thickness, kerf_width, kerf_width_internal, "
            f"kerf_width_external, lead_in_length, lead_in_type, lead_in_angle, lead_in_arc_radius, "
            f"lead_in_arc_angle, lead_out_length, lead_out_type, lead_out_angle, lead_out_arc_radius, "
            f"lead_out_arc_angle, lead_out_overlap, end_gap_length, layer_ref, pierce_time_sec "
            f"FROM `{TABLE}` ORDER BY material, thickness"
        )
        rows = cursor.fetchall()
        cursor.close()
    finally:
        conn.close()
    return [SheetMaterialThickness(**r) for r in rows]


@router.get("/by-material", response_model=list[SheetMaterialThickness])
def get_by_material(
    material: str = Query(..., description="Material name"),
):
    """Return all thickness rows for a given material."""
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            f"SELECT id, material, thickness, kerf_width, kerf_width_internal, "
            f"kerf_width_external, lead_in_length, lead_in_type, lead_in_angle, lead_in_arc_radius, "
            f"lead_in_arc_angle, lead_out_length, lead_out_type, lead_out_angle, lead_out_arc_radius, "
            f"lead_out_arc_angle, lead_out_overlap, end_gap_length, layer_ref, pierce_time_sec "
            f"FROM `{TABLE}` "
            f"WHERE material = %s ORDER BY thickness",
            [material],
        )
        rows = cursor.fetchall()
        cursor.close()
    finally:
        conn.close()
    return [SheetMaterialThickness(**r) for r in rows]


@router.get("/lookup", response_model=Optional[SheetMaterialThickness])
def lookup(
    material: str = Query(..., description="Material name"),
    thickness: float = Query(..., description="Thickness in mm"),
):
    """Look up cutting parameters for an exact (material, thickness) pair."""
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            f"SELECT id, material, thickness, kerf_width, kerf_width_internal, "
            f"kerf_width_external, lead_in_length, lead_in_type, lead_in_angle, lead_in_arc_radius, "
            f"lead_in_arc_angle, lead_out_length, lead_out_type, lead_out_angle, lead_out_arc_radius, "
            f"lead_out_arc_angle, lead_out_overlap, end_gap_length, layer_ref, pierce_time_sec "
            f"FROM `{TABLE}` "
            f"WHERE material = %s AND thickness = %s LIMIT 1",
            [material, thickness],
        )
        row = cursor.fetchone()
        cursor.close()
    finally:
        conn.close()
    if row is None:
        return None
    return SheetMaterialThickness(**row)


@router.post("", response_model=SheetMaterialThickness)
def upsert(body: SheetMaterialThicknessUpdate):
    """Insert or update a material/thickness row."""
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        # layer_ref AND the two split-kerf columns use COALESCE on update:
        # callers that don't know about them (e.g. HeidiNest's existing
        # kerf/lead-in editor, which only ever sends the original 6 fields)
        # leave whatever PE's own dialogs previously set untouched, instead
        # of clobbering them back to NULL on every unrelated save.
        cursor.execute(
            f"INSERT INTO `{TABLE}` "
            f"(material, thickness, kerf_width, kerf_width_internal, kerf_width_external, "
            f"lead_in_length, lead_out_length, end_gap_length, layer_ref) "
            f"VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
            f"ON DUPLICATE KEY UPDATE "
            f"kerf_width = VALUES(kerf_width), "
            f"kerf_width_internal = COALESCE(VALUES(kerf_width_internal), kerf_width_internal), "
            f"kerf_width_external = COALESCE(VALUES(kerf_width_external), kerf_width_external), "
            f"lead_in_length = VALUES(lead_in_length), "
            f"lead_out_length = VALUES(lead_out_length), "
            f"end_gap_length = VALUES(end_gap_length), "
            f"layer_ref = COALESCE(VALUES(layer_ref), layer_ref)",
            [
                body.material,
                body.thickness,
                body.kerf_width,
                body.kerf_width_internal,
                body.kerf_width_external,
                body.lead_in_length,
                body.lead_out_length,
                body.end_gap_length,
                body.layer_ref,
            ],
        )
        conn.commit()
        # Fetch the row back
        cursor.execute(
            f"SELECT id, material, thickness, kerf_width, kerf_width_internal, "
            f"kerf_width_external, lead_in_length, lead_in_type, lead_in_angle, lead_in_arc_radius, "
            f"lead_in_arc_angle, lead_out_length, lead_out_type, lead_out_angle, lead_out_arc_radius, "
            f"lead_out_arc_angle, lead_out_overlap, end_gap_length, layer_ref, pierce_time_sec "
            f"FROM `{TABLE}` "
            f"WHERE material = %s AND thickness = %s LIMIT 1",
            [body.material, body.thickness],
        )
        row = cursor.fetchone()
        cursor.close()
    finally:
        conn.close()
    return SheetMaterialThickness(**row)


@router.put("/layer-ref", response_model=SheetMaterialThickness)
def set_layer_ref(body: LayerRefUpdate):
    """Set (or clear) just the layer_ref field on an existing (material, thickness) row."""
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            f"UPDATE `{TABLE}` SET layer_ref = %s WHERE material = %s AND thickness = %s",
            [body.layer_ref, body.material, body.thickness],
        )
        affected = cursor.rowcount
        conn.commit()
        cursor.execute(
            f"SELECT id, material, thickness, kerf_width, kerf_width_internal, "
            f"kerf_width_external, lead_in_length, lead_in_type, lead_in_angle, lead_in_arc_radius, "
            f"lead_in_arc_angle, lead_out_length, lead_out_type, lead_out_angle, lead_out_arc_radius, "
            f"lead_out_arc_angle, lead_out_overlap, end_gap_length, layer_ref, pierce_time_sec "
            f"FROM `{TABLE}` "
            f"WHERE material = %s AND thickness = %s LIMIT 1",
            [body.material, body.thickness],
        )
        row = cursor.fetchone()
        cursor.close()
    finally:
        conn.close()
    if affected == 0 or row is None:
        raise HTTPException(status_code=404, detail="Row not found")
    return SheetMaterialThickness(**row)


@router.put("/set-field", response_model=SheetMaterialThickness)
def set_field(body: FieldUpdate):
    """Set exactly one of the richer lead-in/lead-out/kerf-split fields on a
    (material, thickness) row — the "Update Default" buttons in PE's
    per-contour panel each call this once, for whichever single field was
    just clicked. `field` is checked against a fixed allowlist before ever
    reaching SQL (see NUMERIC_SETTABLE_FIELDS/STRING_SETTABLE_FIELDS) since
    it's interpolated as a column name, which can't be a bound parameter.
    Upserts (creates the row with defaults for every other column if it
    doesn't exist yet) rather than requiring the row to already exist —
    unlike layer-ref, which assumes SheetMaterialThicknessDialog already
    created the row first.
    """
    if body.field in NUMERIC_SETTABLE_FIELDS:
        value = body.value_num
    elif body.field in STRING_SETTABLE_FIELDS:
        value = body.value_str
    else:
        raise HTTPException(status_code=400, detail=f"Unknown/unsettable field: {body.field}")

    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            f"INSERT INTO `{TABLE}` (material, thickness, `{body.field}`) "
            f"VALUES (%s, %s, %s) "
            f"ON DUPLICATE KEY UPDATE `{body.field}` = VALUES(`{body.field}`)",
            [body.material, body.thickness, value],
        )
        conn.commit()
        cursor.execute(
            f"SELECT id, material, thickness, kerf_width, kerf_width_internal, "
            f"kerf_width_external, lead_in_length, lead_in_type, lead_in_angle, lead_in_arc_radius, "
            f"lead_in_arc_angle, lead_out_length, lead_out_type, lead_out_angle, lead_out_arc_radius, "
            f"lead_out_arc_angle, lead_out_overlap, end_gap_length, layer_ref, pierce_time_sec "
            f"FROM `{TABLE}` "
            f"WHERE material = %s AND thickness = %s LIMIT 1",
            [body.material, body.thickness],
        )
        row = cursor.fetchone()
        cursor.close()
    finally:
        conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Row not found after upsert")
    return SheetMaterialThickness(**row)


@router.delete("/{row_id}")
def delete_row(row_id: int):
    """Delete a material/thickness row by ID."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM `{TABLE}` WHERE id = %s", [row_id])
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
    finally:
        conn.close()
    if affected == 0:
        raise HTTPException(status_code=404, detail="Row not found")
    return {"deleted": row_id}


# ---------------------------------------------------------------------------
# Distinct materials from the sheet_material_thickness table
# ---------------------------------------------------------------------------

@router.get("/materials", response_model=list[str])
def get_distinct_materials():
    """Return distinct material names from the sheet_material_thickness table."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT DISTINCT material FROM `{TABLE}` ORDER BY material"
        )
        items = [r[0] for r in cursor.fetchall()]
        cursor.close()
    finally:
        conn.close()
    return items


@router.get("/thicknesses", response_model=list[float])
def get_distinct_thicknesses(
    material: Optional[str] = Query(None, description="Filter by material"),
):
    """Return distinct thickness values, optionally filtered by material."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        if material:
            cursor.execute(
                f"SELECT DISTINCT thickness FROM `{TABLE}` "
                f"WHERE material = %s ORDER BY thickness",
                [material],
            )
        else:
            cursor.execute(
                f"SELECT DISTINCT thickness FROM `{TABLE}` ORDER BY thickness"
            )
        items = [r[0] for r in cursor.fetchall()]
        cursor.close()
    finally:
        conn.close()
    return items


# ---------------------------------------------------------------------------
# Technology bundle endpoints (read from the merged table)
# ---------------------------------------------------------------------------

@router.get("/technology/hash")
def technology_combined_hash():
    """
    Return the combined hash of all technology bundles.
    Clients compare this against their local hash to determine
    whether an update is needed.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT hash FROM `{TABLE}` "
            f"WHERE hash IS NOT NULL ORDER BY material, thickness"
        )
        hashes = [r[0] for r in cursor.fetchall()]
        cursor.close()
    finally:
        conn.close()
    if not hashes:
        return {"hash": None}
    combined = hashlib.sha256("|".join(hashes).encode()).hexdigest()
    return {"hash": combined}


@router.get("/technology/list", response_model=list[TechnologyBundleInfo])
def technology_list():
    """List all available technology bundles (without the blob data)."""
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            f"SELECT material, thickness, hash, updated_at "
            f"FROM `{TABLE}` ORDER BY material, thickness"
        )
        rows = cursor.fetchall()
        cursor.close()
    finally:
        conn.close()
    result = []
    for r in rows:
        r["updated_at"] = r["updated_at"].isoformat() if r.get("updated_at") else None
        result.append(TechnologyBundleInfo(**r))
    return result


# ---------------------------------------------------------------------------
# Upload Technology.xml blob for a specific (material, thickness) row
# ---------------------------------------------------------------------------

class TechnologyUpload(BaseModel):
    material: str
    thickness: float
    bundle_data_base64: str  # base64-encoded Technology.xml content


@router.put("/technology/upload")
def technology_upload(body: TechnologyUpload):
    """
    Accept a base64-encoded Technology.xml blob and store it in the
    sheet_material_thickness row for the given (material, thickness).
    """
    import base64

    try:
        blob = base64.b64decode(body.bundle_data_base64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 data")

    if not blob:
        raise HTTPException(status_code=400, detail="Empty bundle data")

    blob_hash = hashlib.sha256(blob).hexdigest()

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE `{TABLE}` SET bundle_data = %s, hash = %s "
            f"WHERE material = %s AND thickness = %s",
            [blob, blob_hash, body.material, body.thickness],
        )
        affected = cursor.rowcount
        conn.commit()
        cursor.close()
    finally:
        conn.close()

    if affected == 0:
        raise HTTPException(
            status_code=404,
            detail=f"No row found for {body.material} / {body.thickness}",
        )

    return {"hash": blob_hash, "size": len(blob)}
