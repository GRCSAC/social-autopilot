"""List Buffer organizations and channels, to find a channel id for config.json.

Read-only helper. Buffer channel ids are not shown in the normal Buffer UI, so
this prints them. Handy whenever you connect a new channel, and again each time
the token rotates.

Usage (PowerShell):
  $env:BUFFER_TOKEN = "your-buffer-token"
  python list_channels.py

Then copy the id of the NetVane LinkedIn channel into config.json under
channels.netvane_linkedin.
"""
import json
import os
import urllib.request
import urllib.error

API_URL = "https://api.buffer.com"


def _gql(query, token):
    req = urllib.request.Request(
        API_URL,
        data=json.dumps({"query": query}).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            body = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Buffer HTTP {e.code}: {e.read().decode()[:500]}")
    if body.get("errors"):
        raise SystemExit(f"Buffer GraphQL error: {body['errors']}")
    return body["data"]


def main():
    token = os.environ.get("BUFFER_TOKEN")
    if not token:
        raise SystemExit("BUFFER_TOKEN is not set")

    orgs = _gql("{ account { organizations { id name } } }", token)["account"]["organizations"]
    if not orgs:
        raise SystemExit("No organizations found for this token")

    for org in orgs:
        print(f"\nOrganization: {org.get('name') or '(unnamed)'}  [{org['id']}]")
        q = ('{ channels(input: { organizationId: "%s" }) '
             '{ id service name displayName isQueuePaused } }') % org["id"]
        channels = _gql(q, token)["channels"]
        if not channels:
            print("  (no channels)")
            continue
        for c in channels:
            label = c.get("displayName") or c.get("name") or "(unnamed)"
            paused = "  [queue paused]" if c.get("isQueuePaused") else ""
            print(f"  {c['service']:10} {c['id']}  {label}{paused}")


if __name__ == "__main__":
    main()
