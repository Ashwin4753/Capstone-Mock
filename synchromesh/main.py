from __future__ import annotations
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from interaction.dashboard.app import main as dashboard_main

# -----------------------------
# Paths / directories
# -----------------------------
ROOT_DIR = Path(__file__).resolve().parent
ARTIFACTS_DIR = ROOT_DIR / "artifacts"
LOG_DIR = ARTIFACTS_DIR / "logs"
LOG_FILE = LOG_DIR / "system_logs.log"

LOG_DIR.mkdir(parents=True, exist_ok=True)
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

# -----------------------------
# Logging
# -----------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(str(LOG_FILE), encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("SynchroMesh-Root")


def _bool_env_present(value: str | None) -> bool:
    return bool(value and str(value).strip())


def load_environment() -> dict[str, str]:
    """
    Load environment variables, infer execution capabilities, and expose
    a simplified runtime mode for the dashboard.

    Mode priority:
      1. Explicit SYNCHROMESH_MODE=demo|local|hybrid|remote
      2. Auto-detect from available credentials and local repo support
    """
    load_dotenv()

    figma_token = os.getenv("FIGMA_API_KEY") or os.getenv("FIGMA_ACCESS_TOKEN")
    github_token = os.getenv("GITHUB_TOKEN") or os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN")
    forced_mode = (os.getenv("SYNCHROMESH_MODE") or "").strip().lower()

    has_figma = _bool_env_present(figma_token)
    has_github = _bool_env_present(github_token)

    if forced_mode in {"demo", "local", "hybrid", "remote"}:
        mode = forced_mode
        logger.info("SYNCHROMESH_MODE override detected: %s", mode)
    else:
        if has_github:
            mode = "hybrid"
        else:
            mode = "local"

    logger.info("====================================")
    logger.info("SynchroMesh Environment Configuration")
    logger.info("Execution Mode: %s", mode.upper())
    logger.info("Figma Token Present: %s", has_figma)
    logger.info("GitHub Token Present: %s", has_github)
    logger.info("Artifacts Directory: %s", ARTIFACTS_DIR)
    logger.info("Log File: %s", LOG_FILE)
    logger.info("====================================")

    if not has_github:
        logger.warning("GitHub MCP token not detected. Remote enrichment may be unavailable.")
    if not has_figma:
        logger.info("Figma token not detected. Frontend token enrichment will remain optional.")

    os.environ["SYNCHROMESH_MODE"] = mode
    os.environ["SYNCHROMESH_ARTIFACTS_DIR"] = str(ARTIFACTS_DIR)

    return {
        "mode": mode,
        "has_figma": str(has_figma),
        "has_github": str(has_github),
        "artifacts_dir": str(ARTIFACTS_DIR),
        "log_file": str(LOG_FILE),
    }


if __name__ == "__main__":
    print(
        """
==================================================
SYNCHROMESH: ENGINEERING MODERNIZATION PLATFORM
==================================================
"""
    )

    env_info = load_environment()
    logger.info("Starting premium modernization dashboard in %s mode.", env_info["mode"])
    dashboard_main()