import ipaddress, os, sys

OUT = sys.argv[1]

def mask(prefix):
    return str(ipaddress.ip_network(prefix).netmask)

def net_mask(prefix):
    n = ipaddress.ip_network(prefix)
    return f"{n.network_address} {n.netmask}"

SITES = {
    "A": dict(asn=65001, n=1, agg="10.1.0.0/16", lob="10.255.1.0/24"),
    "B": dict(asn=65002, n=2, agg="10.2.0.0/16", lob="10.255.2.0/24"),
    "C": dict(asn=65003, n=3, agg="10.3.0.0/16", lob="10.255.3.0/24"),
}
ORIGIN = {
    "A": ["0.0.0.0/0", "10.1.0.0/16", "10.255.0.0/24", "10.255.1.0/24"],
    "B": ["10.2.0.0/16", "10.255.2.0/24"],
    "C": ["10.3.0.0/16", "10.255.3.0/24"],
}
R = {
 "A1": dict(g01="10.1.0.0", peer="A2", g02=("10.0.1.0","B1","10.0.1.1"), g03=("10.0.1.2","C1","10.0.1.3"), mgmt="10.255.0.11"),
 "A2": dict(g01="10.1.0.1", peer="A1", g02=("10.0.2.0","B2","10.0.2.1"), g03=("10.0.2.2","C2","10.0.2.3"), mgmt="10.255.0.12"),
 "B1": dict(g01="10.2.0.0", peer="B2", g02=("10.0.1.1","A1","10.0.1.0"), g03=("10.0.1.4","C1","10.0.1.5")),
 "B2": dict(g01="10.2.0.1", peer="B1", g02=("10.0.2.1","A2","10.0.2.0"), g03=("10.0.2.4","C2","10.0.2.5")),
 "C1": dict(g01="10.3.0.0", peer="C2", g02=("10.0.1.3","A1","10.0.1.2"), g03=("10.0.1.5","B1","10.0.1.4")),
 "C2": dict(g01="10.3.0.1", peer="C1", g02=("10.0.2.3","A2","10.0.2.2"), g03=("10.0.2.5","B2","10.0.2.4")),
}

def lo(name):
    return f"10.255.{SITES[name[0]]['n']}.{name[1]}"

def build(name):
    r = R[name]; s = name[0]; site = SITES[s]
    L = []
    add = L.append
    add(f"! {name} - AS {site['asn']} - initial configuration")
    add("! Paste stage by stage and verify after each stage. Edit CHANGE_ME in stage 1 first.")
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
    add("! ===== STAGE 2: interfaces =====")
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
    add(" no shutdown")
    for gi, key in (("0/2", "g02"), ("0/3", "g03")):
        a, nbr, na = r[key]
        add(f"interface GigabitEthernet{gi}")
        add(f" description inter-site to {nbr}")
        add(f" ip address {a} 255.255.255.254")
        add(" no shutdown")
    add("exit")
    if "mgmt" in r:
        add("ip route 0.0.0.0 0.0.0.0 10.255.0.1")
    add(f"ip route {net_mask(site['agg'])} Null0")
    add(f"ip route {net_mask(site['lob'])} Null0")
    add("!")
    add("! ===== STAGE 3: OSPF (area 0, inside the site) =====")
    add("router ospf 1")
    add(f" router-id {lo(name)}")
    add(" passive-interface Loopback0")
    add(" default-information originate")
    add("exit")
    add("interface Loopback0")
    add(" ip ospf 1 area 0")
    add("interface GigabitEthernet0/1")
    add(" ip ospf 1 area 0")
    add(" ip ospf network point-to-point")
    add("exit")
    add("!")
    add("! ===== STAGE 4: prefix-lists (BGP policy) =====")
    def pl(plname, prefixes):
        for i, p in enumerate(prefixes, 1):
            add(f"ip prefix-list {plname} seq {i*10} permit {p}")
    pl(f"PL-OUT-{s}", ORIGIN[s])
    for o in [x for x in "ABC" if x != s]:
        pl(f"PL-IN-{o}", ORIGIN[o])
    add("!")
    add(f"! ===== STAGE 5: BGP (AS {site['asn']}) =====")
    add(f"router bgp {site['asn']}")
    add(f" bgp router-id {lo(name)}")
    add(" bgp log-neighbor-changes")
    ib = lo(r["peer"])
    add(f" neighbor {ib} remote-as {site['asn']}")
    add(f" neighbor {ib} description iBGP {r['peer']}")
    add(f" neighbor {ib} update-source Loopback0")
    ebgp = []
    for key in ("g02", "g03"):
        a, nbr, na = r[key]
        ns = nbr[0]
        ebgp.append((na, nbr, ns))
        add(f" neighbor {na} remote-as {SITES[ns]['asn']}")
        add(f" neighbor {na} description eBGP {nbr}")
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
    add(" exit-address-family")
    add("end")
    add("write memory")
    return "\n".join(L) + "\n"

os.makedirs(OUT, exist_ok=True)
for n in R:
    with open(os.path.join(OUT, f"{n}.cfg"), "w") as f:
        f.write(build(n))
print("generated:", ", ".join(sorted(R)))
