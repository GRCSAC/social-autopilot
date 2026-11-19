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
  python ig_studio.py gate      # is a slot due and free right now? (writes go=true/false)
  python ig_studio.py build     # render the next post into public/cards + _studio_batch.json
  python ig_studio.py publish   # wait for the media URL, publish, write the ledger
  python ig_studio.py probe     # ask Meta to accept every video and one card, publish nothing
  python ig_studio.py stock     # how many posts are waiting and how long they last
  python ig_studio.py lint      # check the library before new items are committed
  python ig_studio.py angles    # every headline and caption opening so far, by app

The schedule is two posts a day, every day, at 11:00 and 19:00 New York time.
Nothing is posted twice: content/studio_schedule.json (the ledger) is the whole
history of the account, and an item whose id is in it is done for good. The
next post is the first library item not in the ledger, preferring an app that
has not just posted. When nothing is waiting, nothing is posted.

REHEARSE=id1,id2 (the workflow's "rehearse" box) builds exactly those items and
takes them as far as Meta accepting them, then stops: nothing is published and
neither the cursor nor the ledger moves.

A library item with "slides" is posted as a carousel, one rendered image per
slide. A library item with a "video" field is posted as a Reel from public/video/
instead of a rendered card. ("once" on older items is no longer read: every
item is posted once.)

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
QUEUE = ROOT / "preview" / "queue"
SLOTS = (11, 19)                # hours in America/New_York: two posts a day, every day
FAILED = "studio_failed"        # state.json: how often Meta refused each waiting item
PARK_AFTER = 3                  # refusals before an item is set aside so the queue moves on
BATCH = ROOT / "_studio_batch.json"
TOKEN_FILE = ROOT / "content" / "ig_studio_token.enc"

API_IG = "https://graph.instagram.com"
API_FB = "https://graph.facebook.com"
VERSION = os.environ.get("IG_API_VERSION", "v27.0")


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


def _now():
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo("America/New_York"))


def _ledger():
    return json.loads(LEDGER.read_text(encoding="utf-8"))


def _state():
    return json.loads(STATE.read_text(encoding="utf-8"))


def _write_ledger(led):
    led["scheduled"].sort(key=lambda r: (r["date"], r["time"]))
    LEDGER.write_text(json.dumps(led, indent=1) + "\n", encoding="utf-8")


def _waiting(lib, led, state, images_only=False):
    """Items never posted or scheduled, in library order. An id in the ledger
    is done for good, so nothing is posted twice. Items Meta has refused
    PARK_AFTER times are set aside until someone looks at them."""
    posted = {r["id"] for r in led["scheduled"]}
    parked = {k for k, v in state.get(FAILED, {}).items() if v >= PARK_AFTER}
    return [it for it in lib if it["id"] not in posted and it["id"] not in parked
            and not (images_only and it.get("video"))]


def _spread(waiting, lib, led, day):
    """The waiting items, those first whose app is not already posting on
    `day` and was not the last post before it. Keeps one app from filling a
    day when something else is waiting."""
    app = {it["id"]: it.get("app") for it in lib}
    rows = sorted(led["scheduled"], key=lambda r: (r["date"], r["time"]))
    avoid = {app.get(r["id"]) for r in rows if r["date"] == day}
    before = [r for r in rows if r["date"] < day]
    if before:
        avoid.add(app.get(before[-1]["id"]))
    return ([it for it in waiting if it.get("app") not in avoid]
            + [it for it in waiting if it.get("app") in avoid])


def _open_slot(now, led, due_only=True):
    """The earliest of today's slots with no post yet. With due_only, only a
    slot whose hour has come, so a morning run that failed is caught up by the
    next run instead of being lost."""
    today = now.date().isoformat()
    taken = {r["time"] for r in led["scheduled"] if r["date"] == today}
    for h in SLOTS:
        if f"{h}:00" not in taken and (now.hour >= h or not due_only):
            return h
    return None


def gate():
    """Decide whether a scheduled run posts now. Slots are 11:00 and 19:00
    New York time, every day; the workflow fires a few times around each so
    one run lands on the hour in winter and in summer time and the next one
    retries a failure. A slot already in the ledger (scheduled in Business
    Suite, or already published by this workflow) is never posted to twice."""
    now = _now()
    today = now.date().isoformat()
    start = CONFIG.get("studio", {}).get("api_start", "")
    led = _ledger()
    slot = _open_slot(now, led)
    if os.environ.get("GITHUB_EVENT_NAME", "schedule") != "schedule":
        go, why = True, "started by hand"
    elif start and today < start:
        go, why = False, f"before the API start date {start}"
    elif slot is None:
        go, why = False, (f"no slot is due and free on {today} "
                          f"(slots {' and '.join(f'{h}:00' for h in SLOTS)} New York)")
    elif not _waiting(_load_lib(), led, _state()):
        go, why = False, "every item in the library has been posted; nothing is repeated"
        print("::warning::Studio Instagram has no new posts left. "
              "Add items to content/studio_instagram.json.")
    else:
        go, why = True, f"slot {today} {slot}:00 New York is free"
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
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    CARDS.mkdir(parents=True, exist_ok=True)
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

    left = None
    if rehearse:
        by_id = {it["id"]: it for it in lib}
        missing = [x for x in rehearse if x not in by_id]
        if missing:
            raise SystemExit(f"rehearse: no such item(s): {', '.join(missing)}")
        items = [one(by_id[x]) for x in rehearse]
    else:
        led = _ledger()
        waiting = _spread(_waiting(lib, led, _state()), lib, led, _now().date().isoformat())
        items = [one(it) for it in waiting[:n]]
        left = len(waiting) - len(items)
    BATCH.write_text(json.dumps({"items": items}, indent=2), encoding="utf-8")
    print(f"Built studio batch: {len(items)} post(s)"
          + (f"; {left} more waiting in the library" if left is not None else ""))
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


def _record(labels):
    """Write what was just published into the ledger: the single history of
    the account, which is what keeps a slot from being filled twice and an
    item from being posted twice."""
    now = _now()
    today = now.date().isoformat()
    led = _ledger()
    for label in labels:
        h = _open_slot(now, led)
        if h is None:                     # started by hand outside a slot
            h = _open_slot(now, led, due_only=False)
        led["scheduled"].append({"id": label, "date": today,
                                 "time": f"{h}:00" if h is not None else now.strftime("%H:%M"),
                                 "scheduled_on": today, "via": "api"})
    led.pop("next_cursor", None)
    _write_ledger(led)


def _item_fault(e):
    """True when Meta refused this particular post, as opposed to refusing the
    token, throttling the account or being unreachable."""
    m = str(e)
    if not isinstance(e, RuntimeError):
        return False
    if any(x in m for x in ("API access blocked", "code 190,", "code 200,", "code 10,",
                            "code 4,", "code 17,", "code 32,", "code 613,")):
        return False
    return m.startswith("Instagram API 4") or m.startswith("container")


def publish():
    dry = os.environ.get("DRY_RUN") == "1"
    batch = json.loads(BATCH.read_text(encoding="utf-8"))
    if dry:
        for it in batch["items"]:
            print(f"  DRY RUN would publish {it['label']}: {it.get('video_url') or ', '.join(it['image_urls'])}")
            print("    " + it["caption"].splitlines()[0])
        print("Dry run: nothing published, ledger untouched.")
        return
    if not batch["items"]:
        print("Nothing to publish: every item in the library has been posted.")
        return
    rec = load_token()
    acct = resolve(rec["token"])
    if acct["kind"] == "instagram":
        rec = refresh_token(rec)
    rehearse = bool(os.environ.get("REHEARSE", "").strip())
    print(f"{'REHEARSING, nothing will be published,' if rehearse else 'publishing'} as "
          f"@{acct['username']} ({acct['kind']} API)")
    state = _state()
    refused = dict(state.get(FAILED, {}))
    failures, posted = 0, []
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
            posted.append(it["label"])
            refused.pop(it["label"], None)
        except Exception as e:
            print(f"  FAIL {it['label']}: {e}")
            failures += 1
            if not rehearse and _item_fault(e):
                refused[it["label"]] = refused.get(it["label"], 0) + 1
                if refused[it["label"]] >= PARK_AFTER:
                    print(f"::warning::{it['label']} was refused {PARK_AFTER} times and is set "
                          f"aside; the next run posts the item after it.")
    if rehearse:
        if failures:
            raise SystemExit(f"{failures} item(s) were not accepted")
        print("Rehearsal done: nothing published, ledger untouched.")
        return
    if posted:
        _record(posted)
    if refused != state.get(FAILED, {}):
        if refused:
            state[FAILED] = refused
        else:
            state.pop(FAILED, None)
        STATE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    if failures:
        raise SystemExit(f"{failures} post(s) failed; not recorded, retried by the next run")
    print(f"ledger updated: {', '.join(posted)}")


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
    """(date, hour) for every slot from now through today+days with no post."""
    now = _now()
    start = CONFIG.get("studio", {}).get("api_start", "")
    taken = {(r["date"], r["time"]) for r in _ledger()["scheduled"]}
    out = []
    for i in range(days + 1):
        d = now.date() + timedelta(days=i)
        iso = d.isoformat()
        if start and iso < start:
            continue
        for h in SLOTS:
            if (iso, f"{h}:00") in taken:
                continue
            if i == 0 and now.hour >= h - 1:
                continue                  # too late to schedule that one today
            out.append((d, h))
    return out


def handoff(days=3):
    """Print, as JSON, the posts to schedule in Business Suite for the free
    slots of the next `days` days, with their rendered images. Images only: a
    Reel waits for the API. Changes nothing."""
    import studio
    lib, state = _load_lib(), _state()
    sim = _ledger()                       # a copy that fills up as slots are assigned
    rows = []
    QUEUE.mkdir(parents=True, exist_ok=True)
    for d, h in _free_slots(days):
        iso = d.isoformat()
        cand = _spread(_waiting(lib, sim, state, images_only=True), lib, sim, iso)
        if not cand:
            break
        it = cand[0]
        sim["scheduled"].append({"id": it["id"], "date": iso, "time": f"{h}:00"})
        specs = studio.slides_of(it)
        files = []
        for i, sp in enumerate(specs, 1):
            tail = f"-{i}" if len(specs) > 1 else ""
            f = QUEUE / f"{iso}-{h:02d}-{it['id']}{tail}.jpg"
            studio.render(sp, f)
            files.append(str(f))
        h12, mer = (h if h <= 12 else h - 12), ("AM" if h < 12 else "PM")
        rows.append({"id": it["id"], "date_iso": iso, "slot": f"{h}:00",
                     "type_date": d.strftime("%m/%d/%Y"),
                     "want_date": f"{d.strftime('%b')} {d.day}, {d.year}",
                     "type_hour": str(h12), "type_minute": "00", "type_meridiem": mer[0],
                     "want_time": f"{h12:02d}:00{mer}", "list_time": f"{h12}:00{mer.lower()}",
                     "files": files, "app": it.get("app", ""),
                     "status_on_card": it.get("status", ""), "caption": it["caption"]})
    print(json.dumps(rows, indent=1, ensure_ascii=False))


def handoff_done(pid, d, slot=None):
    """Record one post as scheduled in Business Suite on date d in `slot`."""
    datetime.strptime(d, "%Y-%m-%d")
    slot = slot or f"{SLOTS[0]}:00"
    if slot not in {f"{h}:00" for h in SLOTS}:
        raise SystemExit(f"refusing: slot must be one of {', '.join(f'{h}:00' for h in SLOTS)}")
    lib, state, led = _load_lib(), _state(), _ledger()
    if pid not in [it["id"] for it in _waiting(lib, led, state, images_only=True)]:
        raise SystemExit(f"refusing: {pid} is not an image item still waiting to be posted")
    if any(r["date"] == d and r["time"] == slot for r in led["scheduled"]):
        raise SystemExit(f"refusing: {d} {slot} already has a post in the ledger")
    led["scheduled"].append({"id": pid, "date": d, "time": slot,
                             "scheduled_on": _now().date().isoformat(), "via": "business-suite"})
    led.pop("next_cursor", None)
    _write_ledger(led)
    print(f"recorded {pid} on {d} {slot} (Business Suite)")


# ------------------------------------------------------------------ stock + lint
def stock():
    """How many posts are waiting, and the last date they cover at two a day."""
    lib, led, state = _load_lib(), _ledger(), _state()
    waiting = _waiting(lib, led, state)
    reels = sum(1 for it in waiting if it.get("video"))
    now = _now()
    start = CONFIG.get("studio", {}).get("api_start", "")
    taken = {(r["date"], r["time"]) for r in led["scheduled"]}
    left, last = len(waiting), None
    for i in range(800):
        if left <= 0:
            break
        iso = (now.date() + timedelta(days=i)).isoformat()
        if start and iso < start:
            continue
        for h in SLOTS:
            if left > 0 and (iso, f"{h}:00") not in taken and not (i == 0 and now.hour > h):
                left -= 1
                last = iso
    cover = (datetime.strptime(last, "%Y-%m-%d").date() - now.date()).days if last else 0
    print(f"stock: {len(waiting)} waiting ({len(waiting) - reels} image posts, {reels} Reels), "
          f"enough through {last or 'today'} ({cover} days); {len(led['scheduled'])} posted or scheduled")
    apps = {}
    posted = {r["id"] for r in led["scheduled"]}
    for it in lib:
        a = apps.setdefault(it.get("app", "?"), [0, 0])
        a[0 if it["id"] in posted else 1] += 1
    print("by app (posted/waiting): " + ", ".join(f"{k} {v[0]}/{v[1]}" for k, v in sorted(apps.items())))
    parked = sorted(k for k, v in state.get(FAILED, {}).items() if v >= PARK_AFTER)
    if parked:
        print("set aside after repeated refusals by Meta: " + ", ".join(parked))
    return cover


def angles(app=None):
    """Every headline and caption opening already in the library, by app, so a
    new item can be checked against what has been said before."""
    posted = {r["id"] for r in _ledger()["scheduled"]}
    for it in sorted(_load_lib(), key=lambda x: (x.get("app", ""), x["id"])):
        if app and it.get("app") != app:
            continue
        kind = "reel" if it.get("video") else ("carousel" if it.get("slides") else
                                               ("screenshot" if it.get("shot") else "card"))
        heads = [sp.get("headline", "") for sp in ([it] + it.get("slides", [])) if sp.get("headline")]
        shots = sorted({sp["shot"] for sp in ([it] + it.get("slides", [])) if sp.get("shot")})
        print(f"{it.get('app')} | {it['id']} | {'posted' if it['id'] in posted else 'waiting'} | {kind}"
              + (f" [{', '.join(shots)}]" if shots else ""))
        for h in heads:
            print(f"    headline: {h}")
        print(f"    caption:  {it['caption'].strip().splitlines()[0]}")


def lint():
    """Check the library before new items are committed: every item can be
    rendered and posted, and nothing says the same thing twice."""
    import re
    import tempfile
    import studio
    lib = _load_lib()
    posted = {r["id"] for r in _ledger()["scheduled"]}
    bad, ids, heads, opens = [], set(), {}, {}
    for it in lib:
        pid = it.get("id") or "(no id)"

        def no(msg):
            bad.append(f"{pid}: {msg}")
        if pid in ids:
            no("this id is used twice")
        ids.add(pid)
        if not re.fullmatch(r"ig-studio-[a-z0-9-]+", pid):
            no("id must look like ig-studio-<app>-<n>")
        for k in ("app", "name", "footer", "caption"):
            if not it.get(k):
                no(f"missing {k}")
        if it.get("app") and not (studio.APPS / f"{it['app']}.png").exists():
            no(f"no icon assets/apps/{it['app']}.png")
        cap = it.get("caption", "")
        tags = re.findall(r"#\w+", cap)
        if len(cap) > 1200:
            no(f"caption is {len(cap)} characters (limit here 1200)")
        if not 3 <= len(tags) <= 6:
            no(f"{len(tags)} hashtags (use 3 to 6)")
        text = json.dumps(it, ensure_ascii=False)
        if "\u2014" in text or "\u2013" in text:
            no("contains a long dash; the house style uses commas, colons or full stops")
        first = cap.strip().split("\n")[0].strip().lower()
        if first and first in opens:
            no(f"caption opens with the same line as {opens[first]}")
        opens.setdefault(first, pid)
        specs = [] if it.get("video") else studio.slides_of(it)
        if it.get("video"):
            if not (VIDEO / it["video"]).exists():
                no(f"video file missing: public/video/{it['video']}")
        elif it.get("slides") and not 2 <= len(specs) <= 10:
            no("a carousel needs 2 to 10 slides")
        for sp in specs:
            h = (sp.get("headline") or "").strip()
            if not h:
                no("a card or slide has no headline")
                continue
            if len(h) > 70:
                no(f"headline is {len(h)} characters (limit 70): {h[:40]}")
            if len(sp.get("sub", "")) > 180:
                no(f"sub line is {len(sp['sub'])} characters (limit 180)")
            if sp.get("shot") and not (studio.SHOTS / sp["shot"]).exists():
                no(f"screenshot missing: assets/shots/{sp['shot']}")
            key = h.lower()
            if key in heads and heads[key] != pid:
                no(f"headline already used by {heads[key]}: {h}")
            heads.setdefault(key, pid)
        if specs and pid not in posted and not any(x.startswith(pid + ":") for x in bad):
            with tempfile.TemporaryDirectory() as tmp:
                try:
                    for i, sp in enumerate(specs):
                        studio.render(sp, Path(tmp) / f"{i}.jpg")
                except Exception as e:
                    no(f"does not render: {e}")
    for b in bad:
        print("  " + b)
    if bad:
        raise SystemExit(f"lint: {len(bad)} problem(s) in {len(lib)} items")
    print(f"lint: ok ({len(lib)} items, {len(lib) - len(posted & ids)} waiting)")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "handoff":
        handoff(int(sys.argv[2]) if len(sys.argv) > 2 else 3)
    elif cmd == "handoff-done":
        if len(sys.argv) not in (4, 5):
            raise SystemExit("usage: python ig_studio.py handoff-done ID YYYY-MM-DD [11:00|19:00]")
        handoff_done(*sys.argv[2:])
    else:
        if cmd == "angles":
            angles(sys.argv[2] if len(sys.argv) > 2 else None)
        else:
            {"check": check, "gate": gate, "build": build, "publish": publish,
             "probe": probe, "health": health, "stock": stock, "lint": lint}[cmd]()
