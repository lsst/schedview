"""Async InfluxDB client module."""

import datetime
import os
from typing import Self

import httpx
import pandas as pd


class InfluxDBError(Exception):
    """Custom exception class for InfluxDB errors."""


class InfluxDBQuery:
    """A class to build InfluxDB queries.

    Parameters
    ----------
    measurement : str
        The name of the InfluxDB measurement to query.
    """

    def __init__(self, measurement: str) -> None:
        self.measurement: str = measurement
        self.time_range: tuple | None = None
        self.fields: list[str] = []
        self.filters: list[tuple[str, str]] = []

    def set_time_range(
        self, start: datetime.datetime, end: datetime.datetime
    ) -> Self:
        self.time_range = (start, end)
        return self

    def set_fields(self, fields: list[str]) -> Self:
        self.fields = fields
        return self

    def filter(self, key: str, value: str) -> Self:
        self.filters.append((key, value))
        return self

    def build_query(self) -> str:
        fields = ", ".join(self.fields) if self.fields else "*"

        query = f'SELECT {fields} FROM "{self.measurement}"'

        conditions = []

        if self.time_range:
            start, end = self.time_range
            conditions.append(f"time >= '{start}' AND time <= '{end}'")

        if self.filters:
            for key, value in self.filters:
                conditions.append(f"\"{key}\" = '{value}'")

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        return query


class AsyncInfluxDBClient:
    """A generic async InfluxDB client.

    Parameters
    ----------
    url : str
        The URL of the InfluxDB API.
    database_name : str
        The name of the database to query.
    username : str, optional
        The username to authenticate with.
    password : str, optional
        The password to authenticate with.
    output_format : str, optional
        The format of the output. Can be "dataframe" otherwise returns JSON.
    """

    def __init__(
        self,
        url: str,
        database_name: str,
        username: str | None,
        password: str | None = None,
        output_format: str = "dataframe",
    ) -> None:
        self.url = url
        self.database_name = database_name
        self.auth = (username, password) if username and password else None
        self.output_format = output_format
        self.client = httpx.AsyncClient()

    async def query(
        self, influxdb_query: InfluxDBQuery
    ) -> pd.DataFrame | dict:
        """Send a query to the InfluxDB API and returns the result
        in the specified format.

        Parameters
        ----------
        query : str
            The InfluxQL query to be executed.
        """
        result = {}
        query = influxdb_query.build_query()
        params = {"db": self.database_name, "q": query}
        try:
            response = await self.client.get(
                self.url, params=params, auth=self.auth
            )
            response.raise_for_status()
            if self.output_format == "dataframe":
                result = self._to_dataframe(response.json())
            else:
                result = response.json()
        except httpx.HTTPError as exc:
            raise InfluxDBError(
                f"Error while requesting {exc.request.url!r}."
            ) from exc

        return result

    def _to_dataframe(self, response: dict) -> pd.DataFrame:
        """Convert an InfluxDB response to a dataframe.

        Parameters
        ----------
        response : dict
            The JSON response from the InfluxDB API.
        """
        # One InfluxQL query is submitted at the time
        statement = response["results"][0]
        # One InfluxDB measurement queried at the time
        series = statement["series"][0]
        result = pd.DataFrame(
            series.get("values", []), columns=series["columns"]
        )
        if "time" not in result.columns:
            return result
        result = result.set_index(pd.to_datetime(result["time"])).drop(
            "time", axis=1
        )
        if result.index.tzinfo is None:
            result.index = result.index.tz_localize("UTC")
        if "tags" in series:
            for k, v in series["tags"].items():
                result[k] = v
        if "name" in series:
            result.name = series["name"]
        return result

    async def close(self) -> None:
        """Close the HTTP client session."""
        await self.client.aclose()


def create_efd_client() -> AsyncInfluxDBClient:
    """Create an instance of InfluxDBClient."""
    url = os.getenv(
        "INFLUXDB_URL",
        "https://usdf-rsp.slac.stanford.edu/influxdb-enterprise-data",
    )
    database_name = os.getenv("INFLUXDB_DATABASE", "efd")
    username = os.getenv("INFLUXDB_USERNAME", "efdreader")
    password = os.getenv("INFLUXDB_PASSWORD")
    return AsyncInfluxDBClient(url, database_name, username, password)
