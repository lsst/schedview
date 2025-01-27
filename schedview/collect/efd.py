import asyncio
import os
import threading
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from functools import partial
from typing import Literal
from warnings import warn

import pandas as pd
import requests
from lsst_efd_client import EfdClient

from schedview.dayobs import DayObs

EfdDatabase = Literal["efd", "obsenv"]

try:
    from lsst.rsp import get_access_token
except ImportError:

    def get_access_token(token_file: str | None = None) -> str:
        token = os.environ.get("ACCESS_TOKEN")
        if token is None and token_file is not None:
            with open("token_file", "r") as f:
                token = f.read()

        if not isinstance(token, str):
            raise ValueError("No access token found.")

        return token


SAL_INDEX_GUESSES = defaultdict(partial([[]].__getitem__, 0), {"lsstcomcam": [1, 3], "latiss": [2]})
BASE_URLS = {
    "summit": "https://summit-lsp.lsst.codes/",
    "tucson": None,
    "base": "https://base-lsp.slac.lsst.codes/",
    "usdf": "https://usdf-rsp.slac.stanford.edu/",
    "usdf-dev": "https://usdf-rsp-dev.slac.stanford.edu/",
    "UNKNOWN": "https://usdf-rsp.slac.stanford.edu/",
}


EFD_NAMES = {
    "summit": "summit_efd",
    "tucson": "tucson_efd",
    "base": "base_efd",
    "usdf": "usdf_efd",
    "usdf-dev": "usdf_efd",
    "UNKNOWN": "usdf_efd",
}

MAX_RETRIES = 2


@dataclass
class ClientConnections:
    site: str | None = None
    base: str | None = None
    token: str | None = None

    @property
    def auth(self) -> tuple[str, str]:
        if self.token is None:
            raise ValueError("No auth token available.")

        return ("user", self.token)

    def __post_init__(self):
        self.io_loop = None
        self.io_thread = None

        # Set up authentication
        if self.token is None:
            self.token = get_access_token()

        # This authentication is for nightlog, exposurelog,
        # nightreport currently
        # But I think it's the same underlying info for EfdClient i.e.
        # https://github.com/lsst/schedview/blob/e11fbd51ee5e22d11fef9a52f66dfcc082181cb6/schedview/app/scheduler_dashboard/influxdb_client.py

        if self.site is None:
            # Try figuring out the site from EXTERNAL_INSTANCE_URL
            location = os.getenv("EXTERNAL_INSTANCE_URL", "")
            if "tucson-teststand" in location:
                self.site = "tucson"
            elif "summit-lsp" in location:
                self.site = "summit"
            elif "base-lsp" in location:
                self.site = "base"
            elif "usdf-rsp" in location:
                if "dev" in location:
                    self.site = "usdf-dev"
                else:
                    self.site = "usdf"
            else:
                warn(f"Could not determine site from EXTERNAL_INSTANCE_URL {location}.")

        if self.site is None:
            # Try figuring out the site from the hostname
            hostname = os.getenv("HOSTNAME", "")
            interactiveNodes = ("sdfrome", "sdfiana")
            if hostname.startswith(interactiveNodes):
                self.site = "usdf"
            elif hostname == "htcondor.ls.lsst.org":
                self.site = "base"
            elif hostname == "htcondor.cp.lsst.org":
                self.site = "summit"
            else:
                warn(f"Could not deterime site from HOSTNAME {hostname}.")

        if self.site is None and self.base is not None:
            # Try figuring out the site from the base URL, if the user
            # supplied one.
            match self.base:
                case "https://summit-lsp.lsst.codes/":
                    self.site = "summit"
                case "https://tucson-teststand.lsst.codes/":
                    self.site = "tucson"
                case "https://base-lsp.slac.lsst.codes/":
                    self.site = "base"
                case "https://usdf-rsp.slac.stanford.edu/":
                    self.site = "usdf"
                case "https://usdf-rsp-dev.slac.stanford.edu/":
                    self.site = "usdf-dev"
                case _:
                    warn(f"Could not determine site from base {self.base}.")

        if self.site is None:
            self.site = "UNKNOWN"

        if self.base is None:
            if self.site in BASE_URLS:
                self.base = BASE_URLS[self.site]
            else:
                warn(f"Unknown site {self.site}, defaulting to usdf base.")
                self.base = "https://usdf-rsp.slac.stanford.edu/"

        try:
            self.efd_name = EFD_NAMES[self.site]
        except KeyError:
            self.efd_name = f"{self.site}_efd"

    @property
    def efd(self) -> EfdClient:
        # The EfdClient needs to be instantiated within an async function
        # to work correctly, but we want to be able to instantiate this class
        # outside of an async function. So instantiate the EfdClient only on
        # request.
        return EfdClient(self.efd_name)

    @property
    def obsenv(self) -> EfdClient:
        # The EfdClient needs to be instantiated within an async function
        # to work correctly, but we want to be able to instantiate this class
        # outside of an async function. So instantiate the EfdClient only on
        # request.
        return EfdClient(self.efd_name, db_name="lsst.obsenv")

    async def _get_efd_fields_for_topic(self, topic, public_only=True, database="efd"):
        client = self.efd if database == "efd" else self.obsenv

        fields = await client.get_fields(topic)
        if public_only:
            fields = [f for f in fields if "private" not in f]

        return fields

    async def query_efd_topic_for_night(
        self,
        topic: str,
        day_obs: DayObs | str | int,
        sal_indexes: tuple[int, ...] = (1, 2, 3),
        fields: list[str] | None = None,
        database: EfdDatabase = "efd",
    ) -> pd.DataFrame:
        """Query and EFD topic for all entries on a night.

        Parameters
        ----------
        topic : `str`
            The topic to query
        day_obs : `DayObs` or `str` or `int`
            The date of the start of the night requested.
        sal_indexes : `tuple[int, ...]`, optional
            Which SAL indexes to query, by default (1, 2, 3).
            Can be guessed by instrument with ``SAL_INDEX_GUESSES[instrument]``
        fields : `list[str]` or `None`, optional
            Fields to query from the topic, by default None, which queries all
            fields.
        database : `str`, optional
            Which EFD database to query: ``efd`` or ``obsenv``,
            by default ``efd``.

        Returns
        -------
        result : `pd.DataFrame`
            The result of the query
        """

        day_obs = day_obs if isinstance(day_obs, DayObs) else DayObs.from_date(day_obs)
        client = self.efd if database == "efd" else self.obsenv

        if fields is None:
            fields = await self._get_efd_fields_for_topic(topic, database=database)

        if not isinstance(sal_indexes, Iterable):
            sal_indexes = [sal_indexes]

        results = []
        for sal_index in sal_indexes:
            result = await client.select_time_series(
                topic, fields, day_obs.start, day_obs.end, index=sal_index
            )
            if isinstance(result, pd.DataFrame) and len(result) > 0:
                results.append(result)

        result = pd.concat(results) if len(results) > 0 else pd.DataFrame()
        result.index.name = "time"

        return result

    async def query_latest_in_efd_topic(
        self,
        topic: str,
        num_records: int = 6,
        sal_indexes: tuple[int, ...] = (1, 2, 3),
        fields: list[str] | None = None,
        database: EfdDatabase = "efd",
    ) -> pd.DataFrame:
        """Query and EFD topic for all entries on a night.

        Parameters
        ----------
        topic : `str`
            The topic to query
        num_records : `int`
            The number of records to return.
        sal_indexes : `tuple[int, ...]`, optional
            Which SAL indexes to query, by default (1, 2, 3).
            Can be guessed by instrument with ``SAL_INDEX_GUESSES[instrument]``
        fields : `list[str]` or `None`, optional
            Fields to query from the topic, by default None, which queries all
            fields.
        database : `str`, optional
            Which EFD database to query: ``efd`` or ``obsenv``,
            by default ``efd``.

        Returns
        -------
        result : `pd.DataFrame`
            The result of the query
        """
        client = self.efd if database == "efd" else self.obsenv

        if fields is None:
            fields = await self._get_efd_fields_for_topic(topic, database=database)

        if not isinstance(sal_indexes, Iterable):
            sal_indexes = [sal_indexes]

        results = []
        for sal_index in sal_indexes:
            result = await client.select_top_n(topic, fields, num_records, index=sal_index)
            if isinstance(result, pd.DataFrame) and len(result) > 0:
                results.append(result)

        result = pd.concat(results) if len(results) > 0 else pd.DataFrame()

        return result

    def sync_query_efd_topic_for_night(self, *args, **kwargs):
        """Just like query_efd_topic_for_night, but run in a separate thread
        and block for results, so it can be run within a separate event loop.
        """
        # Inspired by https://stackoverflow.com/questions/74703727
        # Works even in a panel event loop
        if self.io_loop is None:
            self.io_loop = asyncio.new_event_loop()

        if self.io_thread is None:
            assert isinstance(self.io_loop, asyncio.AbstractEventLoop)
            self.io_thread = threading.Thread(
                target=self.io_loop.run_forever, name="EFD query thread", daemon=True
            )

        def run_async(coro):
            assert isinstance(self.io_thread, threading.Thread)
            assert isinstance(self.io_loop, asyncio.AbstractEventLoop)
            if not self.io_thread.is_alive():
                self.io_thread.start()
            future = asyncio.run_coroutine_threadsafe(coro, self.io_loop)
            return future.result()

        result = run_async(self.query_efd_topic_for_night(*args, **kwargs))
        return result

    def get_with_retries(self, channel, params):
        api_endpoint = f"{self.base}{channel}"
        response = requests.get(api_endpoint, auth=self.auth, params=params)
        try_number = 1
        while not response.status_code == 200:
            if try_number > MAX_RETRIES:
                response.raise_for_status()
            response = requests.get(api_endpoint, auth=self.auth, params=params)
            try_number += 1

        return response.json()
