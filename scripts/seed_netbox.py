#!/usr/bin/env python3
"""Seed NetBox with the WAN lab (3 sites, 6 IOSv routers, 9 cables).

Idempotent: safe to run again, it only creates what is missing.

    pip install pynetbox
    export NETBOX_URL=http://localhost:8000
    export NETBOX_TOKEN=<token>
    python seed_netbox.py
"""
import ipaddress
import os

import pynetbox

TOKEN = os.environ["NETBOX_TOKEN"].strip()
if TOKEN.lower().startswith(("bearer ", "token ")):
    TOKEN = TOKEN.split(None, 1)[1]          # accept a pasted "Bearer xxx"

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


def gi(n):
    return f"GigabitEthernet0/{n}"


# ---------------------------------------------------------------- data ----
SITES = {"A": 65001, "B": 65002, "C": 65003}

# name: (site letter, Loopback0, {interface number: address})
ROUTERS = {
    "A1": ("A", "10.255.1.1/32", {0: "10.255.0.11/24", 1: "10.1.0.0/31", 2: "10.0.1.0/31", 3: "10.0.1.2/31", 6: "10.1.2.2/24", 7: "10.1.1.2/24"}),
    "A2": ("A", "10.255.1.2/32", {0: "10.255.0.12/24", 1: "10.1.0.1/31", 2: "10.0.2.0/31", 3: "10.0.2.2/31", 6: "10.1.2.3/24", 7: "10.1.1.3/24"}),
    "B1": ("B", "10.255.2.1/32", {1: "10.2.0.0/31", 2: "10.0.1.1/31", 3: "10.0.1.4/31", 6: "10.2.2.2/24", 7: "10.2.1.2/24"}),
    "B2": ("B", "10.255.2.2/32", {1: "10.2.0.1/31", 2: "10.0.2.1/31", 3: "10.0.2.4/31", 6: "10.2.2.3/24", 7: "10.2.1.3/24"}),
    "C1": ("C", "10.255.3.1/32", {1: "10.3.0.0/31", 2: "10.0.1.3/31", 3: "10.0.1.5/31", 6: "10.3.2.2/24", 7: "10.3.1.2/24"}),
    "C2": ("C", "10.255.3.2/32", {1: "10.3.0.1/31", 2: "10.0.2.3/31", 3: "10.0.2.5/31", 6: "10.3.2.3/24", 7: "10.3.1.3/24"}),
}

# (device, if#, device, if#, tag) -> 9 cables
LINKS = [
    ("A1", 1, "A2", 1, "intra-site"),
    ("B1", 1, "B2", 1, "intra-site"),
    ("C1", 1, "C2", 1, "intra-site"),
    ("A1", 2, "B1", 2, "plane1"),
    ("A1", 3, "C1", 2, "plane1"),
    ("B1", 3, "C1", 3, "plane1"),
    ("A2", 2, "B2", 2, "plane2"),
    ("A2", 3, "C2", 2, "plane2"),
    ("B2", 3, "C2", 3, "plane2"),
]

HOST_IP = "10.255.0.1/24"          # tun-gns3, default gateway for A1/A2
MGMT_PREFIX = "10.255.0.0/24"

# ------------------------------------------------------- base objects ----
print("Base objects")
tags = {t: ensure(nb.extras.tags, {"slug": t}, name=t)
        for t in ("intra-site", "plane1", "plane2")}

manufacturer = ensure(nb.dcim.manufacturers, {"slug": "cisco"}, name="Cisco")
dtype = ensure(nb.dcim.device_types, {"slug": "iosv"},
               manufacturer=manufacturer.id, model="IOSv")
for i in range(8):
    if not nb.dcim.interface_templates.get(devicetype_id=dtype.id, name=gi(i)):
        nb.dcim.interface_templates.create(device_type=dtype.id, name=gi(i), type="1000base-t")
role = ensure(nb.dcim.device_roles, {"slug": "wan-router"}, name="WAN Router", color="2196f3")
platform = ensure(nb.dcim.platforms, {"slug": "cisco_ios"}, name="Cisco IOS",
                  manufacturer=manufacturer.id)
rir = ensure(nb.ipam.rirs, {"slug": "private"}, name="Private", is_private=True)

sites = {}
for letter, asn in SITES.items():
    sites[letter] = ensure(nb.dcim.sites, {"slug": f"site-{letter.lower()}"},
                           name=f"Site {letter}", status="active")
    if not nb.ipam.asns.get(asn=asn):
        print(f"  + asn: {asn}")
        nb.ipam.asns.create(asn=asn, rir=rir.id, sites=[sites[letter].id],
                            description=f"Site {letter}")

# ------------------------------------------------ devices, IPs, loops ----
print("Devices, interfaces, IPs")
devices, ifaces, primary = {}, {}, {}


def get_iface(dev, name):
    """Find an interface by full name, falling back to the short Gi0/x form."""
    dev_id = devices[dev].id
    for candidate in (name, name.replace("GigabitEthernet", "Gi")):
        iface = nb.dcim.interfaces.get(device_id=dev_id, name=candidate)
        if iface:
            return iface
    raise SystemExit(f"Interface {name} not found on {dev}; "
                     f"check its device type / interface names in NetBox.")


def assign_ip(address, iface, **extra):
    """Make sure `address` exists and is assigned to `iface` (adopt existing IPs)."""
    existing = list(nb.ipam.ip_addresses.filter(address=address))
    for ip in existing:
        if ip.assigned_object_type == "dcim.interface" and ip.assigned_object_id == iface.id:
            return ip                                   # already correct
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
                                       assigned_object_id=iface.id, **extra)


for name, (letter, loopback, addrs) in ROUTERS.items():
    dev = nb.dcim.devices.get(name=name)
    if not dev:
        print(f"  + device: {name}")
        dev = nb.dcim.devices.create(name=name, device_type=dtype.id,
                                     site=sites[letter].id, platform=platform.id,
                                     status="active", **{ROLE_KEY: role.id})
    devices[name] = dev

    lo = nb.dcim.interfaces.get(device_id=dev.id, name="Loopback0")
    if not lo:
        lo = nb.dcim.interfaces.create(device=dev.id, name="Loopback0", type="virtual")
    lo_ip = assign_ip(loopback, lo)

    ips = {num: assign_ip(addr, get_iface(name, gi(num))) for num, addr in addrs.items()}

    # A1/A2 are managed on Gi0/0, B and C are reached through their loopback
    primary[name] = ips[0] if 0 in ips else lo_ip
    if not dev.primary_ip4 or dev.primary_ip4.id != primary[name].id:
        dev.primary_ip4 = primary[name].id
        dev.save()

# ------------------------------------------------------------ cables ----
print("Cables")
for da, ia, db, ib, tag in LINKS:
    a, b = get_iface(da, gi(ia)), get_iface(db, gi(ib))
    if a.cable or b.cable:
        continue
    print(f"  + cable: {da} {gi(ia)} <-> {db} {gi(ib)} [{tag}]")
    nb.dcim.cables.create(
        a_terminations=[{"object_type": "dcim.interface", "object_id": a.id}],
        b_terminations=[{"object_type": "dcim.interface", "object_id": b.id}],
        tags=[tags[tag].id], label=f"{da}-{db}")

# ------------------------------------------------------------ prefixes ----
print("Prefixes")
prefixes = {MGMT_PREFIX: "Management (GNS3 Cloud1 / tun-gns3)"}
for n, letter in enumerate("ABC", 1):
    prefixes[f"10.{n}.0.0/16"] = f"Site {letter} aggregate"
    prefixes[f"10.255.{n}.0/24"] = f"Site {letter} loopbacks"
for name, (letter, loopback, addrs) in ROUTERS.items():
    for num, addr in addrs.items():
        net = ipaddress.ip_interface(addr).network
        if num == 0:
            continue
        kind = {1: "intra-site link", 2: "inter-site link", 3: "inter-site link",
                6: f"Site {letter} LAN-INET", 7: f"Site {letter} LAN-S2S"}[num]
        prefixes.setdefault(str(net), kind)
for prefix, desc in prefixes.items():
    ensure(nb.ipam.prefixes, {"prefix": prefix}, description=desc, status="active")

# host (tun-gns3) address
ensure(nb.ipam.ip_addresses, {"address": HOST_IP},
       status="active", description="Host tun-gns3, default gateway for A1/A2")

# --------------------------------------------------------------- HSRP ----
print("HSRP")
for n, letter in enumerate("ABC", 1):
    # (group, interface, third octet, LAN name, router number that is active)
    for grp, ifnum, third, lan, active in ((1, 7, 1, "LAN-S2S", 2), (2, 6, 2, "LAN-INET", 1)):
        group = ensure(nb.ipam.fhrp_groups, {"name": f"{letter}-{lan}"},
                       protocol="hsrp", group_id=grp)
        vip = f"10.{n}.{third}.1/24"
        if not list(nb.ipam.ip_addresses.filter(address=vip)):
            nb.ipam.ip_addresses.create(address=vip, status="active", role="hsrp",
                                        assigned_object_type="ipam.fhrpgroup",
                                        assigned_object_id=group.id)
        for r in (1, 2):
            iface = get_iface(f"{letter}{r}", gi(ifnum))
            exists = list(nb.ipam.fhrp_group_assignments.filter(
                group_id=group.id, interface_type="dcim.interface", interface_id=iface.id))
            if not exists:
                nb.ipam.fhrp_group_assignments.create(
                    group=group.id, interface_type="dcim.interface",
                    interface_id=iface.id, priority=110 if r == active else 100)

print("Done.")
