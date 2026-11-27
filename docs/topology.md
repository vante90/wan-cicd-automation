# Topology

## Overview

- 3 sites (A, B, C), each its own AS: A = 65001, B = 65002, C = 65003
- 2 Cisco IOSv WAN routers per site: A1/A2, B1/B2, C1/C2
- 9 router-to-router links, arranged as two parallel planes plus one intra-site link per site
- eBGP between sites, iBGP between the two routers in each site, OSPF (area 0) inside each site
- Site A is the exit to the internet and originates the default route (0.0.0.0/0) towards B and C
- Plane 1 is primary for internet and management traffic, plane 2 is primary for site-to-site traffic, and each plane backs up the other
- Two LANs per site, each with its own HSRP gateway:
  - **LAN-INET** (Gi0/6, 10.N.2.0/24): HSRP active on router 1, for hosts that mainly talk to the internet
  - **LAN-S2S** (Gi0/7, 10.N.1.0/24): HSRP active on router 2, for hosts that mainly talk to other sites
- BFD gives fast failure detection
- Later: an Arista spine/leaf fabric behind each site

## Logical diagram

```
   Site A (AS 65001)       Site B (AS 65002)       Site C (AS 65003)
   +----------------+      +----------------+      +----------------+
   |  A1 ====== A2  |      |  B1 ====== B2  |      |  C1 ====== C2  |
   +----------------+      +----------------+      +----------------+

   Plane 1 (primary for internet and management):
             A1 --- B1    A1 --- C1    B1 --- C1
   Plane 2 (primary for site-to-site data):
             A2 --- B2    A2 --- C2    B2 --- C2

   Two LANs per site (example: site B)

   B1 Gi0/6 ---+--- B2 Gi0/6               B1 Gi0/7 ---+--- B2 Gi0/7
            SW-B-INET                                SW-B-S2S
     LAN-INET 10.2.2.0/24                     LAN-S2S 10.2.1.0/24
     VIP 10.2.2.1, active B1                  VIP 10.2.1.1, active B2
     (internet and management)                (site-to-site data)

   Management and internet exit (site A only):

   Host (Linux) tun-gns3 10.255.0.1 --- Cloud1 --- SW-MGMT --+-- A1 Gi0/0
                                                             +-- A2 Gi0/0
```

## Devices

| Device | Site | AS | Plane | Role | Platform |
|---|---|---|---|---|---|
| A1 | A | 65001 | 1 | WAN router, internet exit, HSRP active for LAN-INET, standby for LAN-S2S | IOSv |
| A2 | A | 65001 | 2 | WAN router, internet exit (backup), HSRP active for LAN-S2S, standby for LAN-INET | IOSv |
| B1 | B | 65002 | 1 | WAN router, HSRP active for LAN-INET, standby for LAN-S2S | IOSv |
| B2 | B | 65002 | 2 | WAN router, HSRP active for LAN-S2S, standby for LAN-INET | IOSv |
| C1 | C | 65003 | 1 | WAN router, HSRP active for LAN-INET, standby for LAN-S2S | IOSv |
| C2 | C | 65003 | 2 | WAN router, HSRP active for LAN-S2S, standby for LAN-INET | IOSv |

Naming: `<site letter><router number>` (A1, B2, ...). The router number is also the plane number for inter-site links: routers numbered 1 only connect to other routers numbered 1 in other sites, routers numbered 2 to other 2s.

## Interface convention

| Interface | Use |
|---|---|
| Gi0/0 | A1/A2: management segment and Cloud1 uplink. B1/B2/C1/C2: unused, shut down |
| Gi0/1 | Intra-site link to the other router in the same site |
| Gi0/2 | Inter-site link to the first other site in alphabetical order |
| Gi0/3 | Inter-site link to the second other site in alphabetical order |
| Gi0/4 - Gi0/5 | Spare |
| Gi0/6 | LAN-INET (internet LAN), HSRP group 2 |
| Gi0/7 | LAN-S2S (site-to-site LAN), HSRP group 1. The Arista fabric attaches to a site LAN later |
| Loopback0 | Router ID, iBGP/OSPF source, in-band management address |

IOSv needs 8 network adapters in the GNS3 template for Gi0/7.

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

| Switch | Connected to | Purpose |
|---|---|---|
| SW-MGMT | Cloud1 (tun-gns3), A1 Gi0/0, A2 Gi0/0 | Management and internet exit |
| SW-A-INET | A1 Gi0/6, A2 Gi0/6 | LAN-INET of site A |
| SW-A-S2S | A1 Gi0/7, A2 Gi0/7 | LAN-S2S of site A |
| SW-B-INET | B1 Gi0/6, B2 Gi0/6 | LAN-INET of site B |
| SW-B-S2S | B1 Gi0/7, B2 Gi0/7 | LAN-S2S of site B |
| SW-C-INET | C1 Gi0/6, C2 Gi0/6 | LAN-INET of site C |
| SW-C-S2S | C1 Gi0/7, C2 Gi0/7 | LAN-S2S of site C |

All switches are plain GNS3 Ethernet switches. Use two separate switches per site, so the two LANs never share a broadcast domain. End hosts connect to the switch of the LAN they should use.

## Routing design

- **OSPF:** process 1, area 0, one per site. Covers Loopback0, the intra-site link and both site LANs (passive). Inter-site links are not in OSPF.
- **iBGP:** one session per site between the loopbacks of the two routers, with next-hop-self.
- **eBGP:** one session per inter-site link (6 sessions), on the link addresses.
- **Default route:** A1 and A2 each have a static default route to the host (10.255.0.1) and advertise 0.0.0.0/0 to B and C. B and C originate it into their own OSPF (router 1 with metric 10, router 2 with metric 20).
- **No transit:** each site advertises only its own prefixes, so no site carries traffic between the other two.

### Traffic classes

| Class | Prefixes | Primary | Backup |
|---|---|---|---|
| 1: internet and management | 0.0.0.0/0, loopback blocks (10.255.1-3.0/24), management (10.255.0.0/24), internet LANs (10.1.2.0/24, 10.2.2.0/24, 10.3.2.0/24) | Plane 1 | Plane 2 |
| 2: site-to-site data | Site aggregates (10.1.0.0/16, 10.2.0.0/16, 10.3.0.0/16), which cover the site-to-site LANs (10.N.1.0/24) | Plane 2 | Plane 1 |

The preference is set with BGP local-preference on inbound routes (200 for the primary plane, 100 for the backup plane). iBGP carries it between the two routers of a site, so a router on the non-preferred plane sends traffic over the intra-site link to its sibling.

The internet LANs are advertised as their own /24 routes, so they follow class 1 in every site. That keeps the return path of internet traffic on plane 1 as well.

### Which LAN to use for a host

| Host mostly talks to | Attach to | First hop | Path |
|---|---|---|---|
| The internet (or needs management access) | LAN-INET | Router 1 (VIP .1 on 10.N.2.0/24) | Router 1, plane 1, A1 |
| Other sites | LAN-S2S | Router 2 (VIP .1 on 10.N.1.0/24) | Router 2, plane 2, other site's router 2 |

The LAN is a preference, not a restriction. A host on LAN-S2S can still reach the internet (router 2, then router 1 over the intra-site link, then A1), and a host on LAN-INET can still reach other sites (router 1, then router 2). That costs one extra hop and an asymmetric return path, so place hosts on the LAN that matches their main traffic.

### Failure detection and gateway redundancy

- **BFD:** 500 ms interval, multiplier 3 (about 1.5 s detection) on the intra-site and inter-site links. Used by the eBGP sessions (`fall-over bfd`) and by OSPF on the intra-site link.
- **iBGP:** timers 3/9, since a loopback session cannot use single-hop BFD. OSPF with BFD removes the loopback route quickly when the intra-site link fails.
- **HSRP:** version 2, hello 1 s, hold 3 s, preempt. Group 1 on Gi0/7 (LAN-S2S): router 2 priority 110, router 1 priority 100. Group 2 on Gi0/6 (LAN-INET): router 1 priority 110, router 2 priority 100. Both VIPs end in `.1`. Different group numbers keep the virtual MAC addresses distinct.

### Failure behaviour

| Failure | Result |
|---|---|
| A1 down | Default and management move to plane 2 via A2. Site-to-site data is unaffected. The LAN-INET gateway in A moves to A2 |
| A1-B1 link down | B's internet and management traffic goes B1, B2, A2. C is unaffected |
| B2-C2 link down | B to C data moves to plane 1 (B1-C1) |
| Whole plane 2 down | All site-to-site data moves to plane 1 |
| Whole plane 1 down | Internet and management move to plane 2 |
| Router 1 down at a site | The LAN-INET VIP moves to router 2. LAN-S2S is unaffected. Internet traffic leaves on plane 2 |
| Router 2 down at a site | The LAN-S2S VIP moves to router 1. Site-to-site data leaves on plane 1 |
| Intra-site link down | OSPF and iBGP between the siblings drop. Each router keeps working over its own plane, using the backup routes it learned itself |

HSRP does not track the uplinks. If a router keeps running but loses all its WAN links, it stays the active gateway and forwards over the intra-site link to its sibling. Interface tracking can be added later if needed.

Open item: the host reaches the lab through static routes via A1 (10.255.0.11). If A1 dies, in-band access from the host is lost until the host routes are changed. Options: HSRP on Gi0/0 with a virtual address for the host, or a second route via A2.

Detailed addresses, sessions and policies: see `docs/addressing.md`.

## Management

- Host interface `tun-gns3` (10.255.0.1/24) is bound to Cloud1 in GNS3
- A1 and A2 reach it through Gi0/0 via SW-MGMT
- B and C are managed in-band over their loopbacks, using the routes the host has towards A1
- GNS3 console remains the fallback if a routing change cuts in-band access

## Change log

- 2026-11-26: initial version
- 2026-11-26: primary/secondary planes by traffic class, HSRP on Gi0/7, BFD
- 2026-11-27: two LANs per site: LAN-S2S (Gi0/7, HSRP active on router 2) and LAN-INET (Gi0/6, HSRP active on router 1)
