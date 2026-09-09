"""Check that every configured Buffer channel can actually publish.

Why this exists: buffer_client only sees Buffer's response when a post is added
to the QUEUE. Buffer publishes later, on its own schedule, and a channel whose
authorisation has lapsed fails at THAT point — long after the workflow has gone
green. On 2026-09-06 all six posts queued cleanly and the run passed; Buffer then
failed to publish the Instagram ones because the channel had lost authorisation,
and nothing in the pipeline noticed.

This asks Buffer about the channels themselves. Field names are discovered by
introspecting the Channel type rather than guessed, so it keeps working if
Buffer renames things.

Usage:
  BUFFER_TOKEN=... python health.py          # report, exit 0
  BUFFER_TOKEN=... python health.py --strict # exit 1 if a channel looks unable to post
"""
import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

API_URL = "https://api.buffer.com"

# Substrings that mark a Channel field as being about connection/permission health.
HEALTH_HINTS = ("disconnect", "reconnect", "needsreauth", "reauth", "authoriz",
                "authoris", "expired", "invalid", "error", "locked", "suspend",
                "paused", "connected", "status", "state")

# A field being True usually means trouble, except for these, where True is good.
TRUE_IS_GOOD = ("connected",)


def gql(query, token, variables=None):
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    req = urllib.request.Request(
        API_URL, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {token}"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            body = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Buffer HTTP {e.code}: {e.read().decode()[:500]}")
    if body.get("errors"):
        raise SystemExit(f"Buffer GraphQL error: {body['errors']}")
    return body["data"]


def channel_health_fields(token):
    """Introspect the Channel type and return the scalar fields that look like
    they describe whether the channel can post."""
    q = """{ __type(name: "Channel") { fields { name type { kind name ofType { kind name } } } } }"""
    t = gql(q, token).get("__type")
    if not t:
        return []
    out = []
    for f in t["fields"]:
        ty = f["type"]
        name = ty.get("name") or (ty.get("ofType") or {}).get("name")
        kind = ty.get("kind")
        if kind == "NON_NULL":
            inner = ty.get("ofType") or {}
            name, kind = inner.get("name"), inner.get("kind")
        if kind not in ("SCALAR", "ENUM"):
            continue
        if any(h in f["name"].lower() for h in HEALTH_HINTS):
            out.append(f["name"])
    return sorted(set(out))


def looks_unhealthy(field, value):
    if value is None or value is False:
        return False
    low = field.lower()
    if isinstance(value, bool):
        if any(g in low for g in TRUE_IS_GOOD):
            return False       # e.g. isConnected == True is fine
        return True            # e.g. isDisconnected / needsReconnection == True
    if isinstance(value, str):
        bad = ("error", "disconnect", "expired", "invalid", "unauthor",
               "reconnect", "failed", "suspend")
        return any(b in value.lower() for b in bad)
    return False


def main():
    strict = "--strict" in sys.argv
    report = "--report" in sys.argv
    token = os.environ.get("BUFFER_TOKEN")
    if not token:
        raise SystemExit("BUFFER_TOKEN is not set")

    configured = json.load(open("config.json", encoding="utf-8"))["channels"]
    wanted = set(configured.values())

    fields = channel_health_fields(token)
    print("Channel health fields Buffer exposes:", ", ".join(fields) or "(none found)")

    selection = " ".join(["id", "service", "name", "displayName"] + fields)
    orgs = gql("{ account { organizations { id name } } }", token)["account"]["organizations"]

    seen, problems = {}, []
    for org in orgs:
        q = '{ channels(input: { organizationId: "%s" }) { %s } }' % (org["id"], selection)
        for c in gql(q, token)["channels"]:
            seen[c["id"]] = c

    print()
    for label, cid in configured.items():
        c = seen.get(cid)
        if not c:
            print(f"  MISSING  {label:18} {cid}  -- not visible to this token")
            problems.append(f"{label}: channel not found")
            continue
        flags = {f: c.get(f) for f in fields if looks_unhealthy(f, c.get(f))}
        name = c.get("displayName") or c.get("name") or "(unnamed)"
        if flags:
            print(f"  UNHEALTHY {label:18} {c['service']:10} {name}")
            for f, v in flags.items():
                print(f"              {f} = {v!r}")
            problems.append(f"{label} ({name}): " + ", ".join(f"{f}={v!r}" for f, v in flags.items()))
        else:
            print(f"  ok        {label:18} {c['service']:10} {name}")

    # The decisive check: did Buffer fail to PUBLISH anything recently?
    nodes = _recent_posts(token, orgs[0]["id"])
    failures, queued = publish_failures(nodes), still_queued(nodes)
    by_id = {cid: label for label, cid in configured.items()}
    if failures:
        print()
    for cid, (when, msg) in failures.items():
        label = by_id.get(cid, cid)
        print(f"  FAILED TO PUBLISH {label:18} latest finished post errored ({when})")
        print(f"              {msg}")
        if queued.get(cid):
            print(f"              {queued[cid]} queued behind it; they will fail the same"
                  f" way until it is reconnected.")
        print("              Clears itself once a post on this channel sends successfully.")
        problems.append(f"{label}: latest post failed -- {msg}")

    if problems:
        print("\n" + "\n".join(f"PROBLEM: {p}" for p in problems))
        print("\nA channel that has lost authorisation must be reconnected in Buffer:")
        print("  Buffer -> Channels -> the channel -> Refresh/Reconnect, then re-authorise.")
    if report:
        # Record which channels cannot publish so run.py can skip just those,
        # instead of the whole run dying and taking healthy channels with it.
        bad = {}
        for cid, items in failures.items():
            bad[cid] = items[1]
        Path("content/unhealthy.json").write_text(
            json.dumps(bad, indent=2) + "\n", encoding="utf-8")
        print(f"\nWrote content/unhealthy.json ({len(bad)} unhealthy channel(s)).")

        if strict:
            raise SystemExit(f"{len(problems)} channel(s) cannot publish")
    else:
        print("\nAll configured channels look able to publish.")



# --- publish-failure detection -------------------------------------------
# Buffer's Channel.isDisconnected does NOT flip when authorisation lapses: on
# 2026-09-09 an Instagram post failed with "Buffer has lost authorization to
# post on your behalf" while the channel still reported isDisconnected=False.
# The reliable signal is the posts themselves - a failed one carries
# status="error" and an error.message. That is what the preflight relies on.

_POSTS_Q = """
{ posts(first: %d, input: { organizationId: "%s" }) {
    edges { node { id status channelId channelService dueAt sentAt
                   error { message } } } } }
"""


def _recent_posts(token, org_id, limit=60):
    return [e["node"] for e in gql(_POSTS_Q % (limit, org_id), token)["posts"]["edges"]]


def publish_failures(nodes):
    """{channel_id: (dueAt, message)} for channels whose LATEST finished post
    was a failure.

    Deliberately not "any error in the window": an error stays in Buffer's
    history forever, so that would flag a channel for good and block it long
    after it was fixed. Buffer gives no positive "reconnected" signal either -
    Channel.updatedAt did not move when the Instagram channel was reconnected
    on 2026-09-09 (it still read 2026-07-10), and isDisconnected never flipped.
    The only trustworthy evidence a channel works is a post that actually sent,
    so compare the newest finished post of each kind and let a later success
    clear the flag on its own.
    """
    latest = {}
    for n in nodes:
        status = n.get("status")
        if status not in ("sent", "error"):
            continue          # scheduled/sending prove nothing either way
        when = n.get("sentAt") or n.get("dueAt") or ""
        cid = n["channelId"]
        if cid not in latest or when > latest[cid][0]:
            msg = (n.get("error") or {}).get("message") or "(no message)"
            latest[cid] = (when, status, msg)
    return {cid: (when, msg) for cid, (when, status, msg) in latest.items()
            if status == "error"}


def still_queued(nodes):
    """{channel_id: count} - what a broken channel burns through, one failure
    at a time, until it is reconnected."""
    out = {}
    for n in nodes:
        if n.get("status") in ("scheduled", "sending"):
            out[n["channelId"]] = out.get(n["channelId"], 0) + 1
    return out


if __name__ == "__main__":
    main()
