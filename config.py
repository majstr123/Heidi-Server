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

    # Application versions (read from per-app VERSION files at startup)
    sm_version: str = _read_version(_SM_VERSION_FILE)
    pe_version: str = _read_version(_PE_VERSION_FILE)
    nest_version: str = _read_version(_NEST_VERSION_FILE)
    app_version: str = sm_version  # backward compat / default
    app_download_hint: str = ""
    update_dir: str = ""          # folder with latest build (e.g. build/deploy)

    # Server
    server_host: str = "0.0.0.0"
    server_port: int = 8080

    class Config:
        env_file = str(_ENV_FILE)


settings = Settings()
