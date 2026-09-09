import os
from health import gql
t = os.environ["BUFFER_TOKEN"]
q = gql('{ __type(name: "Query") { fields { name args { name type { kind name ofType { kind name } } } } } }', t)
for f in q["__type"]["fields"]:
    if f["name"] == "posts":
        for a in f["args"]:
            ty = a["type"]; nm = ty.get("name") or (ty.get("ofType") or {}).get("name")
            print("ARG", a["name"], "->", nm)
for tn in ("PostsInput", "PostStatus"):
    ty = gql('{ __type(name: "%s") { kind inputFields { name type { kind name ofType { kind name } } } enumValues { name } } }' % tn, t)["__type"]
    if not ty: print(tn, "-> not found"); continue
    print(f"\n{tn} ({ty['kind']}):")
    for f in (ty.get("inputFields") or []):
        x = f["type"]; nm = x.get("name") or (x.get("ofType") or {}).get("name")
        print(f"   {f['name']}: {nm}")
    for e in (ty.get("enumValues") or []):
        print("   value:", e["name"])
