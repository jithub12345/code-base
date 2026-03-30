# Delinea Break-Glass Ansible Automation

This repository provides an idempotent, production-ready Ansible automation suite for onboarding Break-Glass accounts into CyberArk/Delinea Secret Server (on-prem) via REST APIs.

## Requirements

- Secret Server version 10.9 or newer
- Valid Application Account configured for API access
- An orchestrated Active Directory synchronized into Delinea natively
- Ansible installed locally

## Quickstart

1. Configure Authentication inside `.env` or `group_vars/all/vault.yml`.
   ```bash
   cp .env.example .env
   # Add your Secret Server URL and Credentials. Use client credentials fundamentally. 
   # Password grant can act as a fallback.
   ```

2. Configure Variables. See `examples/vars_example.yml` for reference on defining secret parameters.

3. Run the Playbook:
   ```bash
   ansible-playbook playbooks/onboard_breakglass.yml -i localhost, -e "@examples/vars_example.yml"
   ```

## Roles

* `auth`: Generates an OAuth Token using Client Credentials, gracefully falling-back to Password grants for testing if Client parameters are omitted.
* `ad_lookup`: Identifies natively synchronized AD Groups inside Delinea's API framework (`type: AD`).
* `folder`: Checks for matching folders; performs folder creation safely by verifying parent folder IDs.
* `secret`: Provisions template structures gracefully, verifying names inside generated folders for CRUD actions (`present`/`absent`).
* `permissions`: Resolves mapping configurations natively targeting Delinea Role IDs parameterizing RBAC to specific folder and secret indices.

## Configuration Defaults

Refer to `group_vars/all/vars.yml` for globally structured defaults (`site_id`, `parent_folder_id`, etc.) and configurable Role definitions mapping to your organization's schema.
