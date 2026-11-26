# Addressing and routing plan

## Address blocks

| Block | Use |
|---|---|
| 10.255.0.0/24 | Management segment (host tun-gns3 + A1/A2 Gi0/0) |
| 10.255.1.0/24 | Loopbacks, site A |
| 10.255.2.0/24 | Loopbacks, site B |
| 10.255.3.0/24 | Loopbacks, site C |
| 10.0.1.0/24 | Inter-site links, plane 1 (not advertised) |
| 10.0.2.0/24 | Inter-site links, plane 2 (not advertised) |
| 10.1.0.0/16 | Site A aggregate: intra-site link (10.1.0.0/31), site LAN (10.1.1.0/24), fabric and servers later |
| 10.2.0.0/16 | Site B aggregate, same layout |
| 10.3.0.0/16 | Site C aggregate, same layout |

Rules:
- Point-to-point links use /31 (RFC 3021). The lower-lettered router (or the lower number) gets the even address.
- Loopback numbering is `10.255.<site number>.<router number>/32` (site A = 1, B = 2, C = 3).
- Site LAN is `10.<site number>.1.0/24`: HSRP virtual address `.1`, router 1 `.2`, router 2 `.3`.
- Do not summarize 10.255.0.0/24 into a wider 10.255.0.0/16, it would cover the loopback blocks.

## Host and management

| Device | Interface | Address |
|---|---|---|
| Host (Linux) | tun-gns3 | 10.255.0.1/24 (default gateway for A1/A2) |
| A1 | Gi0/0 | 10.255.0.11/24 |
| A2 | Gi0/0 | 10.255.0.12/24 |

Host routes towards the lab, via A1 (10.255.0.11): 10.1.0.0/16, 10.2.0.0/16, 10.3.0.0/16, 10.255.1.0/24, 10.255.2.0/24, 10.255.3.0/24.

## Router addresses

| Router | Loopback0 | Gi0/1 (intra-site) | Gi0/2 | Gi0/3 | Gi0/7 (site LAN) |
|---|---|---|---|---|---|
| A1 | 10.255.1.1/32 | 10.1.0.0/31 (to A2) | 10.0.1.0/31 (to B1) | 10.0.1.2/31 (to C1) | 10.1.1.2/24 |
| A2 | 10.255.1.2/32 | 10.1.0.1/31 (to A1) | 10.0.2.0/31 (to B2) | 10.0.2.2/31 (to C2) | 10.1.1.3/24 |
| B1 | 10.255.2.1/32 | 10.2.0.0/31 (to B2) | 10.0.1.1/31 (to A1) | 10.0.1.4/31 (to C1) | 10.2.1.2/24 |
| B2 | 10.255.2.2/32 | 10.2.0.1/31 (to B1) | 10.0.2.1/31 (to A2) | 10.0.2.4/31 (to C2) | 10.2.1.3/24 |
| C1 | 10.255.3.1/32 | 10.3.0.0/31 (to C2) | 10.0.1.3/31 (to A1) | 10.0.1.5/31 (to B1) | 10.3.1.2/24 |
| C2 | 10.255.3.2/32 | 10.3.0.1/31 (to C1) | 10.0.2.3/31 (to A2) | 10.0.2.5/31 (to B2) | 10.3.1.3/24 |

## HSRP (site LAN gateways)

| Site | Interface | Virtual IP | Active (priority 110, preempt) | Standby (priority 100) |
|---|---|---|---|---|
| A | Gi0/7 | 10.1.1.1 | A1 | A2 |
| B | Gi0/7 | 10.2.1.1 | B1 | B2 |
| C | Gi0/7 | 10.3.1.1 | C1 | C2 |

Version 2, group 1, hello 1 s, hold 3 s. The site LAN is advertised in OSPF (passive interface) and covered by the site aggregate in BGP.

## BFD

| Where | Setting |
|---|---|
| Interfaces Gi0/1, Gi0/2, Gi0/3 | `bfd interval 500 min_rx 500 multiplier 3` |
| eBGP sessions (6) | `neighbor ... fall-over bfd` |
| OSPF on Gi0/1 | `ip ospf bfd` |
| iBGP sessions (3) | timers 3 9 (loopback sessions do not use single-hop BFD) |

IOSv runs in QEMU and can be slow. If BFD sessions flap under load, raise the interval to 1000 ms.

## OSPF

| Setting | Value |
|---|---|
| Process | 1 |
| Area | 0 (one per site, independent) |
| Router ID | Loopback0 address |
| Interfaces | Loopback0 (passive), Gi0/1 (point-to-point, BFD), Gi0/7 (passive) |
| Not in OSPF | Gi0/0, Gi0/2, Gi0/3 |
| Default route | `default-information originate metric 10 metric-type 1` on router 1, metric 20 on router 2 (B and C learn the default through BGP) |

## BGP

| Router | ASN | Router ID |
|---|---|---|
| A1, A2 | 65001 | 10.255.1.1 / 10.255.1.2 |
| B1, B2 | 65002 | 10.255.2.1 / 10.255.2.2 |
| C1, C2 | 65003 | 10.255.3.1 / 10.255.3.2 |

### iBGP sessions (3)

| Site | Router | Neighbor | Source |
|---|---|---|---|
| A | A1 (10.255.1.1) | A2 (10.255.1.2) | Loopback0, next-hop-self |
| B | B1 (10.255.2.1) | B2 (10.255.2.2) | Loopback0, next-hop-self |
| C | C1 (10.255.3.1) | C2 (10.255.3.2) | Loopback0, next-hop-self |

### eBGP sessions (6)

| Plane | Router | Address | Neighbor | Address | ASNs |
|---|---|---|---|---|---|
| 1 | A1 | 10.0.1.0 | B1 | 10.0.1.1 | 65001 - 65002 |
| 1 | A1 | 10.0.1.2 | C1 | 10.0.1.3 | 65001 - 65003 |
| 1 | B1 | 10.0.1.4 | C1 | 10.0.1.5 | 65002 - 65003 |
| 2 | A2 | 10.0.2.0 | B2 | 10.0.2.1 | 65001 - 65002 |
| 2 | A2 | 10.0.2.2 | C2 | 10.0.2.3 | 65001 - 65003 |
| 2 | B2 | 10.0.2.4 | C2 | 10.0.2.5 | 65002 - 65003 |

### Prefixes each site originates

| Site | Prefixes |
|---|---|
| A | 10.1.0.0/16, 10.255.1.0/24, 10.255.0.0/24 (management), 0.0.0.0/0 (default) |
| B | 10.2.0.0/16, 10.255.2.0/24 |
| C | 10.3.0.0/16, 10.255.3.0/24 |

The /16 aggregates and the loopback /24 blocks are anchored with a static route to Null0 so the `network` statements are valid. The management /24 is a connected route on A1/A2. The default route is a static route to 10.255.0.1 on A1/A2.

### Accept and advertise policy

| Direction | Neighbor | Allowed |
|---|---|---|
| Out | any | Only the site's own prefixes from the table above (prefix-list `PL-OUT-<site>`). No transit |
| In on B and C | from A | 0.0.0.0/0, 10.1.0.0/16, 10.255.1.0/24, 10.255.0.0/24 (`PL-IN-A`) |
| In on A | from B | 10.2.0.0/16, 10.255.2.0/24 (`PL-IN-B`) |
| In on A | from C | 10.3.0.0/16, 10.255.3.0/24 (`PL-IN-C`) |
| In between B and C | from each other | The other site's /16 and loopback /24 only |

### Traffic classes and local-preference

| Class | Prefix-list | Prefixes |
|---|---|---|
| 1: internet and management | `PL-CLASS1` | 0.0.0.0/0, 10.255.0.0/24, 10.255.1.0/24, 10.255.2.0/24, 10.255.3.0/24 |
| 2: site-to-site data | `PL-CLASS2` | 10.1.0.0/16, 10.2.0.0/16, 10.3.0.0/16 |

| Router (plane) | Route-map (inbound, all eBGP neighbors) | Class 1 | Class 2 |
|---|---|---|---|
| A1, B1, C1 (plane 1) | `RM-IN-PLANE1` | local-pref 200 | local-pref 100 |
| A2, B2, C2 (plane 2) | `RM-IN-PLANE2` | local-pref 100 | local-pref 200 |

Both the prefix-list (what is allowed) and the route-map (preference) are applied inbound on every eBGP session.

### Expected paths in normal state

| From | To | Path |
|---|---|---|
| B1 | Internet (default) | B1, A1 |
| B2 | Internet (default) | B2, B1, A1 (over the intra-site link) |
| B1 | Site C aggregate 10.3.0.0/16 | B1, B2, C2 |
| B2 | Site C aggregate 10.3.0.0/16 | B2, C2 |
| B1 | Site C loopbacks 10.255.3.0/24 | B1, C1 |
| Host | Loopback of B1 | Host, A1, B1 |
| A1 | Site B aggregate 10.2.0.0/16 | A1, A2, B2 |

## Verification targets (used by tests)

Normal state:
- 9 BGP sessions Established (3 iBGP, 6 eBGP) and 9 BFD sessions Up
- OSPF neighbor Full between the two routers in each site
- B1, B2, C1, C2 have 0.0.0.0/0 learned from BGP, with local-pref 200 on the router 1 path
- Every router has the other sites' /16 and loopback /24
- The paths in the table above
- HSRP: router 1 Active and router 2 Standby at every site
- Host can SSH to all six loopbacks
- C2 can reach an external address through A

Failover (each reverts when the failure is removed):
- Shut A1: B and C default moves to plane 2, HSRP in A moves to A2, and convergence takes a few seconds
- Shut A1-B1: B's default uses B2 and A2, C is unchanged
- Shut B2-C2: B to C data uses B1-C1
- Shut a router 1 at each site: HSRP VIP moves to router 2

## Change log

- 2026-11-26: initial version
- 2026-11-26: traffic classes and local-preference by plane, HSRP on Gi0/7, BFD
