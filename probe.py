import os, json
from health import gql, _recent_posts
t=os.environ["BUFFER_TOKEN"]
org=gql('{ account { organizations { id } } }',t)["account"]["organizations"][0]["id"]
ch=gql('{ channels(input:{organizationId:"%s"}){ id service displayName updatedAt createdAt } }'%org,t)["channels"]
print("CHANNELS:")
for c in ch:
    print(f"  {c['service']:10} {c.get('displayName'):22} updatedAt={c.get('updatedAt')}")
print("\nINSTAGRAM POSTS (newest first):")
ig=json.load(open("config.json",encoding="utf-8"))["channels"]["instagram"]
ns=[n for n in _recent_posts(t,org,80) if n["channelId"]==ig]
ns.sort(key=lambda n:(n.get("sentAt") or n.get("dueAt") or ""),reverse=True)
for n in ns[:10]:
    print(f"  {n['status']:10} due={n.get('dueAt')} sent={n.get('sentAt')}")
