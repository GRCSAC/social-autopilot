"""Plan and record GRCSAC Studio Instagram posts scheduled in Meta Business Suite.

RETIRED for planning on 2026-11-17: from 2026-12-09 the account is published by
ig_studio.py through Meta's API (see STUDIO-SCHEDULING.md), which writes its
posts into the same ledger. `status` is still the quickest look at the ledger.
`plan` and `done` are kept for reference and know nothing about video items,
carousels or posts made ahead of the cursor. The Business Suite fallback now
uses `python ig_studio.py handoff` and `handoff-done` instead.

The studio account is scheduled by hand-driven browser steps (see
STUDIO-SCHEDULING.md), not by an API. This script is the deterministic half:
it says WHICH cards go on WHICH dates, renders them, and records what was
actually scheduled so the next top-up starts in the right place.

  python studio_queue.py status            # what is scheduled, what is next
  python studio_queue.py plan --weeks 3    # render + print the posts needed to
                                           # keep the queue filled N weeks ahead
  python studio_queue.py done ID DATE      # record one post as scheduled
                                           # (DATE = YYYY-MM-DD), advance cursor

Slots are Mon/Wed/Fri at 11:00 America/New_York. `plan` never proposes a date
that is already in the ledger, in the past, or today.
"""
import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LIB = ROOT / "content" / "studio_instagram.json"
LEDGER = ROOT / "content" / "studio_schedule.json"
STATE = ROOT / "content" / "state.json"
OUT = ROOT / "preview" / "queue"
SLOT_DAYS = {0, 2, 4}          # Mon, Wed, Fri
CURSOR = "studio_instagram"


def _load(p):
    return json.loads(p.read_text(encoding="utf-8"))


def _slots(after, until):
    d = after + timedelta(days=1)
    while d <= until:
        if d.weekday() in SLOT_DAYS:
            yield d
        d += timedelta(days=1)


def _fmt_want(d):
    """How Business Suite shows a picked date, e.g. 'Dec 2, 2026'."""
    return f"{d.strftime('%b')} {d.day}, {d.year}"


def status():
    led, lib = _load(LEDGER), _load(LIB)
    today = date.today()
    upcoming = [r for r in led["scheduled"] if r["date"] >= today.isoformat()]
    print(f"library: {len(lib)} cards, next cursor {led['next_cursor']} "
          f"({lib[led['next_cursor'] % len(lib)]['id']})")
    print(f"scheduled from today on: {len(upcoming)}")
    for r in upcoming:
        print(f"  {r['date']} {r['time']}  {r['id']}")
    if upcoming:
        print(f"queue runs out after {upcoming[-1]['date']}")


def plan(weeks):
    import studio
    led, lib = _load(LEDGER), _load(LIB)
    today = date.today()
    taken = {r["date"] for r in led["scheduled"]}
    last = max([datetime.strptime(d, "%Y-%m-%d").date() for d in taken] + [today])
    horizon = today + timedelta(weeks=weeks)
    OUT.mkdir(parents=True, exist_ok=True)
    cur = led["next_cursor"]
    out = []
    for d in _slots(max(last, today), horizon):
        if d.isoformat() in taken:
            continue
        it = lib[cur % len(lib)]
        f = OUT / f"{d.isoformat()}-{it['id']}.jpg"
        studio.render(it, f)
        out.append({
            "id": it["id"], "file": str(f), "date_iso": d.isoformat(),
            "type_date": d.strftime("%m/%d/%Y"), "want_date": _fmt_want(d),
            "time": "11:00 AM", "status_on_card": it.get("status", ""),
            "app": it["app"], "caption": it["caption"],
        })
        cur += 1
    print(json.dumps(out, indent=1, ensure_ascii=False))
    if not out:
        print(f"# queue already reaches {last.isoformat()}; nothing to add", file=sys.stderr)


def done(pid, d):
    led, lib = _load(LEDGER), _load(LIB)
    want = lib[led["next_cursor"] % len(lib)]["id"]
    if pid != want:
        raise SystemExit(f"refusing: next card is {want}, not {pid}")
    datetime.strptime(d, "%Y-%m-%d")
    if any(r["date"] == d for r in led["scheduled"]):
        raise SystemExit(f"refusing: {d} already has a post in the ledger")
    led["scheduled"].append({"id": pid, "date": d, "time": "11:00",
                             "scheduled_on": date.today().isoformat()})
    led["next_cursor"] += 1
    LEDGER.write_text(json.dumps(led, indent=1) + "\n", encoding="utf-8")
    st = _load(STATE)
    st[CURSOR] = led["next_cursor"] % len(lib)
    STATE.write_text(json.dumps(st, indent=2) + "\n", encoding="utf-8")
    print(f"recorded {pid} on {d}; next cursor {led['next_cursor']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    p = sub.add_parser("plan"); p.add_argument("--weeks", type=int, default=3)
    p = sub.add_parser("done"); p.add_argument("id"); p.add_argument("date")
    a = ap.parse_args()
    if a.cmd == "status":
        status()
    elif a.cmd == "plan":
        plan(a.weeks)
    else:
        done(a.id, a.date)
