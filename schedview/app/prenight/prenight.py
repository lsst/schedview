import warnings
from tempfile import TemporaryDirectory

import numpy as np
import panel as pn
import holoviews as hv
import hvplot
import hvplot.pandas
import bokeh.models.layouts
import logging
from copy import deepcopy

from astropy.time import Time

import rubin_sim
from rubin_sim.scheduler.model_observatory import ModelObservatory

import schedview.compute.astro
import schedview.collect.opsim
import schedview.compute.scheduler
import schedview.collect.footprint
import schedview.plot.visitmap
import schedview.plot.rewards
import schedview.plot.visits
import schedview.plot.maf

# SCHEDULER_FNAME = "/home/n/neilsen/devel/schedview/schedview/data/baseline.pickle.gz"
SCHEDULER_FNAME = (
    "/sdf/data/rubin/user/neilsen/devel/schedview/schedview/data/baseline.pickle.gz"
)
OPSIM_OUTPUT_FNAME = rubin_sim.data.get_baseline()
NIGHT = Time("2023-10-04", scale="utc")
TIMEZONE = "Chile/Continental"
OBSERVATORY = ModelObservatory()
SITE = OBSERVATORY.location

pn.extension("tabulator", css_files=[pn.io.resources.CSS_URLS["font-awesome"]])

logging.basicConfig(format="%(asctime)s %(message)s", level=logging.DEBUG)


def prenight_app():
    night = pn.widgets.DatePicker(name="Night", value=NIGHT.datetime.date())
    timezone = pn.widgets.Select(
        name="Timezone",
        options=[
            "Chile/Continental",
            "US/Pacific",
            "US/Arizona",
            "US/Mountain",
            "US/Central",
            "US/Eastern",
        ],
    )
    scheduler_fname = pn.widgets.TextInput(
        name="Scheduler file name", value=SCHEDULER_FNAME
    )
    opsim_output_fname = pn.widgets.TextInput(
        name="Opsim output", value=OPSIM_OUTPUT_FNAME
    )

    visits_cache = {}
    scheduler_cache = {}

    def almanac_events(night, timezone):
        logging.info("Updating almanac.")
        night_time = Time(night.isoformat())
        almanac_events = schedview.compute.astro.night_events(
            night_time, SITE, timezone
        )
        almanac_events[timezone] = almanac_events[timezone].dt.tz_localize(None)
        almanac_table = pn.widgets.Tabulator(almanac_events)
        logging.info("Finished updating almanac.")
        return almanac_table

    def visit_explorer(opsim_output_fname, night):
        logging.info("Updating visit explorer")
        night_time = Time(night.isoformat())

        visits_cache_key = (opsim_output_fname, night_time)
        visits = visits_cache.get(visits_cache_key, opsim_output_fname)

        (
            visit_explorer,
            visit_explorer_data,
        ) = schedview.plot.visits.create_visit_explorer(
            visits=visits,
            night_date=night_time,
        )

        visits_cache.clear()
        visits_cache[visits_cache_key] = visit_explorer_data["visits"]

        if len(visit_explorer_data["visits"]) < 1:
            visit_explorer = "No visits on this night."

        logging.info("Finished updating visit explorer")

        return visit_explorer

    def visit_skymaps(opsim_output_fname, scheduler_fname, night, timezone="UTC"):
        logging.info("Updating skymaps")
        night_time = Time(night.isoformat())

        visits_cache_key = (opsim_output_fname, night_time)
        visits = visits_cache.get(visits_cache_key, opsim_output_fname)

        if scheduler_fname not in scheduler_cache:
            scheduler, conditions = schedview.collect.scheduler_pickle.read_scheduler(
                scheduler_fname
            )
            scheduler_cache.clear()
            scheduler_cache[scheduler_fname] = scheduler
        else:
            scheduler = deepcopy(scheduler_cache[scheduler_fname])

        vmap, vmap_data = schedview.plot.visitmap.create_visit_skymaps(
            visits=visits,
            scheduler=scheduler,
            night_date=night_time,
            timezone=timezone,
            observatory=OBSERVATORY,
        )

        visits_cache.clear()
        visits_cache[visits_cache_key] = vmap_data["visits"]

        if len(vmap_data["visits"]) < 1:
            vmap = "No visits on this night."

        logging.info("Finished updating skymaps")

        return vmap

    def visit_table(opsim_output_fname, night, timezone="UTC"):
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

        night_time = Time(night.isoformat())

        visits_cache_key = (opsim_output_fname, night_time)
        visits = visits_cache.get(visits_cache_key, opsim_output_fname)

        site = SITE
        night_events = schedview.compute.astro.night_events(
            night_date=night_time, site=site, timezone=timezone
        )
        start_time = Time(night_events.loc["sunset", "UTC"])
        end_time = Time(night_events.loc["sunrise", "UTC"])

        # Collect
        if isinstance(visits, str):
            visits = schedview.collect.opsim.read_opsim(
                visits, Time(start_time).iso, Time(end_time).iso
            )

        visits_cache.clear()
        visits_cache[visits_cache_key] = visits

        visit_table = pn.widgets.Tabulator(visits[columns])

        if len(visits) < 1:
            visit_table = "No visits on this night"
        logging.info("Finished updating visit table")
        return visit_table

    app = pn.Column(
        f'<script src="https://unpkg.com/gpu.js@latest/dist/gpu-browser.min.js"></script>',
        f"<h1>Pre-night briefing</h1>",
        pn.pane.PNG(
            "https://project.lsst.org/sites/default/files/Rubin-O-Logo_0.png", height=50
        ),
        "<h2>Parameters</h2>",
        night,
        timezone,
        scheduler_fname,
        opsim_output_fname,
        "<h2>Astronomical Events</h2>",
        pn.Row(pn.bind(almanac_events, night, timezone)),
        "<h2>Simulated visits</h2>",
        pn.Row(pn.bind(visit_explorer, opsim_output_fname, night)),
        pn.Row(pn.bind(visit_table, opsim_output_fname, night)),
        pn.Row(pn.bind(visit_skymaps, opsim_output_fname, scheduler_fname, night)),
    )

    return app


if __name__ == "__main__":
    app = prenight_app()
    app.show()
