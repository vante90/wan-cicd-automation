# Source of truth (NetBox)

NetBox holds the lab model: 3 sites, 6 IOSv WAN routers, 9 cables, ASNs,
loopbacks, link/LAN prefixes and the HSRP groups. Ansible reads it as inventory.

## Files
| File | Purpose |
|------|---------|
| scripts/seed_netbox.py | Loads the addressing plan into NetBox (idempotent) |
| scripts/query_netbox.py | Example API queries with pynetbox |
| inventory/netbox.yml | Ansible dynamic inventory (netbox.netbox.nb_inventory) |
| inventory/netbox_inventory.py | Fallback inventory script using pynetbox |

## Usage
    export NETBOX_URL=http://localhost:8000 NETBOX_API=http://localhost:8000
    export NETBOX_TOKEN='nbt_...'      # never commit it
    python scripts/seed_netbox.py
    ansible-inventory --graph

## Notes
- Management: A1/A2 are reached on Gi0/0 (10.255.0.11/.12); B and C through their loopbacks.
- Platform decision: see ../platform-decision.md (NetBox chosen over Nautobot).
