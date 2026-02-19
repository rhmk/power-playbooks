#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Ansible module: hmc_create_lpar_lv
#
# Creates a logical volume on VIOS and maps it to an LPAR via virtual SCSI.
# All operations use the HMC (SSH + lshwres, lssyscfg, chhwres, chsyscfg, viosvrcmd).
# Equivalent to the create_lpar_lv role in one module.
#
# Requirements: paramiko (pip install paramiko) on the controller.

from __future__ import absolute_import, division, print_function

ANSIBLE_METADATA = {
    "metadata_version": "1.1",
    "status": ["preview"],
    "supported_by": "community",
}

DOCUMENTATION = r"""
---
module: hmc_create_lpar_lv
short_description: Create logical volume on VIOS and map to LPAR via virtual SCSI (HMC)
description:
  - Creates a logical volume on the VIOS, adds vSCSI server/client adapters,
    and maps the LV to the LPAR. All commands run via SSH to the HMC
    (lshwres, lssyscfg, chhwres, chsyscfg, viosvrcmd). No direct VIOS access.
  - Equivalent to the role create_lpar_lv in a single module.
  - Requires paramiko on the controller (pip install paramiko).
options:
  hmc_host:
    description: HMC hostname or IP.
    required: true
    type: str
  hmc_auth:
    description: HMC credentials (analog to ibm.power_hmc collection).
    required: true
    type: dict
    suboptions:
      username:
        description: HMC SSH username.
        type: str
        required: true
      password:
        description: HMC SSH password.
        type: str
        required: true
  managed_system:
    description: Managed system name (e.g. power91).
    required: true
    type: str
  lpar_name:
    description: LPAR name.
    required: true
    type: str
  vios_name:
    description: VIOS partition name (e.g. power91-vios).
    required: true
    type: str
  volume_name:
    description: Logical volume name on VIOS.
    required: true
    type: str
  volume_group:
    description: Volume group on VIOS.
    required: true
    type: str
  disk_size_gb:
    description: Size of the logical volume in GB.
    default: 50
    type: int
  vtd_name:
    description: VTD name for the mapping (max 15 chars). Default derived from lpar_name.
    type: str
"""

EXAMPLES = r"""
- name: Create LV on VIOS and map to LPAR via HMC
  hmc_create_lpar_lv:
    hmc_host: "{{ inventory_hostname }}"
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
"""

RETURN = r"""
lpar_name:
  description: LPAR name.
  type: str
  returned: always
vios_name:
  description: VIOS partition name.
  type: str
  returned: always
volume_name:
  description: Logical volume name.
  type: str
  returned: always
volume_group:
  description: Volume group.
  type: str
  returned: always
vtd_name:
  description: VTD name used for the mapping.
  type: str
  returned: always
vhost:
  description: vhost adapter name on VIOS.
  type: str
  returned: on success
mapping:
  description: Final lsmap output for the vhost.
  type: str
  returned: on success
"""

__metaclass__ = type

import time

from ansible.module_utils.basic import AnsibleModule

# Optional: paramiko for SSH. Prefer paramiko; fallback to subprocess + ssh/sshpass.
try:
    import paramiko
    HAS_PARAMIKO = True
except ImportError:
    HAS_PARAMIKO = False


def run_ssh_command(module, client, command, check_rc=True):
    """Run a command over SSH and return (rc, stdout, stderr)."""
    if isinstance(command, list):
        command = " ".join(str(c) for c in command)
    stdin, stdout, stderr = client.exec_command(command)
    rc = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if check_rc and rc != 0:
        module.fail_json(
            msg="Command failed",
            command=command,
            rc=rc,
            stdout=out,
            stderr=err,
        )
    return rc, out, err


def run_hmc_command(module, client, args, check_rc=True):
    """Run HMC CLI command. args is a list (e.g. ['lshwres', '-r', 'virtualio', ...])."""
    cmd = " ".join(str(a) for a in args)
    return run_ssh_command(module, client, cmd, check_rc=check_rc)


def run_viosvrcmd(module, client, managed_system, vios_name, vios_cmd, check_rc=True):
    """Run a VIOS command via viosvrcmd on the HMC."""
    # Quote -c for shell so the whole VIOS command is one argument
    safe_cmd = vios_cmd.replace("'", "'\"'\"'")
    command = "viosvrcmd -m %s -p %s -c '%s'" % (managed_system, vios_name, safe_cmd)
    return run_ssh_command(module, client, command, check_rc=check_rc)


def main():
    module_args = dict(
        hmc_host=dict(type="str", required=True),
        hmc_auth=dict(
            type="dict",
            required=True,
            options=dict(
                username=dict(type="str", required=True),
                password=dict(type="str", required=True, no_log=True),
            ),
        ),
        managed_system=dict(type="str", required=True),
        lpar_name=dict(type="str", required=True),
        vios_name=dict(type="str", required=True),
        volume_name=dict(type="str", required=True),
        volume_group=dict(type="str", required=True),
        disk_size_gb=dict(type="int", default=50),
        vtd_name=dict(type="str", default=None),
    )
    module = AnsibleModule(argument_spec=module_args, supports_check_mode=False)

    if not HAS_PARAMIKO:
        module.fail_json(
            msg="paramiko is required for hmc_create_lpar_lv. Install it: pip install paramiko"
        )

    hmc_host = module.params["hmc_host"]
    hmc_auth = module.params["hmc_auth"]
    hmc_username = hmc_auth["username"]
    hmc_password = hmc_auth["password"]
    managed_system = module.params["managed_system"]
    lpar_name = module.params["lpar_name"]
    vios_name = module.params["vios_name"]
    volume_name = module.params["volume_name"]
    volume_group = module.params["volume_group"]
    disk_size_gb = module.params["disk_size_gb"]
    vtd_name = module.params["vtd_name"] or (lpar_name[:11] if len(lpar_name) > 11 else lpar_name) + "_vtd"
    if len(vtd_name) > 15:
        vtd_name = vtd_name[:15]

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            hmc_host,
            username=hmc_username,
            password=hmc_password,
            allow_agent=False,
            look_for_keys=False,
            timeout=30,
        )
    except Exception as e:
        module.fail_json(msg="Failed to connect to HMC %s: %s" % (hmc_host, str(e)))

    rollback = []
    changed = False
    result = dict(
        lpar_name=lpar_name,
        vios_name=vios_name,
        volume_name=volume_name,
        volume_group=volume_group,
        vtd_name=vtd_name,
        vhost=None,
        mapping=None,
    )

    try:
        # --- Slots ---
        _, out, _ = run_hmc_command(module, client, [
            "lshwres", "-r", "virtualio", "--rsubtype", "slot", "--level", "lpar",
            "-m", managed_system,
            "--filter", "lpar_names=%s" % lpar_name,
            "-F", "next_avail_virtual_slot",
        ])
        lpar_slot = out.strip()
        _, out, _ = run_hmc_command(module, client, [
            "lshwres", "-r", "virtualio", "--rsubtype", "slot", "--level", "lpar",
            "-m", managed_system,
            "--filter", "lpar_names=%s" % vios_name,
            "-F", "next_avail_virtual_slot",
        ])
        vios_slot = out.strip()

        # --- VIOS partition ID and LPAR profile name ---
        _, out, _ = run_hmc_command(module, client, [
            "lssyscfg", "-r", "lpar", "-m", managed_system,
            "-F", "lpar_id", "--filter", "lpar_names=%s" % vios_name,
        ])
        vios_id = out.strip()
        _, out, _ = run_hmc_command(module, client, [
            "lssyscfg", "-r", "prof", "-m", managed_system,
            "--filter", "lpar_names=%s" % lpar_name, "-F", "name",
        ])
        profile_name = out.strip()

        # --- Add vSCSI server adapter on VIOS ---
        rc, out, err = run_hmc_command(module, client, [
            "chhwres", "-r", "virtualio", "--rsubtype", "scsi", "-m", managed_system,
            "-o", "a", "-p", vios_name, "-s", vios_slot,
            "-a", "adapter_type=server,remote_lpar_name=%s,remote_slot_num=%s" % (lpar_name, lpar_slot),
        ], check_rc=False)
        if rc != 0 and "already exists" not in (out + err):
            module.fail_json(msg="chhwres (add vSCSI server) failed: %s" % (out + err), rc=rc, stdout=out, stderr=err)
        if rc == 0:
            changed = True
            rollback.append("server_adapter")

        # --- Add vSCSI client adapter to LPAR profile ---
        chsyscfg_i = "name=%s,lpar_name=%s,virtual_scsi_adapters+=%s/client/%s/%s/%s/0" % (
            profile_name, lpar_name, lpar_slot, vios_id, vios_name, vios_slot
        )
        rc, out, err = run_hmc_command(module, client, [
            "chsyscfg", "-r", "prof", "-m", managed_system, "--force", "-i", chsyscfg_i,
        ], check_rc=False)
        if rc != 0 and "virtual adapter has been specified" not in (out + err):
            module.fail_json(msg="chsyscfg (add vSCSI client) failed: %s" % (out + err), rc=rc, stdout=out, stderr=err)
        if rc == 0:
            changed = True
            rollback.append("client_adapter")

        time.sleep(5)

        # --- VIOS: cfgdev (recognize new adapter) ---
        run_viosvrcmd(module, client, managed_system, vios_name, "cfgdev -dev vio0", check_rc=False)

        # --- Partition ID (hex) for this LPAR (for lsmap matching) ---
        _, out, _ = run_hmc_command(module, client, [
            "lssyscfg", "-r", "lpar", "-m", managed_system,
            "-F", "lpar_id", "--filter", "lpar_names=%s" % lpar_name,
        ])
        partition_id = out.strip()
        try:
            part_id_hex = "0x%08x" % int(partition_id)
        except ValueError:
            part_id_hex = "0x%08x" % 0

        # --- Create LV on VIOS ---
        mklv_cmd = "mklv -lv %s %s %dG" % (volume_name, volume_group, disk_size_gb)
        rc, out, err = run_viosvrcmd(module, client, managed_system, vios_name, mklv_cmd, check_rc=False)
        if rc != 0 and "already used" not in (out + err):
            module.fail_json(msg="viosvrcmd mklv failed: %s" % (out + err), rc=rc, stdout=out, stderr=err)
        if rc == 0:
            changed = True
            rollback.append("lv")

        # --- Find vhost for this LPAR (lsmap -all, match partition ID) ---
        _, out, _ = run_viosvrcmd(module, client, managed_system, vios_name, "lsmap -all -fmt ':'")
        vhost = None
        for line in out.splitlines():
            if part_id_hex.lower() in line.lower():
                parts = line.split(":")
                if parts:
                    vhost = parts[0].strip()
                    break
        if not vhost:
            module.fail_json(
                msg="No vhost adapter found for LPAR %s (partition ID %s). Check vSCSI to VIOS %s."
                % (lpar_name, part_id_hex, vios_name),
                lsmap_output=out,
            )

        result["vhost"] = vhost

        # --- Map LV to vhost (VTD) ---
        mkvdev_cmd = "mkvdev -vdev %s -vadapter %s -dev %s" % (volume_name, vhost, vtd_name)
        rc, out, err = run_viosvrcmd(module, client, managed_system, vios_name, mkvdev_cmd, check_rc=False)
        if rc != 0 and "already exists" not in (out + err):
            module.fail_json(msg="viosvrcmd mkvdev failed: %s" % (out + err), rc=rc, stdout=out, stderr=err)
        if rc == 0:
            changed = True
            rollback.append("vtd")

        # --- Verify ---
        _, out, _ = run_viosvrcmd(module, client, managed_system, vios_name,
                                  "lsmap -vadapter %s -fmt ':'" % vhost)
        result["mapping"] = out.strip()

    except Exception as e:
        # Rollback in reverse order
        rollback.reverse()
        for step in rollback:
            try:
                if step == "vtd":
                    run_viosvrcmd(module, client, managed_system, vios_name,
                                  "rmvdev -vtd %s" % vtd_name, check_rc=False)
                elif step == "lv":
                    run_viosvrcmd(module, client, managed_system, vios_name,
                                  "rmlv -f %s" % volume_name, check_rc=False)
                elif step == "client_adapter":
                    chsyscfg_rm = "name=%s,lpar_name=%s,virtual_scsi_adapters-=%s/client/%s/%s/%s/0" % (
                        profile_name, lpar_name, lpar_slot, vios_id, vios_name, vios_slot
                    )
                    run_hmc_command(module, client, [
                        "chsyscfg", "-r", "prof", "-m", managed_system, "--force", "-i", chsyscfg_rm,
                    ], check_rc=False)
                elif step == "server_adapter":
                    run_hmc_command(module, client, [
                        "chhwres", "-r", "virtualio", "--rsubtype", "scsi", "-m", managed_system,
                        "-o", "r", "-p", vios_name, "-s", vios_slot,
                    ], check_rc=False)
            except Exception:
                pass
        module.fail_json(
            msg="hmc_create_lpar_lv failed (rollback performed): %s" % str(e),
            rollback_steps=rollback,
        )
    finally:
        client.close()

    module.exit_json(changed=changed, **result)


if __name__ == "__main__":
    main()
