# Network CI/CD Lab: 3-Site WAN (GNS3)

A network automation portfolio project: a 3-site WAN simulated in GNS3, built and changed only through a Git-driven CI/CD pipeline.

## Topology

- 3 sites (A, B, C), each its own AS (65001, 65002, 65003)
- 2 WAN routers per site (Cisco IOSv): A1/A2, B1/B2, C1/C2
- Links (9 total):
  - Plane 1: A1-B1, A1-C1, B1-C1
  - Plane 2: A2-B2, A2-C2, B2-C2
  - Intra-site: A1-A2, B1-B2, C1-C2
- Routing: eBGP between sites, iBGP between the two routers in each site, OSPF (area 0) behind each site
- Site A is the default route to the internet: A1/A2 connect to GNS3 Cloud1 and announce 0.0.0.0/0 to B and C
- Later: Arista spine/leaf fabric behind each site

## Toolchain

| Purpose | Tool |
|---|---|
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
├── docs/            # topology, addressing plan, lab sizing, decisions
├── inventory/       # Ansible inventory (static, then NetBox dynamic)
├── playbooks/
├── roles/
├── templates/       # Jinja2 config templates
├── tests/           # pyATS and Batfish tests
├── ci/              # Jenkinsfile and pipeline scripts
└── configs/         # config backups
```

## Roadmap

1. Foundations: Git, repo, platform choice, sizing
2. Build the topology in GNS3, with OSPF, iBGP, eBGP and the default route
3. NetBox as source of truth
4. Ansible: templates, dynamic inventory, Vault, roles, backups
5. Testing: linting, pyATS, Batfish
6. CI/CD pipeline with Jenkins
7. Arista spine/leaf fabric

## Git workflow

- `main` is protected: no direct commits
- Work on a branch, open a pull request, review the pipeline result, merge
- Pipeline deploys to the lab only on merge to `main`
