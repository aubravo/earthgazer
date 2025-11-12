from google.cloud import bigquery
from google.oauth2 import service_account

from .settings import EarthGazerSettings

SETTINGS = EarthGazerSettings()
GCLOUD_BUCKET = SETTINGS.gcloud.bucket_name

service_account_credentials = service_account.Credentials.from_service_account_info(
    SETTINGS.gcloud.service_account, scopes=["https://www.googleapis.com/auth/cloud-platform"])

bigquery_client = bigquery.Client(credentials=service_account_credentials)

for result in bigquery_client.query("SELECT 1"):
    print(f"BigQuery connection successful: {result[0]}")
