"""Heidi Server \u2014 Configuration

Reads settings from the .env file next to this script.
Application versions are read from per-app VERSION files.
"""

from pathlib import Path
from pydantic_settings import BaseSettings

_ENV_FILE = Path(__file__).resolve().parent / ".env"
_SM_VERSION_FILE = Path(__file__).resolve().parent.parent / "SheetManager" / "VERSION.txt"
_PE_VERSION_FILE = Path(__file__).resolve().parent.parent / "ProjectExplorer" / "VERSION.txt"
_NEST_VERSION_FILE = Path(__file__).resolve().parent.parent / "HeidiNest" / "VERSION.txt"
_NEST_VERSION_FILE = Path(__file__).resolve().parent.parent / "HeidiNest" / "VERSION.txt"

def _read_version(path: Path) -> str:
    """Read version string from a VERSION file."""
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return "0.0.0"


_VERSION_MARKER_NAMES = {"pe": "pe-version.txt", "nest": "nest-version.txt", "sm": "sm-version.txt"}
_VERSION_FALLBACK_FILES = {"pe": _PE_VERSION_FILE, "nest": _NEST_VERSION_FILE, "sm": _SM_VERSION_FILE}


def published_version(app: str) -> str:
    """The version actually being served to update-checker clients right
    now for `app` ('sm'/'pe'/'nest').

    Reads the *-version.txt marker each app's own deploy-to-stable step
    writes into update_dir (e.g. pe_publish_stable.bat for PE) -- i.e. what
    was deliberately PUBLISHED, not whatever the live source tree's own
    VERSION.txt currently says. Those two used to be the same file, which
    meant bumping VERSION.txt for a local dev-iteration build (done on
    every single test cycle) immediately changed what this server
    advertised to every shop-floor machine polling /version, even though
    the actual files in update_dir -- what /update/manifest and
    /update/file actually hand out -- hadn't changed at all. Falls back to
    the live source VERSION.txt only if update_dir isn't configured or
    nothing's been published there yet (e.g. a fresh checkout, or an app
    -- today, 'sm' -- whose own deploy script doesn't write a marker yet).
    """
    app = app.lower()
    if settings.update_dir:
        marker = Path(settings.update_dir) / _VERSION_MARKER_NAMES.get(app, _VERSION_MARKER_NAMES["sm"])
        if marker.is_file():
            return _read_version(marker)
    return _read_version(_VERSION_FALLBACK_FILES.get(app, _SM_VERSION_FILE))


class Settings(BaseSettings):
    # MySQL connection
    db_host: str = "192.168.52.104"
    db_port: int = 33062
    db_user: str = "Jure"
    db_password: str = ""
    db_name: str = "nalogi"
    db_table: str = "cutting_tickets"
    db_material_table: str = "material"

    # File paths (the server machine must have access to these)
    lantek_files_root: str = "//PC-KONSTRUKTOR1/Database/LantekDB/"
    report_dir: str = "S:/Poročila/"
    cnc_path: str = "P:/3000"
    projects_root: str = "S:/Nacrti/"
    projects_documentation_root: str = "S:/Projekti/Documentation/"

    # Lantek SQL Server (MSSQL via ODBC)
    lantek_server: str = "PC-KONSTRUKTOR1\\LANTEK"
    lantek_database: str = "LantekDB"
    lantek_user: str = "sa"
    lantek_password: str = ""
    lantek_sheet_header_table: str = "DIS_NEST_NEST_00000100"
    lantek_sheet_parts_table: str = "DIS_NEST_NEST_00000500"
    lantek_part_master_table: str = "PPRR_PPRR_00000100"
    lantek_material_map_table: str = "DIS_MMTT_MMTT_00000100"
    lantek_owned_files_table: str = "SYST_OWND_00000100"

    # Application versions -- see published_version() above. NOT stored here
    # as fields: that used to read each app's live source VERSION.txt once
    # at server startup, which drifted from what was actually published the
    # moment anyone bumped VERSION.txt for a local dev build.
    app_download_hint: str = ""
    update_dir: str = ""          # folder with latest build (e.g. build/deploy)

    # Server
    server_host: str = "0.0.0.0"
    server_port: int = 8080

    class Config:
        env_file = str(_ENV_FILE)


settings = Settings()
