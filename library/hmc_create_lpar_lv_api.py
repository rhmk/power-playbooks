#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Ansible module: hmc_create_lpar_lv_api
#
# Same goal as hmc_create_lpar_lv: create LV on VIOS and map to LPAR via vSCSI.
# Uses HMC REST API (https://www.ibm.com/docs/en/power9/0000-REF?topic=POWER9_REF/p9ehl/concepts/ApiOverview.html)
# for session and queries; VIOS commands (mklv, mkvdev, lsmap, cfgdev) still run via viosvrcmd over SSH,
# as they are not exposed as REST operations.
#
# REST: Logon (PUT), ManagedSystem/LogicalPartition/VirtualIOServer search (GET).
# SSH (paramiko): lshwres, lssyscfg, chhwres, chsyscfg, viosvrcmd for the actual changes.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import time
import xml.etree.ElementTree as ET
import urllib.parse

from ansible.module_utils.basic import AnsibleModule

ANSIBLE_METADATA = {"metadata_version": "1.1", "status": ["preview"], "supported_by": "community"}

DOCUMENTATION = r"""
---
module: hmc_create_lpar_lv_api
short_description: Create LV on VIOS and map to LPAR using HMC REST API + SSH
description:
  - Same outcome as hmc_create_lpar_lv: creates logical volume on VIOS and maps it to the LPAR via vSCSI.
  - Uses HMC REST API (port 12443) for session and for reading ManagedSystem, LogicalPartition, VirtualIOServer.
  - Uses SSH (paramiko) for change operations (lshwres, chhwres, chsyscfg, viosvrcmd) as these are not
    exposed as REST operations in the public API.
  - Requires requests and paramiko on the controller.
options: same as hmc_create_lpar_lv (hmc_host, hmc_auth, managed_system, lpar_name, vios_name, volume_name,
  volume_group, disk_size_gb, vtd_name).
"""

# Suppress SSL warning when connecting to HMC with verify=False
try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:
    pass

# Optional
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    import paramiko
    HAS_PARAMIKO = True
except ImportError:
    HAS_PARAMIKO = False

# HMC REST: port 12443, base path
HMC_REST_PORT = 12443
HMC_NS = "http://www.ibm.com/xmlns/systems/power/firmware/web/mc/2012_10/"
ATOM_NS = "http://www.w3.org/2005/Atom"


def ns(tag, namespace=HMC_NS):
    return "{%s}%s" % (namespace, tag)


def atom_ns(tag):
    return "{%s}%s" % (ATOM_NS, tag)


def _parse_session_from_logon_response(response_text):
    """Extract session token from LogonResponse XML body (some HMC versions return it only in body)."""
    if not response_text or not response_text.strip():
        return None
    try:
        root = ET.fromstring(response_text)
        # Try common element names (local name only; namespace can vary by HMC version)
        # HMC returns <X-API-Session> in LogonResponse (with hyphen)
        for local in ("X-API-Session", "XAPISession", "ApiSession", "SessionID", "SessionId", "Token", "session"):
            for elem in root.iter():
                if elem.tag and "}" in elem.tag:
                    tag_local = elem.tag.split("}", 1)[1]
                else:
                    tag_local = elem.tag or ""
                if tag_local == local and elem.text and elem.text.strip():
                    return elem.text.strip()
    except ET.ParseError:
        pass
    return None


def rest_logon(module, base_url, username, password):
    """Logon to HMC REST API. Returns X-API-Session token (from header or response body)."""
    url = base_url + "/rest/api/web/Logon"
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<LogonRequest xmlns="%s" schemaVersion="V1_0">'
        "<UserID>%s</UserID>"
        "<Password>%s</Password>"
        "</LogonRequest>"
    ) % (HMC_NS, _escape_xml(username), _escape_xml(password))
    headers = {
        "Content-Type": "application/vnd.ibm.powervm.web+xml; type=LogonRequest",
        "Accept": "application/vnd.ibm.powervm.web+xml; type=LogonResponse",
    }
    r = requests.put(url, data=body, headers=headers, verify=False, timeout=30)
    if r.status_code != 200:
        module.fail_json(
            msg="HMC REST Logon failed: HTTP %s" % r.status_code,
            body=r.text[:500] if r.text else "",
        )
    token = r.headers.get("X-API-Session")
    if not token:
        token = _parse_session_from_logon_response(r.text)
    if not token:
        module.fail_json(
            msg="HMC REST Logon: no X-API-Session in response header or body",
            response_headers=dict(r.headers),
            response_body_preview=(r.text[:500] if r.text else ""),
        )
    return token


def rest_logoff(module, base_url, session_token):
    """Logoff from HMC REST API."""
    url = base_url + "/rest/api/web/Logon"
    headers = {"X-API-Session": session_token}
    try:
        requests.delete(url, headers=headers, verify=False, timeout=10)
    except Exception:
        pass


def _escape_xml(s):
    if not s:
        return ""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def rest_get_feed(module, base_url, session_token, path, accept=None, fail_on_error=True):
    """GET a REST feed and return response text. If fail_on_error=False and status != 200, return None."""
    url = base_url + path
    headers = {"X-API-Session": session_token}
    if accept:
        headers["Accept"] = accept
    r = requests.get(url, headers=headers, verify=False, timeout=30)
    if r.status_code != 200:
        if fail_on_error:
            module.fail_json(
                msg="HMC REST GET failed: %s (HTTP %s)" % (path, r.status_code),
                response=r.text[:500] if r.text else "",
            )
        return None
    return r.text


def rest_search(module, base_url, session_token, resource, query, fail_on_error=True):
    """Search for a resource. query e.g. (SystemName=='power91'). Returns raw feed XML or None."""
    path = "/rest/api/uom/%s/search/%s" % (resource, urllib.parse.quote(query, safe="()'="))
    return rest_get_feed(module, base_url, session_token, path, fail_on_error=fail_on_error)


def parse_feed_entries(xml_text):
    """Parse Atom feed and return list of entry elements."""
    root = ET.fromstring(xml_text)
    entries = root.findall(".//%s" % atom_ns("entry"))
    return entries


def entry_get_content_value(entry, tag_local_name, namespace=HMC_NS):
    """Get first content element and find child with tag_local_name; return its text."""
    content = entry.find(atom_ns("content"))
    if content is None:
        return None
    child = content.find(".//{%s}%s" % (namespace, tag_local_name))
    if child is None:
        return None
    return (child.text or "").strip()


def entry_get_link_href(entry, rel=None):
    """Get href of link element (default first link). Fallback: id element (Atom)."""
    for link in entry.findall(atom_ns("link")):
        if rel is None or link.get("rel") == rel:
            href = link.get("href")
            if href:
                return href
    elem_id = entry.find(atom_ns("id"))
    if elem_id is not None and elem_id.text:
        return elem_id.text.strip()
    return None


def extract_uuid_from_href(href):
    """Extract UUID from REST href (last path segment)."""
    if not href:
        return None
    return href.rstrip("/").split("/")[-1]


def _find_text_in_entry(entry, local_names):
    """Find first element with local tag name in entry (any namespace) and return its text."""
    for elem in entry.iter():
        if elem.tag and "}" in elem.tag:
            local = elem.tag.split("}", 1)[1]
        else:
            local = elem.tag or ""
        if local in local_names and elem.text:
            return elem.text.strip()
    return None


def _find_name_in_entry(entry, lpar_name):
    """Get partition name from entry: check element text and attributes (any namespace)."""
    name_tags = ("PartitionName", "partitionName", "name", "Name")
    for elem in entry.iter():
        if elem.tag and "}" in elem.tag:
            local = elem.tag.split("}", 1)[1]
        else:
            local = elem.tag or ""
        if local in name_tags and elem.text and elem.text.strip():
            if elem.text.strip() == lpar_name:
                return elem.text.strip()
        for attr in ("PartitionName", "partitionName", "name", "Name"):
            if attr in elem.attrib and elem.attrib[attr] == lpar_name:
                return elem.attrib[attr]
    return None


def _entry_get_any_name(entry):
    """Return first non-empty name-like value found in entry (for debug)."""
    for local in ("PartitionName", "partitionName", "name", "Name"):
        val = _find_text_in_entry(entry, (local,))
        if val:
            return val
    for elem in entry.iter():
        for attr in ("PartitionName", "partitionName", "name", "Name"):
            if attr in elem.attrib:
                return elem.attrib[attr]
    return None


def get_managed_system_uuid(module, base_url, session_token, managed_system_name):
    """Find ManagedSystem by name via search. Returns UUID."""
    safe_name = managed_system_name.replace("'", "\\'")
    for query in ["(SystemName=='%s')", "(Name=='%s')"]:
        q = query % safe_name
        xml_text = rest_search(module, base_url, session_token, "ManagedSystem", q, fail_on_error=False)
        if xml_text:
            entries = parse_feed_entries(xml_text)
            if entries:
                href = entry_get_link_href(entries[0])
                if href:
                    return extract_uuid_from_href(href)
    module.fail_json(msg="ManagedSystem not found: %s" % managed_system_name)


def get_lpar_info(module, base_url, session_token, ms_uuid, lpar_name):
    """Get LPAR entry by name from ManagedSystem's LogicalPartition feed. Returns dict with uuid, partition_id."""
    path = "/rest/api/uom/ManagedSystem/%s/LogicalPartition" % ms_uuid
    xml_text = rest_get_feed(module, base_url, session_token, path)
    entries = parse_feed_entries(xml_text)
    for entry in entries:
        name = _find_name_in_entry(entry, lpar_name)
        if not name:
            found_name = _find_text_in_entry(entry, ("PartitionName", "partitionName", "name", "Name"))
            if found_name and found_name == lpar_name:
                name = found_name
        if not name:
            # Case-insensitive fallback: compare any name in entry to lpar_name
            found_name = _entry_get_any_name(entry)
            if found_name and found_name.strip().lower() == lpar_name.strip().lower():
                name = found_name
        if name:
            href = entry_get_link_href(entry)
            uuid = extract_uuid_from_href(href)
            # Numeric partition ID only (do NOT use "id" - that is the resource UUID in REST)
            part_id = _find_text_in_entry(entry, ("PartitionID", "PartitionId", "LparId"))
            return {"uuid": uuid, "partition_id": part_id, "entry": entry}
    # Debug: show what names we did find
    found_names = [_entry_get_any_name(e) for e in entries[:10]]
    module.fail_json(
        msg="LogicalPartition not found: %s" % lpar_name,
        feed_entry_count=len(entries),
        found_partition_names=found_names,
    )


def get_vios_info(module, base_url, session_token, ms_uuid, vios_name):
    """Get Virtual I/O Server entry by name. Returns dict with uuid, lpar_id."""
    path = "/rest/api/uom/ManagedSystem/%s/VirtualIOServer" % ms_uuid
    xml_text = rest_get_feed(module, base_url, session_token, path)
    entries = parse_feed_entries(xml_text)
    for entry in entries:
        name = _find_name_in_entry(entry, vios_name)
        if not name:
            name = _find_text_in_entry(entry, ("PartitionName", "partitionName", "name", "Name"))
        if name == vios_name:
            href = entry_get_link_href(entry)
            uuid = extract_uuid_from_href(href)
            # Numeric VIOS partition ID for chsyscfg (do NOT use "id" - that is the resource UUID)
            lpar_id = _find_text_in_entry(entry, ("PartitionID", "PartitionId", "LparId"))
            return {"uuid": uuid, "lpar_id": lpar_id}
    module.fail_json(msg="VirtualIOServer not found: %s" % vios_name)


def run_ssh_command(module, client, command, check_rc=True):
    """Run command over SSH. command can be string or list of args."""
    if isinstance(command, list):
        command = " ".join(str(c) for c in command)
    stdin, stdout, stderr = client.exec_command(command)
    rc = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if check_rc and rc != 0:
        module.fail_json(msg="Command failed", command=command, rc=rc, stdout=out, stderr=err)
    return rc, out, err


def run_viosvrcmd(module, client, managed_system, vios_name, vios_cmd, check_rc=True):
    """Run VIOS command via viosvrcmd on the HMC over SSH."""
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

    if not HAS_REQUESTS:
        module.fail_json(msg="hmc_create_lpar_lv_api requires requests. Install: pip install requests")
    if not HAS_PARAMIKO:
        module.fail_json(msg="hmc_create_lpar_lv_api requires paramiko. Install: pip install paramiko")

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

    base_url = "https://%s:%s" % (hmc_host, HMC_REST_PORT)
    session_token = None
    changed = False
    profile_name = lpar_slot = vios_slot = vios_id = ""
    result = dict(
        lpar_name=lpar_name,
        vios_name=vios_name,
        volume_name=volume_name,
        volume_group=volume_group,
        vtd_name=vtd_name,
        vhost=None,
        mapping=None,
        api_used=True,
    )
    rollback = []

    try:
        # --- REST: Logon ---
        session_token = rest_logon(module, base_url, hmc_username, hmc_password)

        # --- REST: Get ManagedSystem UUID ---
        ms_uuid = get_managed_system_uuid(module, base_url, session_token, managed_system)

        # --- REST: Get LPAR info (partition ID) and VIOS lpar_id ---
        lpar_info = get_lpar_info(module, base_url, session_token, ms_uuid, lpar_name)
        vios_info = get_vios_info(module, base_url, session_token, ms_uuid, vios_name)
        vios_id = vios_info.get("lpar_id") or ""
        # chsyscfg expects numeric partition ID (e.g. 1, 2), not UUID; if REST gave us a UUID, we fix it via SSH below
        if not vios_id or "-" in str(vios_id):
            vios_id = ""

        # Partition ID hex for later lsmap matching
        try:
            part_id_int = int(lpar_info.get("partition_id") or 0)
        except (ValueError, TypeError):
            part_id_int = 0
        part_id_hex = "0x%08x" % part_id_int

        # --- SSH: Slots, profile name, and all change operations (REST has no equivalent for chhwres/chsyscfg/viosvrcmd) ---
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            hmc_host,
            username=hmc_username,
            password=hmc_password,
            allow_agent=False,
            look_for_keys=False,
            timeout=30,
        )

        try:
            # If REST did not give us numeric VIOS partition ID, get it via CLI (required for chsyscfg)
            if not vios_id:
                _, out, _ = run_ssh_command(module, client, [
                    "lssyscfg", "-r", "lpar", "-m", managed_system,
                    "-F", "lpar_id", "--filter", "lpar_names=%s" % vios_name,
                ])
                vios_id = out.strip()
            _, out, _ = run_ssh_command(module, client, [
                "lshwres", "-r", "virtualio", "--rsubtype", "slot", "--level", "lpar",
                "-m", managed_system, "--filter", "lpar_names=%s" % lpar_name, "-F", "next_avail_virtual_slot",
            ])
            lpar_slot = out.strip()
            _, out, _ = run_ssh_command(module, client, [
                "lshwres", "-r", "virtualio", "--rsubtype", "slot", "--level", "lpar",
                "-m", managed_system, "--filter", "lpar_names=%s" % vios_name, "-F", "next_avail_virtual_slot",
            ])
            vios_slot = out.strip()
            _, out, _ = run_ssh_command(module, client, [
                "lssyscfg", "-r", "prof", "-m", managed_system,
                "--filter", "lpar_names=%s" % lpar_name, "-F", "name",
            ])
            profile_name = out.strip()

            # --- Add vSCSI server (SSH) ---
            rc, out, err = run_ssh_command(module, client, [
                "chhwres", "-r", "virtualio", "--rsubtype", "scsi", "-m", managed_system,
                "-o", "a", "-p", vios_name, "-s", vios_slot,
                "-a", "adapter_type=server,remote_lpar_name=%s,remote_slot_num=%s" % (lpar_name, lpar_slot),
            ], check_rc=False)
            if rc != 0 and "already exists" not in (out + err):
                module.fail_json(msg="chhwres (add vSCSI server) failed: %s" % (out + err), rc=rc, stdout=out, stderr=err)
            if rc == 0:
                changed = True
                rollback.append("server_adapter")

            # --- Add vSCSI client (SSH) ---
            chsyscfg_i = "name=%s,lpar_name=%s,virtual_scsi_adapters+=%s/client/%s/%s/%s/0" % (
                profile_name, lpar_name, lpar_slot, vios_id, vios_name, vios_slot
            )
            rc, out, err = run_ssh_command(module, client, [
                "chsyscfg", "-r", "prof", "-m", managed_system, "--force", "-i", chsyscfg_i,
            ], check_rc=False)
            if rc != 0 and "virtual adapter has been specified" not in (out + err):
                module.fail_json(msg="chsyscfg (add vSCSI client) failed: %s" % (out + err), rc=rc, stdout=out, stderr=err)
            if rc == 0:
                changed = True
                rollback.append("client_adapter")

            time.sleep(5)
            run_viosvrcmd(module, client, managed_system, vios_name, "cfgdev -dev vio0", check_rc=False)

            # --- Create LV (viosvrcmd) ---
            mklv_cmd = "mklv -lv %s %s %dG" % (volume_name, volume_group, disk_size_gb)
            rc, out, err = run_viosvrcmd(module, client, managed_system, vios_name, mklv_cmd, check_rc=False)
            if rc != 0 and "already used" not in (out + err):
                module.fail_json(msg="viosvrcmd mklv failed: %s" % (out + err), rc=rc, stdout=out, stderr=err)
            if rc == 0:
                changed = True
                rollback.append("lv")

            # --- Find vhost (lsmap) ---
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
                    msg="No vhost adapter found for LPAR %s (partition ID %s)" % (lpar_name, part_id_hex),
                    lsmap_output=out,
                )
            result["vhost"] = vhost

            # --- Map LV to vhost (mkvdev) ---
            mkvdev_cmd = "mkvdev -vdev %s -vadapter %s -dev %s" % (volume_name, vhost, vtd_name)
            rc, out, err = run_viosvrcmd(module, client, managed_system, vios_name, mkvdev_cmd, check_rc=False)
            if rc != 0 and "already exists" not in (out + err):
                module.fail_json(msg="viosvrcmd mkvdev failed: %s" % (out + err), rc=rc, stdout=out, stderr=err)
            if rc == 0:
                changed = True
                rollback.append("vtd")

            _, out, _ = run_viosvrcmd(module, client, managed_system, vios_name,
                                      "lsmap -vadapter %s -fmt ':'" % vhost)
            result["mapping"] = out.strip()

        finally:
            client.close()

    except Exception as e:
        if rollback:
            rollback.reverse()
            try:
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                client.connect(hmc_host, username=hmc_username, password=hmc_password,
                               allow_agent=False, look_for_keys=False, timeout=30)
                for step in rollback:
                    try:
                        if step == "vtd":
                            run_viosvrcmd(module, client, managed_system, vios_name, "rmvdev -vtd %s" % vtd_name, check_rc=False)
                        elif step == "lv":
                            run_viosvrcmd(module, client, managed_system, vios_name, "rmlv -f %s" % volume_name, check_rc=False)
                        elif step == "client_adapter" and profile_name and lpar_slot:
                            chsyscfg_rm = "name=%s,lpar_name=%s,virtual_scsi_adapters-=%s/client/%s/%s/%s/0" % (
                                profile_name, lpar_name, lpar_slot, vios_id, vios_name, vios_slot
                            )
                            run_ssh_command(module, client, ["chsyscfg", "-r", "prof", "-m", managed_system, "--force", "-i", chsyscfg_rm], check_rc=False)
                        elif step == "server_adapter" and vios_slot:
                            run_ssh_command(module, client, [
                                "chhwres", "-r", "virtualio", "--rsubtype", "scsi", "-m", managed_system,
                                "-o", "r", "-p", vios_name, "-s", vios_slot,
                            ], check_rc=False)
                    except Exception:
                        pass
                client.close()
            except Exception:
                pass
        module.fail_json(
            msg="hmc_create_lpar_lv_api failed (rollback attempted): %s" % str(e),
            rollback_steps=rollback,
        )
    finally:
        if session_token:
            rest_logoff(module, base_url, session_token)

    module.exit_json(changed=changed, **result)


if __name__ == "__main__":
    main()
