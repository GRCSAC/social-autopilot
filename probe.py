import os, json, urllib.request, urllib.error
t = os.environ["BUFFER_TOKEN"]
def raw(q, v=None):
    p={"query":q}
    if v: p["variables"]=v
    r=urllib.request.Request("https://api.buffer.com",data=json.dumps(p).encode(),
        headers={"Content-Type":"application/json","Authorization":f"Bearer {t}"},method="POST")
    try:
        with urllib.request.urlopen(r,timeout=45) as x: return json.loads(x.read().decode())
    except urllib.error.HTTPError as e: return {"http":e.code,"body":e.read().decode()[:300]}

org = raw('{ account { organizations { id } } }')["data"]["account"]["organizations"][0]["id"]
print("ORG:", org)
cfg = json.load(open("config.json",encoding="utf-8"))["channels"]
ig = cfg["instagram"]

shapes = [
 ('A', '{ posts(first: 15, input: { organizationId: "%s" }) { edges { node { id status error channelId sentAt } } } }' % org),
 ('B', '{ posts(first: 15, input: { channelIds: ["%s"] }) { edges { node { id status error sentAt } } } }' % ig),
 ('C', '{ posts(first: 15, input: { organizationId: "%s", channelIds: ["%s"] }) { edges { node { id status error sentAt text } } } }' % (org, ig)),
]
for name, q in shapes:
    r = raw(q)
    if "errors" in r or "http" in r:
        msg = str(r.get("errors") or r)[:220]
        print(f"\n{name}: FAILED {msg}")
    else:
        print(f"\n{name}: OK")
        print(json.dumps(r["data"], indent=1)[:1500])
        break
