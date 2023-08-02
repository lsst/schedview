import param
import logging
import numpy as np
import pandas as pd
import os

from astropy.time import Time
import astropy.utils.iers

from rubin_sim.scheduler.model_observatory import ModelObservatory
import rubin_sim.scheduler.example

import schedview.compute.astro
import schedview.collect.opsim
import schedview.compute.scheduler
import schedview.collect.footprint
import schedview.plot.visits
import schedview.plot.visitmap
import schedview.plot.rewards
import schedview.plot.visits
import schedview.plot.maf
import schedview.plot.nightbf
import schedview.param

import panel as pn

AVAILABLE_TIMEZONES = [
    "Chile/Continental",
    "US/Pacific",
    "US/Arizona",
    "US/Mountain",
    "US/Central",
    "US/Eastern",
]
DEFAULT_TIMEZONE = AVAILABLE_TIMEZONES[0]
DEFAULT_CURRENT_TIME = Time.now()
DEFAULT_OPSIM_FNAME = "opsim.db"
DEFAULT_SCHEDULER_FNAME = "scheduler.pickle.xz"
DEFAULT_REWARDS_FNAME = "rewards.h5"
USE_EXAMPLE_SCHEDULER = False

astropy.utils.iers.conf.iers_degraded_accuracy = "warn"

pn.extension(
    "tabulator",
    css_files=[pn.io.resources.CSS_URLS["font-awesome"]],
    sizing_mode="stretch_width",
)
pn.config.console_output = "accumulate"

logging.basicConfig(format="%(asctime)s %(message)s", level=logging.INFO)

debug_info = pn.widgets.Debugger(
    name="Debugger info level", level=logging.DEBUG, sizing_mode="stretch_both"
)


class Prenight(param.Parameterized):
    opsim_output_fname = param.String(
        default=DEFAULT_OPSIM_FNAME,
        doc="The file name or URL of the OpSim output database.",
        label="OpSim output database path or URL",
    )

    scheduler_fname_doc = """URL or file name of the scheduler pickle file.
Such a pickle file can either be of an instance of a subclass of
rubin_sim.scheduler.schedulers.CoreScheduler, or a tuple of the form
(scheduler, conditions), where scheduler is an instance of a subclass of
rubin_sim.scheduler.schedulers.CoreScheduler, and conditions is an
instance of rubin_sim.scheduler.conditions.Conditions."""
    scheduler_fname = param.String(
        default=DEFAULT_SCHEDULER_FNAME,
        doc=scheduler_fname_doc,
        label="URL or file name of scheduler pickle file",
    )

    rewards_fname = param.String(
        default=DEFAULT_REWARDS_FNAME,
        doc="URL or file name of the rewards HDF5 file.",
        label="URL or file name of rewards HDF5 file",
    )

    # Express the night as an instance of datetime.date, so that it can be
    # used with the panel.widgets.DatePicker widget.
    # It represents the local calendar date of sundown for the night to view.
    night = param.Date(
        default=DEFAULT_CURRENT_TIME.datetime.date(),
        doc="The local calendar date of sundown for the night to view.",
        label="Night to view (local time at sunset)",
    )

    timezone = param.ObjectSelector(
        objects=AVAILABLE_TIMEZONES,
        default=DEFAULT_TIMEZONE,
        doc='The timezone in which "local time" is to be shown.',
        label="Timezone",
    )

    tier = param.ObjectSelector(
        default="",
        objects=[""],
        doc="The label for the first index into the CoreScheduler.survey_lists.",
        label="Tier",
    )
    surveys = param.ListSelector(
        objects=[],
        default=[],
        doc="The labels for the second index into the CoreScheduler.survey_lists.",
        label="Surveys",
    )
    basis_function = param.ObjectSelector(
        default="",
        objects=[""],
        doc="The label for the basis function to be shown.",
        label="Basis function",
    )

    _observatory = ModelObservatory()
    _site = _observatory.location
    # Must declare all of these as Parameters, even though they should not
    # be set by the user, because they are used in the @depends methods,
    # and otherwise Parametrized will assume that they depend on
    # everything.
    _visits = schedview.param.DataFrame(
        None,
        doc="The visits for the night.",
        columns={
            "fieldRA": float,
            "fieldDec": float,
            "observationStartMJD": float,
            "filter": str,
            "rotSkyPos": float,
            "rotSkyPos_desired": float,
        },
    )

    # An instance of rubin_sim.scheduler.schedulers.CoreScheduler
    _scheduler = param.Parameter()

    _almanac_events = schedview.param.DataFrame(
        None,
        doc="Events from the rubin_sim alamanc",
        columns={"MJD": float, "LST": float, "UTC": pd.Timestamp},
    )

    _reward_df = schedview.param.DataFrame(
        None,
        columns={
            "basis_function": str,
            "feasible": np.bool_,
            "max_basis_reward": float,
            "basis_area": float,
            "basis_weight": float,
            "tier_label": str,
            "survey_label": str,
            "survey_class": str,
            "survey_reward": float,
            "basis_function_class": object,
            "queue_start_mjd": float,
            "queue_fill_mjd_ns": np.int64,
        },
    )
    _obs_rewards = schedview.param.Series()

    @param.depends("night", "timezone", watch=True)
    def _update_almanac_events(self):
        logging.info("Updating almanac events.")
        night_events = schedview.compute.astro.night_events(
            self.night, self._site, self.timezone
        )

        # Bokeh automatically converts all datetimes to UTC
        # when displaying, which we do not want. So, turn the localized
        # datetimes to naive datetimes so bokeh leaves them alone.
        night_events[self.timezone] = night_events[self.timezone].dt.tz_localize(None)

        self._almanac_events = night_events

    @param.depends("_almanac_events")
    def almanac_events_table(self):
        if self._almanac_events is None:
            return "No almanac events computed."

        logging.info("Updating almanac table.")
        almanac_table = pn.widgets.Tabulator(self._almanac_events)
        return almanac_table

    @param.depends("opsim_output_fname", "_almanac_events", watch=True)
    def _update_visits(self):
        if self.opsim_output_fname is None:
            self._visits = None
            return

        if self._almanac_events is None:
            self._update_almanac_events()

        logging.info("Updating visits.")
        try:
            if not os.path.exists(self.opsim_output_fname):
                raise FileNotFoundError(f"File not found: {self.opsim_output_fname}")

            visits = schedview.collect.opsim.read_opsim(
                self.opsim_output_fname,
                Time(self._almanac_events.loc["sunset", "UTC"]),
                Time(self._almanac_events.loc["sunrise", "UTC"]),
            )
            self._visits = visits
        except Exception as e:
            logging.error(e)
            self._visits = None

    @param.depends("_visits")
    def visit_table(self):
        """Create a tabuler display widget with visits.

        Returns
        -------
        visit_table : `pn.widgets.Tabulator`
            The table of visits.
        """
        if self._visits is None:
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

        visit_table = pn.widgets.Tabulator(self._visits[columns])

        if len(self._visits) < 1:
            visit_table = "No visits on this night"

        logging.info("Finished updating visit table")
        return visit_table

    @param.depends("_visits")
    def visit_explorer(self):
        """Create holoviz explorer on the visits.

        Returns
        -------
        visit_explorer : `hvplot.ui.hvDataFrameExplorer`
            The holoviz plot of visits.
        """
        if self._visits is None:
            return "No visits loaded."

        logging.info("Updating visit explorer")

        (
            visit_explorer,
            visit_explorer_data,
        ) = schedview.plot.visits.create_visit_explorer(
            visits=self._visits,
            night_date=self.night,
        )

        if len(visit_explorer_data["visits"]) < 1:
            visit_explorer = "No visits on this night."

        logging.info("Finished updating visit explorer")

        return visit_explorer

    @param.depends("scheduler_fname", watch=True)
    def _update_scheduler(self):
        logging.info("Updating scheduler.")
        try:
            (
                scheduler,
                conditions,
            ) = schedview.collect.scheduler_pickle.read_scheduler(self.scheduler_fname)

            self._scheduler = scheduler
        except Exception as e:
            logging.error(f"Could not load scheduler from {self.scheduler_fname} {e}")
            if USE_EXAMPLE_SCHEDULER:
                logging.info("Loading example scheduler.")
                self._scheduler = rubin_sim.scheduler.example.example_scheduler(
                    nside=self._nside
                )

    @param.depends(
        "_scheduler",
        "_visits",
    )
    def visit_skymaps(self):
        """Create an interactive skymap of the visits.

        Returns
        -------
        vmap : `bokeh.models.layouts.LayoutDOM`
            The bokeh maps of visits.
        """

        if self._visits is None:
            return "No visits are loaded."

        if self._scheduler is None:
            return "No scheduler is loaded."

        logging.info("Updating skymaps")

        vmap, vmap_data = schedview.plot.visitmap.create_visit_skymaps(
            visits=self._visits,
            scheduler=self._scheduler,
            night_date=self.night,
            timezone=self.timezone,
            observatory=self._observatory,
        )

        if len(vmap_data["visits"]) < 1:
            vmap = "No visits on this night."

        logging.info("Finished updating skymaps")

        return vmap

    @param.depends("rewards_fname", watch=True)
    def _update_reward_df(self):
        if self.rewards_fname is None:
            return None

        logging.info("Updating reward dataframe.")

        try:
            reward_df = pd.read_hdf(self.rewards_fname, "reward_df")
        except Exception as e:
            logging.error(e)

        self._reward_df = reward_df

    @param.depends("_reward_df", watch=True)
    def _update_tier_selector(self):
        if self._reward_df is None:
            self.param["tier"].objects = [""]
            self.tier = ""
            return

        logging.info("Updating tier selector.")
        tiers = self._reward_df.tier_label.unique().tolist()
        self.param["tier"].objects = tiers
        self.tier = tiers[0]

    @param.depends("_reward_df", "tier", watch=True)
    def _update_surveys_selector(self):
        init_displayed_surveys = 7

        if self._reward_df is None or self.tier == "":
            self.param["surveys"].objects = [""]
            self.surveys = ""
            return

        logging.info("Updating surveys selector.")

        surveys = (
            self._reward_df.set_index("tier_label")
            .loc[self.tier, "survey_label"]
            .unique()
            .tolist()
        )
        self.param["surveys"].objects = surveys
        self.surveys = (
            surveys[:init_displayed_surveys]
            if len(surveys) > init_displayed_surveys
            else surveys
        )

    @param.depends("_reward_df", "tier", "surveys", watch=True)
    def _update_basis_function_selector(self):
        if self._reward_df is None or self.tier == "" or self.surveys == "":
            self.param["basis_function"].objects = [""]
            self.basis_function = ""
            return

        logging.info("Updating basis function selector.")

        tier_reward_df = self._reward_df.set_index("tier_label").loc[self.tier, :]

        basis_functions = ["Total"] + (
            tier_reward_df.set_index("survey_label")
            .loc[self.surveys, "basis_function"]
            .unique()
            .tolist()
        )
        self.param["basis_function"].objects = basis_functions
        self.basis_function = "Total"

    @param.depends("rewards_fname", watch=True)
    def _update_obs_rewards(self):
        if self.rewards_fname is None:
            return None

        try:
            obs_rewards = pd.read_hdf(self.rewards_fname, "obs_rewards")
        except Exception as e:
            logging.error(e)

        self._obs_rewards = obs_rewards

    @param.depends("_reward_df", "tier")
    def reward_params(self):
        """Create a param set for the reward plot.

        Returns
        -------
        param_set : `panel.Param`
        """
        if self._reward_df is None:
            this_param_set = pn.Param(
                self.param,
                parameters=["rewards_fname"],
            )
            return this_param_set

        if len(self.param["surveys"].objects) > 10:
            survey_widget = pn.widgets.CrossSelector
        else:
            survey_widget = pn.widgets.MultiSelect

        this_param_set = pn.Param(
            self.param,
            parameters=["rewards_fname", "tier", "basis_function", "surveys"],
            default_layout=pn.Row,
            name="",
            widgets={"surveys": survey_widget},
        )
        return this_param_set

    @param.depends(
        "_reward_df",
        "tier",
        "_obs_rewards",
        "night",
        "surveys",
        "basis_function",
    )
    def reward_plot(self):
        """Create a plot of the rewards.

        Returns
        -------
        fig : `bokeh.plotting.Figure`
            The figure with the reward plot.
        """
        if self._reward_df is None:
            return "No rewards are loaded."

        fig = schedview.plot.nightbf.plot_rewards(
            reward_df=self._reward_df,
            tier_label=self.tier,
            night=self.night,
            observatory=self._observatory,
            obs_rewards=self._obs_rewards,
            surveys=self.surveys,
            basis_function=self.basis_function,
            plot_kwargs={},
        )
        return fig

    @param.depends(
        "_reward_df",
        "tier",
        "_obs_rewards",
        "night",
        "surveys",
    )
    def infeasible_plot(self):
        """Create a plot of infeasible basis functions.

        Returns
        -------
        fig : `bokeh.plotting.Figure`
            The figure..
        """
        if self._reward_df is None:
            return "No rewards are loaded."

        fig = schedview.plot.nightbf.plot_infeasible(
            reward_df=self._reward_df,
            tier_label=self.tier,
            night=self.night,
            observatory=self._observatory,
            surveys=self.surveys,
        )
        return fig


def prenight_app(
    night_date=None, observations=None, scheduler=None, rewards=None, return_app=False
):
    """Create the pre-night briefing app.

    Parameters
    ----------
    night_date : `datetime.date`, optional
        The date of the night to display.
    observations : `str`, optional
        Path to the opsim output databas file.
    scheduler : `str`, optional
        Path to the scheduler pickle file.
    rewards : `str`, optional
        Path to the rewards hdf5 file.
    return_app : `bool`, optional
        Return the instances of the app class itself.

    Returns
    -------
    pn_app : `panel.viewable.Viewable` or
            `tuple` ['panel.viewable.Viewable', `schedview.prenight.Prenight`]
        The pre-night briefing app.
    """
    prenight = Prenight()

    # Rather than set each parameter one at a time, and execute the callbacks
    # for each as they are set, we can use the batch_call_watchers context
    # manager to set all the parameters at once, and only execute the callbacks
    # once.
    with param.parameterized.batch_call_watchers(prenight):
        if night_date is not None:
            prenight.night = night_date

        if observations is not None:
            prenight.opsim_output_fname = observations

        if scheduler is not None:
            prenight.scheduler_fname = scheduler

        if rewards is not None:
            prenight.rewards_fname = rewards

    pn_app = pn.Column(
        "<h1>Pre-night briefing</h1>",
        pn.Row(
            pn.Param(
                prenight,
                parameters=[
                    "night",
                    "timezone",
                    "scheduler_fname",
                    "opsim_output_fname",
                ],
                name="<h2>Parameters</h2>",
                widgets={"night": pn.widgets.DatePicker},
            ),
            pn.Column(
                "<h2>Astronomical Events</h2>",
                pn.param.ParamMethod(
                    prenight.almanac_events_table, loading_indicator=True
                ),
            ),
        ),
        pn.Tabs(
            (
                "Visit explorer",
                pn.param.ParamMethod(prenight.visit_explorer, loading_indicator=True),
            ),
            (
                "Table of visits",
                pn.param.ParamMethod(prenight.visit_table, loading_indicator=True),
            ),
            (
                "Sky maps",
                pn.param.ParamMethod(prenight.visit_skymaps, loading_indicator=True),
            ),
            (
                "Reward plots",
                pn.Column(
                    pn.param.ParamMethod(
                        prenight.reward_params, loading_indicator=True
                    ),
                    pn.param.ParamMethod(prenight.reward_plot, loading_indicator=True),
                    pn.param.ParamMethod(
                        prenight.infeasible_plot, loading_indicator=True
                    ),
                ),
            ),
            dynamic=False,  # When true, visit_table never renders. Why?
        ),
        debug_info,
    ).servable()

    def clear_caches(session_context):
        logging.info("session cleared")
        pn_app.stop()

    try:
        pn.state.on_session_destroyed(clear_caches)
    except RuntimeError as e:
        logging.info("RuntimeError: %s", e)

    if return_app:
        return pn_app, prenight
    else:
        return pn_app


if __name__ == "__main__":
    print("Starting prenight dashboard")

    if "PRENIGHT_PORT" in os.environ:
        prenight_port = int(os.environ["PRENIGHT_PORT"])
    else:
        prenight_port = 8080

    pn.serve(
        prenight_app,
        port=prenight_port,
        title="Prenight Dashboard",
        show=True,
        start=True,
        autoreload=True,
        threaded=True,
    )
