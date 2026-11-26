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
| 10.1.0.0/16 | Site A aggregate (intra-site link now, fabric and servers later) |
| 10.2.0.0/16 | Site B aggregate |
| 10.3.0.0/16 | Site C aggregate |

Rules:
- Point-to-point links use /31 (RFC 3021). The lower-lettered router (or the lower number) gets the even address.
- Loopback numbering is `10.255.<site number>.<router number>/32` (site A = 1, B = 2, C = 3).
- Do not summarize 10.255.0.0/24 into a wider 10.255.0.0/16, it would cover the loopback blocks.

## Host and management

| Device | Interface | Address |
|---|---|---|
| Host (Linux) | tun-gns3 | 10.255.0.1/24 (default gateway for A1/A2) |
| A1 | Gi0/0 | 10.255.0.11/24 |
| A2 | Gi0/0 | 10.255.0.12/24 |

Host routes towards the lab, via A1 (10.255.0.11): 10.1.0.0/16, 10.2.0.0/16, 10.3.0.0/16, 10.255.1.0/24, 10.255.2.0/24, 10.255.3.0/24.

## Router addresses

| Router | Loopback0 | Gi0/1 (intra-site) | Gi0/2 | Gi0/3 |
|---|---|---|---|---|
| A1 | 10.255.1.1/32 | 10.1.0.0/31 (to A2) | 10.0.1.0/31 (to B1) | 10.0.1.2/31 (to C1) |
| A2 | 10.255.1.2/32 | 10.1.0.1/31 (to A1) | 10.0.2.0/31 (to B2) | 10.0.2.2/31 (to C2) |
| B1 | 10.255.2.1/32 | 10.2.0.0/31 (to B2) | 10.0.1.1/31 (to A1) | 10.0.1.4/31 (to C1) |
| B2 | 10.255.2.2/32 | 10.2.0.1/31 (to B1) | 10.0.2.1/31 (to A2) | 10.0.2.4/31 (to C2) |
| C1 | 10.255.3.1/32 | 10.3.0.0/31 (to C2) | 10.0.1.3/31 (to A1) | 10.0.1.5/31 (to B1) |
| C2 | 10.255.3.2/32 | 10.3.0.1/31 (to C1) | 10.0.2.3/31 (to A2) | 10.0.2.5/31 (to B2) |

## OSPF

| Setting | Value |
|---|---|
| Process | 1 |
| Area | 0 (one per site, independent) |
| Router ID | Loopback0 address |
| Interfaces | Loopback0 (passive), Gi0/1 (point-to-point) |
| Not in OSPF | Gi0/0, Gi0/2, Gi0/3 |
| Default route | B and C: `default-information originate` (learned via BGP). A: same, for the fabric later |

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

### Policy

| Direction | Neighbor | Allowed |
|---|---|---|
| Out | any | Only the site's own prefixes from the table above (prefix-list). No transit |
| In on B and C | from A | 0.0.0.0/0, 10.1.0.0/16, 10.255.1.0/24, 10.255.0.0/24 |
| In on A | from B | 10.2.0.0/16, 10.255.2.0/24 |
| In on A | from C | 10.3.0.0/16, 10.255.3.0/24 |
| In between B and C | from each other | The other site's /16 and loopback /24 only |

Naming: `PL-OUT-<site>` (own prefixes), `PL-IN-<neighbor site>` (accepted prefixes), `RM-OUT-<site>` and `RM-IN-<neighbor site>` for the route-maps. These will be generated from NetBox data later.

## Verification targets (used by tests)

- 9 BGP sessions Established (3 iBGP, 6 eBGP)
- OSPF neighbor up between the two routers in each site
- B1, B2, C1, C2 have 0.0.0.0/0 learned from BGP
- Every router has the other sites' /16 and loopback /24
- Host can SSH to all six loopbacks
- C2 can reach an external address through A

## Change log

- 2026-11-26: initial version
