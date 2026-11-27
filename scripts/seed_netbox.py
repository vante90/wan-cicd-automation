#!/usr/bin/env python3
"""Apply data/lab.yml to NetBox. Git is the master, NetBox follows.

    python scripts/seed_netbox.py --validate-only   # check the YAML, no NetBox needed
    python scripts/seed_netbox.py                   # apply it (idempotent)
    python scripts/seed_netbox.py --strict          # also exit 1 if NetBox has drift

Environment: NETBOX_URL (default http://localhost:8000), NETBOX_TOKEN (bare token).
The script never deletes anything. Objects that exist in NetBox but not in the
YAML are only reported as DRIFT.
"""
import argparse
import ipaddress
import os
import sys
from pathlib import Path

import yaml

DEFAULT_DATA = Path(__file__).resolve().parent.parent / "data" / "lab.yml"

ap = argparse.ArgumentParser()
ap.add_argument("--data", default=str(DEFAULT_DATA), help="path to lab.yml")
ap.add_argument("--validate-only", action="store_true", help="check the YAML and stop")
ap.add_argument("--strict", action="store_true", help="exit 1 when drift is found")
args = ap.parse_args()

with open(args.data) as f:
    lab = yaml.safe_load(f)


# ------------------------------------------------------------ validation ----
def validate(lab):
    errors = []
    sites = {s["slug"] for s in lab["sites"]}
    tags = set(lab["tags"])
    devs = {d["name"]: d for d in lab["devices"]}
    if len(devs) != len(lab["devices"]):
        errors.append("duplicate device names")

    seen_ips = {}
    for d in lab["devices"]:
        if d["site"] not in sites:
            errors.append(f"{d['name']}: unknown site {d['site']}")
        if d["primary_interface"] not in d["interfaces"]:
            errors.append(f"{d['name']}: primary_interface {d['primary_interface']} not defined")
        for ifname, ifd in d["interfaces"].items():
            try:
                ip = ipaddress.ip_interface(ifd["ip"])
            except ValueError as e:
                errors.append(f"{d['name']} {ifname}: {e}")
                continue
            key = str(ip.ip)
            if key in seen_ips:
                errors.append(f"duplicate IP {key}: {seen_ips[key]} and {d['name']} {ifname}")
            seen_ips[key] = f"{d['name']} {ifname}"

    used = {}
    for link in lab["links"]:
        if link.get("tag") and link["tag"] not in tags:
            errors.append(f"link {link['a']} - {link['b']}: unknown tag {link['tag']}")
        for end in (link["a"], link["b"]):
            dev, _, ifname = end.partition(":")
            if dev not in devs or ifname not in devs[dev]["interfaces"]:
                errors.append(f"link end {end} does not exist in devices")
            if end in used:
                errors.append(f"{end} is used by two links")
            used[end] = True

    for g in lab["fhrp_groups"]:
        net = None
        for m in g["members"]:
            ifd = devs.get(m["device"], {}).get("interfaces", {}).get(m["interface"])
            if not ifd:
                errors.append(f"HSRP {g['name']}: {m['device']} {m['interface']} not defined")
                continue
            net = ipaddress.ip_interface(ifd["ip"]).network
            if ipaddress.ip_interface(g["vip"]).ip not in net:
                errors.append(f"HSRP {g['name']}: VIP {g['vip']} is not in {net}")
    return errors


def derived_prefixes(lab):
    """Prefixes taken from interface addresses (skipping /32) plus the explicit list."""
    out = {p["prefix"]: p["description"] for p in lab["prefixes"]}
    for d in lab["devices"]:
        for ifd in d["interfaces"].values():
            net = ipaddress.ip_interface(ifd["ip"]).network
            if net.prefixlen < 32:
                out.setdefault(str(net), ifd["description"])
    return out


problems = validate(lab)
if problems:
    print("Validation FAILED:")
    for p in problems:
        print("  -", p)
    sys.exit(1)
PREFIXES = derived_prefixes(lab)
print(f"Validation OK: {len(lab['sites'])} sites, {len(lab['devices'])} devices, "
      f"{len(lab['links'])} links, {len(PREFIXES)} prefixes, {len(lab['fhrp_groups'])} HSRP groups")
if args.validate_only:
    sys.exit(0)

# --------------------------------------------------------------- NetBox ----
import pynetbox  # noqa: E402  (not needed for --validate-only)

TOKEN = os.environ["NETBOX_TOKEN"].strip()
if TOKEN.lower().startswith(("bearer ", "token ")):
    TOKEN = TOKEN.split(None, 1)[1]
nb = pynetbox.api(os.environ.get("NETBOX_URL", "http://localhost:8000"), token=TOKEN)
if TOKEN.startswith("nbt_"):                  # v2 tokens (NetBox 4.5+) use Bearer
    nb.http_session.headers["Authorization"] = f"Bearer {TOKEN}"

major, minor = (int(x) for x in nb.version.split(".")[:2])
ROLE_KEY = "role" if (major, minor) >= (4, 0) else "device_role"


def ensure(endpoint, lookup, **extra):
    """Return the object matching lookup, creating it (lookup + extra) if absent."""
    obj = endpoint.get(**lookup)
    if obj:
        return obj
    print(f"  + {endpoint.name}: {lookup}")
    return endpoint.create(**lookup, **extra)


print("Base objects")
tags = {t: ensure(nb.extras.tags, {"slug": t}, name=t) for t in lab["tags"]}
mf = lab["manufacturer"]
manufacturer = ensure(nb.dcim.manufacturers, {"slug": mf["slug"]}, name=mf["name"])
dt = lab["device_type"]
dtype = ensure(nb.dcim.device_types, {"slug": dt["slug"]},
               manufacturer=manufacturer.id, model=dt["model"])
for i in range(dt["interface_count"]):
    name = f"{dt['interface_prefix']}{i}"
    if not nb.dcim.interface_templates.get(devicetype_id=dtype.id, name=name):
        nb.dcim.interface_templates.create(device_type=dtype.id, name=name, type="1000base-t")
rl = lab["role"]
role = ensure(nb.dcim.device_roles, {"slug": rl["slug"]}, name=rl["name"], color=rl["color"])
pl = lab["platform"]
platform = ensure(nb.dcim.platforms, {"slug": pl["slug"]}, name=pl["name"],
                  manufacturer=manufacturer.id)
rir = ensure(nb.ipam.rirs, {"slug": "private"}, name="Private", is_private=True)

sites = {}
for s in lab["sites"]:
    sites[s["slug"]] = ensure(nb.dcim.sites, {"slug": s["slug"]}, name=s["name"], status="active")
    if not nb.ipam.asns.get(asn=s["asn"]):
        print(f"  + asn: {s['asn']}")
        nb.ipam.asns.create(asn=s["asn"], rir=rir.id, sites=[sites[s["slug"]].id],
                            description=s["name"])

print("Devices, interfaces, IPs")
devices = {}


def get_iface(dev, name):
    """Find an interface by full name, falling back to the short Gi0/x form."""
    for candidate in (name, name.replace("GigabitEthernet", "Gi")):
        iface = nb.dcim.interfaces.get(device_id=devices[dev].id, name=candidate)
        if iface:
            return iface
    raise SystemExit(f"Interface {name} not found on {dev}; "
                     f"check its device type / interface names in NetBox.")


def assign_ip(address, iface):
    """Make sure `address` exists and is assigned to `iface` (adopt existing IPs)."""
    existing = list(nb.ipam.ip_addresses.filter(address=address))
    for ip in existing:
        if ip.assigned_object_type == "dcim.interface" and ip.assigned_object_id == iface.id:
            return ip
    if existing:
        ip = existing[0]
        old = (f"{ip.assigned_object.device.name} {ip.assigned_object.name}"
               if ip.assigned_object else "nothing")
        print(f"  ~ ip: {address} was on {old}, moving to {iface.device.name} {iface.name}")
        ip.assigned_object_type = "dcim.interface"
        ip.assigned_object_id = iface.id
        ip.save()
        return ip
    print(f"  + ip: {address} on {iface.device.name} {iface.name}")
    return nb.ipam.ip_addresses.create(address=address, status="active",
                                       assigned_object_type="dcim.interface",
                                       assigned_object_id=iface.id)


for d in lab["devices"]:
    dev = nb.dcim.devices.get(name=d["name"])
    if not dev:
        print(f"  + device: {d['name']}")
        dev = nb.dcim.devices.create(name=d["name"], device_type=dtype.id,
                                     site=sites[d["site"]].id, platform=platform.id,
                                     status="active", **{ROLE_KEY: role.id})
    elif not dev.platform:
        dev.platform = platform.id
        dev.save()
    devices[d["name"]] = dev

    ips = {}
    for ifname, ifd in d["interfaces"].items():
        if ifname.lower().startswith("loopback"):
            iface = nb.dcim.interfaces.get(device_id=dev.id, name=ifname) or \
                nb.dcim.interfaces.create(device=dev.id, name=ifname, type="virtual")
        else:
            iface = get_iface(d["name"], ifname)
        if iface.description != ifd["description"]:
            iface.description = ifd["description"]
            iface.save()
        ips[ifname] = assign_ip(ifd["ip"], iface)

    primary = ips[d["primary_interface"]]
    if not dev.primary_ip4 or dev.primary_ip4.id != primary.id:
        dev.primary_ip4 = primary.id
        dev.save()

print("Cables")
for link in lab["links"]:
    (da, ia), (db, ib) = link["a"].split(":"), link["b"].split(":")
    a, b = get_iface(da, ia), get_iface(db, ib)
    if a.cable or b.cable:
        continue
    print(f"  + cable: {da} {ia} <-> {db} {ib} [{link.get('tag')}]")
    nb.dcim.cables.create(
        a_terminations=[{"object_type": "dcim.interface", "object_id": a.id}],
        b_terminations=[{"object_type": "dcim.interface", "object_id": b.id}],
        tags=[tags[link["tag"]].id] if link.get("tag") else [], label=f"{da}-{db}")

print("Prefixes")
for prefix, desc in PREFIXES.items():
    ensure(nb.ipam.prefixes, {"prefix": prefix}, description=desc, status="active")
for e in lab["external_ips"]:
    ensure(nb.ipam.ip_addresses, {"address": e["address"]},
           status="active", description=e["description"])

print("HSRP")
for g in lab["fhrp_groups"]:
    group = ensure(nb.ipam.fhrp_groups, {"name": g["name"]},
                   protocol=g["protocol"], group_id=g["group"])
    if not list(nb.ipam.ip_addresses.filter(address=g["vip"])):
        nb.ipam.ip_addresses.create(address=g["vip"], status="active", role="hsrp",
                                    assigned_object_type="ipam.fhrpgroup",
                                    assigned_object_id=group.id)
    for m in g["members"]:
        iface = get_iface(m["device"], m["interface"])
        if not list(nb.ipam.fhrp_group_assignments.filter(
                group_id=group.id, interface_type="dcim.interface", interface_id=iface.id)):
            nb.ipam.fhrp_group_assignments.create(
                group=group.id, interface_type="dcim.interface",
                interface_id=iface.id, priority=m["priority"])

# ---------------------------------------------------------------- drift ----
print("Drift check (report only, nothing is deleted)")
drift = 0
want_devs = {d["name"] for d in lab["devices"]}
for dev in nb.dcim.devices.filter(role=rl["slug"]):
    if dev.name not in want_devs:
        print(f"  DRIFT: device {dev.name} is in NetBox but not in lab.yml")
        drift += 1
for p in nb.ipam.prefixes.filter(within_include="10.0.0.0/8"):
    if str(p.prefix) not in PREFIXES:
        print(f"  DRIFT: prefix {p.prefix} is in NetBox but not in lab.yml")
        drift += 1
print("  none" if not drift else f"  {drift} item(s) differ from git")
print("Done.")
if drift and args.strict:
    sys.exit(1)
