import os

import pytest

if os.getenv("ENABLE_CONTAINER_CLIENT_TESTING") == "0":
    pytest.skip("Container testing not enabled.", allow_module_level=True)
