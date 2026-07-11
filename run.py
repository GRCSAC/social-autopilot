"""Orchestrator for the social autopilot.

Two phases, run in order by the GitHub Actions workflow:

  python run.py build   # pick next items, render Instagram cards into public/,
                        # write _batch.json + the *tentative* next rotation state.
                        # (Workflow then commits public/ so Cloudflare Pages serves
                        #  the images at a public URL.)

  python run.py post    # verify each image URL is live, then queue every post via
                        # the Buffer API. Only on full success is content/state.json
                        # advanced — so a failed run safely retries the same items.

Env:
  PUBLIC_BASE_URL  base URL where public/ is served (e.g. https://x.pages.dev)
  BUFFER_TOKEN     Buffer API token (secret)
  DRY_RUN=1        print the Buffer calls instead of sending them
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

import generate
import buffer_client

ROOT = Path(__file__).resolve().parent
PUBLIC = ROOT / "public"
CARDS = PUBLIC / "cards"
BATCH = ROOT / "_batch.json"
STATE = ROOT / "content" / "state.json"
CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))


def _load(name):
    return json.loads((ROOT / "content" / f"{name}.json").read_text(encoding="utf-8"))


def _take(bank, start, n):
    """n items from bank starting at start, wrapping around."""
    return [bank[(start + i) % len(bank)] for i in range(n)]


def build():
    base = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
    if not base:
        print("WARNING: PUBLIC_BASE_URL not set — Instagram image URLs will be blank")
    CARDS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")

    state = json.loads(STATE.read_text(encoding="utf-8"))
    items, next_state = [], dict(state)

    ig = _load("instagram")
    for it in _take(ig, state["instagram"], CONFIG["posts_per_run"]["instagram"]):
        fname = f"{it['id']}-{stamp}.jpg"
        generate.render(it, CARDS / fname)
        items.append({
            "platform": "instagram",
            "channel_id": CONFIG["channels"]["instagram"],
            "text": it["caption"],
            "image_url": f"{base}/cards/{fname}" if base else None,
            "label": it["id"],
        })
    next_state["instagram"] = (state["instagram"] + CONFIG["posts_per_run"]["instagram"]) % len(ig)

    li = _load("linkedin")
    for it in _take(li, state["linkedin"], CONFIG["posts_per_run"]["linkedin"]):
        items.append({
            "platform": "linkedin",
            "channel_id": CONFIG["channels"]["linkedin"],
            "text": it["text"],
            "image_url": None,
            "label": it["id"],
        })
    next_state["linkedin"] = (state["linkedin"] + CONFIG["posts_per_run"]["linkedin"]) % len(li)

    BATCH.write_text(json.dumps({"items": items, "next_state": next_state}, indent=2), encoding="utf-8")
    print(f"Built batch: {len(items)} posts "
          f"({CONFIG['posts_per_run']['instagram']} IG + {CONFIG['posts_per_run']['linkedin']} LI)")
    for it in items:
        print(f"  - {it['platform']:9} {it['label']}")


def _wait_live(url, tries=12, delay=20):
    """Poll a URL until it returns 200 (Cloudflare Pages needs time to deploy)."""
    for i in range(tries):
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=20) as r:
                if r.status == 200:
                    return True
        except urllib.error.HTTPError as e:
            if e.code == 200:
                return True
        except Exception:
            pass
        print(f"    image not live yet ({i+1}/{tries}), waiting {delay}s: {url}")
        time.sleep(delay)
    return False


def post():
    dry = os.environ.get("DRY_RUN") == "1"
    batch = json.loads(BATCH.read_text(encoding="utf-8"))
    failures = 0
    for it in batch["items"]:
        if it["image_url"] and not dry:
            if not _wait_live(it["image_url"]):
                print(f"  FAIL {it['label']}: image never became reachable")
                failures += 1
                continue
        try:
            res = buffer_client.create_post(
                it["channel_id"], it["text"], image_url=it["image_url"], dry_run=dry)
            pid = res.get("id", "dry-run")
            print(f"  queued {it['platform']:9} {it['label']}  -> {pid}")
        except Exception as e:
            print(f"  FAIL {it['label']}: {e}")
            failures += 1

    if failures:
        raise SystemExit(f"{failures} post(s) failed — state not advanced, will retry next run")

    if dry:
        print("DRY RUN complete — rotation state left unchanged.")
        return
    STATE.write_text(json.dumps(batch["next_state"], indent=2) + "\n", encoding="utf-8")
    print(f"All posts queued. Rotation advanced -> {batch['next_state']}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "build":
        build()
    elif cmd == "post":
        post()
    else:
        print("usage: python run.py [build|post]")
        sys.exit(2)
