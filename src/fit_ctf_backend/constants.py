import os
from dotenv import load_dotenv

load_dotenv()

_ROOT_APP_DIR = "{}/../..".format(os.path.dirname(os.path.realpath(__file__)))
CONFIG_PATH = os.getenv("CONFIG_PATH", f"{_ROOT_APP_DIR}/config")
DEFAULT_PASSWORD_LENGTH = 10

TEMPLATE_FILES = {
    "shadow": "shadow.j2",
    "compose": "compose.yaml.j2",
}
