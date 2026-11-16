# BGP design and addressing

Companion to `topology.md` (node table + link table). This file adds the BGP layer.

## Design summary

- One AS per location, eBGP between locations, iBGP between the two routers inside a location.
- Location B is the "internet edge". In the lab, ISP1/ISP2 are simulated by `ip route 0.0.0.0 0.0.0.0 Null0 220` on B1 and B2, which is then originated into BGP with `network 0.0.0.0`.
- Every other location prefers the default route that comes from B (local-preference 200 inbound on the sessions that lead toward B).
- Each router announces one /24 of its own, hosted on `Loopback1`.

## AS numbers (private range)

| Location | AS | Routers |
|---|---|---|
| A | 65001 | WAN-A1, WAN-A2 |
| B | 65002 | WAN-B1, WAN-B2 (ISP edge) |
| C | 65003 | WAN-C1, WAN-C2 |
| D | 65004 | WAN-D1, WAN-D2 |
| E | 65005 | WAN-E1, WAN-E2 |

## Announced /24 per router

Each is configured on `Loopback1` (`ip address 172.16.N.1 255.255.255.0`) and announced with a `network` statement. Router-id = Loopback0.

| Node | AS | Router-ID (Lo0) | Loopback1 / announced prefix |
|---|---|---|---|
| WAN-A1 | 65001 | 10.1.1.1 | 172.16.1.0/24 |
| WAN-A2 | 65001 | 10.1.1.2 | 172.16.2.0/24 |
| WAN-B1 | 65002 | 10.1.1.3 | 172.16.3.0/24 |
| WAN-B2 | 65002 | 10.1.1.4 | 172.16.4.0/24 |
| WAN-C1 | 65003 | 10.1.1.5 | 172.16.5.0/24 |
| WAN-C2 | 65003 | 10.1.1.6 | 172.16.6.0/24 |
| WAN-D1 | 65004 | 10.1.1.7 | 172.16.7.0/24 |
| WAN-D2 | 65004 | 10.1.1.8 | 172.16.8.0/24 |
| WAN-E1 | 65005 | 10.1.1.9 | 172.16.9.0/24 |
| WAN-E2 | 65005 | 10.1.1.10 | 172.16.10.0/24 |

## iBGP sessions (same AS)

Peered on loopbacks (`update-source Loopback0`, `next-hop-self`). Each pair has a single direct link, so a /32 static route to the peer loopback via the link IP provides reachability (an IGP can replace these later).

| Link # | Local | Remote | Local Lo0 | Remote Lo0 | Static route on local router |
|---|---|---|---|---|---|
| 1 | WAN-A1 | WAN-A2 | 10.1.1.1 | 10.1.1.2 | `ip route 10.1.1.2 255.255.255.255 10.0.0.2` |
| 1 | WAN-A2 | WAN-A1 | 10.1.1.2 | 10.1.1.1 | `ip route 10.1.1.1 255.255.255.255 10.0.0.1` |
| 5 | WAN-B1 | WAN-B2 | 10.1.1.3 | 10.1.1.4 | `ip route 10.1.1.4 255.255.255.255 10.0.0.18` |
| 5 | WAN-B2 | WAN-B1 | 10.1.1.4 | 10.1.1.3 | `ip route 10.1.1.3 255.255.255.255 10.0.0.17` |
| 9 | WAN-C1 | WAN-C2 | 10.1.1.5 | 10.1.1.6 | `ip route 10.1.1.6 255.255.255.255 10.0.0.34` |
| 9 | WAN-C2 | WAN-C1 | 10.1.1.6 | 10.1.1.5 | `ip route 10.1.1.5 255.255.255.255 10.0.0.33` |
| 7 | WAN-D1 | WAN-D2 | 10.1.1.7 | 10.1.1.8 | `ip route 10.1.1.8 255.255.255.255 10.0.0.26` |
| 7 | WAN-D2 | WAN-D1 | 10.1.1.8 | 10.1.1.7 | `ip route 10.1.1.7 255.255.255.255 10.0.0.25` |
| 14 | WAN-E1 | WAN-E2 | 10.1.1.9 | 10.1.1.10 | `ip route 10.1.1.10 255.255.255.255 10.0.0.53` |
| 14 | WAN-E2 | WAN-E1 | 10.1.1.10 | 10.1.1.9 | `ip route 10.1.1.9 255.255.255.255 10.0.0.54` |

## eBGP sessions (between locations)

Peered on the directly connected /30 link IPs (no update-source, no multihop).
"From B" = this session carries the default route from the main site, so inbound local-pref 200 applies.

| Link # | Router 1 (AS) | IP 1 | Router 2 (AS) | IP 2 | From B? |
|---|---|---|---|---|---|
| 2 | WAN-A1 (65001) | 10.0.0.5 | WAN-B1 (65002) | 10.0.0.6 | yes (A1 side) |
| 4 | WAN-A2 (65001) | 10.0.0.13 | WAN-B2 (65002) | 10.0.0.14 | yes (A2 side) |
| 8 | WAN-D2 (65004) | 10.0.0.29 | WAN-B1 (65002) | 10.0.0.30 | yes (D2 side) |
| 10 | WAN-C2 (65003) | 10.0.0.37 | WAN-B1 (65002) | 10.0.0.38 | yes (C2 side) |
| 12 | WAN-E1 (65005) | 10.0.0.45 | WAN-B2 (65002) | 10.0.0.46 | yes (E1 side) |
| 15 | WAN-E2 (65005) | 10.0.0.57 | WAN-B1 (65002) | 10.0.0.58 | yes (E2 side) |
| 3 | WAN-A1 (65001) | 10.0.0.9 | WAN-C1 (65003) | 10.0.0.10 | no (backup path) |
| 6 | WAN-A2 (65001) | 10.0.0.21 | WAN-D1 (65004) | 10.0.0.22 | no (backup path) |
| 11 | WAN-C1 (65003) | 10.0.0.41 | WAN-E1 (65005) | 10.0.0.42 | no (backup path) |
| 13 | WAN-C1 (65003) | 10.0.0.49 | WAN-E2 (65005) | 10.0.0.50 | no (backup path) |

Routers without a direct link to B (C1, D1) learn the default over iBGP from their location partner (local-pref 200 is carried inside the AS) and as a longer-path backup over eBGP from a neighbouring location.

## Default route and local-preference policy

On WAN-B1 and WAN-B2 (simulated ISP default):

```
ip route 0.0.0.0 0.0.0.0 Null0 220
router bgp 65002
 network 0.0.0.0
```

On every non-B router, inbound route-map on the sessions marked "From B":

```
route-map FROM-B-DEFAULT permit 10
 set local-preference 200
!
router bgp <AS>
 neighbor <B-router-link-IP> route-map FROM-B-DEFAULT in
```

All other sessions keep the default local-preference of 100, so the path via B wins and the other locations act as backup.

Note: local-preference is not carried across eBGP. It decides the exit choice inside each AS (for example A1 vs A2), and the iBGP partner sees it.

## Template for one router (WAN-A1)

```
router bgp 65001
 bgp router-id 10.1.1.1
 bgp log-neighbor-changes
 network 172.16.1.0 mask 255.255.255.0
 ! iBGP
 neighbor 10.1.1.2 remote-as 65001
 neighbor 10.1.1.2 update-source Loopback0
 neighbor 10.1.1.2 next-hop-self
 ! eBGP
 neighbor 10.0.0.6 remote-as 65002
 neighbor 10.0.0.6 route-map FROM-B-DEFAULT in
 neighbor 10.0.0.10 remote-as 65003
!
ip route 10.1.1.2 255.255.255.255 10.0.0.2
```

## Verification

- `show ip bgp summary` : all sessions Established.
- `show ip bgp 0.0.0.0` on A1: best path via 10.0.0.6, local-pref 200.
- `show ip route 0.0.0.0` on every non-B router: BGP default present.
- Shut the A1-B1 link: A1 should fail over to the default via A2 (iBGP) or via C1.

## Interface note

Management (10.255.0.x) is on Gi0/7, so Gi0/0 to Gi0/4 are data interfaces exactly as listed in the link table. Update the text in `topology.md` accordingly: the node table header should read "Mgmt IP (Gi0/7)" and the link table note should say data interfaces use Gi0/0 to Gi0/4.
