import param
import logging
import pandas as pd
import os

from astropy.time import Time

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


pn.extension(
    "tabulator",
    css_files=[pn.io.resources.CSS_URLS["font-awesome"]],
    sizing_mode="stretch_width",
)
pn.config.console_output = "disable"

logging.basicConfig(format="%(asctime)s %(message)s", level=logging.INFO)

debug_info = pn.widgets.Debugger(
    name="Debugger info level", level=logging.DEBUG, sizing_mode="stretch_both"
)


class Prenight(param.Parameterized):

    opsim_output_fname = param.String(DEFAULT_OPSIM_FNAME)
    scheduler_fname = param.String(DEFAULT_SCHEDULER_FNAME)
    rewards_fname = param.String(DEFAULT_REWARDS_FNAME)

    night = param.Date(DEFAULT_CURRENT_TIME.datetime.date())
    timezone = param.ObjectSelector(
        objects=AVAILABLE_TIMEZONES,
        default=DEFAULT_TIMEZONE,
    )
    tier = param.ObjectSelector(default="", objects=[""])
    surveys = param.ListSelector(objects=[], default=[])
    basis_function = param.ObjectSelector(default="", objects=[""])

    _observatory = ModelObservatory()
    _site = _observatory.location
    # Must declare all of these as Parameters, even though they should not
    # be set by the user, because they are used in the @depends methods,
    # and otherwise Parametrized will assume that they depend on
    # everything.
    _visits = param.Parameter(None)
    _scheduler = param.Parameter(None)
    _almanac_events = param.Parameter(None)
    _night_time = param.Parameter(None)
    _sunset_time = param.Parameter(None)
    _sunrise_time = param.Parameter(None)
    _reward_df = param.Parameter(None)
    _obs_rewards = param.Parameter(None)

    @param.depends("night", watch=True)
    def _update_night_time(self):
        logging.info("Updating night time.")
        self._night_time = Time(self.night.isoformat())

    @param.depends("_night_time", "timezone", watch=True)
    def _update_almanac_events(self):
        logging.info("Updating almanac events.")
        self._almanac_events = schedview.compute.astro.night_events(
            self._night_time, self._site, self.timezone
        )

    @param.depends("_almanac_events", watch=True)
    def _update_sunset_time(self):
        logging.info("Updating sunset time.")
        self._sunset_time = Time(self._almanac_events.loc["sunset", "UTC"])

    @param.depends("_almanac_events", watch=True)
    def _update_sunrise_time(self):
        logging.info("Updating sunrise time.")
        self._sunrise_time = Time(self._almanac_events.loc["sunrise", "UTC"])

    @param.depends("_almanac_events")
    def almanac_events_table(self):
        if self._almanac_events is None:
            return "No almanac events computed."

        logging.info("Updating almanac table.")
        almanac_table = pn.widgets.DataFrame(self._almanac_events)
        return almanac_table

    @param.depends("opsim_output_fname", "_sunset_time", "_sunrise_time", watch=True)
    def _update_visits(self):
        if self._almanac_events is None:
            self._update_almanac_events()

        logging.info("Updating visits.")
        try:
            visits = schedview.collect.opsim.read_opsim(
                self.opsim_output_fname, self._sunset_time.iso, self._sunrise_time.iso
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
        visit_table : `pn.widgets.DataFrame`
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

        visit_table = pn.widgets.DataFrame(self._visits[columns])

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
            night_date=self._night_time,
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
            night_date=self._night_time,
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


def prenight_app(night_date=None, observations=None, scheduler=None, rewards=None):
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

    Returns
    -------
    pn_app : `panel.viewable.Viewable`
        The pre-night briefing app.
    """
    prenight = Prenight()

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
