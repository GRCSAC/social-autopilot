"""The GRCSAC Studio Instagram ledger at a glance.

  python studio_queue.py status     # what is scheduled from today on, what is waiting

Planning and recording moved to ig_studio.py (`handoff`, `handoff-done`,
`stock`); see STUDIO-SCHEDULING.md.
"""
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LEDGER = ROOT / "content" / "studio_schedule.json"


def status():
    import ig_studio
    led = json.loads(LEDGER.read_text(encoding="utf-8"))
    today = date.today().isoformat()
    upcoming = [r for r in led["scheduled"] if r["date"] >= today]
    print(f"in the ledger from today on: {len(upcoming)}")
    for r in upcoming:
        print(f"  {r['date']} {r['time']}  {r['id']}  ({r.get('via', 'business-suite')})")
    ig_studio.stock()


if __name__ == "__main__":
    if sys.argv[1:] not in ([], ["status"]):
        raise SystemExit("only `status` is left here; use `python ig_studio.py handoff` to plan")
    status()
