import os
import sys
import tempfile

# Use a throwaway SQLite DB for API tests, never the developer's bloodline.db.
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp.name}"
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
