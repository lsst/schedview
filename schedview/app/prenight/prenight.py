import panel as pn
import logging
from copy import deepcopy
import pickle
import lzma
from tempfile import TemporaryDirectory, NamedTemporaryFile

import numpy as np
from astropy.time import Time

import rubin_sim
from rubin_sim.scheduler.model_observatory import ModelObservatory
import rubin_sim.scheduler.example
from rubin_sim.scheduler.utils import SchemaConverter

import schedview.compute.astro
import schedview.collect.opsim
import schedview.compute.scheduler
import schedview.collect.footprint
import schedview.plot.visitmap
import schedview.plot.rewards
import schedview.plot.visits
import schedview.plot.maf
import schedview.plot.nightbf

TEMP_DIR = TemporaryDirectory()
DEFAULT_TIMEZONE = "Chile/Continental"

pn.extension("tabulator", css_files=[pn.io.resources.CSS_URLS["font-awesome"]])

logging.basicConfig(format="%(asctime)s %(message)s", level=logging.DEBUG)


def prenight_app(
    observatory=ModelObservatory(),
    scheduler=None,
    observations=rubin_sim.data.get_baseline(),
    obs_night=None,
    reward_df=None,
    obs_rewards=None,
    timezone=DEFAULT_TIMEZONE,
    nside=None,
):
    """Create the prenight briefing app instance.

    Parameters
    ----------
    observatory : `ModelObservatory` or `None`
        The model observatory to use.
        By default, None.
    scheduler : `rubin_sim.scheduler.schedulers.core_scheduler.CoreScheduler`
        The scheduler instance to use.
    observations : `str`
        The name of the sqlite3 file with the simulation results.
        Defaults to the baseline as specified by the `rubin_sim` dependency.
    obs_night : `astropy.time.Time`
        The night for which to display data. Defaults to the last full night
        in observations.
    reward_df : `pandas.DataFrame` or `None`
        The rewards by survey, as recorded by the `scheduler` instance
        when running the simulation.
        Defaults to None.
    obs_rewards : `pandas.DataFrame` or `None`
        The mapping between scheduler calls and simulated observations,
        as recorded by the `scheduler` instance.
        Defaults to None.
    timezone : `str` or `None`
        The timezone to use for localtime.
    nside : `int` or `None`
        The nside to use for healpix maps to be shown.
    timezone : `str`, optional
        Timezone for horizontal axis, by default "Chile/Continental"

    Returns
    -------
    app : `panel.viewable.Viewable`
        The dashboard app.
    """

    if nside is None:
        try:
            nside = scheduler.nside
        except AttributeError:
            nside = observatory.nside

    if isinstance(observations, str):
        opsim_output_fname = observations
    else:
        # If we are passed an array of observations, write them to a file.
        converter = SchemaConverter()

        # Get a unique temp file name
        with NamedTemporaryFile(
            prefix="opsim-", suffix=".db", dir=TEMP_DIR.name
        ) as temp_file:
            opsim_output_fname = temp_file.name

        converter.obs2opsim(observations, filename=opsim_output_fname)

    if isinstance(scheduler, str) or scheduler is None:
        scheduler_fname = scheduler
    else:
        # Get a unique temp file name
        with NamedTemporaryFile(
            prefix="scheduler-", suffix=".pickle.xz", dir=TEMP_DIR.name
        ) as temp_file:
            scheduler_fname = temp_file.name

        with lzma.open(scheduler_fname, "wb", format=lzma.FORMAT_XZ) as pio:
            pickle.dump(scheduler, pio)

    site = observatory.location

    if obs_night is None:
        if isinstance(observations, str):
            # We were provided a database filename, not actual observations
            converter = SchemaConverter()
            observations = converter.opsim2obs(opsim_output_fname)

        end_mjd = observations["mjd"].max()
        if end_mjd > observatory.sky_model.mjd_right.max():
            # If we cannot look at the last night of the observations,
            # look at the first.
            end_mjd = observations["mjd"].min() + 1

        end_mjd_almanac = observatory.almanac.get_sunset_info(end_mjd)

        # If the last observation is in the first half (pm) of the night,
        # guess that we want to look at the night before. If the simulator
        # is configured to end on an integer mjd, it can happen that that
        # the start of a night is just after the mjd rollover, so we can
        # get just a few observations on the last night, and this last
        # night is probably not the one we want to look at.
        end_mjd_night_middle = 0.5 * (
            end_mjd_almanac["sunset"] + end_mjd_almanac["sunrise"]
        )
        if end_mjd < end_mjd_night_middle:
            end_mjd_almanac = observatory.almanac.get_sunset_info(end_mjd - 1)

        # Get the night MJD based on local noon of sunset.
        sunset_mjd_ut = end_mjd_almanac["sunset"]
        sunset_mjd_local = sunset_mjd_ut + site.lon.deg / 360
        sunset_night_mjd = np.floor(sunset_mjd_local)
        obs_night = Time(sunset_night_mjd, format="mjd", scale="utc")

    night = pn.widgets.DatePicker(name="Night", value=obs_night.datetime.date())
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
        name="Scheduler file name", value=scheduler_fname
    )
    opsim_output_fname = pn.widgets.TextInput(
        name="Opsim output", value=opsim_output_fname
    )

    visits_cache = {}
    scheduler_cache = {}

    def almanac_events(night, timezone):
        logging.info("Updating almanac.")
        night_time = Time(night.isoformat())
        almanac_events = schedview.compute.astro.night_events(
            night_time, site, timezone
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
            if scheduler_fname is None:
                scheduler = rubin_sim.scheduler.example.example_scheduler(nside=nside)
            else:
                (
                    scheduler,
                    conditions,
                ) = schedview.collect.scheduler_pickle.read_scheduler(scheduler_fname)

            scheduler_cache.clear()
            scheduler_cache[scheduler_fname] = scheduler
        else:
            scheduler = deepcopy(scheduler_cache[scheduler_fname])

        vmap, vmap_data = schedview.plot.visitmap.create_visit_skymaps(
            visits=visits,
            scheduler=scheduler,
            night_date=night_time,
            timezone=timezone,
            observatory=observatory,
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

    # ##########################
    # Basis function examination
    # ##########################

    if reward_df is not None:
        tier = pn.widgets.Select(
            name="Tier",
            options=reward_df.tier_label.unique().tolist(),
            value="tier 2",
            width_policy="fit",
        )

        # Survey selection
        surveys = pn.widgets.MultiSelect(
            name="Displayed surveys", options=["foo"], value=["foo"], width_policy="fit"
        )

        def configure_survey_selector(survey_selector, reward_df, tier):
            surveys = (
                reward_df.set_index("tier_label")
                .loc[tier, "survey_label"]
                .unique()
                .tolist()
            )
            survey_selector.options = surveys
            survey_selector.value = surveys[:10] if len(surveys) > 10 else surveys

        configure_survey_selector(surveys, reward_df, tier.value)

        def survey_selector_update_callback(surveys, event):
            new_tier = event.new
            configure_survey_selector(surveys, reward_df, new_tier)

        tier.link(surveys, {"value": survey_selector_update_callback})

        # Basis function selection

        basis_function = pn.widgets.Select(
            name="Reward (Total or basis function maximum)",
            options=["Total"],
            value="Total",
            width_policy="fit",
        )

        def configure_basis_function_selector(basis_function_selector, reward_df, tier):
            basis_functions = (
                reward_df.set_index("tier_label")
                .loc[tier, "basis_function"]
                .unique()
                .tolist()
            )
            basis_function_selector.options = ["Total"] + basis_functions
            basis_function_selector.value = "Total"

        configure_basis_function_selector(basis_function, reward_df, tier.value)

        def basis_function_selector_update_callback(basis_function, event):
            new_tier = event.new
            configure_basis_function_selector(basis_function, reward_df, new_tier)

        tier.link(basis_function, {"value": basis_function_selector_update_callback})

        reward_plot = pn.bind(
            schedview.plot.nightbf.plot_rewards,
            reward_df,
            tier,
            night,
            None,
            obs_rewards,
            surveys,
            basis_function,
            plot_kwargs={"width": 1024},
        )

        infeasible_plot = pn.bind(
            schedview.plot.nightbf.plot_infeasible,
            reward_df,
            tier,
            night,
            None,
            surveys,
            plot_kwargs={"width": 1024},
        )

    # Top level layout

    basic_app = pn.Column(
        '<script src="https://unpkg.com/gpu.js@latest/dist/gpu-browser.min.js"></script>',
        "<h1>Pre-night briefing</h1>",
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

    if reward_df is not None:
        reward_rows = pn.Column(
            "<h2>Reward values through the night</h2>",
            pn.Row(tier, surveys, basis_function),
            reward_plot,
            infeasible_plot,
        )
        app = pn.Column(basic_app, reward_rows)
    else:
        app = basic_app

    return app


if __name__ == "__main__":
    app = prenight_app()
    app.show()