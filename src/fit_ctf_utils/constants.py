import os
import sys
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_PASSWORD_LENGTH = 10
DEFAULT_STARTING_PORT = 10000

# generate root directory paths
load_dotenv()


def get_db_info() -> tuple[str, str]:
    # TODO: move config to SHARE DIR location
    db_host = os.getenv("DB_HOST")
    if not db_host:
        sys.exit("Environment variable `DB_HOST` is not set.")

    db_name = os.getenv("DB_NAME")
    if not db_name:
        sys.exit("Environment variable `DB_NAME` is not set.")
    return db_host, db_name


def get_paths() -> tuple[Path, Path, Path]:
    default_config_path = f"{os.getenv('HOME', '')}/.local/share/FIT_CTF"
    prj_env = os.getenv("PROJECT_SHARE_DIR", f"{default_config_path}/project")
    user_env = os.getenv("USER_SHARE_DIR", f"{default_config_path}/user")
    module_env = os.getenv("MODULE_SHARE_DIR", f"{default_config_path}/module")

    prj_share_path = Path(prj_env)
    user_share_path = Path(user_env)
    module_share_path = Path(module_env)
    return prj_share_path, user_share_path, module_share_path
