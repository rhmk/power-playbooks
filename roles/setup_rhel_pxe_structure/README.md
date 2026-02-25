# Rolle: setup_rhel_pxe_structure

Erstellt aus einem RHEL-ISO die Struktur auf Webserver und TFTP-Server: Repo-Verzeichnis (per rsync vom gemounteten ISO), TFTP-Basis mit GRUB2 für ppc64le, Kernel und Initrd. Keine LPAR-spezifischen Schritte.

**Voraussetzung:** Läuft auf dem Kickstart-Server (z. B. `hosts: kickstart_servers`), Architektur ppc64le.

## Variablen (Auswahl)

- `setup_rhel_pxe_structure_iso_path` – Pfad zum RHEL-ISO (ppc64le)
- `setup_rhel_pxe_structure_rhel_version` – z. B. "9.6"
- `setup_rhel_pxe_structure_kickstart_base_dir`, `setup_rhel_pxe_structure_tftp_root`, `setup_rhel_pxe_structure_repo_dir` – Verzeichnisse
- `setup_rhel_pxe_structure_require_iso` – Bei true schlagen Tasks fehl, wenn das ISO fehlt
- `setup_rhel_pxe_structure_grub_generic` – Bei true wird eine generische `grub.cfg` unter TFTP angelegt

## Beispiel

```yaml
- hosts: kickstart_servers
  become: true
  roles:
    - role: setup_rhel_pxe_structure
      setup_rhel_pxe_structure_iso_path: "/root/rhel-9.6-ppc64le-dvd.iso"
      setup_rhel_pxe_structure_rhel_version: "9.6"
```

Danach die Rolle `register_lpar_pxe` pro LPAR ausführen (MAC, TFTP pro LPAR, Kickstart, DHCP).
