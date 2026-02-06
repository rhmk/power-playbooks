# Power Playbooks

Ansible playbooks for managing IBM Power Systems via HMC (Hardware Management Console).

## Features

- **Multiple managed systems per HMC** - Define a list of systems each HMC manages
- **Individual LPAR control** - Power on/off specific LPARs by name
- **Self-signed certificate support** - Works with HMCs using self-signed SSL certificates

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

Use `create_linux_lpar.yml` to create a new Linux LPAR configured for RHEL installation from a DVD ISO on VIOS.

### Basic Usage

```bash
ansible-playbook create_linux_lpar.yml \
  -i inventory/hosts.yml \
  -e "lpar_name=rhel-server01" \
  -e "hmc_pass=YOUR_PASSWORD"
```

### With Custom Resources

```bash
ansible-playbook create_linux_lpar.yml \
  -i inventory/hosts.yml \
  -e "lpar_name=rhel-server01" \
  -e "lpar_cpu=4" \
  -e "lpar_mem=8192" \
  -e "lpar_disk=100" \
  -e "hmc_pass=YOUR_PASSWORD"
```

### Full Configuration Example

```bash
ansible-playbook create_linux_lpar.yml \
  -i inventory/hosts.yml \
  -e "lpar_name=rhel-server01" \
  -e "lpar_cpu=4" \
  -e "lpar_cpu_min=2" \
  -e "lpar_cpu_max=8" \
  -e "lpar_mem=16384" \
  -e "lpar_disk=200" \
  -e "vios_partition=vios1" \
  -e "vnet_name=ETHERNET0" \
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
| `vios_partition` | `vios1` | VIOS partition name |
| `vnet_name` | `ETHERNET0` | Virtual network name |
| `vnet_vlan` | `0` | VLAN ID (0 = untagged) |

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
├── power_control.yml       # System-level power control
├── lpar_control.yml        # Individual LPAR power control
├── create_linux_lpar.yml   # Create Linux LPAR for RHEL installation
├── upload_media.yml        # Upload ISO/DVD images to HMC repository
├── inventory/
│   ├── hosts.yml           # Static HMC inventory
│   └── lpars.power_hmc.yml # Dynamic LPAR inventory
├── requirements.yml        # Ansible Galaxy dependencies
└── README.md
```

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
