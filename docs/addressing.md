# BGP design and addressing

Companion to `topology.md` (node table + link table). This file adds the BGP layer.

## Design summary

- One AS per location, eBGP between locations, iBGP between the two routers inside a location.
- Location B is the "internet edge". In the lab, ISP1/ISP2 are simulated by `ip route 0.0.0.0 0.0.0.0 Null0 220` on B1 and B2, which is then originated into BGP with `network 0.0.0.0`.
- B1 is the primary exit for every location and B2 is the backup. Non-B routers prefer the default learned from B1 (local-pref 200), then from B2 (150). B1 prefers what it learns from all neighbours at 120 and B2 at 110, so B2 sends traffic through B1 first.
- Inside a location, the router without a direct link to B1 sends the default through its partner (A2 to A1, D1 to D2, C1 to C2, E1 to E2).
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
"From B" = this session receives the default route from the main site. Sessions to B1 get local-pref 200 on the default, sessions to B2 get 150. Other sessions keep 100.

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

Routers without a direct link to B (C1, D1) learn the default over iBGP from their location partner and as a backup over eBGP from a neighbouring location.

## Default route and local-preference policy

Simulated ISP default on WAN-B1 and WAN-B2:

```
ip route 0.0.0.0 0.0.0.0 Null0 220
router bgp 65002
 network 0.0.0.0
```

### Non-B routers: prefer B1, then B2, only for the default

```
ip prefix-list DEFAULT-ONLY seq 5 permit 0.0.0.0/0
route-map FROM-B1 permit 10
 match ip address prefix-list DEFAULT-ONLY
 set local-preference 200
route-map FROM-B1 permit 20
route-map FROM-B2 permit 10
 match ip address prefix-list DEFAULT-ONLY
 set local-preference 150
route-map FROM-B2 permit 20
```

Applied inbound on the eBGP sessions to B1 (A1, C2, D2, E2) and to B2 (A2, E1). The match on the default matters: without it, A would also prefer the path via B toward C, D and E, and those routes would hairpin through B instead of using the direct inter-site links.

Resulting paths for the default:

| Router | Best default | Path |
|---|---|---|
| A1 | eBGP from B1 (LP 200) | A1 > B1 |
| A2 | iBGP from A1 (LP 200) beats eBGP from B2 (150) | A2 > A1 > B1 |
| C2 | eBGP from B1 | C2 > B1 |
| C1 | iBGP from C2 | C1 > C2 > B1 |
| D2 | eBGP from B1 | D2 > B1 |
| D1 | iBGP from D2 | D1 > D2 > B1 |
| E2 | eBGP from B1 | E2 > B1 |
| E1 | iBGP from E2 (LP 200) beats eBGP from B2 (150) | E1 > E2 > B1 |

If B1 or the link to it fails, the B2 path at LP 150 takes over automatically.

### B1 and B2: B1 is primary for traffic toward every location

```
! WAN-B1, on every eBGP neighbour (A1, C2, D2, E2), inbound
route-map FROM-EBGP permit 10
 set local-preference 120
! WAN-B2, on every eBGP neighbour (A2, E1), inbound
route-map FROM-EBGP permit 10
 set local-preference 110
```

B2 learns B1's routes over iBGP with LP 120, which beats its own direct eBGP routes at 110, so B2 sends traffic toward A, C, D and E through B1. If B1 fails, B2 uses its direct sessions. Local-preference never crosses eBGP, so this only controls how AS B sends traffic out.

After changing a route-map, run `clear ip bgp <neighbor> soft in` (or `clear ip bgp * soft in`).

## Verification

- `show ip bgp summary` : all sessions Established.
- `show ip bgp 0.0.0.0` on A1: best path via 10.0.0.6, local-pref 200.
- `show ip route 0.0.0.0` on every non-B router: BGP default present.
- `show ip bgp 0.0.0.0` on A2: best path via 10.1.1.1 (A1), local-pref 200.
- `show ip bgp 172.16.1.0` on B2: best path via 10.1.1.3 (B1), local-pref 120.
- Shut the A1-B1 link: A1 should fail over to the default via A2 (iBGP, local-pref 150 from B2), and A2 should switch to B2 directly.

## Interface note

Management (10.255.0.x) is on Gi0/7, so Gi0/0 to Gi0/4 are data interfaces exactly as listed in the link table. Update the text in `topology.md` accordingly: the node table header should read "Mgmt IP (Gi0/7)" and the link table note should say data interfaces use Gi0/0 to Gi0/4.
