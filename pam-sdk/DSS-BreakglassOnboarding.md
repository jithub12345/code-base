# Automating Breakglass Account Onboarding in Delinea Secret Server with Ansible

To automate “break-glass” account provisioning (creating vault entries and permissions) in Delinea Secret Server, we can use its REST API from an Ansible playbook. The high-level workflow is:

1. **Authenticate** – obtain an API token.  
2. **Ensure AD Group Exists** – verify the target AD group is synced in Secret Server.  
3. **Create Host Folder** – use the Secret Server API to add a folder for the host (if not already present).  
4. **Create Secret** – retrieve a secret stub based on a template, populate fields, and POST it.  
5. **Set Folder Permissions** – assign the folder and its secrets to the AD group with the proper roles (e.g. View).  
6. **Error Handling / Idempotency** – at each step check for existing objects and handle failures gracefully (e.g. HTTP status, missing fields).  

Each of these steps is detailed below with example API calls and Ansible approaches, based on the official Delinea documentation【20†L168-L172】【60†L631-L640】.

## 1. Authenticate to Secret Server (Get a Token)  
First, obtain a bearer token using the OAuth endpoint. Secret Server supports token-based auth; e.g. by POSTing to `/SecretServer/oauth2/token` with `grant_type=password`, your service account username and password【6†L23-L31】【20†L168-L172】. For example, in Ansible you could use the `uri` module:

```yaml
- name: Authenticate to Secret Server
  uri:
    url: "https://<SECRET_SERVER_HOST>/SecretServer/oauth2/token"
    method: POST
    body: "grant_type=password&username={{ vault_user }}&password={{ vault_pass }}"
    headers:
      Content-Type: "application/x-www-form-urlencoded"
    return_content: yes
  register: auth_response
```

On success (HTTP 200), the response contains `access_token`. Store this for subsequent API calls (e.g. as `{{ auth_response.json.access_token }}`). The Delinea guide notes: *“make a call to the `oauth2/token` endpoint in the Secret Server REST API”* to retrieve the access token【20†L168-L172】.

## 2. Ensure AD Group Is Synchronized  
Secret Server must be configured with your AD domain and synchronization groups【10†L90-L99】. (This is typically done once in the UI: add your AD domain, then under its Groups tab select which AD groups to sync.) After that, AD groups appear as “synchronized groups” in Secret Server. In the automation, you should verify the required AD group exists in the sync list. The API doesn’t have a dedicated “create AD group” call; instead you would ensure AD integration is enabled and the group is allowed to sync. One can retrieve the list of synced groups via the Directory Services API (or via the UI) and check for the group. If it’s missing, you would either manually add it in Secret Server or use a Directory Service API (not detailed here) to add it. In practice, the playbook should *check* for the group (by name or ID) before proceeding. Once the group is present, you’ll need its internal ID to assign permissions (see Step 5).

## 3. Create Host Folder in Secret Server  
Use the Folder API to create a new folder named after the host (e.g. `<host short name>`). The PowerShell examples show this pattern: GET a **folder stub**, modify it, then POST it to `/api/v1/folders`【60†L631-L640】【60†L643-L652】. For example:

1. **Get a folder stub** (this returns a JSON template):  
   ```
   GET https://<SECRET_SERVER_HOST>/api/v1/folders/stub
   Authorization: Bearer <token>
   ```
2. **Customize the stub** (in Ansible, parse JSON and set fields):  
   - `folderName`: the new folder name (e.g. host short name)【60†L637-L640】.  
   - `folderTypeId`: typically 1 for standard folder.  
   - Set `inheritPermissions = false` and `inheritSecretPolicy = false` (unless you want to inherit).  
   - If a parent folder is configured via the playbook, set `parentFolderId` from the config.  
3. **POST to create**:  
   ```
   POST https://<SECRET_SERVER_HOST>/api/v1/folders
   Authorization: Bearer <token>
   Content-Type: application/json

   { ... modified stub JSON ... }
   ```
   If successful (HTTP 201), the response contains the new folder’s ID【60†L643-L652】.

In Ansible, you could do something like:

```yaml
- name: Get folder stub
  uri:
    url: "https://<SECRET_SERVER_HOST>/api/v1/folders/stub"
    method: GET
    headers:
      Authorization: "Bearer {{ auth_response.json.access_token }}"
    return_content: yes
  register: folder_stub

- name: Create host folder (if not exists)
  uri:
    url: "https://<SECRET_SERVER_HOST>/api/v1/folders"
    method: POST
    headers:
      Authorization: "Bearer {{ auth_response.json.access_token }}"
      Content-Type: "application/json"
    body: >
      {{ folder_stub.json | combine({
           'folderName': host_short_name,
           'folderTypeId': 1,
           'inheritPermissions': false,
           'inheritSecretPolicy': false,
           'parentFolderId': parent_folder_id
         }) | to_json }}
    status_code: 201,409
  register: folder_result
  failed_when: folder_result.status not in [201,409]
```

Here we allow status 409 (Conflict) to indicate “folder already exists” (you’d need to detect existence by name or path beforehand). The key point is the folder POST call as shown in [60]: “`Invoke-RestMethod $api"/folders" -Method POST` … `$folderAddResult = Invoke-RestMethod $api"/folders" ... -Method POST`”【60†L643-L652】.

## 4. Create the Secret (with Template)  
To add the breakglass account credentials, create a new secret under the folder using the desired secret template. Delinea’s API again provides a **secret stub** based on a template ID【51†L172-L180】. Steps:

1. **Get a secret stub** for your template:  
   ```
   GET https://<SECRET_SERVER_HOST>/api/v1/secrets/stub?filter.secretTemplateId=<TEMPLATE_ID>
   Authorization: Bearer <token>
   ```
2. **Populate required fields** in the JSON (name, site, auto-change settings, and each secret field value)【51†L180-L188】. For example, set the `name`, `secretTemplateId`, `AutoChangeEnabled`, `items[*].itemValue` for fields like Username, Password, etc.
3. **POST to create**:  
   ```
   POST https://<SECRET_SERVER_HOST>/api/v1/secrets
   Authorization: Bearer <token>
   Content-Type: application/json

   { ... modified secret stub JSON ... }
   ```
   On success (HTTP 201), this returns the new secret (including its `id`)【51†L210-L218】.

From the docs: “Get Secret stub… modify… then `Invoke-RestMethod $api"/secrets/" -Method Post`”【51†L172-L180】【51†L210-L218】. In Ansible, use a similar pattern with `uri`. For idempotency, you could first search existing secrets by folder and name, skipping creation if found.

Example snippet:

```yaml
- name: Get secret stub for template
  uri:
    url: "https://<SECRET_SERVER_HOST>/api/v1/secrets/stub?filter.secretTemplateId={{ template_id }}"
    method: GET
    headers:
      Authorization: "Bearer {{ auth_response.json.access_token }}"
    return_content: yes
  register: secret_stub

- name: Create breakglass secret
  uri:
    url: "https://<SECRET_SERVER_HOST>/api/v1/secrets"
    method: POST
    headers:
      Authorization: "Bearer {{ auth_response.json.access_token }}"
      Content-Type: "application/json"
    body: >
      {{ secret_stub.json | combine({
           'name': secret_name,
           'secretTemplateId': template_id,
           'AutoChangeEnabled': true,
           'autoChangeNextPassword': initial_password,
           'SiteId': site_id,
           'items': [
             {'fieldName': 'Username', 'itemValue': username},
             {'fieldName': 'Password', 'itemValue': password},
             /* other fields as needed */
           ]
         }) | to_json }}
    status_code: 201,409
  register: secret_result
  failed_when: secret_result.status not in [201,409]
```

## 5. Assign Folder and Secret Permissions to the AD Group  
Finally, grant the AD group access to the new folder. Folder permissions use roles like *View*, *Edit*, or *Owner*【55†L49-L57】. For example, to allow the group to see the secrets, give it the folder **View** permission. The API for this is the **folder-permissions** endpoint【57†L811-L820】【55†L49-L57】:

1. **Get a folder-permission stub** for the folder:  
   ```
   GET https://<SECRET_SERVER_HOST>/api/v1/folder-permissions/stub?filter.folderId=<FOLDER_ID>
   Authorization: Bearer <token>
   ```
2. **Set the stub fields**: set `GroupId` to your AD group’s ID (leave `UserId` null), and choose roles. For example:
   - `FolderAccessRoleName = "View"` (to let them see the folder and its secrets)【55†L49-L57】.  
   - `SecretAccessRoleName = "View"` (so they can retrieve the secret values) or another appropriate role.  
3. **POST to create permission**:  
   ```
   POST https://<SECRET_SERVER_HOST>/api/v1/folder-permissions
   Authorization: Bearer <token>
   Content-Type: application/json

   { ...permission stub JSON... }
   ```
   Success returns the permission record.

As shown in the PowerShell example: `$folderPermissionCreateArgs = Invoke-RestMethod ... "/folder-permissions/stub?filter.folderId=$folderId"` then fill in `$folderPermissionCreateArgs.GroupId`, `FolderAccessRoleName`, `SecretAccessRoleName` and POST to `/folder-permissions`【57†L811-L820】【57†L825-L834】. In Ansible, you’d do the same via `uri`. For example:

```yaml
- name: Get folder-permissions stub
  uri:
    url: "https://<SECRET_SERVER_HOST>/api/v1/folder-permissions/stub?filter.folderId={{ folder_id }}"
    method: GET
    headers:
      Authorization: "Bearer {{ auth_response.json.access_token }}"
    return_content: yes
  register: perm_stub

- name: Grant group view access to folder
  uri:
    url: "https://<SECRET_SERVER_HOST>/api/v1/folder-permissions"
    method: POST
    headers:
      Authorization: "Bearer {{ auth_response.json.access_token }}"
      Content-Type: "application/json"
    body: >
      {{ perm_stub.json | combine({
           'GroupId': ad_group_id,
           'UserId': null,
           'FolderAccessRoleName': 'View',
           'SecretAccessRoleName': 'View'
         }) | to_json }}
    status_code: 201
```

This ensures the AD group has the *View* role on the folder (and inherits that for secrets), as recommended by Delinea’s folder permissions model【55†L49-L57】.

## 6. Error Handling and Idempotency  
For robustness, each step should check for existing resources and handle errors. Examples:
- **Existing Folder/Secret**: Before creating, use GET or search (e.g. `/api/v1/folders?filter.searchText=`) to see if a folder/secret with that name exists. Skip creation if found. The PowerShell example does a search by name as a best practice【33†L43-L52】.
- **HTTP Status Checks**: In Ansible, use `failed_when` or allowed `status_code` values to catch failures. For example, treat 409 Conflict (already exists) as success or skip.
- **Missing AD Group**: If the AD group isn’t found, the playbook should either fail with a clear message or optionally call a Directory Service API to create/sync it.
- **Cleanup**: If any step fails after creating some objects, decide whether to roll back or just report the error. For example, if secret creation fails, delete the folder if it was newly made.

By checking (with `uri` module calls) and reusing existing IDs, the playbook remains idempotent. For instance, using `status_code: 201,409` treats “already exists” as non-fatal. Always log or fail with clear messages if an unexpected HTTP code is returned. 

## 7. Example Ansible Workflow  

A final playbook might look like:

1. **vars**: Define inputs (`host_short_name`, `parent_folder_id`, `template_id`, `ad_group_id`, etc.).
2. **Task: Get token** (as above).
3. **Task: Find or create folder** – GET `/folders?filter.searchText=<name>`; if not found, GET stub then POST to create【60†L631-L640】【60†L643-L652】.
4. **Task: Find or create secret** – similarly, search by name or unique field; if absent, GET stub and POST【51†L172-L180】【51†L210-L218】.
5. **Task: Assign permissions** – GET `/folder-permissions/stub`, set group and roles, POST【57†L811-L820】【57†L825-L834】.
6. **Handle errors**: use `failed_when` or try/catch patterns. For example, register each URI call and check `status` or JSON fields to detect success.

By following this plan and using the documented API endpoints, you can fully automate the onboarding: logging in, creating folders and secrets, and granting view access to the specified AD group. The official documentation and examples (PowerShell scripts) confirm the required API paths and JSON structure【51†L172-L180】【57†L811-L820】, and can be adapted to Ansible’s `uri` module for a repeatable, idempotent solution.

**Sources:** Official Delinea Secret Server docs and examples (see especially the REST API guides and PowerShell examples)【20†L168-L172】【51†L172-L180】【57†L811-L820】【60†L631-L640】【55†L49-L57】. These detail the endpoints for authentication, folder/secret management, and permissions needed for automation.