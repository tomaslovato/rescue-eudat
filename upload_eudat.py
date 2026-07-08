# This script translate to python instructions from b2share api submission guide 
# https://docs.eudat.eu/b2share/rest/apisubmissionguide/
'''
    Upload to b2share EUDAT Service the CMCC model output formatted accoriding to CMIP6-like standards.
    Copyright (C) 2026 Tomas Lovato (tomas.lovato@cmcc.it)

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
'''

import os, sys, glob
import requests
import yaml

def main():
    ''' Code main driver. '''
    from pathlib import Path
    import copy

    # read b2share token (strip last character '\n')
    MY_TOKEN = Path('MY_TOKEN').read_text()[:-1]
    print('read token from file MY_TOKEN.\n')

    # read arguments
    nargs=len(sys.argv)
    if nargs < 2:
        print('Provide at least input experiment settings <eudat_exp.yaml>'); sys.exit(1)
    casefile=str(sys.argv[1])

    # load experiment settings
    case = yaml.safe_load(open(casefile))
    case['filename'] = casefile
    print('Process input: ' + casefile + '\n' )

    # load variables dict
    if 'variables' not in case.keys():
        case['variables'] = yaml.safe_load(open("variables.yaml"))['variables']
 
    variables = copy.deepcopy(case['variables'])

    for var in variables:
        workflow(MY_TOKEN, case, var)

    print('Completed')

    return


def workflow(token, case, in_var):
    '''Workflow for EUDAT record creation, data upload and submit review request.'''

    key = list(in_var.keys())[0]

    record_id = None
    if 'record_id' in in_var[key]:
        record_id = in_var[key]['record_id']
        check_record_exists(key, record_id)

    # gather files and variables
    dataset = get_dataset_dict(case, in_var)

    # prepare payload
    payload = get_paylod_dict(case, in_var, dataset)

    # create record
    result = manage_b2share_record(token=token, payload=payload, record_id=record_id)
    http_draft = result['links']['self_html']
    print("Successfully created/updated record: " + http_draft +  "\n")

    # associate record id to variable
    if record_id is None:
        record_id = result['id']
        in_var[key]['record_id'] = record_id
        update_case_yaml(case, in_var)
    
    if 'uploaded' not in in_var[key]:
        # Draft, upload and commit file
        print("Start file(s) upload")
        result = upload_file_to_record(
            token=token, record_id=record_id, dataset=dataset
        )
        print("File(s) uploaded successfully!\n")
        in_var[key]['uploaded'] = True
        update_case_yaml(case, in_var)

    if 'submitted' not in in_var[key]:
        ## submit record for review to a community
        submit_draft_review(token=token, record_id=record_id)
        print("Record submitted for review!\n")
        in_var[key]['submitted'] = True
        update_case_yaml(case, in_var)

    return


def get_dataset_dict(case, in_var):
    '''Create dataset dict with keys named after collection and items the list of full path files to iupload'''
    import xarray as xr

    dataset = {}

    table, varname = get_table_and_varname(in_var)
    in_path = '/'.join([case['input_path'], case['experiment'], case['member'], table])

    if varname is None:
       var_list = in_var[table]['variables']
    else:
       var_list = [varname]

    # has variable specific time span
    filter_years = None
    if varname is not None and isinstance(in_var, dict):
        key_dict = in_var[table + '_' + varname]
        filter_years = [str(x) for x in range(int(key_dict['start_date'][:4]), int(key_dict['end_date'][:4])+1)]

    # find files
    for var in var_list:
        file_pattern = in_path + '/**/*' + var + '*' + table + '*.nc'
        files = sorted(glob.glob(file_pattern, recursive=True))

        if not files:
            print('No files found searching :' + file_pattern)
            sys.exit(1)

        if filter_years is not None:
            files = [file for file in files if any(year in file for year in filter_years) ]

        ds = xr.open_dataset(files[0])
        dataset[var] = {'long_name': ds[var].attrs['long_name'], 'units': ds[var].attrs['units'], 'files' : files}
        ds.close()
    
    return dataset


def get_paylod_dict(case, in_var, dataset):
    '''Create payload dict for following steps'''

    # load templates
    payload = yaml.safe_load(open(case['payload_template']))
    authors= yaml.safe_load(open(case['authors']))
   
    # fill in
    payload['metadata']['publication_date'] = case['publication_date']
    for role in ['creators', 'contributors']:
        payload['metadata'][role] = authors[role]
    for date in ['start_date', 'end_date']:
        payload['metadata']['temporal_coverage'][0]['ranges'][date] = case[date]

    # get variables
    table, varname = get_table_and_varname(in_var)

    # title
    new_title = payload['metadata']['title'].replace('expname',case['experiment'])

    # add year span label (used also in description)
    year_span = case['start_date'][:4] + '-' + case['end_date'][:4]
    if varname is not None and isinstance(in_var, dict):
        key_dict = in_var[table + '_' + varname]
        year_span = key_dict['start_date'][:4] + '-' + key_dict['end_date'][:4]

    new_title = new_title.replace('yearspan', year_span)

    # add table and variable
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


#
#  b2share interface
#
def manage_b2share_record(token: str, payload: dict, record_id: str) -> dict:
    """Sends a POST request to the B2SHARE API to create or update a new record.

    :param token: The Bearer token for authentication.
    :param payload: data payload.
    :return: The JSON response from the API or raises an HTTPError.
    """
    # Set up headers (Note: -k in curl bypasses SSL verification.
    # To mimic -k, we set verify=False inside requests.post below)
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }

    try:
        # Create record (POST) or update record (PUT)
        if record_id is None:
            url = "https://b2share.eudat.eu/api/records"
            response = requests.post(url, json=payload, headers=headers,)
        else:
            url = f"https://b2share.eudat.eu/api/records/{record_id}/draft"
            response = requests.put(url, json=payload, headers=headers,)

        # Raise an exception if the response status is 4xx or 5xx
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        if response is not None:
            print(f"Status Code: {response.status_code}")
            print(f"Response: {response.text}")
            sys.exit(1)


def upload_file_to_record(token: str, record_id: str, dataset: dict) -> dict:
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

            ## DRAFT
            url = f"https://b2share.eudat.eu/api/records/{record_id}/draft/files"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            }
            file_draft = [{'key': os.path.basename(file_name)}]
            # making the POST request
            response = requests.post(url, json=file_draft, headers=headers)
            # Raise an exception if the response status is 4xx or 5xx
            response.raise_for_status()

            ## UPLOAD
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

            ## COMMIT
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


def submit_draft_review(token: str, record_id: str,) -> list:
    """Submits a draft record and send request for review in B2SHARE.
    
    :param record_id: The ID of the draft record (record_id).
    :param access_token: Your B2SHARE API bearer access token.
    :param community_id: The ID of the community to submit to.
    :return: The JSON response from the API or raises an HTTPError.
    """
    # EUDAT community id (curl -k -X GET "https://b2share.eudat.eu/api/communities/eudat")
    community_id = "e9b9792e-79fb-4b07-b6b4-b9c2bd06d095"


    ## Submit draft record to community
    url = f"https://b2share.eudat.eu/api/records/{record_id}/draft/review"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    payload = {
        "receiver": { "community": community_id },
        "type": "community-submission"
    }
    try:
        response = requests.put(url, headers=headers, json=payload)
        # Raises an HTTPError if the response code was an error (4xx or 5xx)
        response.raise_for_status() 
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        if response is not None:
            print(f"Status Code: {response.status_code}")
            print(f"Response: {response.text}")
            sys.exit(1)

    ## Send a request for record review
    result = response.json()
    submit_link = result['links']['actions']['submit']
    headers = {
        "Authorization": f"Bearer {token}"
    }
    try:
       # Performing the POST request
       response = requests.post(submit_link, headers=headers)
       # Raises an HTTPError if the response code was an error (4xx or 5xx)
       response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        if response is not None:
            print(f"Status Code: {response.status_code}")
            print(f"Response: {response.text}")
            sys.exit(1)

    return


#
# Utilities
#
def check_record_exists(in_var, record_id):
    """Check if record URL exists. If not stop"""

    record_url = f"https://b2share.eudat.eu/uploads/{record_id}"
    response = requests.get(record_url)
    if response.status_code == 200:
        return 
    else:
        print('Not exisisting record: ' + record_url)
        print(f"Remove 'record_id' from {in_var} dictionary within <case>.yaml")
        sys.exit(1)


def update_case_yaml(case, in_var):
    """Associate record_id to variable and dump into <case>.yaml."""

    var_list = []
    for var in case['variables']:
        if var.keys() == in_var.keys():
            var_list.append(in_var)
        else:
            var_list.append(var)

    # update case
    case['variables'] = var_list

    # save to file
    outfile = case['filename']
    yaml.dump(case, open(outfile,'w'), default_flow_style=False, sort_keys=False)
 
    return


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


def get_table_and_varname(in_var):
    """Get table and variable names from dictionary key"""
    
    if isinstance(in_var, dict):
        key_split = list(in_var.keys())[0].split('_')
        table = key_split[0]
        if len(key_split)>1:
            varname = key_split[1]
        else:
            varname = None

    else:
        print('get_table_and_varname: cannot handle variable name ' + in_var )
        sys.exit(1)
   
    return table, varname
 

#==========================================================================
# Main sentinel
#==========================================================================
if __name__ == "__main__":
    main()
