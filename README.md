# rescue-eudat-upload

A Python tool designed to automate dataset record creation, placeholder registration, and file content uploads onto the [EUDAT B2SHARE](https://b2share.eudat.eu/) platform. 
The tool formats metadata tailored to CMCC (Euro-Mediterranean Center on Climate Change) climate simulations under the Horizon Europe RESCUE project.

---

## 1. Requirements
Ensure you have the following Python packages installed:
* `requests`
* `pyyaml`
* `xarray`
* `xarray`

## 2. Authentication Token
Create a plain text file named `MY_TOKEN` in the root directory of this repository. Paste your EUDAT B2SHARE personal API access token inside it.
```bash
echo "YOUR_B2SHARE_BEARER_TOKEN" > MY_TOKEN
```

## 3. Configuration Files (YAML Support Files)
The tool relies on four specific YAML support files to dynamically combine project parameters, metadata descriptions, creator attributions, and targeted simulation datasets.

###  1. variables.yaml
This file outlines the specific CMIP6 tables and variables you want to extract and process from your data storage. It supports three distinct formatting layouts:

- **Collection Format (Dictionary)**: Defines a CMIP table group targeting multiple distinct variables.
```python
variables:
- SImon: {'variables':['siage', 'siconc', 'sithick'],}
```

- **Single Variable String Format**: A simple Table_VariableName string for straightforward, single-variable mapping.
```python
variables:
- Omon_thetao
```

- **Temporal Subset Format**: Targets a single table and variable but confines the processing to a specific chronological boundary.
```python
variables:
- 6hr_hfls: {start_date: '2015-01-01', end_date: '2059-12-31'}
- 6hr_hfls: {start_date: '2060-01-01', end_date: '2100-12-31'}
```
### 2. Experiment File (e.g., esm-500-actall.yaml)
This case file outlines the active climate simulation parameters, specifying exactly where the data is stored and which configurations to apply.

- `experiment` & `description`: Identifies the simulation case and describes its unique climate scenario parameters.

- `start_date` / `end_date` / `publication_date`: Time range attributes and metadata timestamp configurations.

- `payload_template` / `authors`: Pointers to the respective metadata schemas and author matrices.

- `input_path` / `member`: Absolute system directory path to the NetCDF dataset structure and the targeted ensemble run variant label (e.g., `r1i1p1f1`).

### 3. schema_eudat_cmcc.yaml
Acts as the basic EUDAT B2SHARE metadata payload payload layout. 
It includes pre-configured access rights (public), funding acknowledgments for the European Union's Horizon Europe RESCUE framework, general keywords/subjects, identifier templates.
The following HTML placeholders `expname`, `yearspan`, `variables_description` are dynamically rendered by the code before initiating database pushes.

**NOTE**: this file contains preset information about the model and its grid so manually change it where needed *pay attention to HTML format)

### 4. members.yaml
A structured directory capturing absolute credit details (such as ORCID codes, ROR institution markers, and full naming variants) for all creators and contributors associated with the data generation. 
These records are injected seamlessly into the dynamic B2SHARE payload profile.

## 3. Tool Usage
Run the main driver script by passing your primary experiment settings YAML file as a command-line argument:
```python
$> python upload_eudat.py esm-500-actall.yaml
```
**TIP**: It is better to start using the tool with a minimal list of variables in `variables.yaml` to avoid creating tons of new records that have to be deleted manually!

### Under the Hood Workflow
When executed, `upload_eudat.py` sequentially handles the entire workflow:

1. **Token Extraction**: Evaluates your local `MY_TOKEN` profile.

2. **File Assembly** (`get_dataset_dict`): Navigates the configured `input_path` recursively, scanning for variables matching the format patterns specified in `variables.yaml`. It opens individual records using xarray to pull underlying attribute metadata (`long_name` and `units`).

3. **Payload Rendering** (`get_paylod_dict`): Compiles the full metadata mapping using the template files and injects custom dynamic HTML tags.

4. **Draft Creation** (`create_b2share_record`): Issues an API POST request to seed a pristine draft dataset within the EUDAT system, generating a unique draft URL link.

5. **Placeholder Registration** (`register_draft_files`): Registers empty file placeholders onto the active draft.

6. **Binary Stream Upload** (`upload_and_commit_file_to_draft`): Transmits local NetCDF binary content via stream loops directly to the EUDAT ecosystem and finalizes commits upon delivery.

7. **Submit draft review** (`submit_draft_for_review`): create a submit request for review of the finalized drat to the `EUDAT` community

8. **Request review** (`request_draft_review`): send the submit request for review

## 4. miscellanea

EUDAT: https://b2share.eudat.eu/

API GUIDE: https://docs.eudat.eu/b2share/rest/apisubmissionguide/

**get info from existing record**

```bash
curl -k -X GET "https://b2share.eudat.eu/api/records/<record_id>/draft"   -H "Content-Type: application/json"   -H "Authorization: Bearer MY_TOKEN"
```
