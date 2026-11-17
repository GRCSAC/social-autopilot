"""GRCSAC Studio -> Instagram, directly through Meta's Instagram API.

No Buffer. The studio Instagram account (a professional account) is published to
straight from GitHub Actions with the Instagram API with Instagram Login:
create a media container from a public image URL, then publish it. Images are the
same jsDelivr-served cards the rest of this repo uses.

  python ig_studio.py check     # who the token belongs to, when it expires
  python ig_studio.py build     # render the next card(s) into public/cards + _studio_batch.json
  python ig_studio.py publish   # wait for the image URL, publish, advance the cursor

Environment:
  IG_STUDIO_TOKEN       bootstrap long-lived token (GitHub secret), used only until the
                        encrypted store below exists
  IG_STUDIO_TOKEN_KEY   Fernet key (GitHub secret) for content/ig_studio_token.enc
  PUBLIC_BASE_URL       where public/ is served from (jsDelivr)
  DRY_RUN=1             render + print, no API calls, no state change
  IG_API_VERSION        default v22.0

Token life: Meta long-lived tokens last 60 days and can be refreshed once they are
at least a day old. Every run refreshes and writes the new token back to the
encrypted store, which is committed, so the token never ages out while the
schedule keeps running. If the schedule stops for 60+ days, generate a new token
in the Meta app dashboard and update the IG_STUDIO_TOKEN secret; delete the .enc
file to force the bootstrap path.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
STATE = ROOT / "content" / "state.json"
LIB = ROOT / "content" / "studio_instagram.json"
CARDS = ROOT / "public" / "cards"
BATCH = ROOT / "_studio_batch.json"
TOKEN_FILE = ROOT / "content" / "ig_studio_token.enc"

API = "https://graph.instagram.com"
VERSION = os.environ.get("IG_API_VERSION", "v22.0")
CURSOR = "studio_instagram"


# ------------------------------------------------------------------ http
def _call(method, path, params=None, token=None):
    params = dict(params or {})
    if token:
        params["access_token"] = token
    url = f"{API}/{VERSION}/{path.lstrip('/')}" if not path.startswith("http") else path
    data = None
    if method == "GET":
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    else:
        data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        try:
            msg = json.loads(body)["error"]
            raise RuntimeError(f"Instagram API {e.code}: {msg.get('message')} "
                               f"(code {msg.get('code')}, subcode {msg.get('error_subcode')})")
        except (ValueError, KeyError):
            raise RuntimeError(f"Instagram API {e.code}: {body[:400]}")


def _redact(s):
    return s[:6] + "..." + s[-4:] if s and len(s) > 14 else "***"


# ------------------------------------------------------------------ token store
def _fernet():
    key = os.environ.get("IG_STUDIO_TOKEN_KEY")
    if not key:
        return None
    from cryptography.fernet import Fernet
    return Fernet(key.encode())


def load_token():
    """Return {token, expires_at, refreshed_at} from the encrypted store, else
    from the bootstrap secret."""
    f = _fernet()
    if f and TOKEN_FILE.exists():
        rec = json.loads(f.decrypt(TOKEN_FILE.read_bytes()).decode())
        rec["source"] = "store"
        return rec
    tok = os.environ.get("IG_STUDIO_TOKEN")
    if not tok:
        raise RuntimeError("No token: set IG_STUDIO_TOKEN (bootstrap) and IG_STUDIO_TOKEN_KEY")
    # Unknown age: assume a fresh 60-day token issued now; refresh will correct it.
    now = datetime.now(timezone.utc)
    return {"token": tok, "expires_at": (now + timedelta(days=60)).isoformat(),
            "refreshed_at": now.isoformat(), "source": "bootstrap"}


def save_token(rec):
    f = _fernet()
    if not f:
        print("  (no IG_STUDIO_TOKEN_KEY: refreshed token NOT persisted)")
        return
    out = {k: rec[k] for k in ("token", "expires_at", "refreshed_at")}
    TOKEN_FILE.write_bytes(f.encrypt(json.dumps(out).encode()))
    print(f"  token store written: {TOKEN_FILE.name}")


def refresh_token(rec):
    """Refresh when the token is a day old or older (Meta refuses younger ones).
    Returns the possibly-updated record."""
    now = datetime.now(timezone.utc)
    age = now - datetime.fromisoformat(rec["refreshed_at"])
    if age < timedelta(hours=24) and rec["source"] == "store":
        print(f"  token refreshed {age.seconds // 3600}h ago; not due")
        return rec
    try:
        res = _call("GET", f"{API}/refresh_access_token",
                    {"grant_type": "ig_refresh_token", "access_token": rec["token"]})
    except RuntimeError as e:
        left = datetime.fromisoformat(rec["expires_at"]) - now
        print(f"  refresh failed: {e}")
        if left < timedelta(days=7):
            raise RuntimeError(f"token expires in {left.days} day(s) and cannot be refreshed; "
                               "generate a new one in the Meta app dashboard")
        return rec
    rec = {"token": res["access_token"],
           "expires_at": (now + timedelta(seconds=int(res.get("expires_in", 60 * 86400)))).isoformat(),
           "refreshed_at": now.isoformat(), "source": "store"}
    print(f"  token refreshed; now expires {rec['expires_at'][:10]}")
    save_token(rec)
    return rec


# ------------------------------------------------------------------ commands
def check():
    rec = load_token()
    print(f"token: {_redact(rec['token'])} from {rec['source']}, expires {rec['expires_at'][:10]}")
    me = _call("GET", "me", {"fields": "id,username,account_type"}, rec["token"])
    print(f"account: @{me.get('username')} (id {me.get('id')}, {me.get('account_type')})")
    rec = refresh_token(rec)
    return me


def _load_lib():
    return json.loads(LIB.read_text(encoding="utf-8"))


def build():
    import studio
    base = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
    if not base:
        print("WARNING: PUBLIC_BASE_URL not set; image URLs will be blank")
    n = CONFIG.get("studio", {}).get("posts_per_run", 1)
    lib = _load_lib()
    state = json.loads(STATE.read_text(encoding="utf-8"))
    start = state.get(CURSOR, 0)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    CARDS.mkdir(parents=True, exist_ok=True)
    items = []
    for i in range(n):
        it = lib[(start + i) % len(lib)]
        fname = f"{it['id']}-{stamp}.jpg"
        studio.render(it, CARDS / fname)
        items.append({"label": it["id"], "caption": it["caption"],
                      "image_url": f"{base}/cards/{fname}" if base else None})
    next_state = dict(state)
    next_state[CURSOR] = (start + n) % len(lib)
    BATCH.write_text(json.dumps({"items": items, "next_state": next_state}, indent=2), encoding="utf-8")
    print(f"Built studio batch: {len(items)} post(s)")
    for it in items:
        print(f"  - {it['label']}  {it['image_url']}")


def _wait_live(url, tries=12, delay=20):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url), timeout=20) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        print(f"    image not live yet ({i + 1}/{tries}), waiting {delay}s")
        time.sleep(delay)
    return False


def _publish_one(ig_id, token, image_url, caption):
    res = _call("POST", f"{ig_id}/media", {"image_url": image_url, "caption": caption}, token)
    cid = res["id"]
    for _ in range(12):
        st = _call("GET", cid, {"fields": "status_code,status"}, token)
        code = st.get("status_code")
        if code == "FINISHED":
            break
        if code == "ERROR":
            raise RuntimeError(f"container {cid} failed: {st.get('status')}")
        time.sleep(5)
    else:
        raise RuntimeError(f"container {cid} never finished (last: {st})")
    pub = _call("POST", f"{ig_id}/media_publish", {"creation_id": cid}, token)
    mid = pub["id"]
    try:
        link = _call("GET", mid, {"fields": "permalink"}, token).get("permalink", "")
    except RuntimeError:
        link = ""
    return mid, link


def publish():
    dry = os.environ.get("DRY_RUN") == "1"
    batch = json.loads(BATCH.read_text(encoding="utf-8"))
    if dry:
        for it in batch["items"]:
            print(f"  DRY RUN would publish {it['label']}: {it['image_url']}")
            print("    " + it["caption"].splitlines()[0])
        print("Dry run: nothing published, state not advanced.")
        return
    rec = load_token()
    rec = refresh_token(rec)
    me = _call("GET", "me", {"fields": "id,username"}, rec["token"])
    ig_id = me["id"]
    print(f"publishing as @{me.get('username')}")
    failures = 0
    for it in batch["items"]:
        if not it["image_url"]:
            print(f"  FAIL {it['label']}: no image URL")
            failures += 1
            continue
        if not _wait_live(it["image_url"]):
            print(f"  FAIL {it['label']}: image never became reachable")
            failures += 1
            continue
        try:
            mid, link = _publish_one(ig_id, rec["token"], it["image_url"], it["caption"])
            print(f"  published {it['label']} -> {mid} {link}")
        except Exception as e:
            print(f"  FAIL {it['label']}: {e}")
            failures += 1
    if failures:
        raise SystemExit(f"{failures} post(s) failed; cursor not advanced, retried next run")
    STATE.write_text(json.dumps(batch["next_state"], indent=2) + "\n", encoding="utf-8")
    print(f"cursor advanced: {CURSOR} = {batch['next_state'][CURSOR]}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    {"check": check, "build": build, "publish": publish}[cmd]()
