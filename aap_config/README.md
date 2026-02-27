# AAP Post-Installation Configuration

This directory contains configuration files for setting up AAP Controller resources after installation.

## Files Overview

- `controller_organizations.yml` - Defines organizations
- `controller_teams.yml` - Defines teams within organizations
- `controller_credentials.yml` - Defines credentials for various systems
- `controller_projects.yml` - Defines SCM projects
- `controller_inventories.yml` - Defines inventories, hosts, and groups
- `controller_job_templates.yml` - Defines job templates
- `controller_workflow_job_templates.yml` - Defines workflow job templates
- `ignore_files` - Files to ignore when loading configuration

## Usage

The main playbook `aap_postinstall_config.yaml` will automatically load all `.yml` and `.yaml` files from this directory (except those listed in `ignore_files`) and apply the configuration using the `infra.aap_configuration.dispatch` role.

## Configuration Order

The AAP configuration role will process resources in the following order:
1. Organizations
2. Teams
3. Credentials
4. Projects
5. Inventories (including hosts and groups)
6. Job Templates
7. Workflow Job Templates

## Customization

To customize the configuration:
1. Edit the existing YAML files to match your requirements
2. Add new configuration files following the naming convention `controller_<resource_type>.yml`
3. Update credentials with actual values (use Ansible Vault for sensitive data)
4. Modify project URLs and playbook names to match your repositories

## Security Notes

- Never commit actual credentials to version control
- Use Ansible Vault or external credential management systems
- Review and test configurations in a development environment first
