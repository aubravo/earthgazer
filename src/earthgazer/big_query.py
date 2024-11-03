from __future__ import annotations

from typing import Any, TypeVar

from google.cloud import bigquery
from google.oauth2 import service_account
from jinja2 import Template

T = TypeVar("T", bound="BigQueryHandler")

class BigQueryHandler:
    def __init__(self: T, credentials_path: str) -> None:
        """
        Initialize the BigQueryHandler with the path to the service account credentials.

        :param credentials_path: Path to the service account JSON file
        """
        self.credentials = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        self.client = bigquery.Client(credentials=self.credentials, project=self.credentials.project_id)

    def execute_query(self: T, query: str) -> list[dict[str, Any]]:
        """
        Execute a BigQuery SQL query and return the results.

        :param query: SQL query string
        :return: List of dictionaries representing the query results
        """
        query_job = self.client.query(query)
        results = query_job.result()
        return [dict(row) for row in results]

    def render_query(self: T, query_template: str, params: dict[str, Any]) -> str:
        """
        Render a query template using Jinja2 with the provided parameters.

        :param query_template: Jinja2 template string for the SQL query
        :param params: Dictionary of parameters to render the template
        :return: Rendered SQL query string
        """
        template = Template(query_template)
        return template.render(params)

    def execute_templated_query(self: T, query_template: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Render a query template and execute it, returning the results.

        :param query_template: Jinja2 template string for the SQL query
        :param params: Dictionary of parameters to render the template
        :return: List of dictionaries representing the query results
        """
        rendered_query = self.render_query(query_template, params)
        return self.execute_query(rendered_query)
