"""Print the readable text of a web page, for checking a post against the source.

  python tools/page_text.py https://siftlet.grcsac.com/ [more urls]

Only for GRCSAC's own pages (grcsac.com and its subdomains). Scripts, styles
and tags are stripped; what is left is the text a visitor reads.
"""
import html
import re
import sys
import urllib.parse
import urllib.request


def text_of(url):
    host = urllib.parse.urlparse(url).hostname or ""
    if not (host == "grcsac.com" or host.endswith(".grcsac.com")):
        raise SystemExit(f"refusing {url}: only grcsac.com pages are sources for this account")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (studio content check)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read().decode("utf-8", "replace")
    raw = re.sub(r"(?is)<(script|style|svg|noscript)[^>]*>.*?</\1>", " ", raw)
    raw = re.sub(r"(?i)<(br|/p|/h[1-6]|/li|/div|/section|/tr)[^>]*>", "\n", raw)
    out = html.unescape(re.sub(r"<[^>]+>", " ", raw))
    lines = [re.sub(r"[ \t\r\f\v]+", " ", ln).strip() for ln in out.split("\n")]
    return "\n".join(ln for ln in lines if ln)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    for u in sys.argv[1:]:
        print(f"===== {u}")
        try:
            print(text_of(u))
        except SystemExit:
            raise
        except Exception as e:
            print(f"(could not read: {e})")
