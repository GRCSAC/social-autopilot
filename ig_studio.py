"""GRCSAC Studio -> Instagram, directly through Meta's Instagram API.

No Buffer. The studio Instagram account (a professional account) is published to
straight from GitHub Actions: create a media container from a public image URL,
then publish it. Images are the same jsDelivr-served cards the rest of this repo
uses.

Two kinds of token work, and the script finds out which one it was given:

  instagram   "Instagram API with Instagram Login" (graph.instagram.com). A 60-day
              token that is refreshed on every run. Meta no longer offers this
              setup to new apps.
  facebook    "API setup with Unified login" (graph.facebook.com). A system-user
              token that does not expire, so nothing is refreshed or stored. This
              is what the GRCSAC Studio Autopilot app issues. It needs the
              account's Instagram ID in IG_STUDIO_USER_ID.

  python ig_studio.py check     # who the token belongs to, when it expires
  python ig_studio.py build     # render the next card(s) into public/cards + _studio_batch.json
  python ig_studio.py publish   # wait for the image URL, publish, advance the cursor

Environment:
  IG_STUDIO_TOKEN       the token (GitHub secret). For an instagram token it is only the
                        bootstrap, used until the encrypted store below exists
  IG_STUDIO_USER_ID     the Instagram account ID (GitHub variable); needed for a
                        facebook token, ignored for an instagram one
  IG_STUDIO_TOKEN_KEY   Fernet key (GitHub secret) for content/ig_studio_token.enc
  PUBLIC_BASE_URL       where public/ is served from (jsDelivr)
  DRY_RUN=1             render + print, no API calls, no state change
  IG_API_VERSION        default v27.0

Token life (instagram tokens only): Meta long-lived tokens last 60 days and can be refreshed once they are
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

API_IG = "https://graph.instagram.com"
API_FB = "https://graph.facebook.com"
VERSION = os.environ.get("IG_API_VERSION", "v27.0")
CURSOR = "studio_instagram"


# ------------------------------------------------------------------ http
def _call(method, path, params=None, token=None, api=API_IG):
    params = dict(params or {})
    if token:
        params["access_token"] = token
    url = f"{api}/{VERSION}/{path.lstrip('/')}" if not path.startswith("http") else path
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
    """Never print any part of the token: this repo's Actions logs are public."""
    return f"({len(s)} characters)" if s else "(empty)"


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
        res = _call("GET", f"{API_IG}/refresh_access_token",
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
def resolve(token):
    """Find out which API the token belongs to and which account it posts as.
    Returns {kind, api, id, username}."""
    try:
        me = _call("GET", "me", {"fields": "id,username,account_type"}, token, API_IG)
        return {"kind": "instagram", "api": API_IG, "id": me["id"],
                "username": me.get("username"), "type": me.get("account_type")}
    except RuntimeError as e:
        ig_err = e
    uid = os.environ.get("IG_STUDIO_USER_ID", "").strip()
    if not uid:
        raise RuntimeError(f"not an Instagram-login token ({ig_err}) and IG_STUDIO_USER_ID "
                           "is not set, so the Facebook-login API cannot be tried")
    try:
        me = _call("GET", uid, {"fields": "id,username"}, token, API_FB)
    except RuntimeError as fb_err:
        raise RuntimeError(f"token rejected by both APIs. graph.instagram.com: {ig_err}. "
                           f"graph.facebook.com: {fb_err}")
    return {"kind": "facebook", "api": API_FB, "id": me["id"],
            "username": me.get("username"), "type": "system-user token"}


def _expiry(token):
    """Best effort: when a facebook token expires, from Meta's own inspector."""
    try:
        d = _call("GET", "debug_token", {"input_token": token}, token, API_FB)["data"]
    except (RuntimeError, KeyError) as e:
        return f"expiry unknown ({e})"
    exp = d.get("expires_at", 0)
    scopes = ", ".join(d.get("scopes", []))
    when = "never expires" if not exp else         "expires " + datetime.fromtimestamp(exp, timezone.utc).strftime("%Y-%m-%d")
    return f"{when}; scopes: {scopes}"


def check():
    rec = load_token()
    acct = resolve(rec["token"])
    print(f"token: {_redact(rec['token'])} from {rec['source']}, {acct['kind']} API")
    print(f"account: @{acct['username']} (id {acct['id']}, {acct['type']})")
    if acct["kind"] == "instagram":
        print(f"  expires {rec['expires_at'][:10]}")
        refresh_token(rec)
    else:
        print(f"  {_expiry(rec['token'])}; nothing to refresh")
    # Read-only proof that the token may publish: Meta only answers this with
    # the content-publish permission. Nothing is posted.
    try:
        q = _call("GET", f"{acct['id']}/content_publishing_limit",
                  {"fields": "quota_usage,config"}, rec["token"], acct["api"])
        d = (q.get("data") or [{}])[0]
        print(f"  may publish: yes ({d.get('quota_usage')} of "
              f"{(d.get('config') or {}).get('quota_total')} posts used in the last 24h)")
    except RuntimeError as e:
        raise RuntimeError(f"token can read the account but may not publish: {e}")
    return acct


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


def _publish_one(acct, token, image_url, caption):
    api, ig_id = acct["api"], acct["id"]
    res = _call("POST", f"{ig_id}/media", {"image_url": image_url, "caption": caption}, token, api)
    cid = res["id"]
    for _ in range(12):
        st = _call("GET", cid, {"fields": "status_code,status"}, token, api)
        code = st.get("status_code")
        if code == "FINISHED":
            break
        if code == "ERROR":
            raise RuntimeError(f"container {cid} failed: {st.get('status')}")
        time.sleep(5)
    else:
        raise RuntimeError(f"container {cid} never finished (last: {st})")
    pub = _call("POST", f"{ig_id}/media_publish", {"creation_id": cid}, token, api)
    mid = pub["id"]
    try:
        link = _call("GET", mid, {"fields": "permalink"}, token, api).get("permalink", "")
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
    acct = resolve(rec["token"])
    if acct["kind"] == "instagram":
        rec = refresh_token(rec)
    print(f"publishing as @{acct['username']} ({acct['kind']} API)")
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
            mid, link = _publish_one(acct, rec["token"], it["image_url"], it["caption"])
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
