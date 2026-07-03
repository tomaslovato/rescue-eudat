# rescue-eudat

A Python tool designed to automate dataset record creation, placeholder registration, and file content uploads onto the [EUDAT B2SHARE](https://b2share.eudat.eu/) platform. 
The tool formats metadata tailored to CMCC Foundation (Euro-Mediterranean Center on Climate Change Foundation) climate simulations under the Horizon Europe [RESCUE](https://rescue-climate.eu/) project (Grant Agreement no. 10105693).

---

## 1. Requirements
Ensure you have the following Python packages (and dependencies) installed:
* `requests`
* `pyyaml`
* `xarray`

## 2. Authentication Token
Create a plain text file named `MY_TOKEN` in the root directory of this repository (it won't show using git as it was addded to `.gitignore` list to avoid commit errors). 
Paste your EUDAT B2SHARE personal API access token inside it, as in the following shell example:
```bash
echo "YOUR_B2SHARE_BEARER_TOKEN" > MY_TOKEN
```

## 3. Configuration Files (YAML Support Files)
The tool relies on four specific YAML support files to dynamically combine project parameters, metadata descriptions, creator attributions, and targeted simulation datasets.

###  1. variables.yaml
This file outlines the specific CMIP6 tables and variables you want to extract and process from your data storage. 
Input fields are collected as list items within the dictionary key `variables`, such that duplicated Table_VariableName definitions can be defined by the user (see e.g. 'Temporal Subset of Single Variable Format'). 

Three distinct formatting layouts are supported:

- **Variables Collection Format by Table (Dictionary)**: Defines a single CMIP table group collecting multiple distinct variables.
```yaml
variables:
- SImon: {'variables':['siage', 'siconc', 'sithick'],}
```

- **Single Variable Format (String)**: A single Table_VariableName string for straightforward mapping.
```yaml
variables:
- Omon_thetao
```

- **Temporal Subset of Single Variable Format (Dictionary)**: as in the above, it targets a single Table_VariableName mapping but confines the processing to a specific chronological boundary. This applies to large size high-frequency datasets that have to be split over multiple records. The specific chronological boundary overrides the general naming convention set in the experiment case (e.g. `esm-500-actall.yaml`) for these variable records.
```yaml
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
Acts as the basic EUDAT B2SHARE metadata payload layout. 
It includes pre-configured access rights (public), funding acknowledgments, general keywords/subjects, identifier templates.
The following HTML placeholders `expname`, `yearspan`, `variables_description` are dynamically rendered by the code before initiating database pushes.

**NOTE**: this file contains preset information about the model and its grid, so user-defined changes are needed (pay attention to HTML formatting)

### 4. members.yaml
A structured dictionary capturing absolute credit details (such as ORCID codes, ROR institution markers, and full naming of authors) for all creators and contributors associated with the data generation. 
These records are automatically injected by the code into the payload layout.

## 3. Tool Usage
**The script always generate a new record. Updates to existing records needs to be implemeted.**

Run the main driver script by passing your primary experiment settings YAML file (e.g. `esm-500-actall.yaml`) as a command-line argument:
```bash
$> python upload_eudat.py esm-500-actall.yaml
```
**TIP**: It is better to start using the tool with a minimal list of variables in `variables.yaml` to avoid creating tons of new records that have to be deleted manually!

### Under the Hood Workflow
When executed, `upload_eudat.py` sequentially handles the entire workflow (see homonymous function):

1. **Token Extraction**: Evaluates your local `MY_TOKEN` profile.

2. **File Assembly** (`get_dataset_dict`): Navigates the configured `input_path` recursively, scanning for variables matching the format patterns specified in `variables.yaml`. It opens individual records using xarray to pull underlying attribute metadata (`long_name` and `units`). Tailored to CMCC data catalogue.

3. **Payload Rendering** (`get_paylod_dict`): Compiles the full metadata mapping using the template files and injects custom dynamic HTML tags. Tailored to CMCC data catalogue.

4. **Draft Creation** (`create_b2share_record`): Issues a B2SHARE API POST request to seed a new draft dataset within the EUDAT system, generating a unique draft ID URL link.

5. **Placeholder Registration** (`register_draft_files`): Registers empty file placeholders onto the active draft.

6. **Binary Stream Upload of Data** (`upload_and_commit_file_to_draft`): Local NetCDF files are sent using binary coding to the EUDAT service via stream loops directly perfoming each file upload and immediately commit upon delivery.

#### TODO: code in place but commented in workflow function, NEED TO BE TESTED

7. **Submit draft review** (`submit_draft_for_review`): create a submit request for review of the finalized drat to the `EUDAT` community

8. **Request review** (`request_draft_review`): send the submit request for review

## 4. miscellanea

EUDAT: https://b2share.eudat.eu/

API GUIDE: https://docs.eudat.eu/b2share/rest/apisubmissionguide/

**retrieve info from an existing record providing <record_id> and MY_TOKEN values**

```bash
curl -k -X GET "https://b2share.eudat.eu/api/records/<record_id>/draft"   -H "Content-Type: application/json"   -H "Authorization: Bearer MY_TOKEN"
```
