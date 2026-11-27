#!/usr/bin/env python3
"""Step 4: learn the NetBox API with pynetbox (and the equivalent curl calls).

    export NETBOX_URL=http://localhost:8000
    export NETBOX_TOKEN='nbt_xxx.yyy'      # bare token, no "Bearer"
    python query_netbox.py

Equivalent raw calls:
    curl -s -H "Authorization: Bearer $NETBOX_TOKEN" -H "Accept: application/json" \
         "$NETBOX_URL/api/dcim/devices/?site=site-a&brief=1" | jq
"""
import os

import pynetbox

TOKEN = os.environ["NETBOX_TOKEN"].strip().removeprefix("Bearer ").removeprefix("Token ")
nb = pynetbox.api(os.environ.get("NETBOX_URL", "http://localhost:8000"), token=TOKEN)
if TOKEN.startswith("nbt_"):
    nb.http_session.headers["Authorization"] = f"Bearer {TOKEN}"

print("== 1. All WAN routers with their management IP")
for d in nb.dcim.devices.filter(role="wan-router"):
    print(f"  {d.name:3} {d.site.name:7} {d.primary_ip4}")

print("\n== 2. Devices of one site")
for d in nb.dcim.devices.filter(site="site-a"):
    print(" ", d.name)

print("\n== 3. Interfaces and IPs of A1")
a1 = nb.dcim.devices.get(name="A1")
for i in nb.dcim.interfaces.filter(device_id=a1.id):
    ips = [str(ip) for ip in nb.ipam.ip_addresses.filter(interface_id=i.id)]
    print(f"  {i.name:20} {', '.join(ips) or '-'}")

print("\n== 4. Plane 1 cables (tag filter)")
for c in nb.dcim.cables.filter(tag="plane1"):
    a = c.a_terminations[0].object
    b = c.b_terminations[0].object
    print(f"  {a.device.name} {a.name} <-> {b.device.name} {b.name}")

print("\n== 5. Which device owns this IP?")
for ip in nb.ipam.ip_addresses.filter(address="10.255.2.1/32"):
    print(f"  {ip.address} -> {ip.assigned_object.device.name} {ip.assigned_object.name}")

print("\n== 6. Prefixes inside 10.1.0.0/16 (site A)")
for p in nb.ipam.prefixes.filter(within="10.1.0.0/16"):
    print(f"  {p.prefix:16} {p.description}")

print("\n== 7. ASNs")
for a in nb.ipam.asns.all():
    print(f"  AS{a.asn}  sites={[s.name for s in a.sites]}")
