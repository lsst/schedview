import collections.abc
import itertools
import logging
import warnings
from collections import OrderedDict

import bokeh.core.properties
import bokeh.models
import bokeh.plotting
import healpy as hp
import numpy as np
import pandas as pd
import rubin_sim.scheduler.basis_functions
import rubin_sim.scheduler.example
import rubin_sim.scheduler.schedulers
import rubin_sim.scheduler.surveys
from astropy.time import Time
from rubin_sim.scheduler.features.conditions import Conditions
from rubin_sim.scheduler.model_observatory import ModelObservatory
from rubin_sim.scheduler.schedulers.core_scheduler import CoreScheduler as CoreScheduler
from rubin_sim.utils import survey_start_mjd
from uranography.api import ArmillarySphere, HorizonMap, MollweideMap, Planisphere, make_zscale_linear_cmap

from schedview.collect import read_scheduler
from schedview.compute.scheduler import make_scheduler_summary_df, make_unique_survey_name
from schedview.compute.survey import make_survey_reward_df

DEFAULT_MJD = survey_start_mjd() + 0.2
DEFAULT_NSIDE = 32


def make_logger():
    logger = logging.getLogger("sched_logger")
    logger.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s: %(message)s")
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    return logger


LOGGER = make_logger()


class BadSchedulerError(Exception):
    pass


class BadConditionsError(Exception):
    pass


class SchedulerDisplay:
    tooltips = [
        ("RA", "@center_ra"),
        ("Decl", "@center_decl"),
    ]

    key_markup = """<h1>Key</h1>
<ul>
<li><b>Black line</b> Horizon</li>
<li><b>Red line</b> ZD=70 deg.</li>
<li><b>Green line</b> Ecliptic</li>
<li><b>Blue line</b> Galactic plane</li>
<li><b>Yellow dot</b> Sun position</li>
<li><b>Gray dot</b> Moon position</li>
<li><b>Red dot</b> Survey field(s)</li>
<li><b>Green dot</b> Telescope pointing</li>
</ul>
    """

    def __init__(self, init_key="AvoidDirectWind", nside=DEFAULT_NSIDE, scheduler=None):
        self._scheduler = None
        self.survey_index = [None, None]
        self.healpix_maps = OrderedDict()
        self.init_key = init_key
        self.map_key = init_key
        self.nside = nside
        self.healpix_cmap = None
        self.data_sources = {}
        self.glyphs = {}
        self.bokeh_models = {}
        self.sphere_maps = {}
        self._figure = None
        mjd = Time.now().mjd if DEFAULT_MJD is None else DEFAULT_MJD
        try:
            self.observatory = ModelObservatory(mjd_start=mjd - 1, nside=nside)
        except ValueError:
            self.observatory = None

        if scheduler is None:
            scheduler = rubin_sim.scheduler.example.example_scheduler(nside=nside, mjd_start=DEFAULT_MJD)
            if self.observatory is not None:
                conditions = self.observatory.return_conditions()
            else:
                conditions = Conditions(mjd_start=mjd - 1, nside=nside)
                conditions.mjd = mjd

            scheduler.update_conditions(conditions)
            scheduler.request_observation()

        self.scheduler = scheduler

    @property
    def map_keys(self):
        """Return keys for the available healpix maps"""
        keys = list(self.healpix_maps.keys())
        return keys

    @property
    def mjd(self):
        # Sometimes conditions.mjd is a one-d numpy array, sometimes a float.
        # make sure we always return a float.
        return float(self.conditions.mjd)

    @mjd.setter
    def mjd(self, value):
        """Update the interface for a new date

        Parameters
        ----------
        value : `float`
            The new MJD
        """

        # Sometimes a loaded pickle will have close to a represented
        # time, but not identical, and we do not want to try to recreate
        # the conditions object if we have loaded it and not changed the
        # time. So, check only that the mjd is close, not that it
        # is identical.
        if np.abs(value - self.mjd) < (1.0 / (24 * 60 * 60)):
            # Nothing needs to be done
            return

        if self.observatory.nside != self.scheduler.nside:
            self.observatory = ModelObservatory(
                nside=self.scheduler.nside,
                mjd_start=self.observatory.mjd_start,
                alt_min=np.degrees(self.observatory.alt_min),
                lax_dome=self.observatory.lax_dome,
                cloud_limit=self.observatory.cloud_limit,
                sim_to_o=self.observatory.sim__to_o,
                park_after=self.observatory.park_after * 60 * 24,
            )

        LOGGER.info(f"Creating conditions for mjd {value}")

        try:
            # If we cannot go to the requested MJD, follback on
            # on we can go to:
            if value < self.observatory.sky_model.mjd_left.min():
                LOGGER.info("Cannot go to requested date, going to earliest.")
                self.observatory.mjd = self.observatory.sky_model.mjd_left.min() + 1.0
            elif value > self.observatory.sky_model.mjd_right.max():
                LOGGER.info("Cannot go to requested date, going to latest.")
                self.observatory.mjd = self.observatory.sky_model.mjd_right.max() - 1.0
            else:
                self.observatory.mjd = value

            conditions = self.observatory.return_conditions()

            # Make sure we have set a time at night, and if we have night
            # go to the sunsrise or sunset on the same night.
            if conditions.sun_n18_setting > self.observatory.mjd:
                self.observatory.mjd = conditions.sun_n18_setting
                conditions = self.observatory.return_conditions()
            if conditions.sun_n18_rising < self.observatory.mjd:
                self.observatory.mjd = conditions.sun_n18_rising
                conditions = self.observatory.return_conditions()

            LOGGER.info("Conditions created")
        except (ValueError, AttributeError):
            # If we do not have the right cache of sky brightness
            # values on disk, we may not be able to instantiate
            # ModelObservatory, but we should be able to run
            # it anyway. Fake up a conditions object as well as
            # we can.
            conditions = Conditions(mjd_start=value - 1, nside=self.nside)
            conditions.mjd = value
            LOGGER.warning("Created dummy conditions.")

        self.conditions = conditions

    @property
    def time(self):
        """Return the time as an astropy Time objec.

        Return
        ------
        time : `astropy.time.Time`
            The time
        """
        time = Time(self.mjd, format="mjd", scale="utc")
        time.format = "iso"
        return time

    @time.setter
    def time(self, time):
        """Set the time according to a time string.

        Parameters
        ----------
        time : `astropy.time.Time` or `str`
            The new time
        Parameterers are the same as for `pandas.to_datetime`.
        """
        if isinstance(time, Time):
            new_mjd = time.mjd
        elif isinstance(time, pd.Timestamp):
            new_mjd = time.to_julian_date() - 2400000.5
        else:
            try:
                new_mjd = Time(time).mjd
            except ValueError:
                new_mjd = pd.to_datetime(time, utc=True).to_julian_date() - 2400000.5

        self.mjd = new_mjd

    def _update_healpix_maps(self):
        """Update healpix values from the scheduler."""
        # Be sure we keep using the same dictionary, and just update it,
        # rather than use a new one because any new one we make won't propogate
        # into other callbacks.
        self.healpix_maps.clear()
        full_healpix_maps = self.scheduler.get_healpix_maps(
            survey_index=self.survey_index, conditions=self.conditions
        )
        for key in full_healpix_maps:
            new_key = key.replace(" ", "_").replace(".", "_").replace("@", "_")
            values = full_healpix_maps[key]
            if values.shape[0] != hp.nside2npix(self.nside):
                values[np.isnan(values)] = hp.UNSEEN
                values = hp.ud_grade(
                    values,
                    self.nside,
                )
                values[values == hp.UNSEEN] = np.nan
            self.healpix_maps[new_key] = values

        survey = self.scheduler.survey_lists[self.survey_index[0]][self.survey_index[1]]
        reward = survey.calc_reward_function(self.conditions)
        if not (isinstance(reward, np.ndarray) and len(reward) > 1):
            try:
                basis_weights = survey.basis_weights
                basis_functions = survey.basis_functions
                supported_survey = True
            except AttributeError:
                supported_survey = False

            if supported_survey:
                npix = hp.nside2npix(self.nside)
                reward = np.zeros(npix)
                indx = np.arange(npix)
                for bf, weight in zip(basis_functions, basis_weights):
                    basis_value = bf(self.conditions, indx=indx)
                    if isinstance(basis_value, np.ndarray):
                        basis_value[np.isnan(basis_value)] = hp.UNSEEN
                        basis_value = hp.ud_grade(basis_value, self.nside)
                        basis_value[basis_value == hp.UNSEEN] = np.nan
                    reward += basis_value * weight

        if isinstance(reward, np.ndarray) and len(reward) > 1:
            if reward.shape[0] != hp.nside2npix(self.nside):
                reward[np.isnan(reward)] = hp.UNSEEN
                reward = hp.ud_grade(
                    reward,
                    self.nside,
                )
            reward[reward == hp.UNSEEN] = np.nan
            if np.any(np.isfinite(reward)):
                self.healpix_maps["reward"] = reward

    @property
    def healpix_values(self):
        """Healpix numpy array for the current map."""
        if len(self.healpix_maps) == 0:
            npix = hp.nside2npix(self.nside)
            values = np.ones(npix)
            return values

        return self.healpix_maps[self.map_key]

    def load(self, file_name):
        """Load scheduler data

        Parameters
        ----------
        file_name : `str`
            The file name from which to load scheduler state.
        """
        scheduler, conditions = read_scheduler(file_name)
        if not isinstance(scheduler, CoreScheduler):
            raise BadSchedulerError()

        if not isinstance(conditions, Conditions):
            raise BadConditionsError()

        scheduler.update_conditions(conditions)
        self.scheduler = scheduler

    @property
    def scheduler(self):
        return self._scheduler

    @scheduler.setter
    def scheduler(self, scheduler):
        """Set the scheduler visualized.

        Parameters
        ----------
        scheduler : `rubin_sim.scheduler.schedulers.CoreScheduler`
            The new scheduler to visualize
        """
        # Work separated into _set_scheduler so that it can be overriden by
        # subclasses.
        self._set_scheduler(scheduler)

    def _set_scheduler(self, scheduler):
        LOGGER.debug("Setting the scheduler")
        self._scheduler = scheduler

        self.survey_index[0] = self.scheduler.survey_index[0]
        self.survey_index[1] = self.scheduler.survey_index[1]

        if self.survey_index[0] is None:
            self.survey_index = [0, 0]
        if self.survey_index[1] is None:
            self.survey_index[1] = 0

        self.conditions = scheduler.conditions

    @property
    def conditions(self):
        return self.scheduler.conditions

    @conditions.setter
    def conditions(self, conditions):
        """Update the figure to represent changed conditions.

        Parameters
        ----------
        conditions : `rubin_sim.scheduler.features.conditions.Conditions`
            The new conditions.
        """
        if conditions.nside != self.nside:
            warnings.warn("Setting conditions to an unequal nside.")

        self._set_conditions(conditions)

    def _set_conditions(self, conditions):
        # Separated from the decorated setter so that it can be overridden
        # in a subclass.
        LOGGER.info("Updating interface for new conditions")
        self.scheduler.update_conditions(conditions)
        self.scheduler.request_observation()
        self._update_healpix_maps()

        # If the current map is no longer valid, pick a valid one.
        # Otherwise, keep displaying the same map.
        if self.map_key not in self.map_keys:
            self.map_key = self.map_keys[-1]

        for sphere_map in self.sphere_maps.values():
            sphere_map.mjd = self.mjd

        if "armillary_sphere" in self.sphere_maps:
            self.sphere_maps["armillary_sphere"].sliders["mjd"].value = self.sphere_maps[
                "armillary_sphere"
            ].mjd

        LOGGER.info("Finished updating conditions")

    def _unique_survey_name(self, survey_index=None):
        survey_name = make_unique_survey_name(self.scheduler, survey_index)
        return survey_name

    @property
    def tier_names(self):
        """List of names of tiers in current survey."""
        tiers = [f"tier {t}" for t in np.arange(len(self.scheduler.survey_lists))]
        return tiers

    def select_tier(self, tier):
        """Set the tier being displayed."""
        LOGGER.info(f"swiching tier to {tier}")
        self.survey_index[0] = self.tier_names.index(tier)
        self.survey_index[1] = 0

    @property
    def surveys_in_tier(self):
        """List of surveys in the current tier."""
        tier = self.survey_index[0]
        surveys_in_tier = [
            self._unique_survey_name([tier, i]) for i in range(len(self.scheduler.survey_lists[tier]))
        ]
        return surveys_in_tier

    def select_survey(self, survey):
        """Update the display to show a given survey.

        Parameters
        ----------
        survey : `str`
            The name of the survey to select.
        """
        # keep using the same survey_index list, and just update it,
        # not create a new one, because any new one we make won't propogate
        # into other callbacks.
        self.survey_index[1] = self.surveys_in_tier.index(survey)
        self._update_healpix_maps()

    def select_value(self, map_key):
        """Select the value to be displayed on the maps.

        Parameters
        ----------
        map_key : `str`
            The name of the value to be mapped
        """
        LOGGER.info(f"Switching value to {map_key}")
        self.map_key = map_key

    def make_sphere_map(
        self,
        key,
        cls,
        title,
        frame_width=512,
        frame_height=512,
        decorate=True,
        horizon_graticules=False,
    ):
        if "hover_tool" not in self.bokeh_models:
            self.bokeh_models["hover_tool"] = bokeh.models.HoverTool(renderers=[], tooltips=self.tooltips)

        plot = bokeh.plotting.figure(
            frame_width=frame_width,
            frame_height=frame_height,
            tools=[self.bokeh_models["hover_tool"]],
            match_aspect=True,
            title=title,
            output_backend="webgl",
        )
        sphere_map = cls(plot=plot, mjd=self.mjd)

        if "healpix" in self.data_sources:
            sphere_map.add_healpix(
                self.data_sources["healpix"],
                cmap=self.healpix_cmap,
                nside=self.nside,
            )
        else:
            sphere_map.add_healpix(self.healpix_values, nside=self.nside)
            self.data_sources["healpix"] = sphere_map.plot.select(name="hpix_ds")[0]
            self.healpix_cmap = sphere_map.healpix_cmap

        healpix_renderer = sphere_map.plot.select(name="hpix_renderer")[0]
        self.bokeh_models["hover_tool"].renderers.append(healpix_renderer)

        if "horizon" in self.data_sources:
            sphere_map.add_horizon(data_source=self.data_sources["horizon"])
        else:
            self.data_sources["horizon"] = sphere_map.add_horizon()

        if "zd70" in self.data_sources:
            sphere_map.add_horizon(
                zd=70,
                data_source=self.data_sources["zd70"],
                line_kwargs={"color": "red", "line_width": 2},
            )
        else:
            self.data_sources["zd70"] = sphere_map.add_horizon(
                zd=70, line_kwargs={"color": "red", "line_width": 2}
            )

        if horizon_graticules:
            sphere_map.add_horizon_graticules()

        if decorate:
            sphere_map.decorate()

        if "survey_marker" not in self.data_sources:
            self.data_sources["survey_marker"] = self.make_survey_marker_data_source(sphere_map)

        sphere_map.add_marker(
            data_source=self.data_sources["survey_marker"],
            name="Field",
            circle_kwargs={"color": "red", "fill_alpha": 0.5},
        )

        if "telescope_marker" not in self.data_sources:
            self.data_sources["telescope_marker"] = self.make_telescope_marker_data_source(sphere_map)

        sphere_map.add_marker(
            data_source=self.data_sources["telescope_marker"],
            name="Field",
            circle_kwargs={"color": "green", "fill_alpha": 0.5},
        )

        if "moon_marker" not in self.data_sources:
            self.data_sources["moon_marker"] = self.make_moon_marker_data_source(sphere_map)

        sphere_map.add_marker(
            data_source=self.data_sources["moon_marker"],
            name="Moon",
            circle_kwargs={"color": "lightgray", "fill_alpha": 0.8},
        )

        if "sun_marker" not in self.data_sources:
            self.data_sources["sun_marker"] = self.make_sun_marker_data_source(sphere_map)

        sphere_map.add_marker(
            data_source=self.data_sources["sun_marker"],
            name="Sun",
            circle_kwargs={"color": "yellow", "fill_alpha": 1},
        )

        self.bokeh_models[key] = plot
        self.sphere_maps[key] = sphere_map

    def _make_marker_data_source(
        self,
        sphere_map=None,
        name="telescope",
        source_name="conditions",
        ra_name="telRA",
        decl_name="telDec",
        source_units="radians",
    ):
        """Create a bokeh datasource for an object at a set of coordinates.

        Parameters
        ----------
        sphere_map: `schedview.plot.SphereMap`
            The instance of SphereMap to use to create the data source
        name : 'str'
            The name of the thing to mark.
        source_name : `str`
            The name of the member object to provide the coordinates.
        ra_name : `str`
            The name of the member with the RA.
        decl_name : `str`
            The name of the member with the declination.
        source_units : `str`
            'radians' or 'degrees', according to what is provided by the source

        Returns
        -------
        data_source: `bokeh.models.ColumnDataSource`
            The DataSource with the column data.
        """
        if sphere_map is None:
            sphere_map = tuple(self.sphere_maps.values())[0]

        sources = {
            "conditions": self.conditions,
            "survey": self.scheduler.survey_lists[self.survey_index[0]][self.survey_index[1]],
        }
        source = sources[source_name]

        # If the telescope position is not set in our instance of
        # conditions, use an empty array
        ra = getattr(source, ra_name, np.array([]))
        decl = getattr(source, decl_name, np.array([]))
        if ra is None:
            ra = np.array([])
        if decl is None:
            decl = np.array([])
        LOGGER.debug(f"{name.capitalize()} coordinates: ra={np.degrees(ra)}, decl={np.degrees(decl)}")
        if source_units == "radians":
            ra_deg = np.degrees(ra)
            decl_deg = np.degrees(decl)
        elif source_units in ("degrees", "deg"):
            ra_deg = ra
            decl_deg = decl

        data = {
            "ra": ra_deg.tolist(),
            "decl": decl_deg.tolist(),
            "name": [name] * len(ra_deg),
            "glyph_size": [20] * len(ra_deg),
        }
        data_source = bokeh.models.ColumnDataSource(data=data, name=name)
        sphere_map.connect_controls(data_source)
        return data_source

    def make_moon_marker_data_source(self, sphere_map=None):
        """Create a bokeh datasource for the moon.

        Parameters
        ----------
        sphere_map: `schedview.plot.SphereMap`
            The instance of SphereMap to use to create the data source

        Returns
        -------
        data_source: `bokeh.models.ColumnDataSource`
            The DataSource with the column data.
        """
        data_source = self._make_marker_data_source(
            sphere_map=sphere_map,
            name="moon",
            source_name="conditions",
            ra_name="moonRA",
            decl_name="moonDec",
            source_units="radians",
        )
        return data_source

    def update_moon_marker_bokeh_model(self):
        """Update the moon data source."""
        if "telescope_marker" not in self.data_sources:
            return

        sphere_map = tuple(self.sphere_maps.values())[0]
        data_source = self.make_moon_marker_data_source(sphere_map)
        data = dict(data_source.data)
        if "moon_marker" in self.data_sources:
            self.data_sources["moon_marker"].data = data

    def make_sun_marker_data_source(self, sphere_map=None):
        """Create a bokeh datasource for the sun.

        Parameters
        ----------
        sphere_map: `schedview.plot.SphereMap`
            The instance of SphereMap to use to create the data source

        Returns
        -------
        data_source: `bokeh.models.ColumnDataSource`
            The DataSource with the column data.
        """
        data_source = self._make_marker_data_source(
            sphere_map=sphere_map,
            name="sun",
            source_name="conditions",
            ra_name="sunRA",
            decl_name="sunDec",
            source_units="radians",
        )
        return data_source

    def update_sun_marker_bokeh_model(self):
        """Update the sun data source."""
        if "telescope_marker" not in self.data_sources:
            return

        sphere_map = tuple(self.sphere_maps.values())[0]
        data_source = self.make_sun_marker_data_source(sphere_map)
        data = dict(data_source.data)
        if "sun_marker" in self.data_sources:
            self.data_sources["sun_marker"].data = data

    def make_telescope_marker_data_source(self, sphere_map=None):
        """Create a bokeh datasource for the current telescope pointing.

        Parameters
        ----------
        sphere_map: `schedview.plot.SphereMap`
            The instance of SphereMap to use to create the data source

        Returns
        -------
        data_source: `bokeh.models.ColumnDataSource`
            The DataSource with the column data.
        """
        data_source = self._make_marker_data_source(
            sphere_map=sphere_map,
            name="telescope",
            source_name="conditions",
            ra_name="telRA",
            decl_name="telDec",
            source_units="radians",
        )
        return data_source

    def update_telescope_marker_bokeh_model(self):
        """Update the telescope pointing data source."""
        if "telescope_marker" not in self.data_sources:
            return

        sphere_map = tuple(self.sphere_maps.values())[0]
        data_source = self.make_telescope_marker_data_source(sphere_map)
        data = dict(data_source.data)
        if "telescope_marker" in self.data_sources:
            self.data_sources["telescope_marker"].data = data

    def make_survey_marker_data_source(self, sphere_map=None, max_fields=50):
        """Create a bokeh datasource for the pointings for the current survey.

        Parameters
        ----------
        sphere_map: `schedview.plot.SphereMap`
            The instance of SphereMap to use to create the data source
        max_fields: `int`
            Maximum number of fields to display (none shown if the scheduler
            has more fields.)

        Returns
        -------
        data_source: `bokeh.models.ColumnDataSource`
            The DataSource with the column data.
        """
        survey = self.scheduler.survey_lists[self.survey_index[0]][self.survey_index[1]]
        try:
            ra_name = "ra" if len(survey.ra) <= max_fields else ""
            decl_name = "dec" if len(survey.dec) <= max_fields else ""
        except AttributeError:
            ra_name = ""
            decl_name = ""

        data_source = self._make_marker_data_source(
            sphere_map=sphere_map,
            name="Field",
            source_name="survey",
            ra_name=ra_name,
            decl_name=decl_name,
            source_units="radians",
        )
        return data_source

    def update_survey_marker_bokeh_model(self):
        """Update the survey pointing data source."""
        if "survey_marker" not in self.data_sources:
            return

        sphere_map = tuple(self.sphere_maps.values())[0]
        data_source = self.make_survey_marker_data_source(sphere_map)
        data = dict(data_source.data)
        if "survey_marker" in self.data_sources:
            self.data_sources["survey_marker"].data = data

    def update_healpix_bokeh_model(self):
        """Update the healpix value data source."""
        if "healpix" not in self.data_sources:
            return

        LOGGER.debug("Updating helpix bokeh models")

        sphere_map = tuple(self.sphere_maps.values())[0]
        # sphere_map = ArmillarySphere(mjd=self.conditions.mjd)

        if "Zenith_shadow_mask" in self.map_keys:
            zenith_mask = self.healpix_maps["Zenith_shadow_mask"]
            cmap_sample_data = self.healpix_values[zenith_mask == 1]
        elif "y_sky" in self.map_keys:
            sb_mask = np.isfinite(self.healpix_maps["y_sky"])
            cmap_sample_data = self.healpix_values[sb_mask]
            if len(cmap_sample_data) == 0:
                # It's probably day, so the color map will be bad regardless.
                cmap_sample_data = self.healpix_values
        else:
            cmap_sample_data = self.healpix_values

        self.healpix_cmap = make_zscale_linear_cmap(cmap_sample_data)

        new_ds = sphere_map.make_healpix_data_source(
            self.healpix_values,
            nside=self.nside,
            bound_step=1,
        )
        new_data = dict(new_ds.data)

        for key in self.map_keys:
            # The datasource might not have all healpixels
            # or have them in the same order
            # so force the order by indexing on new_data["hpid"]
            new_data[key] = self.healpix_maps[key][new_data["hpid"]]

        # Replace the data to be shown
        self.data_sources["healpix"].data = new_data

        for sphere_map in self.sphere_maps.values():
            sphere_map.healpix_glyph.fill_color = self.healpix_cmap
            sphere_map.healpix_glyph.line_color = self.healpix_cmap

    def update_hovertool_bokeh_model(self):
        """Update the hovertool with available value."""
        if "hover_tool" not in self.bokeh_models:
            return

        tooltips = []
        data = self.data_sources["healpix"].data
        for data_key in data.keys():
            if not isinstance(data[data_key][0], collections.abc.Sequence):
                if data_key == "center_ra":
                    label = "RA"
                elif data_key == "center_decl":
                    label = "Decl"
                else:
                    label = data_key.replace("_", " ")

                reference = f"@{data_key}"
                tooltips.append((label, reference))

        self.bokeh_models["hover_tool"].tooltips = tooltips

    def make_reward_table(self):
        """Create the bokeh model for a table of rewards."""
        # Bokeh's DataTable doesn't like to expand to accommodate extra rows,
        # so create a dummy with lots of rows initially.
        df = pd.DataFrame(
            np.nan,
            index=range(30),
            columns=[
                "basis_function",
                "feasible",
                "max_basis_reward",
                "max_accum_reward",
            ],
        )

        self.bokeh_models["reward_table"] = bokeh.models.DataTable(
            source=bokeh.models.ColumnDataSource(df),
            columns=[bokeh.models.TableColumn(field=c, title=c) for c in df],
        )

    def update_reward_table_bokeh_model(self):
        """Update the bokeh model for the table of rewards."""
        if "reward_table" in self.bokeh_models:
            survey = self.scheduler.survey_lists[self.survey_index[0]][self.survey_index[1]]
            reward_df = make_survey_reward_df(survey, self.conditions)

            any_bad_urls = False
            for doc_url in reward_df["doc_url"].values:
                if doc_url is None or "http" not in doc_url:
                    any_bad_urls = True
                    break

            if any_bad_urls:
                basis_function_formatter = bokeh.models.widgets.HTMLTemplateFormatter(
                    template="Not a basis real function"
                )
            else:
                basis_function_formatter = bokeh.models.widgets.HTMLTemplateFormatter(
                    template='<a href="<%= doc_url %>" target="_blank"><%= value %></a>'
                )

            self.bokeh_models["reward_table"].source = bokeh.models.ColumnDataSource(reward_df)

            new_columns = []
            for column_name in reward_df.columns:
                if column_name == "basis_function":
                    new_column = bokeh.models.TableColumn(
                        field=column_name,
                        title=column_name,
                        formatter=basis_function_formatter,
                    )
                elif column_name == "doc_url":
                    continue
                else:
                    new_column = bokeh.models.TableColumn(field=column_name, title=column_name)
                new_columns.append(new_column)

            self.bokeh_models["reward_table"].columns = new_columns

    def make_status_indicator(self):
        """Create an indicator of what the visualization app is doing."""
        self.bokeh_models["status_indicator"] = bokeh.models.Div(text="<p></p>")

    def make_chosen_survey(self):
        """Create the bokeh model for text showing the chosen survey."""
        self.bokeh_models["chosen_survey"] = bokeh.models.Div(text="<p>No chosen survey</p>")

    def update_chosen_survey_bokeh_model(self):
        """Update the bokeh model for text showing the chosen survey."""
        if (
            "chosen_survey" in self.bokeh_models
            and len(self.scheduler.survey_index) == 2
            and self.scheduler.survey_index[0] is not None
            and self.scheduler.survey_index[1] is not None
        ):
            tier = f"tier {self.scheduler.survey_index[0]}"
            survey = self._unique_survey_name()
            self.bokeh_models["chosen_survey"].text = f"<p>Chosen survey: {tier}, {survey}</p>"

    def make_displayed_value_metadata(self):
        """Create the bokeh model specifying what values are displayed."""
        self.bokeh_models["displayed_value_metadata"] = bokeh.models.Div(text="<p>No displayed values</p>")

    def update_displayed_value_metadata_bokeh_model(self):
        """Update the bokeh model specifying what values are displayed."""
        if "displayed_value_metadata" in self.bokeh_models:
            tier = f"tier {self.survey_index[0]}"
            survey = self._unique_survey_name()
            self.bokeh_models[
                "displayed_value_metadata"
            ].text = f"<p>Displayed value: {self.map_key} from {tier}, {survey}</p>"

    def make_time_display(self):
        """Create the bokeh model showing what time is being represented."""
        self.bokeh_models["time_display"] = bokeh.models.Div(text="<p>No time.</p>")

    def update_time_display_bokeh_model(self):
        """Update the bokeh model showing what time is being represented."""
        iso_time = Time(self.mjd, format="mjd", scale="utc").iso
        if "time_display" in self.bokeh_models:
            self.bokeh_models["time_display"].text = f"<p>{iso_time}</p>"

    def make_scheduler_summary_df(self):
        """Summarize the reward from each scheduler

        Returns
        -------
        survey_df : `pandas.DataFrame`
            A table showing the reword for each feasible survey, and the
            basis functions that result in it being infeasible for the rest.
        """
        survey_df = make_scheduler_summary_df(self.scheduler, self.conditions)
        return survey_df

    def make_reward_summary_table(self):
        """Create the bokeh model of the table of rewards."""
        # Bokeh's DataTable doesn't like to expand to accommodate extra rows,
        # so create a dummy with lots of rows initially.
        df = pd.DataFrame(
            np.nan,
            index=range(300),
            columns=["tier", "survey_name", "reward"],
        )
        self.data_sources["reward_summary_table"] = bokeh.models.ColumnDataSource(df)
        self.bokeh_models["reward_summary_table"] = bokeh.models.DataTable(
            source=self.data_sources["reward_summary_table"],
            columns=[bokeh.models.TableColumn(field=c, title=c) for c in df],
        )
        self.update_reward_summary_table_bokeh_model()

    def update_reward_summary_table_bokeh_model(self):
        """Update the bokeh model of the table of rewards."""
        LOGGER.info("Updating reward summary table bokeh model")

        if "reward_summary_table" in self.bokeh_models:
            scheduler_summary_df = self.make_scheduler_summary_df()

            def to_sigfig(x):
                try:
                    value = float(x)
                except ValueError:
                    return x

                return float("{:.5g}".format(value))

            scheduler_summary_df["reward"] = scheduler_summary_df["reward"].apply(to_sigfig)

            # Get URLs for survey documentation
            # Flatten the list of lists of surveys into one long list
            surveys = itertools.chain.from_iterable(self.scheduler.survey_lists)
            survey_class_names = ["rubin_sim.scheduler.surveys." + s.__class__.__name__ for s in surveys]
            survey_doc_url = [f"https://rubin-sim.lsst.io/api/{cn}.html#{cn}" for cn in survey_class_names]
            survey_name_formatter = bokeh.models.widgets.HTMLTemplateFormatter(
                template='<a href="<%= doc_url %>" target="_blank"><%= value %></a>'
            )

            scheduler_summary_df["doc_url"] = survey_doc_url

            self.bokeh_models["reward_summary_table"].source.data = dict(
                bokeh.models.ColumnDataSource(scheduler_summary_df).data
            )

            new_columns = []
            for column_name in scheduler_summary_df.columns:
                if column_name == "survey_name":
                    new_column = bokeh.models.TableColumn(
                        field=column_name,
                        title=column_name,
                        formatter=survey_name_formatter,
                    )
                elif column_name == "doc_url":
                    continue
                else:
                    new_column = bokeh.models.TableColumn(field=column_name, title=column_name)
                new_columns.append(new_column)

            self.bokeh_models["reward_summary_table"].columns = new_columns

    def make_figure(self):
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
        self.bokeh_models["mjd_slider"].visible = False
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
        self.make_sphere_map(
            "mollweide",
            MollweideMap,
            "Mollweide",
            frame_width=512,
            frame_height=512,
            decorate=True,
        )

        self.bokeh_models["key"] = bokeh.models.Div(text=self.key_markup)
        self.make_time_display()
        self.make_displayed_value_metadata()

        self.bokeh_models["reward_table_title"] = bokeh.models.Div(
            text="<h2>Basis functions for displayed survey</h2>"
        )
        self.make_reward_table()

        self.bokeh_models["reward_summary_table_title"] = bokeh.models.Div(
            text="<h2>Rewards for all survey schedulers</h2>"
        )
        self.make_reward_summary_table()
        self.make_chosen_survey()

        arm_controls = [
            self.bokeh_models["alt_slider"],
            self.bokeh_models["az_slider"],
        ]

        figure = bokeh.layouts.row(
            bokeh.layouts.column(
                self.bokeh_models["altaz"],
                self.bokeh_models["time_display"],
                self.bokeh_models["displayed_value_metadata"],
                self.bokeh_models["chosen_survey"],
                self.bokeh_models["reward_table_title"],
                self.bokeh_models["reward_table"],
                self.bokeh_models["reward_summary_table_title"],
                self.bokeh_models["reward_summary_table"],
            ),
            bokeh.layouts.column(
                self.bokeh_models["planisphere"],
                self.bokeh_models["key"],
                self.bokeh_models["mollweide"],
                self.bokeh_models["armillary_sphere"],
                *arm_controls,
            ),
        )

        return figure

    def update_bokeh_models(self):
        """Update all bokeh models with current data."""
        LOGGER.debug("Updating bokeh data models.")
        self.update_reward_table_bokeh_model()
        self.update_reward_summary_table_bokeh_model()
        self.update_healpix_bokeh_model()
        self.update_hovertool_bokeh_model()
        self.update_telescope_marker_bokeh_model()
        self.update_moon_marker_bokeh_model()
        self.update_sun_marker_bokeh_model()
        self.update_survey_marker_bokeh_model()
        self.update_time_display_bokeh_model()
        self.update_displayed_value_metadata_bokeh_model()
        self.update_chosen_survey_bokeh_model()

    @property
    def figure(self):
        """Return a figure for this display.

        Returns
        -------
        figure : `bokeh.models.layouts.LayoutDOM`
            A bokeh figure that can be displayed in a notebook (e.g. with
            ``bokeh.io.show``) or used to create a bokeh app.
        """
        if self._figure is None:
            self._figure = self.make_figure()

        return self._figure


class SchedulerNotebookDisplay(SchedulerDisplay):
    def __init__(self, *args, **kwargs):
        # docstring in parent class
        # notebook_handle must be initialized so overridden methods
        # called by the parent __init__ will run.
        self.notebook_handle = None
        super().__init__(*args, **kwargs)

    def _set_conditions(self, conditions):
        super()._set_conditions(conditions)
        self.update_display()

    def select_tier(self, tier):
        # docstring in parent class
        super().select_tier(tier)
        self.update_display()

    def select_survey(self, survey):
        # docstring in parent class
        super().select_survey(survey)
        self.update_display()

    def select_value(self, value):
        # docstring in parent class
        super().select_value(value)
        self.update_display()

    def update_display(self):
        """Update the display."""
        if self.notebook_handle is not None:
            self.update_bokeh_models()
            bokeh.io.push_notebook(handle=self.notebook_handle)

    def show(self):
        """Show the display."""
        self.notebook_handle = bokeh.io.show(self.figure, notebook_handle=True)
