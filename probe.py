import os, json, urllib.request, urllib.error
t=os.environ["BUFFER_TOKEN"]
def raw(q):
    r=urllib.request.Request("https://api.buffer.com",data=json.dumps({"query":q}).encode(),
      headers={"Content-Type":"application/json","Authorization":f"Bearer {t}"},method="POST")
    try:
        with urllib.request.urlopen(r,timeout=45) as x: return json.loads(x.read().decode())
    except urllib.error.HTTPError as e: return {"http":e.code,"body":e.read().decode()[:300]}
ty=raw('{ __type(name:"PostPublishingError"){ fields { name } } }')
print("PostPublishingError fields:", [f["name"] for f in ty["data"]["__type"]["fields"]] if ty.get("data",{}).get("__type") else ty)
org=raw('{ account { organizations { id } } }')["data"]["account"]["organizations"][0]["id"]
q='{ posts(first: 25, input: { organizationId: "%s" }) { edges { node { id status channelId channelService sentAt dueAt error { message } } } } }' % org
r=raw(q)
if "errors" in r: print("QUERY FAILED:", str(r["errors"])[:300])
else:
    nodes=[e["node"] for e in r["data"]["posts"]["edges"]]
    print(f"\n{len(nodes)} recent posts:")
    for n in nodes:
        err=(n.get("error") or {}).get("message")
        print(f"  {n['channelService']:10} {n['status']:14} due={n.get('dueAt')} sent={n.get('sentAt')} err={err}")
