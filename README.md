# Power Playbooks

Ansible playbooks for managing IBM Power Systems via HMC (Hardware Management Console).

## Ziele des Repositories

1. **LPARs anlegen und löschen** – LPAR erstellen (mit oder ohne Netboot), LV auf VIOS, LPAR löschen
2. **LPARs per Netboot installieren** – RHEL-Installation über PXE/Kickstart (TFTP, DHCP, Kickstart-Datei)
3. **Neue RHEL-Versionen auf dem Kickstart-Server ablegen** – ISO einspielen, Repo- und TFTP-Struktur anlegen

## Features

- **Multiple managed systems per HMC** – Liste verwalteter Systeme pro HMC
- **LPAR-Steuerung** – Ein/Aus, Anlegen, Löschen
- **Self-signed certificate support** – HMCs mit selbstsignierten Zertifikaten

## Prerequisites

1. **Ansible** (2.9+)
2. **Python 3** on the control node
3. **sshpass** installed (`brew install hudochenkov/sshpass/sshpass` on macOS)
4. **Network access** to the HMC from the control node
5. **HMC credentials** with appropriate permissions

## Installation

Install the required Ansible collection:

```bash
ansible-galaxy collection install -r requirements.yml
```

## Configuration

### Inventory Setup

Edit `inventory/hosts.yml` to configure your HMC hosts and managed systems:

```yaml
all:
  children:
    hmc:
      hosts:
        10.32.104.241:
          managed_systems_list:
            - "power91"
            - "power92"

        10.32.104.242:
          managed_systems_list:
            - "power93"

      vars:
        hmc_user: "admin"
```

### Credentials

**Option 1: Command line**

```bash
ansible-playbook power_control.yml -e "hmc_pass=YOUR_PASSWORD"
```

**Option 2: Environment variable**

```bash
export HMC_PASSWORD="your_password"
ansible-playbook power_control.yml -e "hmc_pass=$HMC_PASSWORD"
```

**Option 3: Ansible Vault**

```bash
ansible-vault create group_vars/hmc/vault.yml
# Add: hmc_pass: "your_secure_password"
```

## Usage

### Power On All Systems

```bash
ansible-playbook power_control.yml \
  -i inventory/hosts.yml \
  -e "power_state=on" \
  -e "hmc_pass=YOUR_PASSWORD"
```

### Power Off All Systems

```bash
ansible-playbook power_control.yml \
  -i inventory/hosts.yml \
  -e "power_state=off" \
  -e "hmc_pass=YOUR_PASSWORD"
```

### Target a Specific HMC

```bash
ansible-playbook power_control.yml \
  -i inventory/hosts.yml \
  -l 10.32.104.241 \
  -e "power_state=off" \
  -e "hmc_pass=YOUR_PASSWORD"
```

### Override Managed Systems at Runtime

```bash
ansible-playbook power_control.yml \
  -i inventory/hosts.yml \
  -e '{"managed_systems_list": ["power91"]}' \
  -e "power_state=off" \
  -e "hmc_pass=YOUR_PASSWORD"
```

## LPAR Control

Use `lpar_control.yml` to power on/off individual LPARs by name.

### Power On an LPAR

```bash
ansible-playbook lpar_control.yml \
  -i inventory/hosts.yml \
  -e "lpar_name=my_lpar" \
  -e "power_state=on" \
  -e "hmc_pass=YOUR_PASSWORD"
```

### Power Off an LPAR

```bash
ansible-playbook lpar_control.yml \
  -i inventory/hosts.yml \
  -e "lpar_name=my_lpar" \
  -e "power_state=off" \
  -e "hmc_pass=YOUR_PASSWORD"
```

### Specify the Managed System

If you know which system the LPAR is on (faster):

```bash
ansible-playbook lpar_control.yml \
  -i inventory/hosts.yml \
  -e "lpar_name=my_lpar" \
  -e "managed_system=power91" \
  -e "power_state=on" \
  -e "hmc_pass=YOUR_PASSWORD"
```

If you don't specify `managed_system`, the playbook will search all systems defined in `managed_systems_list` to find the LPAR.

## Delete LPAR

Use `lpar_delete.yml` to remove an LPAR (LPAR is shut down first).

```bash
ansible-playbook lpar_delete.yml -i inventory/hosts.yml \
  -e "lpar_name=my_lpar" \
  -e "managed_system=power91" \
  -e "hmc_pass=YOUR_PASSWORD" \
  -e "confirm_delete=yes"
```

Without `confirm_delete=yes` the playbook exits with a reminder to set it.

## Neue RHEL-Version auf Kickstart-Server

Kickstart-Server einmalig einrichten oder neue RHEL-Version hinzufügen:

```bash
ansible-playbook setup_kickstart_server.yml -i inventory/hosts.yml \
  -e "rhel_version=9.6" \
  -e "iso_path=/path/to/rhel-9.6-ppc64le-dvd.iso"
```

Legt ISO/Repo/TFTP-Struktur an (Mount, rsync, GRUB2, Kernel/Initrd), installiert den Standard-TFTP-Server (tftp-server) und httpd und konfiguriert Firewall sowie SELinux.

### Nur GRUB-Konfiguration aktualisieren

Um ausschließlich die generische `grub.cfg` für Power-Network-Boot neu zu installieren (z. B. nach Änderung an `templates/grub_generic.cfg.j2`), das Playbook mit dem Tag `install_grub_generic` ausführen:

```bash
ansible-playbook setup_kickstart_server.yml -i inventory/hosts.yml --tags install_grub_generic
```

Es werden nur die Tasks mit diesem Tag ausgeführt; Voraussetzung ist, dass `grub_generic: true` gesetzt ist (Standard im Playbook).

## Upload Media (ISO/DVD Images)

Use `upload_media.yml` to upload ISO/DVD images to the HMC's VIOS repository. The HMC pulls the file via SFTP or NFS from a remote server.

### Upload via SFTP

The simplest approach is to use your control node as the SFTP server (SSH must be enabled):

```bash
ansible-playbook upload_media.yml \
  -i inventory/hosts.yml \
  -e "iso_file=/home/user/images/AIX_7.3_DVD1.iso" \
  -e "sftp_server=192.168.1.100" \
  -e "sftp_user=myuser" \
  -e "sftp_password=mypassword" \
  -e "hmc_pass=YOUR_PASSWORD"
```

### Upload via NFS

If you have an NFS server with the ISO:

```bash
ansible-playbook upload_media.yml \
  -i inventory/hosts.yml \
  -e "iso_file=/exports/images/AIX_7.3_DVD1.iso" \
  -e "media_type=nfs" \
  -e "nfs_server=192.168.1.50" \
  -e "nfs_mount=/exports/images" \
  -e "hmc_pass=YOUR_PASSWORD"
```

### Custom Repository Directory

By default, images are stored in `uploaded_images` directory. Override with:

```bash
-e "repository_dir=aix_images"
```

### Prerequisites for SFTP Upload from Control Node

1. SSH/SFTP must be enabled on your control node
2. The HMC must have network access to your control node
3. Use your control node's IP address that the HMC can reach

## Create Linux LPAR

Use `lpar_create.yml` to create a new Linux LPAR configured for RHEL installation from a DVD ISO on VIOS.

### Basic Usage

```bash
ansible-playbook lpar_create.yml \
  -i inventory/hosts.yml \
  -e "lpar_name=rhel-server01" \
  -e "hmc_pass=YOUR_PASSWORD"
```

### With Custom Resources

```bash
ansible-playbook lpar_create.yml \
  -i inventory/hosts.yml \
  -e "lpar_name=rhel-server01" \
  -e "lpar_cpu=4" \
  -e "lpar_mem=8192" \
  -e "lpar_disk=100" \
  -e "hmc_pass=YOUR_PASSWORD"
```

### Full Configuration Example

```bash
ansible-playbook lpar_create.yml \
  -i inventory/hosts.yml \
  -e "lpar_name=rhel-server01" \
  -e "lpar_cpu=4" \
  -e "lpar_cpu_min=2" \
  -e "lpar_cpu_max=8" \
  -e "lpar_mem=16384" \
  -e "lpar_disk=200" \
  -e "vios_name=vios1" \
  -e "virtual_network=ETHERNET0" \
  -e "hmc_pass=YOUR_PASSWORD"
```

### LPAR Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `lpar_name` | *(required)* | Name of the new LPAR |
| `lpar_cpu` | `2` | Number of virtual processors |
| `lpar_cpu_min` | `1` | Minimum processors |
| `lpar_cpu_max` | `4` | Maximum processors |
| `lpar_mem` | `4096` | Memory in MB |
| `lpar_mem_min` | `2048` | Minimum memory in MB |
| `lpar_mem_max` | `16384` | Maximum memory in MB |
| `lpar_disk` | `50` | Disk size in GB |
| `vios_name` | *(required)* | VIOS partition name |
| `vios_volume_group` | *(required)* | Volume group on VIOS for LPAR disk |
| `virtual_network` | `VLAN1-ETHERNET0` | Virtual network name |
| `vlan_id` | `1` | VLAN ID (0 = untagged) |

### VIOS Setup for DVD Installation

After creating the LPAR, configure the virtual optical device on VIOS:

```bash
# On VIOS: Find the virtual host adapter
lsmap -all | grep <lpar_name>

# Create virtual optical device
mkvdev -fbo -vadapter vhostX

# Load the RHEL ISO
loadopt -vtd vtoptX -disk /path/to/rhel-dvd.iso

# Verify
lsmap -vadapter vhostX
```

Then power on the LPAR and boot from the virtual optical device.

## Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `power_state` | `on` | Desired power state: `on` or `off` |
| `managed_systems_list` | *(from inventory)* | List of managed system names per HMC |
| `hmc_user` | `hscroot` | HMC username |
| `hmc_pass` | *(empty)* | HMC password (**required**) |

## Dynamic Inventory

Use `inventory/lpars.power_hmc.yml` to automatically discover all LPARs from the HMC.

### Setup

```bash
# Set credentials
export HMC_USER=admin
export HMC_PASS=your_password
```

### Test the Inventory

```bash
ansible-inventory -i inventory/lpars.power_hmc.yml --list --yaml
```

### Use with Playbooks

```bash
ansible-playbook your_playbook.yml -i inventory/lpars.power_hmc.yml
```

### Auto-Generated Groups

The dynamic inventory automatically creates these groups:

| Group | Description |
|-------|-------------|
| `aix_lpars` | All AIX partitions |
| `vios_lpars` | All VIOS partitions |
| `linux_lpars` | All Linux partitions |
| `ibmi_lpars` | All IBM i partitions |
| `running_lpars` | Partitions in running state |
| `not_activated` | Partitions not activated |
| `system_<name>` | LPARs grouped by managed system (e.g., `system_power91`) |

### Requirements for LPAR Discovery

LPARs must have one of the following to appear in the inventory:

1. **RMC IP address** configured (check with `lsrsrc IBM.MCP` on the LPAR)
2. **DNS-resolvable hostname** matching the LPAR name

To enable RMC on AIX/Linux LPARs:
```bash
/usr/sbin/rsct/bin/rmcctrl -A
/usr/sbin/rsct/install/bin/recfgct
```

Or add LPAR names to `/etc/hosts` on your control node.

## Project Structure

```
power-playbooks/
├── power_control.yml           # Managed Systems ein/aus
├── lpar_control.yml            # Einzelne LPAR ein/aus
├── lpar_delete.yml             # LPAR löschen (mit Bestätigung: -e confirm_delete=yes)
├── lpar_create.yml             # LPAR anlegen + VIOS-LV (hmc_create_lpar_lv_api)
├── lpar_create_old.yml         # LPAR anlegen + Rolle create_lpar_lv
├── lpar_netinstall.yml         # LPAR für Netboot: Kea-DHCP, GRUB, Kickstart, lpar_netboot
├── add_lv_to_lpar.yml          # Nur LV auf VIOS anlegen und an LPAR mappen (Rolle create_lpar_lv)
├── setup_kickstart_server.yml  # Kickstart-Server: RHEL-ISO, Repo, TFTP (tftp-server), httpd
├── upload_media.yml            # ISO in HMC/VIOS-Repository hochladen
├── download_rhel_media.yml      # RHEL-DVD-ISO von Red Hat API herunterladen
├── lpar_info.yml               # LPAR-Infos vom HMC abfragen
├── inventory/
│   ├── hosts.yml
│   ├── group_vars/
│   └── lpars.power_hmc.yml
├── roles/
│   └── create_lpar_lv/        # LV auf VIOS anlegen und mappen
├── library/                   # Lokale Module (hmc_create_lpar_lv, hmc_create_lpar_lv_api)
├── templates/                 # Für setup_kickstart_server, lpar_netinstall
├── requirements.yml
└── README.md
```

### Lokale Konfiguration (nicht versionieren)

Die Dateien `my_lpar_cfg.yml` und `lpar_config.yml` sind in `.gitignore` eingetragen und werden **nicht** ins Repository oder auf den Server übernommen. Für Passwörter und lokale LPAR-Variablen verwenden (z. B. `-e @my_lpar_cfg.yml`); sensible Werte mit Ansible Vault schützen.

## Troubleshooting

### SSL Certificate Errors

The playbook automatically disables SSL verification for self-signed certificates via environment variables.

### sshpass Not Found

Install sshpass:
- **macOS**: `brew install hudochenkov/sshpass/sshpass`
- **Ubuntu/Debian**: `apt-get install sshpass`
- **RHEL/CentOS**: `yum install sshpass`

### HSCL0831 Error

This error occurs when trying to power off a system with running LPARs. Use `lpar_control.yml` to shut down individual LPARs first.

## References

- [IBM Power HMC Collection Documentation](https://ibm.github.io/ansible-power-hmc/)
- [power_system module](https://ibm.github.io/ansible-power-hmc/modules/power_system.html)
- [powervm_lpar_instance module](https://ibm.github.io/ansible-power-hmc/modules/powervm_lpar_instance.html)
