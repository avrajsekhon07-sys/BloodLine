import os
import sys
import tempfile
import secrets

# Use a throwaway SQLite DB for API tests, never the developer's bloodline.db.
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp.name}"
os.environ["BLOODLINE_ALLOW_DESTRUCTIVE_SEED"] = "1"
os.environ["BLOODLINE_LOCAL_DEMO_PASSWORD"] = secrets.token_urlsafe(24)
os.environ["BLOODLINE_TEST_PASSWORD"] = os.environ["BLOODLINE_LOCAL_DEMO_PASSWORD"]
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
