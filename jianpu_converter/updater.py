"""Self-update: find a newer GitHub release, download it, run its installer.

The installed app asks GitHub for its latest *published* release, compares the
release tag (``v1.0.1`` …) with ``__version__`` and — when the user agrees —
downloads the ``JianpuConverter-Setup-*.exe`` asset and launches it silently.
The installer (``installer/JianpuConverter.nsi``) closes the running app,
replaces the files and, because we pass ``/RELAUNCH``, starts the new version
again.  Friends therefore only ever have to click "Update now" once.

Everything here is best-effort: when the machine is offline, GitHub is
unreachable or the response looks unexpected, these functions return None /
raise a clear RuntimeError and the app keeps working unchanged.

Standard library only (urllib) - no third-party dependency is added.
"""


import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

from . import GITHUB_REPO, __version__


GITHUB_API_LATEST = ("https://api.github.com/repos/%s/releases/latest"
                     % GITHUB_REPO)
GITHUB_RELEASES_PAGE = "https://github.com/%s/releases" % GITHUB_REPO

# GitHub asks every client to identify itself; being explicit also means a
# blocked/limited request fails fast instead of hanging.
_USER_AGENT = "JianpuConverter/%s (+https://github.com/%s)" % (__version__,
                                                               GITHUB_REPO)

_TIMEOUT = 8            # seconds for the small JSON request
_DOWNLOAD_TIMEOUT = 60  # seconds for the installer download
_CHUNK = 64 * 1024


class ReleaseInfo:
    """A published GitHub release that carries a downloadable installer."""

    def __init__(self, version, tag, name, notes, asset_name, asset_url,
                 page_url, digest=""):
        self.version = version      # normalised digits, e.g. "1.0.1"
        self.tag = tag              # the git tag, e.g. "v1.0.1"
        self.name = name            # release title
        self.notes = notes          # release body (may be empty)
        self.asset_name = asset_name
        self.asset_url = asset_url  # browser_download_url of the .exe
        self.page_url = page_url    # human-readable release page
        self.digest = digest        # "sha256:..." when GitHub provides one

    def __repr__(self):
        return "ReleaseInfo(%s, %s)" % (self.version, self.asset_name)


def parse_version(text):
    """``"v1.2.3"`` → ``(1, 2, 3)``; tolerates ``1.2.3-beta`` / junk input.

    Always returns a 3-tuple so tuple comparison is meaningful even for
    sloppy tags like ``v1.2``.
    """
    numbers = re.findall(r"\d+", str(text or ""))
    parts = [int(n) for n in numbers[:3]]
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def is_newer(remote_version, local_version=None):
    """True when *remote_version* is a later (numeric) version than local."""
    return parse_version(remote_version) > parse_version(
        local_version or __version__)


def _normalise_version(tag):
    return ".".join(str(n) for n in parse_version(tag))


def _pick_installer_asset(assets):
    """Choose the Setup .exe out of a release payload's asset list."""
    best = None
    for asset in assets or []:
        name = asset.get("name") or ""
        url = asset.get("browser_download_url")
        if not url or not name.lower().endswith(".exe"):
            continue
        # prefer "JianpuConverter-Setup-1.0.1.exe" over any other .exe
        score = 2 if "setup" in name.lower() else 1
        if best is None or score > best[0]:
            best = (score, asset)
    return best[1] if best else None


def fetch_latest_release(timeout=_TIMEOUT):
    """Return the newest published release, or None (offline / no release).

    GitHub answers ``/releases/latest`` with 404 while the repository has no
    published release yet - that is a normal state, not an error.
    """
    request = urllib.request.Request(
        GITHUB_API_LATEST,
        headers={"User-Agent": _USER_AGENT,
                 "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8", "replace"))
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return None
    return _release_from_payload(payload)


def check_for_update(current_version=None):
    """Return a ReleaseInfo when GitHub has a newer version, else None."""
    info = fetch_latest_release()
    if info is not None and is_newer(info.version, current_version):
        return info
    return None


def download_installer(info, dest_dir=None, progress=None):
    """Download the installer of *info* and return the local file path.

    progress(bytes_done, total_bytes) is called while downloading (total is 0
    when the server does not send a Content-Length).  When GitHub published a
    sha256 digest the file is verified and removed on mismatch.
    """
    target_dir = dest_dir or tempfile.mkdtemp(prefix="jianpu_update_")
    path = os.path.join(target_dir, info.asset_name or "JianpuConverter-Setup.exe")
    digest = hashlib.sha256()
    request = urllib.request.Request(info.asset_url,
                                     headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(request, timeout=_DOWNLOAD_TIMEOUT) as response:
        total = int(response.headers.get("Content-Length") or 0)
        done = 0
        with open(path, "wb") as out_file:
            while True:
                chunk = response.read(_CHUNK)
                if not chunk:
                    break
                out_file.write(chunk)
                digest.update(chunk)
                done += len(chunk)
                if progress is not None:
                    progress(done, total)

    expected = (info.digest or "").lower()
    if expected.startswith("sha256:"):
        if digest.hexdigest().lower() != expected.split(":", 1)[1].strip():
            os.remove(path)
            raise RuntimeError(
                "The downloaded installer failed its checksum check.")
    return path


def launch_installer(path, relaunch=True):
    """Run the downloaded setup silently, detached from this process.

    ``/S`` = NSIS silent mode, ``/RELAUNCH`` = start the freshly installed app
    again once the upgrade is finished.  Detaching (DETACHED_PROCESS) lets the
    current app exit without killing the installer.
    """
    args = [path, "/S"]
    if relaunch:
        args.append("/RELAUNCH")
    flags = 0
    if os.name == "nt":
        flags = (getattr(subprocess, "DETACHED_PROCESS", 0)
                 | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    subprocess.Popen(args, close_fds=True, creationflags=flags)


def _release_from_payload(payload):
    """Build a ReleaseInfo from GitHub's JSON (or None if it has no .exe)."""
    if not isinstance(payload, dict):
        return None
    tag = payload.get("tag_name") or ""
    if not tag:
        return None
    asset = _pick_installer_asset(payload.get("assets"))
    if asset is None:
        return None
    name = payload.get("name") or tag
    return ReleaseInfo(
        version=_normalise_version(tag),
        tag=tag,
        name=name,
        notes=(payload.get("body") or "").strip(),
        asset_name=asset.get("name") or "JianpuConverter-Setup.exe",
        asset_url=asset["browser_download_url"],
        page_url=payload.get("html_url") or GITHUB_RELEASES_PAGE,
        digest=asset.get("digest") or "",
    )


def is_frozen():
    """True inside the PyInstaller build (i.e. for friends' installed app)."""
    return bool(getattr(sys, "frozen", False))
