# Network CI/CD Lab: 3-Site WAN (GNS3)

A network automation portfolio project: a 3-site WAN simulated in GNS3, built and changed only through a Git-driven CI/CD pipeline.

## Status

Phase 2 (build the topology) is in progress: links are cabled in GNS3, the addressing plan is written and the bootstrap configs are generated. See the roadmap below.

## Topology

- 3 sites (A, B, C), each its own AS (65001, 65002, 65003)
- 2 WAN routers per site (Cisco IOSv): A1/A2, B1/B2, C1/C2
- Links (9 total):
  - Plane 1: A1-B1, A1-C1, B1-C1
  - Plane 2: A2-B2, A2-C2, B2-C2
  - Intra-site: A1-A2, B1-B2, C1-C2
- Routing: eBGP between sites, iBGP between the two routers in each site, OSPF (area 0) behind each site
- Site A is the default route to the internet: A1/A2 connect to GNS3 Cloud1 (host TAP interface `tun-gns3`, 10.255.0.0/24) and announce 0.0.0.0/0 to B and C
- B and C are managed in-band over their loopbacks
- Later: Arista spine/leaf fabric behind each site

Full details: [docs/topology.md](docs/topology.md) and [docs/addressing.md](docs/addressing.md).

## Toolchain

| Purpose | Tool |
|---|---|
| Lab platform | GNS3 with Cisco IOSv |
| Source of truth | NetBox |
| Configuration and deployment | Ansible (Jinja2, Vault) |
| Pre-deploy analysis | Batfish |
| Post-deploy tests | pyATS |
| Linting | yamllint, ansible-lint, pre-commit |
| CI/CD | Jenkins |

## Repository layout

```
.
├── README.md
├── docs/            # topology, addressing plan, platform decision, lab sizing
├── configs/
│   └── bootstrap/   # first-boot configs for A1..C2 (generated), later config backups
├── scripts/         # host setup (tun-gns3, routing, NAT) and the bootstrap config generator
├── inventory/       # Ansible inventory (static, then NetBox dynamic)
├── playbooks/
├── roles/
├── templates/       # Jinja2 config templates
├── tests/           # pyATS and Batfish tests
└── ci/              # Jenkinsfile and pipeline scripts
```

## Documentation

| File | Content |
|---|---|
| [docs/platform-decision.md](docs/platform-decision.md) | Why GNS3, IOSv image, management access |
| [docs/topology.md](docs/topology.md) | Devices, interface convention, links, routing design |
| [docs/addressing.md](docs/addressing.md) | Address blocks, per-router addresses, OSPF/BGP sessions and policy |
| docs/lab-sizing.md | Planned: RAM and CPU measurements |

## Getting started

1. Host: create the `tun-gns3` TAP interface, lab routes and NAT (see `scripts/` and [docs/platform-decision.md](docs/platform-decision.md)).
2. GNS3: build the 6-router topology and cable it as in [docs/topology.md](docs/topology.md).
3. Routers: paste the files from `configs/bootstrap/` stage by stage into each router console (set a real password where `CHANGE_ME` appears, and never commit it).
4. Regenerate the bootstrap files after changing the plan: `python3 scripts/gen_configs.py configs/bootstrap`

## Roadmap

1. Foundations
   - [x] Git, repo, folder layout
   - [x] Platform choice (GNS3)
   - [ ] Lab sizing
2. Build the topology in GNS3, with OSPF, iBGP, eBGP and the default route
   - [x] Links cabled
   - [x] Addressing and routing plan
   - [x] Bootstrap configs generated
   - [ ] Configs applied and verified (OSPF, 9 BGP sessions, default route)
3. [ ] NetBox as source of truth
4. [ ] Ansible: templates, dynamic inventory, Vault, roles, backups
5. [ ] Testing: linting, pyATS, Batfish
6. [ ] CI/CD pipeline with Jenkins
7. [ ] Arista spine/leaf fabric

## Git workflow

- `main` is protected: no direct commits
- Work on a branch, open a pull request, review the pipeline result, merge
- Pipeline deploys to the lab only on merge to `main`
