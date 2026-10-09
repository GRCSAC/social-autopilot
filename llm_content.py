"""Generate fresh, on-brand social posts with Claude.

Called by run.py `build` when config.json "mode" == "generate". Produces
Instagram quote cards + LinkedIn posts in Paul Zarou's book voice, matching the
same item schema the curated library uses, so the renderer and Buffer pipeline
are unchanged. Recently used lines are remembered in content/recent.json and fed
back so themes don't repeat. The house humanizer rule (no em/en dashes, no
" - " punctuation, no curly quotes) is enforced by the prompt and a sanitize pass.

Every draft then goes through quality.check (stock AI vocabulary, the sentence
shapes models default to, invisible characters, and a LinkedIn first line that
survives the mobile cut). A batch that trips the gate is sent back with the
reasons and rewritten, up to MAX_ATTEMPTS; after that QualityError is raised and
run.py falls back to the curated library for the week rather than post slop.

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

import quality

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content"
RECENT = CONTENT / "recent.json"
API_URL = "https://api.anthropic.com/v1/messages"
MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")
MAX_ATTEMPTS = 3

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
- Quote cards are attributed to Paul Zarou.
- Never invent a statistic, a client, a named person, or a story from Paul's
  life. These post under his real name. Observations, yes. Anecdotes, no.
- Do not write the shapes models default to: "it's not X, it's Y",
  "not only X but also Y", a one-word teaser line, a closing "Thoughts?".
- Never use these words or phrases, in any form:
  {banned}

The first line of a LinkedIn post is the hook. On a phone only the first line
shows before "...more", so it must stand alone, under 120 characters, and make
a manager want the rest. Write it as a plain, specific claim or observation,
the kind of sentence that is true the moment you read it. Not a question to the
crowd, not a tease, not a hashtag, not "I" announcing something. Three shapes
that work in Paul's voice: the uncomfortable thing said plainly; the moment a
manager recognises from the other chair; the cost of a habit stated in concrete
terms. The hook may be the same sentence as the quote card, or a different one."""


def _banned_words():
    lex = json.loads((CONTENT / "slop.json").read_text(encoding="utf-8"))
    return ", ".join(lex["words"] + lex["phrases"])


def _sanitize(s):
    """Enforce the house humanizer rules on any generated string."""
    if not s:
        return s
    s = quality.scrub(s)                                          # invisible chars, hard spaces
    s = s.replace("—", ", ").replace("–", "-")          # em dash -> comma, en dash -> hyphen
    s = s.replace("‘", "'").replace("’", "'")           # curly single
    s = s.replace("“", '"').replace("”", '"')           # curly double
    s = re.sub(r"\s+-\s+", ", ", s)                               # " - " -> ", "
    s = re.sub(r"[ \t]{2,}", " ", s)                              # collapse double spaces
    s = re.sub(r"[ \t]+\n", "\n", s)
    return s.strip()


def _compose(lines, tags, hook=None):
    """Join paragraph strings with blank lines, then a hashtag line. Arrays in,
    so the model never has to emit raw newlines inside a JSON string. A hook,
    when given, is the first paragraph on its own."""
    paras = ([hook] if hook else []) + list(lines or [])
    body = "\n\n".join(_sanitize(l) for l in paras if l and l.strip())
    tagline = " ".join(
        (t if t.startswith("#") else "#" + t.lstrip("#")).strip()
        for t in (tags or []) if t and t.strip())
    return (body + ("\n\n" + tagline if tagline else "")).strip()


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


_POST_ITEM = {
    "instagram": {
        "type": "object",
        "properties": {
            "eyebrow": {"type": "string", "description": "e.g. 'On Hard Conversations'"},
            "quote": {"type": "string", "description": "one true sentence for the card"},
            "caption_lines": {"type": "array", "items": {"type": "string"},
                              "description": "2-4 paragraphs, one string each, no line breaks inside; "
                                             "the first paragraph stands alone under 150 characters"},
            "hashtags": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["eyebrow", "quote", "caption_lines", "hashtags"],
    },
    "linkedin": {
        "type": "object",
        "properties": {
            "eyebrow": {"type": "string"},
            "quote": {"type": "string", "description": "one sentence for the card"},
            "hook": {"type": "string",
                     "description": "the first line of the post, alone, under 120 characters; "
                                    "a plain specific claim that survives the mobile cut"},
            "body_lines": {"type": "array", "items": {"type": "string"},
                           "description": "3-6 paragraphs after the hook, ending with a genuine "
                                          "question, one string each"},
            "hashtags": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["eyebrow", "quote", "hook", "body_lines", "hashtags"],
    },
}
POSTS_TOOL = {
    "name": "emit_posts",
    "description": "Return the generated social posts as structured data.",
    "input_schema": {
        "type": "object",
        "properties": {
            "instagram": {"type": "array", "items": _POST_ITEM["instagram"]},
            "linkedin": {"type": "array", "items": _POST_ITEM["linkedin"]},
        },
        "required": ["instagram", "linkedin"],
    },
}


def _call(messages, max_tokens=4000):
    """Force a structured tool response so the JSON is API-validated, never parsed
    out of free text. Returns the tool input dict."""
    key = os.environ["ANTHROPIC_API_KEY"]  # KeyError here => misconfigured, run fails loudly
    body = json.dumps({
        "model": MODEL,
        "max_tokens": max_tokens,
        "system": SYSTEM.replace("{banned}", _banned_words()),
        "tools": [POSTS_TOOL],
        "tool_choice": {"type": "tool", "name": "emit_posts"},
        "messages": messages,
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
    for b in data.get("content", []):
        if b.get("type") == "tool_use":
            return b.get("input", {})
    raise RuntimeError(f"no tool_use in response (stop_reason={data.get('stop_reason')})")


def _prompt(n_ig, n_li):
    ig_ex, li_ex = _fewshot()
    avoid = "\n".join(f"- {q}" for q in _recent()[-24:]) or "(none yet)"
    # Show the voice via the real caption text, but require ARRAY output (each
    # paragraph its own string) so the JSON never contains raw line breaks.
    return f"""Write fresh leadership posts.

Match the VOICE of these real examples, but write entirely new ideas:

Example Instagram quote line: "{ig_ex.get('quote', '')}"
Example Instagram caption:
{ig_ex.get('caption', '')}

Example LinkedIn post (note how the first line stands on its own):
{li_ex.get('text', '')}

Do NOT repeat these recently used lines or their themes:
{avoid}

Every paragraph is a separate string with NO line breaks inside it. For
LinkedIn, "hook" is the opening line on its own (under 120 characters), then
"body_lines" continue from it. For Instagram the first caption paragraph does
the same job (under 150 characters). hashtags each start with #.

Give {n_ig} instagram items and {n_li} linkedin items. Every post a distinct idea,
concrete and true. No em dashes, no en dashes, no curly quotes."""


def _assemble(data, n_ig, n_li, stamp):
    out_ig, out_li, quotes = [], [], []
    for i, x in enumerate(data.get("instagram", [])[:n_ig]):
        q = _sanitize(x["quote"])
        quotes.append(q)
        out_ig.append({
            "id": f"ig-gen-{stamp}-{i + 1}", "type": "quote",
            "eyebrow": _sanitize(x.get("eyebrow", "")), "quote": q,
            "attribution": "Paul Zarou",
            "caption": _compose(x.get("caption_lines", []), x.get("hashtags")),
        })
    for i, x in enumerate(data.get("linkedin", [])[:n_li]):
        q = _sanitize(x["quote"])
        quotes.append(q)
        out_li.append({
            "id": f"li-gen-{stamp}-{i + 1}",
            "text": _compose(x.get("body_lines", []), x.get("hashtags"),
                             hook=x.get("hook")),
            "card": {"type": "quote", "eyebrow": _sanitize(x.get("eyebrow", "")),
                     "quote": q, "attribution": "Paul Zarou"},
        })
    return out_ig, out_li, quotes


def _validate(out_ig, out_li, n_ig, n_li):
    """Problems with a batch: shortfalls, blanks, then the quality gate.
    Returns a list of strings, empty when the batch is good to post."""
    problems = []
    if len(out_ig) < n_ig or len(out_li) < n_li:
        problems.append(f"short batch: got {len(out_ig)} instagram / {len(out_li)} linkedin")
    for it in out_ig:
        if not it["caption"] or not it["quote"]:
            problems.append(f"{it['id']}: empty caption or quote")
        for issue in quality.check_item(it, "instagram"):
            problems.append(f"{it['id']}: {issue}")
    for it in out_li:
        if not it["text"] or not it["card"]["quote"]:
            problems.append(f"{it['id']}: empty post or quote")
        for issue in quality.check_item(it, "linkedin"):
            problems.append(f"{it['id']}: {issue}")
    return problems


def generate(n_ig, n_li, stamp):
    """Return (instagram_items, linkedin_items) matching the curated schema.
    Drafts that fail the quality gate go back to the model with the reasons;
    after MAX_ATTEMPTS the batch is abandoned with QualityError."""
    messages = [{"role": "user", "content": _prompt(n_ig, n_li)}]
    problems = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            data = _call(messages)  # API-validated tool output, already a dict
        except Exception as e:  # transient network / API: one plain retry
            print(f"  generation attempt {attempt}: API error, retrying once ({e})")
            data = _call(messages)
        out_ig, out_li, quotes = _assemble(data, n_ig, n_li, stamp)
        problems = _validate(out_ig, out_li, n_ig, n_li)
        if not problems:
            if attempt > 1:
                print(f"  quality gate passed on attempt {attempt}")
            _save_recent(quotes)
            return out_ig, out_li
        print(f"  quality gate rejected attempt {attempt}:")
        for p in problems:
            print(f"    - {p}")
        # Keep the model's own draft in the thread so it rewrites rather than
        # re-rolls, and name every reason so the fix is targeted.
        messages.append({"role": "assistant", "content": [
            {"type": "tool_use", "id": f"draft{attempt}", "name": "emit_posts", "input": data}]})
        messages.append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": f"draft{attempt}",
             "content": "Rejected. Fix every point below and return the full set again:\n"
                        + "\n".join(f"- {p}" for p in problems)}]})
    raise quality.QualityError(
        f"generated posts still failed the quality gate after {MAX_ATTEMPTS} attempts: "
        + "; ".join(problems[:6]))
