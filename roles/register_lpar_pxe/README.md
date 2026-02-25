# Rolle: register_lpar_pxe

Registriert eine LPAR für PXE-Installation: MAC-Adresse von der HMC holen, TFTP-Verzeichnis anlegen, Kickstart-Datei erzeugen und DHCP (ISC oder KEA DHCP4) konfigurieren.

## Abhängigkeiten

- Ansible Collection **ibm.power_hmc**
- Inventory mit Gruppe `kickstart_servers` (oder Variable `pxe_register_kickstart_server`)

## Pflichtvariablen

- `pxe_register_hmc_host` – HMC-Host
- `pxe_register_hmc_password` – HMC-Passwort
- `pxe_register_managed_system` – Managed System (z. B. power91)
- `pxe_register_lpar_name` – LPAR-Name
- `pxe_register_network_name` – Virtuelles Netz (z. B. VLAN1-ETHERNET0)
- `pxe_register_host_ip` – IP der LPAR
- `pxe_register_hostname` – FQDN der LPAR
- `pxe_register_host_gw` – Gateway
- `pxe_register_host_netmask` – Netmask
- `pxe_register_host_subnet` – Subnetz
- `pxe_register_dns_ip` – DNS-Server
- `pxe_register_dhcp_backend` – `isc` oder `kea4`

## DHCP-Backends

### ISC DHCP (dhcpd)

- Task-Datei: `tasks/setup_dhcp_isc.yml`
- Fügt einen `blockinfile`-Block in `/etc/dhcp/dhcpd.conf` ein und startet `dhcpd` neu.

### KEA DHCP4

- Task-Datei: `tasks/setup_dhcp_kea4.yml`
- Fügt ein JSON-Reservation-Snippet in `pxe_register_kea_reservations_file` ein (Default: `/etc/kea/kea-dhcp4-reservations-manual.conf`).
- Format wie gewünscht: `hostname`, `hw-address`, `ip-address`, `next-server`, `boot-file-name`, `option-data` (host-name, domain-name, tftp-server-name, boot-file-name).
- Hinweis: Die Datei wird per `blockinfile` mit Markern ergänzt. Wenn Kea eine reine JSON-Array-Datei erwartet, die Einträge ggf. manuell in ein `reservations`-Array übernehmen oder die Haupt-Config entsprechend anpassen.

## Beispiel

```yaml
- hosts: localhost
  connection: local
  roles:
    - role: register_lpar_pxe
      pxe_register_hmc_host: "10.32.104.241"
      pxe_register_hmc_password: "{{ hmc_pass }}"
      pxe_register_managed_system: power91
      pxe_register_lpar_name: mkoch02
      pxe_register_network_name: VLAN1-ETHERNET0
      pxe_register_host_ip: 10.32.98.241
      pxe_register_hostname: mkoch02.coe.muc.redhat.com
      pxe_register_host_gw: 10.32.111.254
      pxe_register_host_netmask: 255.255.252.0
      pxe_register_host_subnet: 10.32.96.0
      pxe_register_dns_ip: 10.32.96.1
      pxe_register_dhcp_backend: kea4
      pxe_register_domain_name: coe.muc.redhat.com
```
