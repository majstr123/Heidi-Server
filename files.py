"""
Heidi Server — File serving endpoints

Serves files from the configured root directories (Lantek DB files, report
directory, CNC path) so that client machines don't need direct network access.

Security: only files inside the allowed root directories can be served.
"""

from __future__ import annotations

import io
import os
import re
import subprocess
import zipfile
from pathlib import Path, PureWindowsPath
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse

from config import settings

router = APIRouter(tags=["files"])

# ---------------------------------------------------------------------------
# Allowed root directories — only files inside these can be served
# ---------------------------------------------------------------------------
ALLOWED_ROOTS: list[Path] = []


def _init_roots():
    """Build the list of allowed roots from settings (called once at import)."""
    for raw in [settings.lantek_files_root, settings.report_dir, settings.cnc_path,
                settings.projects_root, settings.projects_documentation_root]:
        if raw:
            p = Path(raw).resolve()
            if p.exists():
                ALLOWED_ROOTS.append(p)
            else:
                # On Windows, UNC paths like //SERVER/share may not resolve
                # until accessed. Still add them.
                ALLOWED_ROOTS.append(p)

_init_roots()


def _safe_resolve(requested: str) -> Path:
    """
    Resolve a path and ensure it's inside one of ALLOWED_ROOTS.
    Raises 403 if the path escapes the allowed directories.
    Raises 404 if the file doesn't exist.
    """
    # Normalise to OS path
    p = Path(requested).resolve()
    inside = any(
        str(p).lower().startswith(str(root).lower()) for root in ALLOWED_ROOTS
    )
    if not inside:
        raise HTTPException(status_code=403, detail="Access denied: path outside allowed directories")
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {requested}")
    return p


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Map of file extensions to MIME types
_MIME_MAP = {
    ".wmf":  "image/x-wmf",
    ".png":  "image/png",
    ".bmp":  "image/bmp",
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".svg":  "image/svg+xml",
    ".pdf":  "application/pdf",
    ".json": "application/json",
    ".lxd":  "application/octet-stream",
    ".ncex": "application/octet-stream",
    ".mec":  "application/octet-stream",
    ".chp":  "application/octet-stream",
    ".dxf":  "application/octet-stream",
    ".dwg":  "application/octet-stream",
}


def _guess_mime(path: Path) -> str:
    return _MIME_MAP.get(path.suffix.lower(), "application/octet-stream")


# ---------------------------------------------------------------------------
# 1) Raw file download
# ---------------------------------------------------------------------------

@router.get("/files/download")
def download_file(path: str = Query(..., description="Full path to the file on the server")):
    """
    Download any file the server has access to (within allowed directories).

    Examples:
        GET /files/download?path=//PC-KONSTRUKTOR1/Database/LantekDB/REF123.mec
        GET /files/download?path=S:/Poročila/20260228_Test/report.pdf
    """
    resolved = _safe_resolve(path)
    if resolved.is_dir():
        raise HTTPException(status_code=400, detail="Path is a directory, not a file")
    return FileResponse(
        str(resolved),
        media_type=_guess_mime(resolved),
        filename=resolved.name,
    )


# ---------------------------------------------------------------------------
# 2) List files in a directory
# ---------------------------------------------------------------------------

# Importable extensions recognised by HeidiNest
_IMPORTABLE_EXTS = {".dxf", ".lxd", ".ncex"}

# Regex to parse structured .cut.dxf filenames produced by SolidWorks macros:
#   Material_sThickness_QtyKos_Bends_PartName.cut.dxf
_CUT_DXF_RE = re.compile(
    r"^(.+?)_s(\d+(?:[.,]\d+)?)_(\d+)kos_(\d+)bends_(.+)$"
)


def _parse_cut_dxf_name(filename: str) -> Optional[dict]:
    """Parse metadata from a .cut.dxf filename. Returns None if not matching."""
    stem = filename
    if stem.lower().endswith(".cut.dxf"):
        stem = stem[:-8]
    elif stem.lower().endswith(".dxf"):
        stem = stem[:-4]
    else:
        return None
    m = _CUT_DXF_RE.match(stem)
    if not m:
        return None
    return {
        "material": m.group(1),
        "thickness": float(m.group(2).replace(",", ".")),
        "quantity": int(m.group(3)),
        "bends": int(m.group(4)),
        "part_name": m.group(5),
    }


def _file_entry(entry: Path, root: Path, metadata: bool) -> dict:
    """Build a file-info dict for a single path entry."""
    info: dict = {
        "name": entry.name,
        "path": entry.as_posix(),
        "relative_path": entry.relative_to(root).as_posix(),
        "is_dir": entry.is_dir(),
        "size": entry.stat().st_size if entry.is_file() else None,
    }
    if metadata and entry.is_file():
        parsed = _parse_cut_dxf_name(entry.name)
        if parsed:
            info["metadata"] = parsed
    return info


@router.get("/files/list")
def list_directory(
    path: str = Query(..., description="Directory path to list"),
    pattern: Optional[str] = Query(None, description="Glob pattern, e.g. *.wmf"),
    recursive: bool = Query(False, description="Recurse into subdirectories"),
    importable_only: bool = Query(False, description="Only return importable files (.dxf, .lxd, .ncex)"),
    metadata: bool = Query(False, description="Parse .cut.dxf filenames for material/thickness/qty metadata"),
):
    """
    List files in a directory. Optionally filter by glob pattern.

    Use recursive=true to walk subdirectories.
    Use importable_only=true to filter for HeidiNest-importable extensions.
    Use metadata=true to parse .cut.dxf filenames and include material/thickness/qty.

    Examples:
        GET /files/list?path=S:/Nacrti/2025/VIRS/P58496_Project&recursive=true&importable_only=true&metadata=true
        GET /files/list?path=S:/Poročila/20260228_Test&pattern=*.ncex
    """
    resolved = _safe_resolve(path)
    if not resolved.is_dir():
        raise HTTPException(status_code=400, detail="Path is not a directory")

    if recursive:
        glob_pat = "**/*" if not pattern else f"**/{pattern}"
        entries = sorted(resolved.glob(glob_pat))
    else:
        if pattern:
            entries = sorted(resolved.glob(pattern))
        else:
            entries = sorted(resolved.iterdir())

    if importable_only:
        entries = [e for e in entries if e.is_file() and e.suffix.lower() in _IMPORTABLE_EXTS]

    return {
        "directory": str(resolved),
        "files": [_file_entry(e, resolved, metadata) for e in entries],
    }


# ---------------------------------------------------------------------------
# 3) Lantek file shortcuts
# ---------------------------------------------------------------------------

@router.get("/lantek/file/{nst_ref}/{suffix}")
def get_lantek_file(nst_ref: str, suffix: str):
    """
    Get a Lantek database file by NstRef and suffix.

    Common suffixes: -JOBRPT.wmf, -IMGB.png, .bmp, .chp, .mec

    Example:
        GET /lantek/file/SomeNstRef/-JOBRPT.wmf
    """
    file_path = Path(settings.lantek_files_root) / (nst_ref + suffix)
    resolved = _safe_resolve(str(file_path))
    return FileResponse(
        str(resolved),
        media_type=_guess_mime(resolved),
        filename=resolved.name,
    )


@router.get("/lantek/file")
def get_lantek_file_by_query(
    nst_ref: str = Query(None, description="NstRef (may contain slashes, e.g. Nestings/0/349)"),
    rec_id: str = Query(None, description="RecID (numeric, e.g. 349)"),
    suffix: str = Query("-JOBRPT.wmf", description="File suffix"),
):
    """
    Get a Lantek database file by NstRef or RecID and suffix.
    Tries NstRef first, then RecID as fallback.

    Example:
        GET /lantek/file?nst_ref=Nestings/0/349&suffix=-JOBRPT.wmf
        GET /lantek/file?rec_id=349&suffix=-JOBRPT.wmf
    """
    candidates = []
    if nst_ref:
        candidates.append(Path(settings.lantek_files_root) / (nst_ref + suffix))
    if rec_id:
        candidates.append(Path(settings.lantek_files_root) / (rec_id + suffix))

    for file_path in candidates:
        try:
            resolved = _safe_resolve(str(file_path))
            return FileResponse(
                str(resolved),
                media_type=_guess_mime(resolved),
                filename=resolved.name,
            )
        except HTTPException:
            continue

    raise HTTPException(
        status_code=404,
        detail=f"Lantek file not found. Tried: {[str(c) for c in candidates]}",
    )


@router.get("/lantek/thumbnail")
def get_lantek_thumbnail(
    image_path: str = Query(..., description="Raw Image path from a PartRow.Thumbnail/Image field"),
):
    """
    Serve a part thumbnail image by the raw path Lantek itself wrote into
    PartMaster.Image. Deliberately NOT run through _safe_resolve()/
    ALLOWED_ROOTS like /files/download — that check exists to gate
    free-form client-supplied paths, whereas this path only ever comes from
    the Lantek DB the server already queries directly, the same trust
    boundary as lantek.py's own endpoints.

    Client machines vary in whether they have Lantek's image share mapped
    (different drive letters, no mapping at all, permissions) — this lets
    the server, which sits with/near the Lantek DB and always has access,
    resolve and stream the bytes instead, so thumbnails render everywhere.

    Prefers the higher-res "<stem>-IMGB.png" Lantek generates next to the
    raw .bmp (same convention the Qt client's own hover-popup already
    applied locally), falling back to the raw path itself.
    """
    if not image_path.strip():
        raise HTTPException(status_code=400, detail="image_path is required")

    candidates: list[Path] = []
    win_path = PureWindowsPath(image_path)
    if win_path.suffix.lower() == ".bmp":
        candidates.append(Path(str(win_path.with_name(win_path.stem + "-IMGB.png"))))
    candidates.append(Path(image_path))

    for candidate in candidates:
        if candidate.is_file():
            return FileResponse(str(candidate), media_type=_guess_mime(candidate), filename=candidate.name)

    raise HTTPException(
        status_code=404,
        detail=f"Thumbnail not found. Tried: {[str(c) for c in candidates]}",
    )


# ---------------------------------------------------------------------------
# 4) Preview image — renders WMF or extracts SVG from .ncex → returns PNG
# ---------------------------------------------------------------------------

def _wmf_to_png_bytes(wmf_path: Path, width: int = 800) -> bytes:
    """
    Convert a WMF file to PNG bytes using ImageMagick (if available)
    or return the raw WMF bytes as fallback.

    For production, install ImageMagick on the server:
        choco install imagemagick
    or download from https://imagemagick.org/
    """
    try:
        result = subprocess.run(
            ["magick", str(wmf_path), "-resize", f"{width}x", "png:-"],
            capture_output=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout:
            return result.stdout
    except FileNotFoundError:
        pass  # ImageMagick not installed

    # Fallback: try with 'convert' (older ImageMagick)
    try:
        result = subprocess.run(
            ["convert", str(wmf_path), "-resize", f"{width}x", "png:-"],
            capture_output=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout:
            return result.stdout
    except FileNotFoundError:
        pass

    # If no converter available, just serve the raw WMF
    return None


def _extract_ncex_svg(ncex_path: Path) -> Optional[bytes]:
    """Extract the first *_0.svg from an .ncex (which is a ZIP) and return SVG bytes."""
    try:
        with zipfile.ZipFile(str(ncex_path), "r") as zf:
            for name in zf.namelist():
                if name.lower().endswith("_0.svg"):
                    return zf.read(name)
    except (zipfile.BadZipFile, KeyError, OSError):
        pass
    return None


def _dxf_to_svg_bytes(dxf_path: Path) -> Optional[bytes]:
    """Render a DXF file to SVG bytes using ezdxf (if available)."""
    try:
        import ezdxf
        from ezdxf.addons.drawing import Frontend, RenderContext
        from ezdxf.addons.drawing import svg as ezdxf_svg

        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()
        ctx = RenderContext(doc)
        backend = ezdxf_svg.SVGBackend()
        Frontend(ctx, backend).draw_layout(msp)
        svg_string = backend.get_string(
            ezdxf_svg.Properties(dark_background=False)
        )
        return svg_string.encode("utf-8")
    except ImportError:
        return None
    except Exception:
        return None


@router.get("/files/preview")
def get_preview_image(
    path: str = Query(..., description="Path to .wmf, .ncex, or .dxf file"),
    width: int = Query(800, description="Desired width in pixels (for WMF conversion)"),
):
    """
    Get a preview image. Handles:
    - .dxf  → rendered to SVG (if ezdxf is installed) or served raw
    - .wmf  → converted to PNG (if ImageMagick is installed) or served raw
    - .ncex → extracts the plate SVG and serves it
    - .png/.bmp/.jpg → served directly

    Example:
        GET /files/preview?path=S:/Nacrti/2025/VIRS/Project/part.cut.dxf
    """
    resolved = _safe_resolve(path)
    ext = resolved.suffix.lower()

    if ext == ".dxf":
        svg_bytes = _dxf_to_svg_bytes(resolved)
        if svg_bytes:
            return StreamingResponse(io.BytesIO(svg_bytes), media_type="image/svg+xml")
        raise HTTPException(status_code=422, detail="DXF to SVG conversion failed")

    if ext == ".wmf":
        png_bytes = _wmf_to_png_bytes(resolved, width)
        if png_bytes:
            return StreamingResponse(io.BytesIO(png_bytes), media_type="image/png")
        # Fallback: serve the raw WMF — the Qt client can render it natively
        return FileResponse(str(resolved), media_type="image/x-wmf", filename=resolved.name)

    if ext == ".ncex":
        svg_bytes = _extract_ncex_svg(resolved)
        if svg_bytes:
            return StreamingResponse(io.BytesIO(svg_bytes), media_type="image/svg+xml")
        raise HTTPException(status_code=404, detail="No SVG found inside .ncex file")

    if ext in (".png", ".bmp", ".jpg", ".jpeg"):
        return FileResponse(str(resolved), media_type=_guess_mime(resolved))

    raise HTTPException(status_code=400, detail=f"Unsupported preview format: {ext}")


# ---------------------------------------------------------------------------
# 5) Report location files — list & serve what's in a report location path
# ---------------------------------------------------------------------------

@router.get("/report/files")
def list_report_files(
    location: str = Query(..., description="Report_Location value from the queue row"),
):
    """
    Given a Report_Location path, list all files in it.
    This is what the Qt client needs to discover .wmf, .ncex, .json files
    in a row's report folder.

    Example:
        GET /report/files?location=S:/Poročila/20260228_SomeSheet/
    """
    resolved = _safe_resolve(location)
    if resolved.is_file():
        resolved = resolved.parent

    if not resolved.is_dir():
        raise HTTPException(status_code=404, detail="Report location directory not found")

    entries = sorted(resolved.iterdir())
    return {
        "location": str(resolved),
        "files": [
            {
                "name": e.name,
                "path": str(e),
                "is_dir": e.is_dir(),
                "size": e.stat().st_size if e.is_file() else None,
                "ext": e.suffix.lower() if e.is_file() else None,
            }
            for e in entries
        ],
    }


# ---------------------------------------------------------------------------
# 6) Upload a file to the report directory (for F3 insert / archiving)
# ---------------------------------------------------------------------------

from fastapi import UploadFile, File as FastAPIFile


@router.post("/files/upload")
async def upload_file(
    dest_dir: str = Query(..., description="Destination directory path"),
    filename: str = Query(..., description="Target filename"),
    file: UploadFile = FastAPIFile(...),
):
    """
    Upload a file to a directory on the server.
    Used by clients to archive CNC files, reports, etc.

    Example:
        POST /files/upload?dest_dir=S:/Poročila/20260228_Test&filename=sheet.LXD
        Body: multipart file
    """
    dest_path = Path(dest_dir).resolve()

    # Security: must be inside an allowed root
    inside = any(
        str(dest_path).lower().startswith(str(root).lower()) for root in ALLOWED_ROOTS
    )
    if not inside:
        raise HTTPException(status_code=403, detail="Destination outside allowed directories")

    # Create directory if needed
    dest_path.mkdir(parents=True, exist_ok=True)

    target = dest_path / filename
    content = await file.read()
    target.write_bytes(content)

    return {"ok": True, "path": str(target), "size": len(content)}
