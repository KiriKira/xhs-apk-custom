import os
import re
from pathlib import Path

import requests


def _headers():
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def download_apkeditor():
    """Download the latest stable APKEditor release into bins/apkeditor.jar."""
    out = Path("bins/apkeditor.jar")
    out.parent.mkdir(parents=True, exist_ok=True)

    response = requests.get(
        "https://api.github.com/repos/REAndroid/APKEditor/releases",
        headers=_headers(),
        timeout=60,
    )
    response.raise_for_status()

    releases = [r for r in response.json() if not r.get("prerelease") and not r.get("draft")]
    if not releases:
        raise RuntimeError("No stable APKEditor release found")

    asset = None
    for candidate in releases[0].get("assets", []):
        if re.search(r"APKEditor.*\.jar$", candidate.get("name", ""), re.IGNORECASE):
            asset = candidate
            break

    if asset is None:
        raise RuntimeError("Latest APKEditor release has no matching JAR asset")

    print(f"Downloading APKEditor: {asset['name']}")
    with requests.get(asset["browser_download_url"], stream=True, timeout=120) as download:
        download.raise_for_status()
        with out.open("wb") as handle:
            for chunk in download.iter_content(1024 * 1024):
                if chunk:
                    handle.write(chunk)

    if out.stat().st_size < 1_000_000:
        raise RuntimeError(f"APKEditor download is unexpectedly small: {out.stat().st_size} bytes")

    return str(out)
