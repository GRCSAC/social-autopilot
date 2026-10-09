"""Quality gate for generated posts.

Everything the autopilot publishes goes out under Paul's name, so a generated
post has to read like him before it is queued. The sanitizer in llm_content.py
already fixes punctuation (dashes, curly quotes). This module catches what a
find-and-replace cannot fix and the post has to be rewritten for:

  slop         stock AI vocabulary and phrases (content/slop.json)
  shapes       the sentence shapes models default to ("it's not X, it's Y",
               "not only ... but also", emoji, hashtag walls)
  fingerprint  characters a keyboard does not produce: invisible Unicode
               (zero-width joiners and the like), hard spaces, the ellipsis
               character. scrub() removes these; the others need a rewrite.
  hook         the first line of a LinkedIn post is all that shows before
               "...more" on a phone (about 140 characters). It has to stand
               alone, so a long first line is rejected.

Usage
  python quality.py draft.txt          # issues for one file (- for stdin)
  python quality.py --library          # check every curated item; prints a
                                       # count, exits 1 if anything trips
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LEXICON = ROOT / "content" / "slop.json"

HOOK_MAX = 140      # LinkedIn mobile cut, roughly
HOOK_MAX_IG = 150   # Instagram caption cut, roughly; warn only


class QualityError(RuntimeError):
    """Raised by llm_content when a batch still fails after retries."""


def _lex():
    return json.loads(LEXICON.read_text(encoding="utf-8"))


def _term_re(term):
    # whole-word match; interior spaces may be any whitespace
    return re.compile(r"(?<!\w)" + re.escape(term).replace(r"\ ", r"\s+") + r"(?!\w)",
                      re.IGNORECASE)


_COMPILED = None


def _compiled():
    global _COMPILED
    if _COMPILED is None:
        lex = _lex()
        _COMPILED = {
            "terms": [(t, _term_re(t)) for t in lex["words"] + lex["phrases"]],
            "shapes": [(s["id"], re.compile(s["regex"])) for s in lex["shapes"]],
        }
    return _COMPILED


def scrub(text):
    """Remove the fingerprint characters that can be fixed mechanically."""
    if not text:
        return text
    text = "".join(c for c in text if unicodedata.category(c) != "Cf")
    text = text.replace(" ", " ").replace(" ", " ").replace(" ", " ")
    text = text.replace("…", "...")
    return text


def check(text, platform=None):
    """Return a list of human-readable issues. Empty list means the text passes."""
    issues = []
    if not text or not text.strip():
        return ["empty"]
    cx = _compiled()

    hits = sorted({t for t, rx in cx["terms"] if rx.search(text)})
    if hits:
        issues.append("stock wording: " + ", ".join(hits))

    for sid, rx in cx["shapes"]:
        if rx.search(text):
            issues.append(f"shape: {sid}")

    invisible = sum(1 for c in text if unicodedata.category(c) == "Cf")
    hard = sum(text.count(c) for c in "   ")
    dashes = text.count("—") + text.count("–")
    curly = sum(text.count(c) for c in "‘’“”")
    if invisible or hard or dashes or curly or "…" in text:
        issues.append(f"fingerprint: {invisible} invisible, {hard} hard space, "
                      f"{dashes} dash, {curly} curly quote")
    if re.search(r"\s-\s", text):
        issues.append("fingerprint: spaced hyphen used as a dash")

    first = text.strip().split("\n", 1)[0].strip()
    if platform == "linkedin" and len(first) > HOOK_MAX:
        issues.append(f"hook: first line is {len(first)} chars, must stand alone under {HOOK_MAX}")
    if platform == "linkedin" and first.startswith("#"):
        issues.append("hook: first line is a hashtag")
    return issues


def check_item(item, platform):
    """Issues for one generated item in the library schema."""
    if platform == "instagram":
        line = item.get("quote") or item.get("hook") or ""
        return check(line, None) + check(item.get("caption", ""), "instagram")
    out = check(item.get("text", ""), "linkedin")
    card = item.get("card") or {}
    if card.get("quote"):
        out += check(card["quote"], None)
    return out


def _library():
    total = 0
    for name, platform in (("instagram", "instagram"), ("linkedin", "linkedin"),
                           ("netvane_linkedin", "linkedin")):
        p = ROOT / "content" / f"{name}.json"
        if not p.exists():
            continue
        for it in json.loads(p.read_text(encoding="utf-8")):
            issues = check_item(it, platform)
            for i in issues:
                print(f"  {it['id']:36} {i}")
            total += len(issues)
    print(f"{total} issue(s) across the curated library")
    return total


if __name__ == "__main__":
    if "--library" in sys.argv:
        sys.exit(1 if _library() else 0)
    src = next((a for a in sys.argv[1:] if not a.startswith("--")), "-")
    if src == "-":
        sys.stdin.reconfigure(encoding="utf-8")
    text = sys.stdin.read() if src == "-" else Path(src).read_text(encoding="utf-8")
    platform = "linkedin" if "--linkedin" in sys.argv else None
    found = check(text, platform)
    print("\n".join(found) if found else "clean")
    sys.exit(1 if found else 0)
