#!/usr/bin/env python3
"""Fallback dynamic inventory (use if nb_inventory rejects your v2 token).

    ansible-inventory -i netbox_inventory.py --graph
Reads NETBOX_URL and NETBOX_TOKEN from the environment.
"""
import json
import os
import sys

import pynetbox

TOKEN = os.environ["NETBOX_TOKEN"].strip().removeprefix("Bearer ").removeprefix("Token ")
nb = pynetbox.api(os.environ.get("NETBOX_URL", "http://localhost:8000"), token=TOKEN)
if TOKEN.startswith("nbt_"):
    nb.http_session.headers["Authorization"] = f"Bearer {TOKEN}"

inv = {"_meta": {"hostvars": {}}, "all": {"children": ["ungrouped"]}}


def group(name):
    return inv.setdefault(name, {"hosts": []})["hosts"]


for d in nb.dcim.devices.filter(role="wan-router"):
    ifaces = {}
    for ip in nb.ipam.ip_addresses.filter(device_id=d.id):
        ifaces.setdefault(ip.assigned_object.name, []).append(str(ip))
    asn = next(iter(nb.ipam.asns.filter(site_id=d.site.id)), None)
    inv["_meta"]["hostvars"][d.name] = {
        "ansible_host": str(d.primary_ip4).split("/")[0],
        "ansible_network_os": "cisco.ios.ios",
        "ansible_connection": "ansible.netcommon.network_cli",
        "site": d.site.slug,
        "bgp_asn": asn.asn if asn else None,
        "interfaces": ifaces,
    }
    group(f"sites_{d.site.slug}".replace("-", "_")).append(d.name)
    group("device_roles_wan_router").append(d.name)

print(json.dumps(inv, indent=2) if "--host" not in sys.argv else "{}")
