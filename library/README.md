# Ansible Library (lokale Module)

## hmc_create_lpar_lv

Erstellt auf der VIOS ein Logical Volume, legt vSCSI-Adapter (LPAR ↔ VIOS) an und mappt das LV als virtuelles SCSI-Laufwerk an die LPAR. Alle Befehle laufen über die HMC (SSH); es wird keine direkte VIOS-Verbindung benötigt.

**Entspricht** der Rolle `create_lpar_lv`, als ein einziges Ansible-Modul.

### Voraussetzung

- **paramiko** auf dem Controller: `pip install paramiko`

### Verwendung

Das Modul läuft auf dem Controller (z. B. `hosts: localhost`, `connection: local`) und baut selbst die SSH-Verbindung zur HMC auf.

```yaml
- name: Create LV on VIOS and map to LPAR via HMC
  hmc_create_lpar_lv:
    hmc_host: "10.32.104.241"
    hmc_auth:
      username: "{{ hmc_username }}"
      password: "{{ hmc_password }}"
    managed_system: power91
    lpar_name: mylpar
    vios_name: power91-vios
    volume_name: mylpar_boot
    volume_group: datavg
    disk_size_gb: 100
  register: lv_result
```

Übergabe wie bei der **ibm.power_hmc**-Collection (`hmc_auth` mit `username` und `password`).

### Parameter (Pflicht)

| Parameter         | Beschreibung                    |
|------------------|----------------------------------|
| hmc_host         | HMC-Hostname oder IP             |
| hmc_auth         | Dict mit `username` und `password` (HMC SSH)   |
| managed_system   | Managed System (z. B. power91)   |
| lpar_name        | Name der LPAR                   |
| vios_name        | Name der VIOS-Partition         |
| volume_name      | Name des Logical Volume         |
| volume_group     | Volume Group auf der VIOS       |

### Optionale Parameter

| Parameter      | Default   | Beschreibung                    |
|----------------|-----------|----------------------------------|
| disk_size_gb   | 50        | LV-Größe in GB                   |
| vtd_name       | (abgeleitet) | VTD-Name (max. 15 Zeichen)   |

### Rückgabe

- `vhost`: vhost-Adaptername auf der VIOS  
- `mapping`: Ausgabe von `lsmap -vadapter <vhost>`  
- `changed`: true, wenn etwas geändert wurde  

Bei Fehler wird ein Rollback durchgeführt (VTD entfernen, LV entfernen, vSCSI-Adapter entfernen).

---

## hmc_create_lpar_lv_api

Gleiches Ziel wie `hmc_create_lpar_lv`, nutzt aber die **HMC REST API** (Port 12443) für Session und Abfragen.

- **REST:** Logon (PUT), ManagedSystem-Suche, LogicalPartition- und VirtualIOServer-Feeds (UUID, PartitionID).
- **SSH (paramiko):** Alle Änderungen (lshwres, chhwres, chsyscfg, viosvrcmd), da die öffentliche REST-API keine Jobs für vSCSI-Anlage oder VIOS-Befehle (mklv, mkvdev) bereitstellt.

Referenz: [IBM HMC REST APIs – ApiOverview](https://www.ibm.com/docs/en/power9/0000-REF?topic=POWER9_REF/p9ehl/concepts/ApiOverview.html).

### Voraussetzung

- **requests** und **paramiko** auf dem Controller: `pip install requests paramiko`

### Verwendung

Parameter und Rückgabe wie bei `hmc_create_lpar_lv`; Aufruf mit Modulnamen `hmc_create_lpar_lv_api`:

```yaml
- name: Create LV via HMC REST API + SSH
  hmc_create_lpar_lv_api:
    hmc_host: "{{ hmc_host }}"
    hmc_auth:
      username: "{{ hmc_username }}"
      password: "{{ hmc_password }}"
    managed_system: "{{ managed_system }}"
    lpar_name: "{{ lpar_name }}"
    vios_name: "{{ vios_name }}"
    volume_name: "{{ volume_name }}"
    volume_group: "{{ volume_group }}"
    disk_size_gb: "{{ lpar_disk }}"
  register: lv_result
```

Rückgabe enthält zusätzlich `api_used: true`.
