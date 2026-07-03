# rescue-eudat

EUDAT: https://b2share.eudat.eu/

GUIDE: https://docs.eudat.eu/b2share/rest/apisubmissionguide/

**get info from existing record**

curl -k -X GET "https://b2share.eudat.eu/api/records/7yqzx-q5t41/draft"   -H "Content-Type: application/json"   -H "Authorization: Bearer pIUYZFq6RDuYsScHcP4ZBfzBzmKfG12b75wnl48HxoqAJ1w9uD99FXYtTyAy"

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
```
```

or a simple string reporting the table and the variable name for single variables upload
```python
variables:
- Omon_thetao
```






