"""Build the static frontend with a public FastAPI URL for Render Static Sites."""
import json
import ipaddress
import os
import re
import shutil
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
DIST = Path(os.getenv("BLOODLINE_BUILD_DIR", str(ROOT / "dist"))).resolve()


def validate_api_origin(value: str) -> str:
    """Accept only a public HTTPS origin, without credentials or URL components."""
    value = value.strip()
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        port = parsed.port  # Access validates malformed and out-of-range ports.
    except ValueError as exc:
        raise ValueError("BLOODLINE_API_URL must be a valid HTTPS origin.") from exc

    if (
        parsed.scheme.lower() != "https"
        or not parsed.netloc
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
        or any(char.isspace() for char in value)
    ):
        raise ValueError("BLOODLINE_API_URL must be an HTTPS origin without credentials, path, query, or fragment.")

    hostname = hostname.rstrip(".").lower()
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise ValueError("BLOODLINE_API_URL cannot point to localhost.")

    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        try:
            ascii_host = hostname.encode("idna").decode("ascii")
        except UnicodeError as exc:
            raise ValueError("BLOODLINE_API_URL must contain a valid public hostname.") from exc
        labels = ascii_host.split(".")
        if len(labels) < 2 or any(
            not label or len(label) > 63 or not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", label)
            for label in labels
        ):
            raise ValueError("BLOODLINE_API_URL must contain a valid public hostname.")
        host_for_url = ascii_host
    else:
        if not address.is_global:
            raise ValueError("BLOODLINE_API_URL cannot point to a private or local IP address.")
        host_for_url = f"[{address.compressed}]" if address.version == 6 else address.compressed

    port_suffix = f":{port}" if port and port != 443 else ""
    return f"https://{host_for_url}{port_suffix}"


try:
    API_URL = validate_api_origin(os.getenv("BLOODLINE_API_URL", ""))
except ValueError as exc:
    raise SystemExit(f"{exc} Set BLOODLINE_API_URL to the deployed HTTPS FastAPI origin before building.") from exc

if DIST.exists() and any(DIST.iterdir()):
    raise SystemExit(f"Refusing to overwrite non-empty build directory: {DIST}")
DIST.mkdir(parents=True, exist_ok=True)
for name in ("index.html", "viz.js", "ml-pages.js", "sw.js"):
    shutil.copy2(ROOT / name, DIST / name)
(DIST / "config.js").write_text(
    "window.BLOODLINE_CONFIG = "
    + json.dumps({"apiUrl": API_URL, "demoMode": os.getenv("BLOODLINE_FACULTY_DEMO", "0") == "1"})
    + ";\n",
    encoding="utf-8",
)
print(f"Built static BloodLine frontend for {API_URL} (faculty demo {'enabled' if os.getenv('BLOODLINE_FACULTY_DEMO', '0') == '1' else 'disabled'}).")
