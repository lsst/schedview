import bokeh.core.properties
import bokeh.models
import bokeh.plotting
import pandas as pd
from astropy.time import Time
from rubin_sim.scheduler.example import example_scheduler
from rubin_sim.scheduler.model_observatory import ModelObservatory
from uranography.api import ArmillarySphere, HorizonMap, MollweideMap, Planisphere

from schedview.collect import read_scheduler, sample_pickle
from schedview.plot.scheduler import DEFAULT_MJD, DEFAULT_NSIDE, LOGGER, SchedulerDisplay


class SchedulerDisplayApp(SchedulerDisplay):
    include_mollweide = False

    def make_pickle_entry_box(self):
        """Make the entry box for a file name from which to load state."""
        file_input_box = bokeh.models.TextInput(
            value=sample_pickle() + " ",
            title="Pickle path:",
        )

        # Need a bokeh model we can use to send a callback to to get the
        # browser to show an error. See
        # https://discourse.bokeh.org/t/send-user-warning-messages-on-python-error/6750
        file_read_status = bokeh.models.Div(name="file read status", text="Initial", visible=False)
        code = 'if (file_read_status.text.startsWith("Could not read")) {alert(file_read_status.text); }'
        file_read_status.js_on_change(
            "text",
            bokeh.models.callbacks.CustomJS(args={"file_read_status": file_read_status}, code=code),
        )

        def switch_pickle(attrname, old, new):
            def do_switch_pickle():
                LOGGER.info(f"Loading {new}.")
                file_read_status.text = f"Read of {new} in progress."
                try:
                    # load updates the survey & conditions, which updates
                    # bokeh models...
                    self.load(new)
                    file_read_status.text = "Read {new} successfully."
                except Exception as e:
                    LOGGER.warning(f"Failed to load file {new}: {e}")
                    file_read_status.text = f"Could not read {new}: {e}"

                LOGGER.debug(f"Finished loading {new}")

                # If we do not have access to the document, this won't
                # do anything and is unnecessary, but that's okay.
                self.enable_controls()

            if file_input_box.document is None:
                # If we don't have access to the document, we can't disable
                # the controls, so just do it.
                do_switch_pickle()
            else:
                # disable the controls, and ask the document to do the update
                # on the following event look tick.
                self.disable_controls("Switching pickle.")
                file_input_box.document.add_next_tick_callback(do_switch_pickle)

        file_input_box.on_change("value", switch_pickle)
        self.bokeh_models["file_input_box"] = file_input_box

        self.bokeh_models["file_read_status"] = file_read_status

    def _set_scheduler(self, scheduler):
        LOGGER.info("Setting scheduler")
        super()._set_scheduler(scheduler)
        self.update_tier_selector()
        self.update_reward_summary_table_bokeh_model()

    def _set_conditions(self, conditions):
        super()._set_conditions(conditions)
        self.update_healpix_bokeh_model()
        self.update_reward_table_bokeh_model()
        self.update_reward_summary_table_bokeh_model()
        self.update_hovertool_bokeh_model()
        self.update_telescope_marker_bokeh_model()
        self.update_moon_marker_bokeh_model()
        self.update_sun_marker_bokeh_model()
        self.update_survey_marker_bokeh_model()
        self.update_chosen_survey_bokeh_model()
        self.update_mjd_slider_bokeh_model()
        self.update_time_input_box_bokeh_model()

    def make_time_selector(self):
        """Create the time selector slider bokeh model."""
        time_selector = bokeh.models.Slider(
            title="MJD",
            start=self.mjd - 1,
            end=self.mjd + 1,
            value=self.mjd,
            step=1.0 / 1440,
        )

        def switch_time(attrname, old, new):
            if time_selector.document is None:
                # If we don't have access to the document, we can't disable
                # the controls, so don't try.
                self.mjd = new
            else:
                # To disable controls as the time is being updated, we need to
                # separate the callback so it happens in two event loop ticks:
                # the first tick disables the controls, the next one
                # actually updates the MJD and then re-enables the controls.
                def do_switch_time():
                    self.mjd = new
                    self.enable_controls()

                self.disable_controls("Updating for new time.")
                time_selector.document.add_next_tick_callback(do_switch_time)

        time_selector.on_change("value_throttled", switch_time)
        self.bokeh_models["time_selector"] = time_selector
        self.update_time_selector_bokeh_model()

    def update_time_selector_bokeh_model(self):
        """Update the time selector limits and value to match the date."""
        if "time_selector" in self.bokeh_models:
            self.bokeh_models["time_selector"].start = self.conditions.sun_n12_setting
            self.bokeh_models["time_selector"].end = self.conditions.sun_n12_rising
            self.bokeh_models["time_selector"].value = self.conditions.mjd

    def add_mjd_slider_callback(self):
        """Create the mjd slider bokeh model."""
        mjd_slider = self.bokeh_models["mjd_slider"]

        def switch_time(attrname, old, new):
            if mjd_slider.document is None:
                # If we don't have access to the document, we can't disable
                # the controls, so don't try.
                self.mjd = new
            else:
                # To disable controls as the time is being updated, we need to
                # separate the callback so it happens in two event loop ticks:
                # the first tick disables the controls, the next one
                # actually updates the MJD and then re-enables the controls.
                def do_switch_time():
                    self.mjd = new
                    self.enable_controls()

                self.disable_controls("Updating for new MJD.")
                mjd_slider.document.add_next_tick_callback(do_switch_time)

        mjd_slider.on_change("value_throttled", switch_time)
        self.update_time_selector_bokeh_model()

    def update_mjd_slider_bokeh_model(self):
        """Update the time selector limits and value to match the date."""
        if "mjd_slider" in self.bokeh_models:
            self.bokeh_models["mjd_slider"].start = self.conditions.sun_n12_setting
            self.bokeh_models["mjd_slider"].end = self.conditions.sun_n12_rising
            self.bokeh_models["mjd_slider"].value = self.conditions.mjd

    def make_time_input_box(self):
        """Create the time entry box bokeh model."""
        time_input_box = bokeh.models.TextInput(title="Date and time (UTC):")
        self.bokeh_models["time_input_box"] = time_input_box
        self.update_time_input_box_bokeh_model()

        def switch_time(attrname, old, new):
            new_mjd = pd.to_datetime(new, utc=True).to_julian_date() - 2400000.5

            if time_input_box.document is None:
                # If we don't have access to the document, we can't disable
                # the controls, so don't try.
                self.mjd = new_mjd
            else:
                # To disable controls as the time is being updated, we need to
                # separate the callback so it happens in two event loop ticks:
                # the first tick disables the controls, the next one
                # actually updates the MJD and then re-enables the controls.
                def do_switch_time():
                    self.mjd = new_mjd
                    self.enable_controls()

                self.disable_controls("Changing time.")
                time_input_box.document.add_next_tick_callback(do_switch_time)

        time_input_box.on_change("value", switch_time)

    def update_time_input_box_bokeh_model(self):
        """Update the time selector limits and value to match the date."""
        if "time_input_box" in self.bokeh_models:
            iso_time = Time(self.mjd, format="mjd", scale="utc").iso
            self.bokeh_models["time_input_box"].value = iso_time

    def make_tier_selector(self):
        """Create the tier selector bokeh model."""
        tier_selector = bokeh.models.Select(value=None, options=[None])

        def switch_tier(attrname, old, new):
            self.select_tier(new)

        tier_selector.on_change("value", switch_tier)
        self.bokeh_models["tier_selector"] = tier_selector
        self.update_tier_selector()

    def update_tier_selector(self):
        """Update tier selector to represent tiers for the current survey."""
        if "tier_selector" in self.bokeh_models:
            options = self.tier_names
            self.bokeh_models["tier_selector"].options = options
            self.bokeh_models["tier_selector"].value = options[self.survey_index[0]]

    def select_tier(self, tier):
        """Set the tier being displayed."""
        super().select_tier(tier)
        self.update_survey_selector()

    def make_survey_selector(self):
        """Create the survey selector bokeh model."""
        survey_selector = bokeh.models.Select(value=None, options=[None])

        def switch_survey(attrname, old, new):
            self.select_survey(new)

        survey_selector.on_change("value", switch_survey)
        self.bokeh_models["survey_selector"] = survey_selector

    def update_survey_selector(self):
        """Uptade the survey selector to the current scheduler and tier."""
        if "survey_selector" in self.bokeh_models:
            options = [
                self._unique_survey_name([self.survey_index[0], s])
                for s in range(len(self.scheduler.survey_lists[self.survey_index[0]]))
            ]
            self.bokeh_models["survey_selector"].options = options
            self.bokeh_models["survey_selector"].value = options[self.survey_index[1]]

    def select_survey(self, survey):
        """Set the tier being displayed."""
        super().select_survey(survey)
        # Note that updating the value selector triggers the
        # callback, which updates the maps themselves
        self.update_value_selector()
        self.update_reward_table_bokeh_model()
        self.update_hovertool_bokeh_model()
        self.update_survey_marker_bokeh_model()

    def make_value_selector(self):
        """Create the bokeh model to select which value to show in maps."""
        value_selector = bokeh.models.Select(value=None, options=[None])

        def switch_value(attrname, old, new):
            self.select_value(new)

        value_selector.on_change("value", switch_value)
        self.bokeh_models["value_selector"] = value_selector

    def update_value_selector(self):
        """Update the value selector bokeh model to show available options."""
        if "value_selector" in self.bokeh_models:
            self.bokeh_models["value_selector"].options = self.map_keys
            if self.map_key in self.map_keys:
                self.bokeh_models["value_selector"].value = self.map_key
            elif self.init_key in self.map_keys:
                self.bokeh_models["value_selector"].value = self.init_key
            else:
                self.bokeh_models["value_selector"].value = self.map_keys[-1]

    def select_value(self, map_key):
        """Set the tier being displayed."""
        super().select_value(map_key)
        self.update_healpix_bokeh_model()

    def update_time_display_bokeh_model(self):
        """Update the value of the displayed time."""
        if "mjd" in self.sliders:
            self.update_mjd_slider_bokeh_model()

        if "time_input_box" in self.bokeh_models:
            self.update_time_input_box_bokeh_model()

    def update_displayed_value_metadata_bokeh_model(self):
        self.update_tier_selector()

    def _select_survey_from_summary_table(self, attr, old, new):
        LOGGER.debug("Called select_survey_from_summary_table")
        selected_index = new[0]
        tier_name = self.data_sources["reward_summary_table"].data["tier"][selected_index]
        survey_name = self.data_sources["reward_summary_table"].data["survey_name"][selected_index]

        # Update the selectors, and this will run
        # the callbacks to do all the updates
        self.bokeh_models["tier_selector"].value = tier_name
        self.bokeh_models["survey_selector"].value = survey_name

    def make_reward_summary_table(self):
        super().make_reward_summary_table()

        self.data_sources["reward_summary_table"].selected.on_change(
            "indices",
            self._select_survey_from_summary_table,
        )

    def disable_controls(self, message="Busy"):
        """Disable all controls.

        Intended to be used while plot elements are updating, and the
        control therefore do not do what the user probably intends.

        Parameters
        ----------
        message : `str`
            Message to display in status indicator.
        """
        LOGGER.info("Disabling controls")

        try:
            text = f"""<h1>Dashboard Status</h1>
                <p style="font-weight: bold; font-size: large; background-color:red">
                {message}
                </p>"""
            self.bokeh_models["status_indicator"].text = text
        except KeyError:
            pass

        for model in self.bokeh_models.values():
            try:
                model.disabled = True
            except AttributeError:
                pass

    def enable_controls(self):
        """Enable all controls."""
        LOGGER.info("Enabling controls")
        for model in self.bokeh_models.values():
            try:
                model.disabled = False
            except AttributeError:
                pass

        try:
            self.bokeh_models["status_indicator"].text = "<p></p>"
        except KeyError:
            pass

    def make_figure(self):
        """Create a bokeh figures showing sky maps for scheduler behavior.

        Returns
        -------
        fig : `bokeh.models.layouts.LayoutDOM`
            A bokeh figure that can be displayed in a notebook (e.g. with
            ``bokeh.io.show``) or used to create a bokeh app.
        """
        self.make_status_indicator()

        self.make_sphere_map(
            "altaz",
            HorizonMap,
            "Alt Az",
            frame_width=512,
            frame_height=512,
            decorate=False,
            horizon_graticules=True,
        )

        self.bokeh_models["key"] = bokeh.models.Div(text=self.key_markup)

        self.bokeh_models["reward_table_title"] = bokeh.models.Div(
            text="<h2>Basis functions for displayed survey</h2>"
        )
        self.make_reward_table()

        self.bokeh_models["reward_summary_table_title"] = bokeh.models.Div(
            text="<h2>Rewards for all survey schedulers</h2>"
        )
        self.make_reward_summary_table()
        self.make_chosen_survey()
        self.make_value_selector()
        self.make_survey_selector()
        self.make_tier_selector()
        self.make_pickle_entry_box()

        controls = [
            self.bokeh_models["file_input_box"],
            self.bokeh_models["file_read_status"],
        ]

        if self.observatory is not None:
            self.make_time_input_box()
            controls.append(self.bokeh_models["time_input_box"])

        controls += [
            self.bokeh_models["tier_selector"],
            self.bokeh_models["survey_selector"],
            self.bokeh_models["value_selector"],
        ]

        figure = bokeh.layouts.column(
            self.bokeh_models["status_indicator"],
            self.bokeh_models["key"],
            self.bokeh_models["altaz"],
            *controls,
            self.bokeh_models["chosen_survey"],
            self.bokeh_models["reward_table_title"],
            self.bokeh_models["reward_table"],
            self.bokeh_models["reward_summary_table_title"],
            self.bokeh_models["reward_summary_table"],
        )

        return figure

    def make_figure_with_many_projections(self):
        """Create a bokeh figures showing sky maps for scheduler behavior.

        Returns
        -------
        fig : `bokeh.models.layouts.LayoutDOM`
            A bokeh figure that can be displayed in a notebook (e.g. with
            ``bokeh.io.show``) or used to create a bokeh app.
        """

        self.make_sphere_map(
            "armillary_sphere",
            ArmillarySphere,
            "Armillary Sphere",
            frame_width=512,
            frame_height=512,
            decorate=True,
        )
        self.bokeh_models["alt_slider"] = self.sphere_maps["armillary_sphere"].sliders["alt"]
        self.bokeh_models["az_slider"] = self.sphere_maps["armillary_sphere"].sliders["az"]
        self.bokeh_models["mjd_slider"] = self.sphere_maps["armillary_sphere"].sliders["mjd"]
        # self.bokeh_models["mjd_slider"].visible = False
        self.make_sphere_map(
            "planisphere",
            Planisphere,
            "Planisphere",
            frame_width=512,
            frame_height=512,
            decorate=True,
        )
        self.make_sphere_map(
            "altaz",
            HorizonMap,
            "Alt Az",
            frame_width=512,
            frame_height=512,
            decorate=False,
            horizon_graticules=True,
        )

        if self.include_mollweide:
            self.make_sphere_map(
                "mollweide",
                MollweideMap,
                "Mollweide",
                frame_width=512,
                frame_height=512,
                decorate=True,
            )

        self.bokeh_models["key"] = bokeh.models.Div(text=self.key_markup)

        self.bokeh_models["reward_table_title"] = bokeh.models.Div(
            text="<h2>Basis functions for displayed survey</h2>"
        )
        self.make_reward_table()

        self.bokeh_models["reward_summary_table_title"] = bokeh.models.Div(
            text="<h2>Rewards for all survey schedulers</h2>"
        )
        self.make_reward_summary_table()
        self.make_chosen_survey()
        self.make_value_selector()
        self.make_survey_selector()
        self.make_tier_selector()
        self.make_pickle_entry_box()

        # slider was created by SphereMap
        self.add_mjd_slider_callback()

        arm_controls = [
            self.bokeh_models["alt_slider"],
            self.bokeh_models["az_slider"],
        ]

        controls = [self.bokeh_models["file_input_box"]]

        if self.observatory is not None:
            self.make_time_input_box()
            controls.append(self.bokeh_models["time_input_box"])

        controls += [
            self.bokeh_models["mjd_slider"],
            self.bokeh_models["tier_selector"],
            self.bokeh_models["survey_selector"],
            self.bokeh_models["value_selector"],
        ]

        if self.include_mollweide:
            map_column = bokeh.layouts.column(
                self.bokeh_models["altaz"],
                self.bokeh_models["planisphere"],
                self.bokeh_models["armillary_sphere"],
                *arm_controls,
                self.bokeh_models["mollweide"],
            )
        else:
            map_column = bokeh.layouts.column(
                self.bokeh_models["altaz"],
                self.bokeh_models["planisphere"],
                self.bokeh_models["armillary_sphere"],
                *arm_controls,
            )

        figure = bokeh.layouts.row(
            bokeh.layouts.column(
                self.bokeh_models["key"],
                *controls,
                self.bokeh_models["chosen_survey"],
                self.bokeh_models["reward_table_title"],
                self.bokeh_models["reward_table"],
                self.bokeh_models["reward_summary_table_title"],
                self.bokeh_models["reward_summary_table"],
            ),
            map_column,
        )

        return figure


def make_scheduler_map_figure(
    scheduler_pickle_fname="baseline.pickle.gz",
    nside=DEFAULT_NSIDE,
):
    """Create a set of bekeh figures showing sky maps for scheduler behavior.

    Parameters
    ----------
    scheduler_pickle_fname : `str`, optional
        File from which to load the scheduler state. If set to none, look for
        the file name in the ``SCHED_PICKLE`` environment variable.
        By default None
    nside : int, optional
        Healpix nside to use for display, by default 32

    Returns
    -------
    fig : `bokeh.models.layouts.LayoutDOM`
        A bokeh figure that can be displayed in a notebook (e.g. with
        ``bokeh.io.show``) or used to create a bokeh app.
    """
    if scheduler_pickle_fname is None:
        start_mjd = DEFAULT_MJD - 1
        observatory = ModelObservatory(mjd_start=start_mjd, nside=nside)
        observatory.mjd = DEFAULT_MJD
        conditions = observatory.return_conditions()
        scheduler = example_scheduler(mjd_start=start_mjd, nside=nside)
        scheduler.update_conditions(conditions)
        scheduler.request_observation()
    else:
        scheduler, conditions = read_scheduler(sample_pickle(scheduler_pickle_fname))

    scheduler.update_conditions(conditions)
    scheduler_map = SchedulerDisplayApp(nside=nside, scheduler=scheduler)

    figure = scheduler_map.make_figure()

    return figure


def add_scheduler_map_app(doc):
    """Add a scheduler map figure to a bokeh document

    Parameters
    ----------
    doc : `bokeh.document.document.Document`
        The bokeh document to which to add the figure.
    """
    figure = make_scheduler_map_figure(None)
    doc.add_root(figure)


if __name__.startswith("bokeh_app_"):
    doc = bokeh.plotting.curdoc()
    add_scheduler_map_app(doc)
