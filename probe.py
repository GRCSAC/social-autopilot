"""Throwaway: dump the bits of Buffer's schema we need to detect failed posts."""
import os, json
from health import gql
t = os.environ["BUFFER_TOKEN"]

root = gql('{ __type(name: "Query") { fields { name args { name type { kind name ofType { name } } } } } }', t)
print("ROOT QUERY FIELDS:")
for f in root["__type"]["fields"]:
    args = ",".join(a["name"] for a in f["args"])
    print(f"  {f['name']}({args})")

for tn in ("Post", "Channel"):
    ty = gql('{ __type(name: "%s") { fields { name type { kind name ofType { kind name } } } } }' % tn, t)["__type"]
    if not ty: continue
    print(f"\n{tn.upper()} FIELDS:")
    print("  " + ", ".join(f["name"] for f in ty["fields"]))
