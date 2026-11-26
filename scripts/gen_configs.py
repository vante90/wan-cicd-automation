#!/usr/bin/env python3
"""Generate the bootstrap router configs for the 3-site lab.

The data tables below mirror docs/addressing.md. Run:
    python3 scripts/gen_configs.py configs/bootstrap
Later phases replace this with NetBox data + Jinja2 templates + Ansible.
"""
import ipaddress
import os
import sys

OUT = sys.argv[1] if len(sys.argv) > 1 else "configs/bootstrap"

SITES = {
    "A": dict(asn=65001, n=1, agg="10.1.0.0/16", lob="10.255.1.0/24"),
    "B": dict(asn=65002, n=2, agg="10.2.0.0/16", lob="10.255.2.0/24"),
    "C": dict(asn=65003, n=3, agg="10.3.0.0/16", lob="10.255.3.0/24"),
}

# Prefixes each site originates (and so what its neighbours may accept from it)
ORIGIN = {
    "A": ["0.0.0.0/0", "10.1.0.0/16", "10.255.0.0/24", "10.255.1.0/24"],
    "B": ["10.2.0.0/16", "10.255.2.0/24"],
    "C": ["10.3.0.0/16", "10.255.3.0/24"],
}

# Traffic classes: class 1 prefers plane 1, class 2 prefers plane 2
CLASS1 = ["0.0.0.0/0", "10.255.0.0/24", "10.255.1.0/24", "10.255.2.0/24", "10.255.3.0/24"]
CLASS2 = ["10.1.0.0/16", "10.2.0.0/16", "10.3.0.0/16"]
LP_PRIMARY, LP_BACKUP = 200, 100

BFD = "bfd interval 500 min_rx 500 multiplier 3"

# g02 / g03 = (own address, neighbour name, neighbour address)
R = {
    "A1": dict(g01="10.1.0.0", peer="A2", g02=("10.0.1.0", "B1", "10.0.1.1"), g03=("10.0.1.2", "C1", "10.0.1.3"), mgmt="10.255.0.11"),
    "A2": dict(g01="10.1.0.1", peer="A1", g02=("10.0.2.0", "B2", "10.0.2.1"), g03=("10.0.2.2", "C2", "10.0.2.3"), mgmt="10.255.0.12"),
    "B1": dict(g01="10.2.0.0", peer="B2", g02=("10.0.1.1", "A1", "10.0.1.0"), g03=("10.0.1.4", "C1", "10.0.1.5")),
    "B2": dict(g01="10.2.0.1", peer="B1", g02=("10.0.2.1", "A2", "10.0.2.0"), g03=("10.0.2.4", "C2", "10.0.2.5")),
    "C1": dict(g01="10.3.0.0", peer="C2", g02=("10.0.1.3", "A1", "10.0.1.2"), g03=("10.0.1.5", "B1", "10.0.1.4")),
    "C2": dict(g01="10.3.0.1", peer="C1", g02=("10.0.2.3", "A2", "10.0.2.2"), g03=("10.0.2.5", "B2", "10.0.2.4")),
}


def mask(prefix):
    return str(ipaddress.ip_network(prefix).netmask)


def net_mask(prefix):
    n = ipaddress.ip_network(prefix)
    return f"{n.network_address} {n.netmask}"


def lo(name):
    return f"10.255.{SITES[name[0]]['n']}.{name[1]}"


def lan(name):
    """Site LAN (Gi0/7): VIP .1, router 1 = .2, router 2 = .3"""
    n = SITES[name[0]]["n"]
    return f"10.{n}.1.1", f"10.{n}.1.{1 + int(name[1])}"


def check():
    """Fail early if the tables are inconsistent."""
    seen = {}
    for name, r in R.items():
        addrs = [lo(name), r["g01"], r["g02"][0], r["g03"][0]]
        if "mgmt" in r:
            addrs.append(r["mgmt"])
        addrs.append(lan(name)[1])
        for a in addrs:
            assert a not in seen, f"duplicate address {a}: {name} and {seen[a]}"
            seen[a] = name
        peer = r["peer"]
        assert R[peer]["peer"] == name, f"{name}/{peer} not mirrored"
        assert ipaddress.ip_interface(f"{r['g01']}/31").network == \
            ipaddress.ip_interface(f"{R[peer]['g01']}/31").network, f"intra-site subnet {name}/{peer}"
        for key in ("g02", "g03"):
            a, nbr, na = r[key]
            back = [v for k, v in R[nbr].items() if k in ("g02", "g03") and v[1] == name]
            assert len(back) == 1 and back[0][0] == na and back[0][2] == a, f"link {name}-{nbr} not mirrored"
            assert ipaddress.ip_interface(f"{a}/31").network == ipaddress.ip_interface(f"{na}/31").network
            assert name[1] == nbr[1], f"{name}-{nbr} crosses planes"
    for s, o in ORIGIN.items():
        for p in o:
            assert p in CLASS1 or p in CLASS2, f"{p} originated by {s} has no traffic class"


def build(name):
    r = R[name]
    s = name[0]
    site = SITES[s]
    plane = int(name[1])
    vip, own_lan = lan(name)
    lp1, lp2 = (LP_PRIMARY, LP_BACKUP) if plane == 1 else (LP_BACKUP, LP_PRIMARY)
    L = []
    add = L.append

    add(f"! {name} - AS {site['asn']} - plane {plane} - initial configuration")
    add("! Paste stage by stage and verify after each stage. Edit CHANGE_ME in stage 1 first.")
    add("! Stage 6 needs the site LAN switch cabled to Gi0/7 first.")
    add("!")
    add("! ===== STAGE 1: base and SSH =====")
    add(f"hostname {name}")
    add("no ip domain lookup")
    add("ip domain name lab.local")
    add("username admin privilege 15 secret CHANGE_ME")
    add("ip ssh version 2")
    add("line con 0")
    add(" logging synchronous")
    add(" exec-timeout 0 0")
    add("line vty 0 4")
    add(" login local")
    add(" transport input ssh")
    add(" exec-timeout 0 0")
    add("exit")
    add("! Wait for the key generation to finish before pasting the next stage")
    add("crypto key generate rsa modulus 2048")
    add("!")
    add("! ===== STAGE 2: interfaces (with BFD timers) =====")
    add("interface Loopback0")
    add(" description Router ID / in-band management")
    add(f" ip address {lo(name)} 255.255.255.255")
    add("interface GigabitEthernet0/0")
    if "mgmt" in r:
        add(" description MGMT Cloud1 tun-gns3 via SW-MGMT")
        add(f" ip address {r['mgmt']} 255.255.255.0")
        add(" no shutdown")
    else:
        add(" description unused")
        add(" shutdown")
    add("interface GigabitEthernet0/1")
    add(f" description intra-site to {r['peer']} Gi0/1")
    add(f" ip address {r['g01']} 255.255.255.254")
    add(f" {BFD}")
    add(" no shutdown")
    for gi, key in (("0/2", "g02"), ("0/3", "g03")):
        a, nbr, na = r[key]
        add(f"interface GigabitEthernet{gi}")
        add(f" description inter-site to {nbr}")
        add(f" ip address {a} 255.255.255.254")
        add(f" {BFD}")
        add(" no shutdown")
    add("exit")
    if "mgmt" in r:
        add("ip route 0.0.0.0 0.0.0.0 10.255.0.1")
    add(f"ip route {net_mask(site['agg'])} Null0")
    add(f"ip route {net_mask(site['lob'])} Null0")
    add("!")
    add("! ===== STAGE 3: OSPF (area 0, inside the site, with BFD) =====")
    add("router ospf 1")
    add(f" router-id {lo(name)}")
    add(" passive-interface Loopback0")
    add(f" default-information originate metric {10 * plane} metric-type 1")
    add("exit")
    add("interface Loopback0")
    add(" ip ospf 1 area 0")
    add("interface GigabitEthernet0/1")
    add(" ip ospf 1 area 0")
    add(" ip ospf network point-to-point")
    add(" ip ospf bfd")
    add("exit")
    add("!")
    add("! ===== STAGE 4: prefix-lists and route-maps (BGP policy) =====")

    def pl(plname, prefixes):
        for i, p in enumerate(prefixes, 1):
            add(f"ip prefix-list {plname} seq {i * 10} permit {p}")

    pl(f"PL-OUT-{s}", ORIGIN[s])
    for o in [x for x in "ABC" if x != s]:
        pl(f"PL-IN-{o}", ORIGIN[o])
    pl("PL-CLASS1", CLASS1)
    pl("PL-CLASS2", CLASS2)
    add(f"route-map RM-IN-PLANE{plane} permit 10")
    add(" match ip address prefix-list PL-CLASS1")
    add(f" set local-preference {lp1}")
    add(f"route-map RM-IN-PLANE{plane} permit 20")
    add(" match ip address prefix-list PL-CLASS2")
    add(f" set local-preference {lp2}")
    add("!")
    add(f"! ===== STAGE 5: BGP (AS {site['asn']}) =====")
    add(f"router bgp {site['asn']}")
    add(f" bgp router-id {lo(name)}")
    add(" bgp log-neighbor-changes")
    ib = lo(r["peer"])
    add(f" neighbor {ib} remote-as {site['asn']}")
    add(f" neighbor {ib} description iBGP {r['peer']}")
    add(f" neighbor {ib} update-source Loopback0")
    add(f" neighbor {ib} timers 3 9")
    ebgp = []
    for key in ("g02", "g03"):
        a, nbr, na = r[key]
        ns = nbr[0]
        ebgp.append((na, nbr, ns))
        add(f" neighbor {na} remote-as {SITES[ns]['asn']}")
        add(f" neighbor {na} description eBGP {nbr}")
        add(f" neighbor {na} fall-over bfd")
    add(" address-family ipv4")
    for p in ORIGIN[s]:
        if p == "0.0.0.0/0":
            add("  network 0.0.0.0")
        else:
            add(f"  network {p.split('/')[0]} mask {mask(p)}")
    add(f"  neighbor {ib} activate")
    add(f"  neighbor {ib} next-hop-self")
    for na, nbr, ns in ebgp:
        add(f"  neighbor {na} activate")
        add(f"  neighbor {na} prefix-list PL-OUT-{s} out")
        add(f"  neighbor {na} prefix-list PL-IN-{ns} in")
        add(f"  neighbor {na} route-map RM-IN-PLANE{plane} in")
    add(" exit-address-family")
    add("exit")
    add("!")
    add("! ===== STAGE 6: site LAN and HSRP (Gi0/7) =====")
    add("interface GigabitEthernet0/7")
    add(" description site LAN (HSRP gateway)")
    add(f" ip address {own_lan} 255.255.255.0")
    add(" standby version 2")
    add(f" standby 1 ip {vip}")
    add(f" standby 1 priority {110 if plane == 1 else 100}")
    add(" standby 1 preempt")
    add(" standby 1 timers 1 3")
    add(" ip ospf 1 area 0")
    add(" no shutdown")
    add("exit")
    add("router ospf 1")
    add(" passive-interface GigabitEthernet0/7")
    add("end")
    add("write memory")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    check()
    os.makedirs(OUT, exist_ok=True)
    for n in R:
        with open(os.path.join(OUT, f"{n}.cfg"), "w") as f:
            f.write(build(n))
    print("generated:", ", ".join(sorted(R)), "->", OUT)
