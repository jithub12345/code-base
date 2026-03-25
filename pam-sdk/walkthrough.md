# Delinea Secret Server Integration — Walkthrough

## What Was Built

Two minimal, production-sane Git repositories for retrieving secrets from **Delinea Secret Server (on-prem)** using API token authentication.

---

## 1. Python Client — `delinea-python-client/`

| File | Purpose |
|------|---------|
| [client.py](file:///D:/Code%20Base/delinea-python-client/src/client.py) | ~35 lines — calls REST API, extracts `password` slug |
| [requirements.txt](file:///D:/Code%20Base/delinea-python-client/requirements.txt) | `requests` + `python-dotenv` |
| [.env.example](file:///D:/Code%20Base/delinea-python-client/.env.example) | Template for `TSS_BASE_URL`, `TSS_API_TOKEN`, `SECRET_ID` |
| [README.md](file:///D:/Code%20Base/delinea-python-client/README.md) | Setup and run instructions |

**Design choice**: Used direct `requests` calls instead of `python-tss-sdk` — the SDK adds complexity for what is a single GET request. Keeps the dependency footprint minimal.

**Run**: `pip install -r requirements.txt` → edit `.env` → `python src/client.py`

---

## 2. Ansible Client — `delinea-ansible-client/`

| File | Purpose |
|------|---------|
| [playbook.yml](file:///D:/Code%20Base/delinea-ansible-client/playbook.yml) | 3 tasks: fetch → extract → display |
| [inventory.ini](file:///D:/Code%20Base/delinea-ansible-client/inventory.ini) | Localhost inventory |
| [group_vars/all.yml](file:///D:/Code%20Base/delinea-ansible-client/group_vars/all.yml) | Connection variables |
| [README.md](file:///D:/Code%20Base/delinea-ansible-client/README.md) | Setup, run, and Vault guidance |

**Design choice**: Used built-in `uri` module + Jinja2 `selectattr` filter — zero external dependencies. Includes `tss_validate_certs` toggle for self-signed cert environments.

**Run**: Edit `group_vars/all.yml` → `ansible-playbook -i inventory.ini playbook.yml`

---

## Verification

- ✅ Both repos Git-initialized with clean initial commits
- ✅ `.gitignore` files exclude secrets (`.env`, `.vault_pass`)
- ✅ Code is directly runnable after configuring credentials
- ✅ No placeholders — all code is complete
