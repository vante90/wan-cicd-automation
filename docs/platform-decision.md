# Platform decision: GNS3

Date: 2026-11-26

## Decision

The lab runs on **GNS3** with Cisco **IOSv** routers.

## Why GNS3

- GUI topology that is easy to screenshot and show in a portfolio demo
- The Cloud node bridges the lab to the host, so NetBox, Batfish, Ansible and Jenkins running locally can reach the devices
- Runs IOSv natively, and Arista images can be added later
- Considered containerlab: lighter and declarative (good for Git), but IOSv support is weaker and the Cloud bridge is less convenient for this design

## IOSv image

- Source: <fill in, for example Cisco CML licence / personal Cisco subscription>
- Licence confirmed: <yes/no>
- Image filename and version: <fill in>
- Image is NOT stored in this repository

## Host

- Host: <fill in model, CPU, RAM>
- Sizing results: see docs/lab-sizing.md

## Management access

- GNS3 Cloud1 is bound to a host TAP interface named `tun-gns3`, created at boot by a systemd service (`tun-gns3.service`)
- The host side of the interface is 10.255.0.1/24 and is the default gateway for A1/A2
- A1 and A2 connect to Cloud1 with their Gi0/0 (management) interfaces through the switch SW-MGMT (A1 10.255.0.11, A2 10.255.0.12)
- The host routes the lab prefixes via A1 and NATs lab traffic to the internet (see `scripts/`)
- A1/A2 advertise 10.255.0.0/24 over BGP, so B and C can reply to the host
- B and C are managed in-band through their loopbacks
- Every router also has a GNS3 console as a fallback if a routing change breaks in-band management
- SSH from the host, local user, RSA 2048 key
- The final addressing is defined in docs/addressing.md
