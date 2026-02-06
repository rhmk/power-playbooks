# Role: create_lpar_lv

Erstellt auf einer VIOS ein Logical Volume, legt die virtuellen SCSI-Adapter (LPAR ↔ VIOS) an und mappt das LV als virtuelles SCSI-Laufwerk an die LPAR. Die Rolle kann in einem Playbook mit `hosts: hmc` ausgeführt werden; die Steuerung erfolgt vom Ansible Control Node aus per SSH zur HMC und zur VIOS.

## Abhängigkeiten

- Ansible Collection **ibm.power_hmc** (z.B. `ansible-galaxy collection install -r requirements.yml`)
- **sshpass** auf dem Control Node (für HMC-/VIOS-SSH mit Passwort)

## Pflichtparameter

| Variable | Beschreibung |
|----------|--------------|
| `create_lpar_lv_lpar_name` | Name der LPAR (wie auf der HMC) |
| `create_lpar_lv_managed_system` | Name des Managed Systems (z.B. `power91`) |
| `create_lpar_lv_volume_name` | Name des Logical Volume auf der VIOS (z.B. `mylpar_runix`) |
| `create_lpar_lv_volume_group` | Volume Group auf der VIOS (z.B. `datavg`) |
| `create_lpar_lv_vios_name` | Name der VIOS-Partition (z.B. `power91-vios`) |
| `create_lpar_lv_hmc_password` | HMC-Passwort (SSH) |
| `create_lpar_lv_vios_password` | VIOS-Passwort (User padmin) |

## Optionale Parameter (mit Default)

| Variable | Default | Beschreibung |
|----------|---------|--------------|
| `create_lpar_lv_hmc_host` | `inventory_hostname` | HMC-Hostname oder IP (wenn Playbook `hosts: hmc` hat, ist das der jeweilige HMC-Host) |
| `create_lpar_lv_hmc_username` | `hmc_user` / `hscroot` | HMC-Benutzer |
| `create_lpar_lv_disk_size_gb` | `50` | Größe des Logical Volume in GB |
| `create_lpar_lv_vios_ip` | – | IP oder Hostname der VIOS (wenn nicht gesetzt wird `create_lpar_lv_vios_name` für SSH verwendet) |
| `create_lpar_lv_vios_user` | `padmin` | VIOS-SSH-Benutzer |
| `create_lpar_lv_vscsi_client_slot` | `3` | Slot-Nummer des virtuellen SCSI-Client-Adapters an der LPAR |
| `create_lpar_lv_vscsi_server_slot` | (PartitionID + 10) | Slot-Nummer des virtuellen SCSI-Server-Adapters an der VIOS |
| `create_lpar_lv_vtd_name` | abgeleitet aus LPAR-Name | VTD-Name für das Mapping (max. 15 Zeichen) |

## Verwendung

Playbook `create_lpar_lv.yml` im Repository-Root:

```bash
ansible-playbook create_lpar_lv.yml -i inventory/hosts.yml \
  -e "create_lpar_lv_lpar_name=mylpar" \
  -e "create_lpar_lv_managed_system=power91" \
  -e "create_lpar_lv_volume_name=mylpar_runix" \
  -e "create_lpar_lv_volume_group=datavg" \
  -e "create_lpar_lv_vios_name=power91-vios" \
  -e "create_lpar_lv_vios_ip=10.32.104.243" \
  -e "create_lpar_lv_disk_size_gb=100" \
  -e "hmc_pass=YOUR_HMC_PASS" \
  -e "create_lpar_lv_hmc_password={{ hmc_pass }}" \
  -e "create_lpar_lv_vios_password=YOUR_VIOS_PASS"
```

Oder Variablen in `group_vars/hmc/` / Vault ablegen und nur Playbook ausführen.

## Hinweise

- **VIOS IP:** Wenn die VIOS nur unter ihrem Partitionsnamen (z.B. `power91-vios`) per DNS erreichbar ist, kann `create_lpar_lv_vios_ip` entfallen. Sonst explizit setzen (z.B. `10.32.104.243`).
- **Slots:** Wenn die LPAR bereits einen vSCSI-Client auf Slot 3 hat, einen anderen freien Slot mit `create_lpar_lv_vscsi_client_slot` wählen (bzw. passenden Server-Slot mit `create_lpar_lv_vscsi_server_slot`).
- **Passwörter:** In Produktion `create_lpar_lv_hmc_password` und `create_lpar_lv_vios_password` per Ansible Vault oder anderem Secret-Management setzen.
