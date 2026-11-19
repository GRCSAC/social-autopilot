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

  python ig_studio.py check     # who the token belongs to, may it publish, latest posts
  python ig_studio.py gate      # should a scheduled run post today? (writes go=true/false)
  python ig_studio.py build     # render the next card(s) into public/cards + _studio_batch.json
  python ig_studio.py publish   # wait for the media URL, publish, advance the cursor
  python ig_studio.py probe     # ask Meta to accept every video and one card, publish nothing

REHEARSE=id1,id2 (the workflow's "rehearse" box) builds exactly those items and
takes them as far as Meta accepting them, then stops: nothing is published and
neither the cursor nor the ledger moves.

A library item with "slides" is posted as a carousel, one rendered image per
slide. A library item with a "video" field is posted as a Reel from public/video/ instead
of a rendered card. "once": true means it is posted a single time and skipped when
the library comes round again (a clip that says "Updated November 9" does not age
well).

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
VIDEO = ROOT / "public" / "video"
LEDGER = ROOT / "content" / "studio_schedule.json"
ONCE_DONE = "studio_once_done"
AHEAD = "studio_posted_ahead"   # posted by the fallback before the cursor reached them
QUEUE = ROOT / "preview" / "queue"
SLOT_DAYS = {0, 2, 4}           # Mon, Wed, Fri
SLOT_HOUR = 11                  # America/New_York
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
            said = " ".join(str(msg[k]) for k in ("error_user_title", "error_user_msg") if msg.get(k))
            raise RuntimeError(f"Instagram API {e.code}: {msg.get('message')} "
                               f"(code {msg.get('code')}, subcode {msg.get('error_subcode')}, "
                               f"type {msg.get('type')})" + (f" Meta says: {said}" if said else ""))
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
def _diagnose(token, uid):
    """The Facebook-login API refused the token. Ask a few read-only questions
    to see how far the refusal reaches. Prints outcomes only, never ids."""
    probes = [("the token itself (who am I)", "me", {"fields": "id"}),
              ("the app behind the token", "app", {"fields": "id"}),
              ("Instagram accounts the token can reach", "me/instagram_accounts", {"fields": "id"}),
              ("the Instagram account, id only", uid, {"fields": "id"}),
              ("the Instagram account's posts", f"{uid}/media", {"limit": 1})]
    print("diagnosis (read-only):")
    for label, path, params in probes:
        try:
            _call("GET", path, params, token, API_FB)
            print(f"  ok       {label}")
        except RuntimeError as e:
            print(f"  REFUSED  {label}: {e}")


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
        _diagnose(token, uid)
        raise RuntimeError(f"token rejected by both APIs. graph.instagram.com: {ig_err}. "
                           f"graph.facebook.com: {fb_err}")
    return {"kind": "facebook", "api": API_FB, "id": me["id"],
            "username": me.get("username"), "type": "system-user token"}


def _expiry(token):
    """Best effort: when a facebook token expires, from Meta's own inspector."""
    try:
        d = _call("GET", "debug_token", {"input_token": token}, token, API_FB)["data"]
    except (RuntimeError, KeyError):
        # Meta's inspector refuses a system-user token as its own key.
        return "expiry not readable with this token (the login configuration issues non-expiring ones)"
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
    # What is actually on the account, newest first: the quickest way to see
    # whether a scheduled post went out, whichever route scheduled it.
    try:
        m = _call("GET", f"{acct['id']}/media", {"fields": "timestamp,caption", "limit": 5},
                  rec["token"], acct["api"]).get("data", [])
        print(f"  latest posts on the account: {len(m)} shown")
        for it in m:
            first = (it.get("caption") or "").splitlines()[0][:60] if it.get("caption") else "(no caption)"
            print(f"    {it.get('timestamp', '')[:16]}Z  {first}")
    except RuntimeError as e:
        print(f"  could not list posts: {e}")
    return acct


def _load_lib():
    return json.loads(LIB.read_text(encoding="utf-8"))


def _base():
    return os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")


def _video_url(it):
    f = VIDEO / it["video"]
    if not f.exists():
        raise RuntimeError(f"{it['id']}: video file missing: public/video/{it['video']}")
    return f"{_base()}/video/{it['video']}" if _base() else None


def gate():
    """Decide whether a scheduled run posts now. Slots are Mon/Wed/Fri 11:00
    Eastern; the workflow fires at 15:00 and 16:00 UTC so one of the two lands
    on 11:00 in both winter and summer time. A date already in the ledger (a
    post scheduled in Business Suite, or one this workflow already published)
    is never posted to twice."""
    from zoneinfo import ZoneInfo
    now = datetime.now(ZoneInfo("America/New_York"))
    today = now.date().isoformat()
    start = CONFIG.get("studio", {}).get("api_start", "")
    led = json.loads(LEDGER.read_text(encoding="utf-8"))
    if os.environ.get("GITHUB_EVENT_NAME", "schedule") != "schedule":
        go, why = True, "started by hand"
    elif start and today < start:
        go, why = False, f"before the API start date {start}"
    elif now.weekday() not in SLOT_DAYS:
        go, why = False, "not a Monday, Wednesday or Friday in New York"
    elif now.hour < SLOT_HOUR:
        go, why = False, f"before {SLOT_HOUR}:00 in New York"
    elif any(r["date"] == today for r in led["scheduled"]):
        go, why = False, f"{today} already has a post in the ledger"
    else:
        go, why = True, f"slot {today} {SLOT_HOUR}:00 New York is free"
    print(f"gate: {'GO' if go else 'SKIP'} ({why})")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"go={'true' if go else 'false'}\n")
    return go


def build():
    import studio
    base = _base()
    if not base:
        print("WARNING: PUBLIC_BASE_URL not set; media URLs will be blank")
    n = CONFIG.get("studio", {}).get("posts_per_run", 1)
    lib = _load_lib()
    state = json.loads(STATE.read_text(encoding="utf-8"))
    cur = state.get(CURSOR, 0)
    done = list(state.get(ONCE_DONE, []))
    ahead = list(state.get(AHEAD, []))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    CARDS.mkdir(parents=True, exist_ok=True)
    items, looked = [], 0
    rehearse = [x.strip() for x in os.environ.get("REHEARSE", "").split(",") if x.strip()]

    def one(it):
        if it.get("video"):
            return {"label": it["id"], "caption": it["caption"],
                    "image_urls": [], "video_url": _video_url(it)}
        urls = []
        specs = studio.slides_of(it)
        for i, sp in enumerate(specs, 1):
            tail = f"-{i}" if len(specs) > 1 else ""
            fname = f"{it['id']}-{stamp}{tail}.jpg"
            studio.render(sp, CARDS / fname)
            urls.append(f"{base}/cards/{fname}" if base else None)
        return {"label": it["id"], "caption": it["caption"], "image_urls": urls, "video_url": None}

    if rehearse:
        by_id = {it["id"]: it for it in lib}
        missing = [x for x in rehearse if x not in by_id]
        if missing:
            raise SystemExit(f"rehearse: no such item(s): {', '.join(missing)}")
        items = [one(by_id[x]) for x in rehearse]
    while not rehearse and len(items) < n and looked < len(lib):
        it = lib[cur % len(lib)]
        cur += 1
        looked += 1
        if it["id"] in ahead:
            ahead.remove(it["id"])        # the fallback already posted it
            continue
        if it.get("once") and it["id"] in done:
            continue                      # a one-time post that already ran
        items.append(one(it))
        if it.get("once"):
            done.append(it["id"])
    next_state = dict(state)
    if not rehearse:
        next_state[CURSOR] = cur % len(lib)
        if done:
            next_state[ONCE_DONE] = done
        if ahead or AHEAD in state:
            next_state[AHEAD] = ahead
    BATCH.write_text(json.dumps({"items": items, "next_state": next_state}, indent=2), encoding="utf-8")
    print(f"Built studio batch: {len(items)} post(s)")
    for it in items:
        print(f"  - {it['label']}  {it['video_url'] or ', '.join(u or '(no url)' for u in it['image_urls'])}")


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


def _create(acct, token, params):
    """Create a container. Meta fetches the media the moment it is asked, and a
    file pushed seconds ago may not be on every CDN edge yet: Meta then answers
    2207052 ("media could not be fetched"). That one is worth waiting out."""
    last = None
    for attempt in range(6):
        try:
            return _call("POST", f"{acct['id']}/media", params, token, acct["api"])["id"]
        except RuntimeError as e:
            if "2207052" not in str(e):
                raise
            last = e
            print(f"    Meta could not fetch the media yet ({attempt + 1}/6), waiting 30s")
            time.sleep(30)
    raise last


def _wait_done(acct, token, cid, tries):
    st = {}
    for _ in range(tries):
        st = _call("GET", cid, {"fields": "status_code,status"}, token, acct["api"])
        code = st.get("status_code")
        if code == "FINISHED":
            return cid
        if code == "ERROR":
            raise RuntimeError(f"container {cid} failed: {st.get('status')}")
        time.sleep(5)
    raise RuntimeError(f"container {cid} never finished (last: {st})")


def _container(acct, token, image_urls, video_url, caption):
    """Create the media container for one post and wait until Meta has fetched
    and processed it: a Reel, a single image, or a carousel of images. Nothing
    is visible on the account until media_publish is called; an unpublished
    container simply expires."""
    api, ig_id = acct["api"], acct["id"]
    if isinstance(image_urls, str):
        image_urls = [image_urls]
    if video_url:
        cid = _create(acct, token, {"media_type": "REELS", "video_url": video_url,
                                    "caption": caption, "share_to_feed": "true"})
        return _wait_done(acct, token, cid, 60)       # video processing: up to 5 minutes
    if len(image_urls) == 1:
        cid = _create(acct, token, {"image_url": image_urls[0], "caption": caption})
        return _wait_done(acct, token, cid, 12)
    kids = []
    for n, u in enumerate(image_urls, 1):
        try:
            kid = _create(acct, token, {"image_url": u, "is_carousel_item": "true"})
            kids.append(_wait_done(acct, token, kid, 12))
        except RuntimeError as e:
            raise RuntimeError(f"slide {n} of {len(image_urls)}: {e}")
    try:
        cid = _call("POST", f"{ig_id}/media", {"media_type": "CAROUSEL", "children": ",".join(kids),
                                               "caption": caption}, token, api)["id"]
    except RuntimeError as e:
        raise RuntimeError(f"carousel of {len(kids)} accepted slides: {e}")
    return _wait_done(acct, token, cid, 12)


def _publish_one(acct, token, image_urls, caption, video_url=None):
    api, ig_id = acct["api"], acct["id"]
    cid = _container(acct, token, image_urls, video_url, caption)
    pub = _call("POST", f"{ig_id}/media_publish", {"creation_id": cid}, token, api)
    mid = pub["id"]
    try:
        link = _call("GET", mid, {"fields": "permalink"}, token, api).get("permalink", "")
    except RuntimeError:
        link = ""
    return mid, link


def probe():
    """Dress rehearsal: have Meta fetch and process every video in the library
    and the newest hosted card, and report what it says. Publishes nothing."""
    rec = load_token()
    acct = resolve(rec["token"])
    print(f"probing as @{acct['username']} ({acct['kind']} API); nothing will be published")
    jobs = [(it["id"], None, _video_url(it)) for it in _load_lib() if it.get("video")]
    cards = sorted(CARDS.glob("ig-studio-*.jpg"), key=lambda f: f.name)
    if cards and _base():
        jobs.append((cards[-1].stem, f"{_base()}/cards/{cards[-1].name}", None))
    bad = 0
    for label, img, vid in jobs:
        url = vid or img
        if not url or not _wait_live(url):
            print(f"  FAIL {label}: not reachable at {url}")
            bad += 1
            continue
        try:
            cid = _container(acct, rec["token"], [img] if img else [], vid, "probe, never published")
            print(f"  ok   {label}: Meta accepted it (container {cid}, left unpublished)")
        except Exception as e:
            print(f"  FAIL {label}: {e}")
            bad += 1
    if bad:
        raise SystemExit(f"{bad} of {len(jobs)} item(s) were not accepted")
    print(f"all {len(jobs)} item(s) accepted")


def _record(labels, next_state):
    """Write what was just published into the ledger, so the gate never posts
    twice on one date and the ledger stays the single history of the account."""
    from zoneinfo import ZoneInfo
    today = datetime.now(ZoneInfo("America/New_York")).date().isoformat()
    led = json.loads(LEDGER.read_text(encoding="utf-8"))
    for label in labels:
        led["scheduled"].append({"id": label, "date": today, "time": f"{SLOT_HOUR}:00",
                                 "scheduled_on": today, "via": "api"})
    led["next_cursor"] = next_state[CURSOR]
    LEDGER.write_text(json.dumps(led, indent=1) + "\n", encoding="utf-8")


def publish():
    dry = os.environ.get("DRY_RUN") == "1"
    batch = json.loads(BATCH.read_text(encoding="utf-8"))
    if dry:
        for it in batch["items"]:
            print(f"  DRY RUN would publish {it['label']}: {it.get('video_url') or ', '.join(it['image_urls'])}")
            print("    " + it["caption"].splitlines()[0])
        print("Dry run: nothing published, state not advanced.")
        return
    rec = load_token()
    acct = resolve(rec["token"])
    if acct["kind"] == "instagram":
        rec = refresh_token(rec)
    rehearse = bool(os.environ.get("REHEARSE", "").strip())
    print(f"{'REHEARSING, nothing will be published,' if rehearse else 'publishing'} as "
          f"@{acct['username']} ({acct['kind']} API)")
    failures = 0
    for it in batch["items"]:
        urls = [it["video_url"]] if it.get("video_url") else list(it.get("image_urls") or [])
        if not urls or not all(urls):
            print(f"  FAIL {it['label']}: no media URL")
            failures += 1
            continue
        if not all(_wait_live(u) for u in urls):
            print(f"  FAIL {it['label']}: media never became reachable")
            failures += 1
            continue
        try:
            if rehearse:
                cid = _container(acct, rec["token"], it.get("image_urls"), it.get("video_url"), it["caption"])
                kind = "Reel" if it.get("video_url") else ("carousel of %d" % len(urls) if len(urls) > 1 else "image")
                print(f"  ok   {it['label']}: Meta accepted the {kind} (container {cid}, left unpublished)")
                continue
            mid, link = _publish_one(acct, rec["token"], it.get("image_urls"), it["caption"],
                                     it.get("video_url"))
            print(f"  published {it['label']} -> {mid} {link}")
        except Exception as e:
            print(f"  FAIL {it['label']}: {e}")
            failures += 1
    if failures:
        raise SystemExit(f"{failures} post(s) failed; cursor not advanced, retried next run")
    if rehearse:
        print("Rehearsal done: nothing published, cursor and ledger untouched.")
        return
    STATE.write_text(json.dumps(batch["next_state"], indent=2) + "\n", encoding="utf-8")
    _record([it["label"] for it in batch["items"]], batch["next_state"])
    print(f"cursor advanced: {CURSOR} = {batch['next_state'][CURSOR]}")


# ------------------------------------------------------------------ fallback
# When Meta's API refuses the token, the post still has to go out. The same
# library is then scheduled in Meta Business Suite by browser (the laptop
# routine in STUDIO-SCHEDULING.md). These commands are the deterministic half
# of that: is the API healthy, which posts cover which free dates, and
# recording what was scheduled so the API never posts on those dates as well.
def health():
    """One line for the fallback routine to read. Never fails the run, so a
    blocked token does not send a failure email every morning."""
    try:
        rec = load_token()
        acct = resolve(rec["token"])
        _call("GET", f"{acct['id']}/content_publishing_limit", {"fields": "quota_usage"},
              rec["token"], acct["api"])
        print(f"health: ok (@{acct['username']} may publish)")
    except (Exception, SystemExit) as e:
        print(f"health: BLOCKED ({e})")


def _free_slots(days):
    """Slot dates from today through today+days that have no post yet."""
    from zoneinfo import ZoneInfo
    now = datetime.now(ZoneInfo("America/New_York"))
    start = CONFIG.get("studio", {}).get("api_start", "")
    taken = {r["date"] for r in json.loads(LEDGER.read_text(encoding="utf-8"))["scheduled"]}
    out = []
    for i in range(days + 1):
        d = now.date() + timedelta(days=i)
        iso = d.isoformat()
        if d.weekday() not in SLOT_DAYS or iso in taken or (start and iso < start):
            continue
        if i == 0 and now.hour >= SLOT_HOUR - 1:
            continue                      # too late to schedule today's 11:00
        out.append(d)
    return out


def _next_images(state, lib, n):
    """The next n items the fallback can post: images only (video waits for
    the API), in library order from the cursor, nothing posted before."""
    cur = state.get(CURSOR, 0)
    done, ahead = set(state.get(ONCE_DONE, [])), set(state.get(AHEAD, []))
    out = []
    for i in range(len(lib)):
        if len(out) >= n:
            break
        it = lib[(cur + i) % len(lib)]
        if it.get("video") or it["id"] in ahead or (it.get("once") and it["id"] in done):
            continue
        out.append(it)
    return out


def handoff(days=7):
    """Print, as JSON, the posts to schedule in Business Suite for the free
    slots of the next `days` days, with their rendered images. Changes nothing."""
    import studio
    lib = _load_lib()
    state = json.loads(STATE.read_text(encoding="utf-8"))
    slots = _free_slots(days)
    rows = []
    QUEUE.mkdir(parents=True, exist_ok=True)
    for d, it in zip(slots, _next_images(state, lib, len(slots))):
        specs = studio.slides_of(it)
        files = []
        for i, sp in enumerate(specs, 1):
            tail = f"-{i}" if len(specs) > 1 else ""
            f = QUEUE / f"{d.isoformat()}-{it['id']}{tail}.jpg"
            studio.render(sp, f)
            files.append(str(f))
        rows.append({"id": it["id"], "date_iso": d.isoformat(),
                     "type_date": d.strftime("%m/%d/%Y"),
                     "want_date": f"{d.strftime('%b')} {d.day}, {d.year}",
                     "time": "11:00 AM", "files": files, "app": it.get("app", ""),
                     "status_on_card": it.get("status", ""), "caption": it["caption"]})
    print(json.dumps(rows, indent=1, ensure_ascii=False))


def handoff_done(pid, d):
    """Record one post as scheduled in Business Suite on date d."""
    from zoneinfo import ZoneInfo
    datetime.strptime(d, "%Y-%m-%d")
    lib = _load_lib()
    ids = [it["id"] for it in lib]
    state = json.loads(STATE.read_text(encoding="utf-8"))
    led = json.loads(LEDGER.read_text(encoding="utf-8"))
    if pid not in [it["id"] for it in _next_images(state, lib, len(lib))]:
        raise SystemExit(f"refusing: {pid} is not an image item still waiting to be posted")
    if any(r["date"] == d for r in led["scheduled"]):
        raise SystemExit(f"refusing: {d} already has a post in the ledger")
    it = lib[ids.index(pid)]
    ahead = list(state.get(AHEAD, [])) + [pid]
    cur = state.get(CURSOR, 0)
    while lib[cur % len(lib)]["id"] in ahead:     # the cursor itself was posted: move on
        ahead.remove(lib[cur % len(lib)]["id"])
        cur += 1
    state[CURSOR], state[AHEAD] = cur % len(lib), ahead
    if it.get("once"):
        state[ONCE_DONE] = list(state.get(ONCE_DONE, [])) + [pid]
    today = datetime.now(ZoneInfo("America/New_York")).date().isoformat()
    led["scheduled"].append({"id": pid, "date": d, "time": f"{SLOT_HOUR}:00",
                             "scheduled_on": today, "via": "business-suite"})
    led["scheduled"].sort(key=lambda r: r["date"])
    led["next_cursor"] = state[CURSOR]
    STATE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    LEDGER.write_text(json.dumps(led, indent=1) + "\n", encoding="utf-8")
    print(f"recorded {pid} on {d} (Business Suite); cursor {state[CURSOR]}, "
          f"posted ahead of the cursor: {', '.join(ahead) or 'none'}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "handoff":
        handoff(int(sys.argv[2]) if len(sys.argv) > 2 else 7)
    elif cmd == "handoff-done":
        if len(sys.argv) != 4:
            raise SystemExit("usage: python ig_studio.py handoff-done ID YYYY-MM-DD")
        handoff_done(sys.argv[2], sys.argv[3])
    else:
        {"check": check, "gate": gate, "build": build, "publish": publish,
         "probe": probe, "health": health}[cmd]()
