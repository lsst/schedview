from tempfile import TemporaryDirectory, NamedTemporaryFile
import param
import logging
from pathlib import Path
import pandas as pd
from zoneinfo import ZoneInfo
import pickle
import lzma

from astropy.time import Time

from rubin_sim.scheduler.model_observatory import ModelObservatory
import rubin_sim.scheduler.example
from rubin_sim.scheduler.utils import SchemaConverter

import schedview.compute.astro
import schedview.collect.opsim
import schedview.compute.scheduler
import schedview.collect.footprint
import schedview.plot.visits
import schedview.plot.visitmap
import schedview.plot.rewards
import schedview.plot.visits
import schedview.plot.maf

import panel as pn

TEMP_DIR = TemporaryDirectory()
DEFAULT_TIMEZONE = "Chile/Continental"
DEFAULT_CURRENT_TIME = Time(
    pd.Timestamp("2025-08-01 23:00:00", tzinfo=ZoneInfo(DEFAULT_TIMEZONE))
)
DEFAULT_OPSIM_FNAME = f"{str(Path.home())}/tmp/opsim.db"
DEFAULT_SCHEDULER_FNAME = f"{str(Path.home())}/tmp/scheduler.pickle.xz"

pn.extension(
    "tabulator",
    css_files=[pn.io.resources.CSS_URLS["font-awesome"]],
    sizing_mode="stretch_width",
)
pn.config.console_output = "disable"

logging.basicConfig(format="%(asctime)s %(message)s", level=logging.INFO)

debug_info = pn.widgets.Debugger(
    name="Debugger info level", level=logging.INFO, sizing_mode="stretch_both"
)


class Prenight(param.Parameterized):

    _observatory = ModelObservatory()
    _site = _observatory.location

    opsim_output_fname = param.String(DEFAULT_OPSIM_FNAME + " unloaded")
    scheduler_fname = param.String(DEFAULT_SCHEDULER_FNAME + " unloaded")
    night = param.Date(DEFAULT_CURRENT_TIME.datetime.date())
    timezone = param.ObjectSelector(
        objects=[
            "Chile/Continental",
            "US/Pacific",
            "US/Arizona",
            "US/Mountain",
            "US/Central",
            "US/Eastern",
        ],
        default=DEFAULT_TIMEZONE,
    )
    visits = None
    scheduler = None
    almanac_events = None
    night_time = None
    sunset_time = None
    sunrise_time = None

    @param.depends("night", watch=True)
    def update_night_time(self):
        self.night_time = Time(self.night.isoformat())

    @param.depends("night_time", "timezone", watch=True)
    def update_almanac_events(self):
        self.almanac_events = schedview.compute.astro.night_events(
            self.night_time, self._site, self.timezone
        )

    @param.depends("almanac_events", watch=True)
    def update_sunset_time(self):
        self.sunset_time = Time(self.almanac_events.loc["sunset", "UTC"])

    @param.depends("almanac_events", watch=True)
    def update_sunrise_time(self):
        self.sunrise_time = Time(self.almanac_events.loc["sunrise", "UTC"])

    @param.depends("almanac_events", "night", "timezone")
    def almanac_events_table(self):
        if self.almanac_events is None:
            return "No almanac events computed."

        logging.info("Updating almanac.")
        almanac_table = pn.widgets.DataFrame(self.almanac_events)
        return almanac_table

    @param.depends("opsim_output_fname", "sunset_time", "sunrise_time", watch=True)
    def update_visits(self):
        if self.almanac_events is None:
            self.update_almanac_events()

        try:
            visits = schedview.collect.opsim.read_opsim(
                self.opsim_output_fname, self.sunset_time.iso, self.sunrise_time.iso
            )
            self.visits = visits
        except:
            self.visits = None

    def set_opsim_output_from_observations(self, observations):
        converter = SchemaConverter()

        with NamedTemporaryFile(
            prefix="opsim-", suffix=".db", dir=TEMP_DIR.name
        ) as temp_file:
            opsim_output_fname = temp_file.name

        logging.info(f"Saving observations to {opsim_output_fname}.")
        converter.obs2opsim(observations, filename=opsim_output_fname)

        self.opsim_output_fname = opsim_output_fname

    @param.depends("visits", "night_time")
    def visit_table(self):
        if self.visits is None:
            return "No visits loaded."

        logging.info("Updating visit table")
        columns = [
            "start_date",
            "fieldRA",
            "fieldDec",
            "altitude",
            "azimuth",
            "filter",
            "airmass",
            "slewTime",
            "moonDistance",
            "block_id",
            "note",
        ]

        visit_table = pn.widgets.DataFrame(self.visits[columns])

        if len(self.visits) < 1:
            visit_table = "No visits on this night"

        logging.info("Finished updating visit table")
        return visit_table

    @param.depends("visits", "night_time")
    def visit_explorer(self):
        if self.visits is None:
            return "No visits loaded."

        logging.info("Updating visit explorer")

        (
            visit_explorer,
            visit_explorer_data,
        ) = schedview.plot.visits.create_visit_explorer(
            visits=self.visits,
            night_date=self.night_time,
        )

        if len(visit_explorer_data["visits"]) < 1:
            visit_explorer = "No visits on this night."

        logging.info("Finished updating visit explorer")

        return visit_explorer

    @param.depends("scheduler_fname", watch=True)
    def update_scheduler(self):
        try:
            (
                scheduler,
                conditions,
            ) = schedview.collect.scheduler_pickle.read_scheduler(self.scheduler_fname)

            self.scheduler = scheduler
        except:
            self.scheduler = rubin_sim.scheduler.example.example_scheduler(
                nside=self._nside
            )

    def set_scheduler_from_instance(self, scheduler):
        # Get a unique temp file name
        with NamedTemporaryFile(
            prefix="scheduler-", suffix=".pickle.xz", dir=TEMP_DIR.name
        ) as temp_file:
            scheduler_fname = temp_file.name

        logging.info(f"Saving scheduler to {scheduler_fname}.")
        with lzma.open(scheduler_fname, "wb", format=lzma.FORMAT_XZ) as pio:
            pickle.dump(scheduler, pio)

        self.scheduler_fname = scheduler_fname

    @param.depends(
        "scheduler",
        "visits",
        "night_time",
    )
    def visit_skymaps(self):
        if self.visits is None:
            return "No visits are loaded."

        if self.scheduler is None:
            return "No scheduler is loaded."

        logging.info("Updating skymaps")

        vmap, vmap_data = schedview.plot.visitmap.create_visit_skymaps(
            visits=self.visits,
            scheduler=self.scheduler,
            night_date=self.night_time,
            timezone=self.timezone,
            observatory=self._observatory,
        )

        if len(vmap_data["visits"]) < 1:
            vmap = "No visits on this night."

        logging.info("Finished updating skymaps")

        return vmap


def prenight_app(night_date=None, observations=None, scheduler=None):
    prenight = Prenight()

    if night_date is not None:
        prenight.night = night_date

    if observations is not None:
        prenight.set_opsim_output_from_observations(observations)

    if scheduler is not None:
        prenight.set_scheduler_from_instance(scheduler)

    pn_app = pn.Column(
        "<h1>Pre-night briefing</h1>",
        pn.Row(
            pn.Param(
                prenight,
                name="<h2>Parameters</h2>",
                widgets={"night": pn.widgets.DatePicker},
            ),
            pn.Column(
                "<h2>Astronomical Events</h2>",
                prenight.almanac_events_table,
            ),
        ),
        "<h2>Simulated Visits</h2>",
        pn.Row(
            prenight.visit_explorer,
            prenight.visit_table,
        ),
        prenight.visit_skymaps,
        debug_info,
    ).servable()

    def clear_caches(session_context):
        logging.info("session cleared")
        pn_app.stop()

    try:
        pn.state.on_session_destroyed(clear_caches)
    except RuntimeError as e:
        logging.info("RuntimeError: %s", e)

    return pn_app


if __name__ == "__main__":
    print("Starting prenight dashboard")
    pn.serve(
        prenight_app,
        port=8080,
        title="Prenight Dashboard",
        show=True,
        start=True,
        autoreload=True,
        threaded=True,
    )
