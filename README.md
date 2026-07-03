# rescue-eudat

EUDAT: https://b2share.eudat.eu/

GUIDE: https://docs.eudat.eu/b2share/rest/apisubmissionguide/

**get info from existing record**

curl -k -X GET "https://b2share.eudat.eu/api/records/7yqzx-q5t41/draft"   -H "Content-Type: application/json"   -H "Authorization: Bearer MY_TOKEN"

## setup

Create local file named `MY_TOKEN` which contain the b2share token.

Experiment setup file


Variables list in `variables.yaml`

Use the dictionay form to setup a variable collection 
```python
variables:
- SImon: {'variables':['siage', 'siconc', 'sithick'],}
```

or to create a temporal selection of data
```python
variables:
- 6hr_hfls: {start_date: '2015-01-01', end_date: '2059-12-31'}
- 6hr_hfls: {start_date: '2060-01-01', end_date: '2100-12-31'}
```

or a simple string reporting the table and the variable name for single variables upload
```python
variables:
- Omon_thetao
```

## usage

Given an experiment case named `esm-500-actall.yaml` use the following:
```python
$> python upload_eudat.py esm-500-actall.yaml
```





