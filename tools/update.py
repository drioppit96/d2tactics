"""Download the newest D2 Tactics from GitHub and patch it over this folder.

Keeps your settings.ini (new options are added, your values stay), your samples
and caches. Works with a public repository as is; for a private one, put a
GitHub access token in a file called github_token.txt next to main.py.
"""
import configparser
import io
import json
import os
import shutil
import ssl
import sys
import urllib.error
import urllib.request
import zipfile

REPO = "drioppit96/d2tactics"
BRANCH = "main"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION_FILE = os.path.join(ROOT, "version.txt")
TOKEN_FILE = os.path.join(ROOT, "github_token.txt")
KEEP = {"settings.ini", "options.ini", "github_token.txt", "version.txt"}           # never overwritten
SKIP_DIRS = ("d2samples", "d2samples2", "cache", ".git")


def _contexts():
    yield ssl.create_default_context()
    # old Windows (7) may lack newer root certificates: fall back to pip's bundled ones
    try:
        from pip._vendor import certifi
        yield ssl.create_default_context(cafile=certifi.where())
    except Exception:
        pass


def fetch(url, accept="application/vnd.github+json"):
    headers = {"User-Agent": "d2tactics-updater", "Accept": accept}
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE) as f:
            token = f.read().strip()
        if token:
            headers["Authorization"] = "token " + token
    last = None
    for ctx in _contexts():
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, context=ctx, timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError:
            raise
        except Exception as e:      # certificate or connection problem: try the next option
            last = e
    raise last


def merge_settings(new_text):
    """Take the new settings.ini layout (new options, comments) but keep every value you set."""
    path = os.path.join(ROOT, "settings.ini")
    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write(new_text)
        return
    mine = configparser.ConfigParser()
    mine.read(path)
    out, section, added = [], None, []
    for line in new_text.splitlines():
        st = line.strip()
        if st.startswith("[") and st.endswith("]"):
            section = st[1:-1]
        elif section and "=" in st and not st.startswith(("#", ";")):
            key = st.split("=", 1)[0].strip()
            if mine.has_option(section, key):
                line = "%s = %s" % (key, mine.get(section, key))
            else:
                added.append(key)
        out.append(line)
    with open(path, "w") as f:
        f.write("\n".join(out) + "\n")
    if added:
        print("  settings.ini: new options %s (your other settings were kept)" % ", ".join(added))


def main():
    print("Checking GitHub for updates...")
    try:
        info = json.loads(fetch("https://api.github.com/repos/%s/commits/%s" % (REPO, BRANCH)).decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print("\nGitHub says the repository was not found. It is private, so the updater needs")
            print("either the repository to be public, or a token in github_token.txt.")
        else:
            print("\nGitHub error: %s" % e)
        return 1
    except Exception as e:
        print("\nCould not reach GitHub: %s" % e)
        return 1
    sha = info["sha"]
    msg = info.get("commit", {}).get("message", "").split("\n")[0]
    have = open(VERSION_FILE).read().strip() if os.path.exists(VERSION_FILE) else ""
    if have == sha:
        print("You already have the newest version (%s)." % sha[:7])
        return 0
    print("New version %s: %s" % (sha[:7], msg))
    print("Downloading...")
    data = fetch("https://api.github.com/repos/%s/zipball/%s" % (REPO, sha), accept="application/vnd.github+json")
    z = zipfile.ZipFile(io.BytesIO(data))
    names = z.namelist()
    prefix = names[0].split("/")[0] + "/"
    updated = 0
    for name in names:
        if not name.startswith(prefix) or name.endswith("/"):
            continue
        rel = name[len(prefix):]
        if not rel or rel.split("/")[0] in SKIP_DIRS:
            continue
        if rel == "settings.ini":
            merge_settings(z.read(name).decode("utf-8", "replace"))
            continue
        if rel in KEEP:
            continue
        dest = os.path.join(ROOT, *rel.split("/"))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        content = z.read(name)
        if os.path.exists(dest):
            with open(dest, "rb") as f:
                if f.read() == content:
                    continue
        tmp = dest + ".new"
        with open(tmp, "wb") as f:
            f.write(content)
        try:
            os.replace(tmp, dest)
        except OSError:
            shutil.copyfile(tmp, dest)
            os.remove(tmp)
        updated += 1
    with open(VERSION_FILE, "w") as f:
        f.write(sha)
    print("Done: %d files updated. You now have version %s." % (updated, sha[:7]))
    return 0


if __name__ == "__main__":
    code = main()
    sys.exit(code)
