"""Checks GitHub releases for a newer version, once, in the background."""
import json
import re
import threading
import urllib.request

from src.version import APP_VERSION, GITHUB_REPO


def _parse(tag):
    """'v15.1' -> (15, 1); None when the tag is not a version number."""
    match = re.fullmatch(r"v?(\d+(?:\.\d+)*)", str(tag).strip())
    return tuple(int(n) for n in match.group(1).split(".")) if match else None


class UpdateChecker:
    def __init__(self):
        self.latest_tag = None
        self.release_url = f"https://github.com/{GITHUB_REPO}/releases/latest"
        self.update_available = False
        threading.Thread(target=self._check, daemon=True).start()

    def _check(self):
        try:
            request = urllib.request.Request(
                f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
                headers={"Accept": "application/vnd.github+json", "User-Agent": "RubikSimulator"},
            )
            with urllib.request.urlopen(request, timeout=8) as response:
                data = json.load(response)
            latest, current = _parse(data.get("tag_name")), _parse(APP_VERSION)
            if latest is None or current is None:
                return
            self.release_url = data.get("html_url") or self.release_url
            self.latest_tag = data["tag_name"]
            self.update_available = latest > current
        except Exception:
            pass  # offline or rate limited: no banner
