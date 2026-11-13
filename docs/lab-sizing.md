# Lab sizing

Date: 2026-11-13
Goal: measure the real cost of a few IOSv nodes and extrapolate to the full 10-node WAN topology (A1, A2, B1, B2, C1, C2, D1, D2, E1, E2).

## Host

| Item | Value |
|---|---|
| Machine | Lenovo ThinkCentre M80q |
| CPU threads (`nproc`) | 16 |
| RAM total | 31276 MB |
| Swap | 8191 MB (never used during the test) |
| Platform | GNS3 on Linux, QEMU with KVM |

## Node configuration (from the QEMU command line)

- IOSv, `-m 512M`, `-smp cpus=1`, `-enable-kvm`
- 8 e1000 NICs per node
- Two qcow2 disks per node

## Method

1. Take a baseline with `free -m`, `nproc` and `uptime`.
2. Start nodes one at a time. After each start, wait about a minute, then run `free -m`, `top -bn1` and `ps -eo pid,rss,pcpu,args --sort=-rss | grep qemu`.
3. Compare "used" memory between steps and compute RAM per node.

Note: A1 was already running when the baseline was taken (its QEMU process is older than the others). So the baseline already includes one node, and the test added A2, B1, B2 and E1. Five nodes were running at the end.

## Measurements

| Step | Time | Nodes running | Started | RAM used (MB) | Delta (MB) | Available (MB) | CPU idle (%) | Load avg (1 min) |
|---|---|---|---|---|---|---|---|---|
| Baseline | 16:44 | 1 | A1 (already running) | 3969 | n/a | 27307 | not captured | 0.34 |
| 1 | 16:45 | 2 | A2 | 4284 | +315 | 26992 | 97.2 | 0.53 |
| 2 | 16:46 | 3 | B1 | 4650 | +366 | 26625 | 93.4 | 0.70 |
| 3 | 16:47 | 4 | B2 | 4988 | +338 | 26287 | 97.1 | 0.95 |
| 4 | 16:49 | 5 | E1 | 5310 | +322 | 25966 | 91.3 | 0.73 |

Resident memory (RSS) per QEMU process, from `ps`:

| Node | RSS (MB) |
|---|---|
| A1 | ~337 |
| A2 | ~387 |
| B1 | ~388 |
| B2 | ~387 |
| E1 | ~388 |

## Results

- RAM per node, from the change in used memory: about **335 MB** (average of +315, +366, +338, +322).
- RAM per node, from RSS (conservative): about **387 MB**.
- CPU: a booting IOSv uses roughly 60-80% of one core for the first 1-2 minutes, then falls to about 10% or less. Overall CPU stayed at 91% idle or better, and the load average never went above 1.
- No swap used at any point.

## Extrapolation to 10 nodes

| Item | Estimate |
|---|---|
| Lab only, from the used-memory delta (10 x 335 MB) | ~3.4 GB |
| Lab only, from RSS (10 x 387 MB) | ~3.9 GB |
| Lab only, with a 15% margin on the RSS figure | ~4.5 GB |
| Host total at 10 nodes (baseline without nodes ~3.6 GB + lab) | ~7-7.5 GB |
| Free RAM left on a 31 GB host | ~23 GB |

Initial estimate was 5-6 GB for 10 nodes. The measured figure is lower: about 3.4-3.9 GB for the lab itself, so the estimate was conservative.

CPU at 10 nodes: steady state should use well under 2 cores. A cold start of all 10 at once would peak at about 10 cores for 1-2 minutes, which fits in 16 threads, but starting in batches of 3-4 is smoother.

## Conclusion

- The 10-node IOSv WAN fits comfortably on this host, with plenty of headroom for NetBox/Nautobot, Jenkins and Batfish running on the same machine.
- Keep 512 MB per node. IOSv needs it, and the savings from reducing it would be small.
- Start nodes in batches, not all at once.

## Caveats and next check

- Each reading was taken 1-2 minutes after a node started, not at steady state. IOSv memory grows slightly over time.
- The nodes had no routing protocols or full configuration yet. Memory use will rise a little once OSPF/BGP and the full config are running.
- Repeat the measurement with all 10 nodes up and configured, and update the table.
