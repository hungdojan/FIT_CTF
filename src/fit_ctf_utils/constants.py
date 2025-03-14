import os
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_PASSWORD_LENGTH = 10
DEFAULT_STARTING_PORT = 10000
DEFAULT_MODULE_BUILD_DIRNAME = "build_dir"
DEFAULT_PROJECT_MODULE_PREFIX = "prj_"
DEFAULT_USER_MODULE_PREFIX = "usr_"

# generate root directory paths
load_dotenv()
__default_config_path = f"{os.getenv('HOME', '')}/.local/share/FIT_CTF"
__prj_share_dir = os.getenv("PROJECT_SHARE_DIR", f"{__default_config_path}/project")
__user_share_dir = os.getenv("USER_SHARE_DIR", f"{__default_config_path}/user")
__module_share_dir = os.getenv("MODULE_SHARE_DIR", f"{__default_config_path}/module")

PRJ_SHARE_PATH = Path(__prj_share_dir)
USER_SHARE_PATH = Path(__user_share_dir)
MODULE_SHARE_PATH = Path(__module_share_dir)
