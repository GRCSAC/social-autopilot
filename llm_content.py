"""Generate fresh, on-brand social posts with Claude.

Called by run.py `build` when config.json "mode" == "generate". Produces
Instagram quote cards + LinkedIn posts in Paul Zarou's book voice, matching the
same item schema the curated library uses, so the renderer and Buffer pipeline
are unchanged. Recently used lines are remembered in content/recent.json and fed
back so themes don't repeat. The house humanizer rule (no em/en dashes, no
" - " punctuation, no curly quotes) is enforced by the prompt and a sanitize pass.

Env:
  ANTHROPIC_API_KEY   Anthropic API key (secret)
  ANTHROPIC_MODEL     optional model override (default: claude-sonnet-5)
"""
import json
import os
import re
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content"
RECENT = CONTENT / "recent.json"
API_URL = "https://api.anthropic.com/v1/messages"
MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")

SYSTEM = """You write social posts for Paul Zarou, a leadership author drawing on two
decades leading teams in financial services. His books are about compassionate,
honest leadership: being tough on the problem and gentle with the person.

Voice, follow exactly:
- Measured, plain, and concrete. Second person. No hype, no cliche, no buzzwords,
  no motivational-poster tone. One clear, true idea per post, earned with a
  specific observation a real manager would recognize.
- NEVER use em dashes or en dashes. NEVER use " - " as punctuation. Use periods,
  commas, or a colon instead. Use straight quotes only, never curly quotes.
- No emojis. Plain hashtags only, a few at the end.
- Quote cards are attributed to Paul Zarou."""


def _sanitize(s):
    """Enforce the house humanizer rules on any generated string."""
    if not s:
        return s
    s = s.replace("—", ", ").replace("–", "-")          # em dash -> comma, en dash -> hyphen
    s = s.replace("‘", "'").replace("’", "'")            # curly single
    s = s.replace("“", '"').replace("”", '"')            # curly double
    s = re.sub(r"\s+-\s+", ", ", s)                                # " - " -> ", "
    s = re.sub(r"[ \t]{2,}", " ", s)                              # collapse double spaces
    s = re.sub(r"[ \t]+\n", "\n", s)
    return s.strip()


def _recent():
    if RECENT.exists():
        try:
            return json.loads(RECENT.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def _save_recent(quotes, keep=40):
    hist = _recent() + [q for q in quotes if q]
    RECENT.write_text(json.dumps(hist[-keep:], indent=2, ensure_ascii=False) + "\n",
                      encoding="utf-8")


def _fewshot():
    ig = json.loads((CONTENT / "instagram.json").read_text(encoding="utf-8"))
    li = json.loads((CONTENT / "linkedin.json").read_text(encoding="utf-8"))
    ig_ex = next((x for x in ig if x.get("type") == "quote"), ig[0])
    return ig_ex, li[0]


def _call(prompt, max_tokens=3000):
    key = os.environ["ANTHROPIC_API_KEY"]  # KeyError here => misconfigured, run fails loudly
    body = json.dumps({
        "model": MODEL,
        "max_tokens": max_tokens,
        "system": SYSTEM,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")
    req = urllib.request.Request(API_URL, data=body, method="POST", headers={
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Anthropic HTTP {e.code}: {e.read().decode()[:400]}")
    return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")


def _extract_json(text):
    m = re.search(r"\{.*\}", text, re.S)
    return json.loads(m.group(0) if m else text)


def _prompt(n_ig, n_li):
    ig_ex, li_ex = _fewshot()
    ig_shape = {k: ig_ex[k] for k in ("eyebrow", "quote", "caption") if k in ig_ex}
    li_shape = {"text": li_ex["text"], "card": li_ex.get("card")}
    avoid = "\n".join(f"- {q}" for q in _recent()[-24:]) or "(none yet)"
    return f"""Write fresh leadership posts. Return ONLY a JSON object, no prose around it.

Match the VOICE and SHAPE of these real examples, but write entirely new ideas.

Instagram quote-card example:
{json.dumps(ig_shape, ensure_ascii=False, indent=2)}

LinkedIn example:
{json.dumps(li_shape, ensure_ascii=False, indent=2)}

Do NOT repeat these recently used lines or their themes:
{avoid}

Return exactly this JSON shape:
{{
  "instagram": [
    {{ "eyebrow": "On <topic>", "quote": "one true sentence, straight quotes",
       "caption": "2 to 4 short paragraphs, then a blank line, then 4 to 6 plain hashtags" }}
  ],
  "linkedin": [
    {{ "eyebrow": "On <topic>", "quote": "one sentence for the card",
       "text": "3 to 6 short paragraphs ending with a question, then a blank line and a few hashtags" }}
  ]
}}
Give {n_ig} instagram items and {n_li} linkedin items. Every post a distinct idea.
No em dashes, no en dashes, no curly quotes."""


def generate(n_ig, n_li, stamp):
    """Return (instagram_items, linkedin_items) matching the curated schema."""
    prompt = _prompt(n_ig, n_li)
    last_err = None
    for attempt in range(2):
        try:
            data = _extract_json(_call(prompt))
            break
        except Exception as e:  # bad JSON / transient — retry once
            last_err = e
    else:
        raise RuntimeError(f"generation failed after retries: {last_err}")

    out_ig, out_li, quotes = [], [], []
    for i, x in enumerate(data.get("instagram", [])[:n_ig]):
        q = _sanitize(x["quote"])
        quotes.append(q)
        out_ig.append({
            "id": f"ig-gen-{stamp}-{i + 1}", "type": "quote",
            "eyebrow": _sanitize(x.get("eyebrow", "")), "quote": q,
            "attribution": "Paul Zarou", "caption": _sanitize(x["caption"]),
        })
    for i, x in enumerate(data.get("linkedin", [])[:n_li]):
        q = _sanitize(x["quote"])
        quotes.append(q)
        out_li.append({
            "id": f"li-gen-{stamp}-{i + 1}", "text": _sanitize(x["text"]),
            "card": {"type": "quote", "eyebrow": _sanitize(x.get("eyebrow", "")),
                     "quote": q, "attribution": "Paul Zarou"},
        })

    if len(out_ig) < n_ig or len(out_li) < n_li:
        raise RuntimeError(f"generation short: got {len(out_ig)} IG / {len(out_li)} LI")
    _save_recent(quotes)
    return out_ig, out_li
