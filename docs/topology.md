# Topology

## Overview

- 3 sites (A, B, C), each its own AS: A = 65001, B = 65002, C = 65003
- 2 Cisco IOSv WAN routers per site: A1/A2, B1/B2, C1/C2
- 9 router-to-router links, arranged as two parallel planes plus one intra-site link per site
- eBGP between sites, iBGP between the two routers in each site, OSPF (area 0) inside each site
- Site A is the exit to the internet and originates the default route (0.0.0.0/0) towards B and C
- Later: an Arista spine/leaf fabric behind each site

## Logical diagram

```
   Site A (AS 65001)       Site B (AS 65002)       Site C (AS 65003)
   +----------------+      +----------------+      +----------------+
   |  A1 ====== A2  |      |  B1 ====== B2  |      |  C1 ====== C2  |
   +----------------+      +----------------+      +----------------+

   Plane 1:  A1 --- B1    A1 --- C1    B1 --- C1
   Plane 2:  A2 --- B2    A2 --- C2    B2 --- C2

   Management and internet exit (site A only):

   Host (Linux) tun-gns3 10.255.0.1 --- Cloud1 --- SW-MGMT --+-- A1 Gi0/0
                                                             +-- A2 Gi0/0
```

## Devices

| Device | Site | AS | Role | Platform |
|---|---|---|---|---|
| A1 | A | 65001 | WAN router, internet exit | IOSv |
| A2 | A | 65001 | WAN router, internet exit | IOSv |
| B1 | B | 65002 | WAN router | IOSv |
| B2 | B | 65002 | WAN router | IOSv |
| C1 | C | 65003 | WAN router | IOSv |
| C2 | C | 65003 | WAN router | IOSv |

Naming: `<site letter><router number>` (A1, B2, ...). The router number is also the plane number for inter-site links: routers numbered 1 only connect to other routers numbered 1 in other sites, routers numbered 2 to other 2s.

## Interface convention

| Interface | Use |
|---|---|
| Gi0/0 | A1/A2: management segment and Cloud1 uplink. B1/B2/C1/C2: unused, shut down |
| Gi0/1 | Intra-site link to the other router in the same site |
| Gi0/2 | Inter-site link to the first other site in alphabetical order |
| Gi0/3 | Inter-site link to the second other site in alphabetical order |
| Gi0/4 | Reserved: downlink to the Arista fabric (later) |
| Gi0/5 - Gi0/7 | Spare |
| Loopback0 | Router ID, iBGP/OSPF source, in-band management address |

## Links

| ID | Type | End 1 | End 2 | Subnet |
|---|---|---|---|---|
| L1 | Intra-site | A1 Gi0/1 | A2 Gi0/1 | 10.1.0.0/31 |
| L2 | Intra-site | B1 Gi0/1 | B2 Gi0/1 | 10.2.0.0/31 |
| L3 | Intra-site | C1 Gi0/1 | C2 Gi0/1 | 10.3.0.0/31 |
| L4 | Plane 1 | A1 Gi0/2 | B1 Gi0/2 | 10.0.1.0/31 |
| L5 | Plane 1 | A1 Gi0/3 | C1 Gi0/2 | 10.0.1.2/31 |
| L6 | Plane 1 | B1 Gi0/3 | C1 Gi0/3 | 10.0.1.4/31 |
| L7 | Plane 2 | A2 Gi0/2 | B2 Gi0/2 | 10.0.2.0/31 |
| L8 | Plane 2 | A2 Gi0/3 | C2 Gi0/2 | 10.0.2.2/31 |
| L9 | Plane 2 | B2 Gi0/3 | C2 Gi0/3 | 10.0.2.4/31 |

GNS3-only connections (not router links):

| Connection | End 1 | End 2 |
|---|---|---|
| M1 | Cloud1 (tun-gns3) | SW-MGMT |
| M2 | SW-MGMT | A1 Gi0/0 |
| M3 | SW-MGMT | A2 Gi0/0 |

## Routing design

- **OSPF:** process 1, area 0, one per site. Covers Loopback0 and the intra-site link only. Inter-site links are not in OSPF. Loopback0 is passive and the intra-site link is point-to-point.
- **iBGP:** one session per site between the loopbacks of the two routers, with next-hop-self.
- **eBGP:** one session per inter-site link (6 sessions), on the link addresses.
- **Default route:** A1 and A2 each have a static default route to the host (10.255.0.1) and advertise 0.0.0.0/0 to B and C. B and C originate it into their own OSPF.
- **No transit:** each site advertises only its own prefixes, so no site carries traffic between the other two.
- **Failure behaviour:** if one inter-site link fails, the router on the other plane in the same site still has a path through iBGP and the intra-site link. If a whole plane fails, the other plane carries everything.

Detailed addresses, sessions and policies: see `docs/addressing.md`.

## Management

- Host interface `tun-gns3` (10.255.0.1/24) is bound to Cloud1 in GNS3
- A1 and A2 reach it through Gi0/0 via SW-MGMT
- B and C are managed in-band over their loopbacks, using the routes the host has towards A1
- GNS3 console remains the fallback if a routing change cuts in-band access

## Change log

- 2026-11-26: initial version
