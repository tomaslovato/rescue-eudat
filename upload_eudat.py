import os, sys, glob
import requests
import yaml

# EUDAT: https://b2share.eudat.eu/

# GUIDE: https://docs.eudat.eu/b2share/rest/apisubmissionguide/

# get info from record curl -k -X GET "https://b2share.eudat.eu/api/records/7yqzx-q5t41/draft"   -H "Content-Type: application/json"   -H "Authorization: Bearer pIUYZFq6RDuYsScHcP4ZBfzBzmKfG12b75wnl48HxoqAJ1w9uD99FXYtTyAy"


def main():
    ''' Code main driver. '''
    from pathlib import Path

    MY_TOKEN = Path('MY_TOKEN').read_text()[:-1]

    # read arguments
    nargs=len(sys.argv)
    if nargs < 2:
        print('Provide at least input experiment settings <eudat_exp.yaml>'); sys.exit(1)
    casefile=str(sys.argv[1])

    # load experiment settings
    case = yaml.safe_load(open(casefile))
    print('Process input: ' + casefile + '\n' )

    # load variables dict
    variables = yaml.safe_load(open("variables.yaml"))

    for var in variables['variables']:
        workflow(MY_TOKEN, case, var)

    print('done')

    return


def workflow(token, case, var_dict):
    '''Workflow for EUDAT record creation and data upload.'''

    # gather files and variables
    dataset = get_dataset_dict(case, var_dict)

    # prepare payload
    payload = get_paylod_dict(case, var_dict, dataset)

    # create record
    print("Create Record")
    try:
        result = create_b2share_record(token=token, payload=payload)
        http_draft = result['links']['self_html']
        print("Successfully created record: " + http_draft +  "!\n")
        rid = result['id']
    except requests.exceptions.HTTPError as err:
        print(f"HTTP Error occurred: {err}")
    except Exception as e:
        print(f"An error occurred: {e}")

    # Add file metadata into record
    print("Register files metadata")
    try:
        result = register_draft_files(
            token=token, record_id=rid, dataset=dataset
        )
        print("Files registered to draft successfully!\n")
    except requests.exceptions.HTTPError as err:
        print(f"HTTP Error occurred: {err}")
    except Exception as e:
        print(f"An error occurred: {e}")

    # Upload and commit file content
    print("Start files upload and commit")
    try:
        result = upload_and_commit_file_to_draft(
            token=token,
            record_id=rid,
            dataset=dataset
        )
        print("File uploaded successfully!\n")
    except requests.exceptions.HTTPError as err:
        print(f"HTTP Error occurred: {err}")

    # Create a request to submit to a community

    # Submit the record to the community

    return


def get_dataset_dict(case, var_dict):
    '''Create payload dict for following steps'''
    import xarray as xr

    dataset = {}

    table, varname = get_table_and_varname(var_dict)
    in_path = '/'.join([case['input_path'], case['experiment'], case['member'], table])

    if varname is None:
       var_list = var_dict[table]['variables']
    else:
       var_list = [varname]

    # find files
    for var in var_list:
        file_pattern = in_path + '/**/*' + var + '*' + table + '*.nc'
        files = sorted(glob.glob(file_pattern, recursive=True))
        if not files:
            print('No files found searching :' + file_pattern)
            sys.exit(1)
        else:
            ds = xr.open_dataset(files[0])
            dataset[var] = {'long_name': ds[var].attrs['long_name'], 'units': ds[var].attrs['units'], 'files' : files}
            ds.close()
    
    return dataset


def get_paylod_dict(case, var_dict, dataset):
    '''Create payload dict for following steps'''

    # load templates
    payload = yaml.safe_load(open(case['payload_template']))
    members= yaml.safe_load(open(case['members']))
   
    # fill in
    payload['metadata']['publication_date'] = case['publication_date']
    for role in ['creators', 'contributors']:
        payload['metadata'][role] = members[role]
    for date in ['start_date', 'end_date']:
        payload['metadata']['temporal_coverage'][0]['ranges'][date] = case[date]

    # year span label
    year_span = case['start_date'][:4] + '-' + case['end_date'][:4]

    # title
    new_title = payload['metadata']['title'].replace('expname',case['experiment']).replace('yearspan', year_span)

    # get variables
    table, varname = get_table_and_varname(var_dict)
    if varname is None:
        new_title = new_title + '_' + table
    else:
        new_title = new_title + '_' + table + '_' + varname
    payload['metadata']['title'] = new_title
    
    # description text
    new_descr = payload['metadata']['description'].replace('expname',case['experiment']).replace('yearspan', year_span)
    new_descr = new_descr.replace('expdescr',case['description'])

    data_freq = table + ' (' + cmip_freq_long(table) + ')'
    new_descr = new_descr.replace('data-frequency', data_freq)

    # realization member
    themember = case['member'][1] + ' (' + case['member'] + ')'
    new_descr = new_descr.replace('themember', themember)
 
    # add variables list
    html_line = '<li><strong>varname:</strong>&nbsp;name_units&nbsp;</li>\n'
    new_variables = ''
    for var in dataset.keys():
        name_units = dataset[var]['long_name'] + ' (' + dataset[var]['units'] + ')'
        new_variables = new_variables + html_line.replace('varname', var).replace('name_units', name_units)

    new_descr = new_descr.replace('variables_description', new_variables)
    payload['metadata']['description'] = new_descr

    return payload


def create_b2share_record(token: str, payload: dict) -> dict:
    """Sends a POST request to the B2SHARE API to create a new record.

    :param token: The Bearer token for authentication.
    :param payload: data payload.
    :return: The JSON response from the API or raises an HTTPError.
    """
    url = "https://b2share.eudat.eu/api/records"

    # Set up headers (Note: -k in curl bypasses SSL verification.
    # To mimic -k, we set verify=False inside requests.post below)
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }

    # Making the request. verify=False handles the '-k' insecure flag.
    response = requests.post(
        url, json=payload, headers=headers,
    )

    # Raise an exception if the response status is 4xx or 5xx
    response.raise_for_status()

    return response.json()


def register_draft_files(token: str, record_id: str, dataset: dict) -> list:
    """Registers placeholder entries for files to be uploaded to a draft record.

    :param token: The Bearer token for authentication.
    :param record_id: The ID of the draft record ($RID).
    :param dataset: dictionary organized by variables with data to upload
    :return: The JSON response list from the API or raises an HTTPError.
    """
    url = f"https://b2share.eudat.eu/api/records/{record_id}/draft/files"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }

    files_list = []
    for var in dataset.keys():
        var_files = [{'key': os.path.basename(file)} for file in dataset[var]['files']]
        files_list = files_list + var_files

    # Making the POST request.
    # Note: If you need to bypass SSL errors like the previous `-k` command,
    # add `verify=False` to the post arguments below.
    response = requests.post(url, json=files_list, headers=headers)

    # Raise an exception if the response status is 4xx or 5xx
    response.raise_for_status()

    return response.json()


def upload_and_commit_file_to_draft(token: str, record_id: str,  dataset: dict) -> dict:
    """Uploads anc commit a local file's content to a registered placeholder in a draft record.

    :param token: The Bearer token for authentication.
    :param record_id: The ID of the draft record ($RID).
    :param dataset: dictionary organized by variables with data to upload
    :return: The JSON response from the API or raises an HTTPError.
    """
    for var in dataset.keys():
        var_files = dataset[var]['files']
        for file_path in var_files:
            file_name = os.path.basename(file_path)
            print(' - ' + file_name)

            ## upload
            url = f"https://b2share.eudat.eu/api/records/{record_id}/draft/files/{file_name}/content"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/octet-stream",
            }

            # Open the file in binary mode and stream it using PUT
            with open(file_path, "rb") as file_data:
                response = requests.put(url, data=file_data, headers=headers)

            # Raise an exception if the response status is 4xx or 5xx
            response.raise_for_status()

            ## commit
            url = f"https://b2share.eudat.eu/api/records/{record_id}/draft/files/{file_name}/commit"
            headers = {
                "Authorization": f"Bearer {token}",
            }

            # Making the POST request to commit the file.
            # Note: B2SHARE expects a POST with no body here.
            response = requests.post(url, headers=headers)
        
            # Raise an exception if the response status is 4xx or 5xx
            response.raise_for_status()

    return response.json()


def submit_draft_for_review(token: str, record_id: str,) -> list:
    """Submits a draft record for review in B2SHARE.
    
    :param record_id: The ID of the draft record ($RID).
    :param access_token: Your B2SHARE API bearer access token.
    :param community_id: The ID of the community to submit to.
    :return: The JSON response from the API or raises an HTTPError.
    """
    # EUDAT community id (curl -k -X GET "https://b2share.eudat.eu/api/communities/eudat")
    community_id = "e9b9792e-79fb-4b07-b6b4-b9c2bd06d095"

    url = f"https://b2share.eudat.eu/api/records/{record_id}/draft/review"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    payload = {
        "receiver": { "community": community_id },
        "type": "community-submission"
    }
    
    response = requests.put(url, headers=headers, json=payload)

    # Raises an HTTPError if the response code was an error (4xx or 5xx)
    response.raise_for_status() 

    return response.json()


def request_draft_review(token: str, response_link: str) -> list:
    """Sends a POST request to record submission using response_link.
    
    :param token: Your API bearer access token.
    :param response_link: The full URL endpoint ("<response_link>").
    :return: Response JSON dictionary if successful, None otherwise.
    """
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    
    # Performing the POST request
    response = requests.post(response_link, headers=headers)
    
    # Raises an HTTPError if the response code was an error (4xx or 5xx)
    response.raise_for_status() 
    
    return response.json()


def cmip_freq_long(freq):
    '''Return dataset frequency description '''
    freq_dict = {
        '6hr'  :'6-hourly atmospheric data',
        'Amon' : 'Monthly atmospheric data',
        'day'  : 'Daily ocean data',
        'Eday' : 'Daily land data',
        'Emon' : 'Monthly land data',
        'Eyr'  : 'Annual land data',
        'LImon': 'Monthly land-ice data',
        'Lmon' : 'Monthly land data',
        'Oday' : 'Daily ocean data',
        'Omon' : 'Monthly ocean data',
        'SImon': 'Monthly sea ice data',
    }

    if freq in freq_dict.keys():
        freq_description = freq_dict[freq]
    else:
        print('Frequency not available in cmip_freq_long dict: ' + freq )
        sys.exit(1)

    return freq_description


def get_table_and_varname(var_dict):
    """Get table and variable names from input dict/list."""
    
    if isinstance(var_dict, dict):  
        table = list(var_dict.keys())[0]
        varname = None
        # TODO later on add case for year subsamples
    elif isinstance(var_dict, str):
        table = var_dict.split('_')[0]
        varname = var_dict.split('_')[1]
    else:
        print('get_table_and_varname: cannot handle variable name ' + var_dict )
        sys.exit(1)
   
    return table, varname
 

#==========================================================================
# Main sentinel
#==========================================================================
if __name__ == "__main__":
    main()
