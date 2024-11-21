from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build

def get_google_service(api_name, api_version, scopes):
    credentials = ServiceAccountCredentials.from_json_keyfile_name('readbooks-432315-e83fae6ea4ef.json', scopes)
    return build(api_name, api_version, credentials=credentials)
