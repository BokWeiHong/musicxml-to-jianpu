"""Publish the built installer as a GitHub release (one command).

Usage::

    set GITHUB_TOKEN=ghp_...            # classic token with "repo" scope
    python publish_release.py --notes "Fixed rests, bigger numbers"

    python publish_release.py --dry-run # show the plan, touch nothing
    python publish_release.py --asset release\\JianpuConverter-Setup-1.0.1.exe

What it does:
  1. reads __version__ and locates release\\JianpuConverter-Setup-<version>.exe
  2. creates (or reuses) the GitHub release tagged ``v<version>``
  3. uploads the installer as the release asset
  4. prints the release URL

Installed copies of the app poll ``/releases/latest`` (see updater.py), so
publishing the release here is all that is needed for friends to be offered
the update - they just click "Update now" in the app.
"""


import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jianpu_converter import GITHUB_REPO, __version__  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
API = "https://api.github.com/repos/%s" % GITHUB_REPO
UPLOAD_API = "https://uploads.github.com/repos/%s" % GITHUB_REPO
USER_AGENT = "JianpuConverter-publisher/%s" % __version__


def _request(url, token, method="GET", data=None, content_type=None):
    """Call the GitHub API and return (status, parsed-json-or-bytes)."""
    headers = {"Authorization": "Bearer " + token,
               "Accept": "application/vnd.github+json",
               "User-Agent": USER_AGENT}
    if content_type:
        headers["Content-Type"] = content_type
    request = urllib.request.Request(url, data=data, headers=headers,
                                     method=method)
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            body = response.read()
            status = response.status
    except urllib.error.HTTPError as err:
        body = err.read()
        status = err.code
    try:
        return status, json.loads(body.decode("utf-8", "replace"))
    except ValueError:
        return status, body


def _explain(status, payload):
    if isinstance(payload, dict) and payload.get("message"):
        hint = ""
        if status == 401:
            hint = ("\nCheck that GITHUB_TOKEN is a valid token with the "
                    "\"repo\" scope (Settings -> Developer settings -> "
                    "Personal access tokens).")
        elif status == 403:
            hint = ("\nThe token authenticated but may not publish to this "
                    "repository.  For a fine-grained token: Repository access "
                    "-> include this repo, and Repository permissions -> "
                    "Contents: Read and write.  A classic token needs the "
                    "\"repo\" scope.")
        return "GitHub said: %s%s" % (payload["message"], hint)
    return "GitHub returned HTTP %s" % status


def _head_commit():
    """The commit the tag should point at (the one you built from)."""
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                             capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except Exception:
        return None


def main(argv):
    args = argv[1:]
    dry_run = "--dry-run" in args
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if "--token" in args:
        token = args[args.index("--token") + 1]
    notes = ""
    if "--notes" in args:
        notes = args[args.index("--notes") + 1]
    asset = os.path.join(ROOT, "release",
                         "JianpuConverter-Setup-%s.exe" % __version__)
    if "--asset" in args:
        asset = args[args.index("--asset") + 1]

    tag = "v" + __version__
    print("Repository : %s" % GITHUB_REPO)
    print("Version    : %s  (tag %s)" % (__version__, tag))
    print("Installer  : %s" % asset)
    if not os.path.isfile(asset):
        raise SystemExit(
            "Installer not found.\n\nBuild it first:\n"
            "  python patch_jianpu_ly_src.py\n"
            "  python -m PyInstaller JianpuConverter.spec\n"
            "  Copy-Item -Recurse -Force lilypond-2.26.0 dist\\JianpuConverter\\\n"
            "  tools\\nsis\\nsis-3.09\\makensis.exe installer\\JianpuConverter.nsi")
    print("Size       : %.1f MB" % (os.path.getsize(asset) / 1048576.0))
    if dry_run:
        print("\n[dry run] would publish tag %s and upload %s"
              % (tag, os.path.basename(asset)))
        return 0
    if not token:
        raise SystemExit(
            "No GitHub token found.\n\n"
            "Create a classic personal access token with the \"repo\" scope, "
            "then run:\n"
            "  set GITHUB_TOKEN=ghp_your_token_here\n"
            "  python publish_release.py --notes \"what changed\"")

    # 1. is this version already released (re-publishing)?
    status, payload = _request("%s/releases/tags/%s" % (API, tag), token)
    if status == 200:
        release = payload
        print("Reusing existing release %s" % release["html_url"])
    elif status == 404:
        body = {"tag_name": tag,
                "name": "Jianpu Converter %s" % __version__,
                "body": notes or "Bug fixes and improvements.",
                "draft": False,
                "prerelease": False}
        commit = _head_commit()
        if commit:
            body["target_commitish"] = commit
        status, release = _request(API + "/releases", token, "POST",
                                   json.dumps(body).encode("utf-8"),
                                   "application/json")
        if status not in (200, 201):
            raise SystemExit("Could not create the release.\n"
                             + _explain(status, release))
        print("Created release %s" % release["html_url"])
    else:
        raise SystemExit("Could not look up the release.\n"
                         + _explain(status, payload))

    release_id = release["id"]
    asset_name = os.path.basename(asset)

    # 2. replace a previously uploaded asset with the same name
    status, assets = _request("%s/releases/%s/assets" % (API, release_id), token)
    if status == 200:
        for existing in assets:
            if existing.get("name") == asset_name:
                print("Replacing existing asset %s" % asset_name)
                _request("%s/releases/assets/%s" % (API, existing["id"]),
                         token, "DELETE")

    # 3. upload the installer
    with open(asset, "rb") as handle:
        data = handle.read()
    status, payload = _request(
        "%s/releases/%s/assets?name=%s" % (UPLOAD_API, release_id,
                                           urllib.parse.quote(asset_name)),
        token, "POST", data, "application/octet-stream")
    if status not in (200, 201):
        raise SystemExit("Upload failed.\n" + _explain(status, payload))
    print("Uploaded %s" % asset_name)

    print("\nDone. Installed apps will now be offered v%s:" % __version__)
    print("  %s" % release["html_url"])
    print("\nReminder: the app checks /releases/latest, so this release must "
          "not be a draft or pre-release.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

