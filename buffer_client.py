"""Minimal Buffer GraphQL API client.

Buffer's API is GraphQL at https://api.buffer.com. We create posts with
`createPost`, mode `addToQueue` so each post drops into the channel's existing
posting schedule (the Mon/Wed/Fri slots we configured in Buffer). Images are
attached BY URL via assets:[{image:{url}}] — Buffer fetches them itself, which is
why the file never has to be uploaded through a browser.

Docs: https://developers.buffer.com/examples/create-image-post.html
"""
import json
import os
import urllib.request
import urllib.error

API_URL = "https://api.buffer.com"

_MUTATION = """
mutation CreatePost($input: CreatePostInput!) {
  createPost(input: $input) {
    ... on PostActionSuccess { post { id } }
    ... on MutationError { message }
  }
}
"""


def create_post(channel_id, text, image_url=None, token=None, dry_run=False):
    token = token or os.environ.get("BUFFER_TOKEN")
    if not token and not dry_run:
        raise RuntimeError("BUFFER_TOKEN is not set")

    post_input = {
        "channelId": channel_id,
        "text": text,
        "schedulingType": "automatic",
        "mode": "addToQueue",
    }
    if image_url:
        post_input["assets"] = [{"image": {"url": image_url}}]

    payload = {"query": _MUTATION, "variables": {"input": post_input}}

    if dry_run:
        print("DRY RUN — would send to Buffer:")
        print(json.dumps(payload, indent=2)[:1200])
        return {"dryRun": True}

    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode(),
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
        raise RuntimeError(f"Buffer HTTP {e.code}: {e.read().decode()[:500]}")

    if body.get("errors"):
        raise RuntimeError(f"Buffer GraphQL error: {body['errors']}")
    result = body["data"]["createPost"]
    if "message" in result:
        raise RuntimeError(f"Buffer rejected post: {result['message']}")
    return result["post"]
