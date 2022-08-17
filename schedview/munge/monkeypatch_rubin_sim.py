from io import StringIO
from collections import OrderedDict
from copy import deepcopy

import pandas as pd
import numpy as np
import healpy as hp

import rubin_sim
import rubin_sim.scheduler
import rubin_sim.scheduler.surveys
import rubin_sim.scheduler.features.conditions
import rubin_sim.scheduler.basis_functions


class Core_scheduler(rubin_sim.scheduler.schedulers.core_scheduler.Core_scheduler):
    def get_basis_functions(self, survey_index=None, conditions=None):
        """Get basis functions for a specific survey in provided conditions.

        Parameters
        ----------
        survey_index : `List` [`int`], optional
            A list with two elements: the survey list and the element within
            that survey list for which the basis function should be retrieved.
            If ``None``, use the latest survey to make an addition to the
            queue.
        conditions : `rubin_sim.scheduler.features.conditions.Conditions`, optional  # noqa W505
            The conditions for which to return the basis functions.
            If ``None``, use the conditions associated with this sceduler.
            By default None.

        Returns
        -------
        basis_funcs : `OrderedDict` ['str`, `rubin_sim.scheduler.basis_functions.basis_functions.Base_basis_function`]  # noqa W505
            A dictionary of the basis functions, where the keys are names for
            the basis functions and the values are the functions themselves.
        """
        if survey_index is None:
            survey_index = self.survey_index

        if conditions is None:
            conditions = self.conditions

        survey = self.survey_lists[survey_index[0]][survey_index[1]]
        basis_funcs = OrderedDict()
        for basis_func in survey.basis_functions:
            if hasattr(basis_func(conditions), "__len__"):
                basis_funcs[basis_func.__class__.__name__] = basis_func
        return basis_funcs

    def get_healpix_maps(self, survey_index=None, conditions=None):
        """Get the healpix maps for a specific survey, in provided conditions.

        Parameters
        ----------
        survey_index : `List` [`int`], optional
            A list with two elements: the survey list and the element within
            that survey list for which the maps that should be retrieved.
            If ``None``, use the latest survey to make an addition to
            the queue.
        conditions : `rubin_sim.scheduler.features.conditions.Conditions`, optional  # noqa W505
            The conditions for the maps to be returned. If ``None``, use
            the conditions associated with this sceduler. By default None.

        Returns
        -------
        basis_funcs : `OrderedDict` ['str`, `numpy.ndarray`]
            A dictionary of the maps, where the keys are names for the maps and
            values are the numpy arrays as used by ``healpy``.
        """
        if survey_index is None:
            survey_index = self.survey_index

        if conditions is None:
            conditions = self.conditions

        maps = OrderedDict()
        for band in conditions.skybrightness.keys():
            maps[f"{band}_sky"] = deepcopy(conditions.skybrightness[band])
            maps[f"{band}_sky"][maps[f"{band}_sky"] < -1e30] = np.nan

        basis_functions = self.get_basis_functions(survey_index, conditions)

        for basis_func_key in basis_functions.keys():
            label = basis_functions[basis_func_key].label()
            maps[label] = basis_functions[basis_func_key](conditions)

        return maps

    def __repr__(self):
        if isinstance(
            self.pointing2hpindx, rubin_sim.scheduler.utils.utils.hp_in_lsst_fov
        ):
            camera = "LSST"
        elif isinstance(
            self.pointing2hpindx, rubin_sim.scheduler.utils.utils.hp_in_comcam_fov
        ):
            camera = "comcam"
        else:
            camera = None

        this_repr = f"""{self.__class__.__qualname__}(
            surveys={repr(self.survey_lists)},
            camera="{camera}",
            nside={repr(self.nside)},
            rotator_limits={repr(self.rotator_limits)},
            survey_index={repr(self.survey_index)},
            log={repr(self.log)}
        )"""
        return this_repr

    def __str__(self):
        if isinstance(
            self.pointing2hpindx, rubin_sim.scheduler.utils.utils.hp_in_lsst_fov
        ):
            camera = "LSST"
        elif isinstance(
            self.pointing2hpindx, rubin_sim.scheduler.utils.utils.hp_in_comcam_fov
        ):
            camera = "comcam"
        else:
            camera = None

        output = StringIO()
        print(f"# {self.__class__.__name__} at {hex(id(self))}", file=output)

        misc = pd.Series(
            {
                "camera": camera,
                "nside": self.nside,
                "rotator limits": self.rotator_limits,
                "survey index": self.survey_index,
                "Last chosen": str(
                    self.survey_lists[self.survey_index[0]][self.survey_index[1]]
                ),
            }
        )
        misc.name = "value"
        print(misc.to_markdown(), file=output)

        print("", file=output)
        print("## Surveys", file=output)

        if len(self.survey_lists) == 0:
            print("Scheduler contains no surveys.", file=output)

        for tier_index, tier_surveys in enumerate(self.survey_lists):
            print(file=output)
            print(f"### Survey list {tier_index}", file=output)
            print(self.surveys_df(tier_index).to_markdown(), file=output)

        print("", file=output)
        print(str(self.conditions), file=output)

        print("", file=output)
        print("## Queue", file=output)
        print(
            pd.concat(pd.DataFrame(q) for q in self.queue)[
                ["ID", "flush_by_mjd", "RA", "dec", "filter", "exptime", "note"]
            ]
            .set_index("ID")
            .to_markdown(),
            file=output,
        )

        result = output.getvalue()
        return result

    def _repr_markdown_(self):
        return str(self)

    def surveys_df(self, tier):
        surveys = []
        survey_list = self.survey_lists[tier]
        for survey_list_elem, survey in enumerate(survey_list):
            reward = np.max(survey.reward) if tier <= self.survey_index[0] else None
            chosen = (tier == self.survey_index[0]) and (
                survey_list_elem == self.survey_index[1]
            )
            surveys.append({"survey": str(survey), "reward": reward, "chosen": chosen})

        df = pd.DataFrame(surveys).set_index("survey")
        return df

    def make_reward_df(self, conditions):
        survey_dfs = []
        for index0, survey_list in enumerate(self.survey_lists):
            for index1, survey in enumerate(survey_list):
                survey_df = survey.make_reward_df(conditions)
                survey_df["list_index"] = index0
                survey_df["survey_index"] = index1
                survey_dfs.append(survey_df)

        survey_df = pd.concat(survey_dfs).set_index(["list_index", "survey_index"])
        return survey_df


class Conditions(rubin_sim.scheduler.features.conditions.Conditions):
    def __repr__(self):
        return f"<{self.__class__.__name__} mjd_start='{self.mjd_start}' at {hex(id(self))}>"

    def __str__(self):
        output = StringIO()
        print(f"{self.__class__.__qualname__} at {hex(id(self))}", file=output)
        print("============================", file=output)
        print("nside: ", self.nside, file=output)
        print("site: ", self.site.name, file=output)
        print("exptime: ", self.exptime, file=output)
        print("lmst: ", self.lmst, file=output)
        print("season_offset: ", self.season_offset, file=output)
        print("sun_RA_start: ", self.sun_RA_start, file=output)
        print("clouds: ", self.clouds, file=output)
        print("current_filter: ", self.current_filter, file=output)
        print("mounted_filters: ", self.mounted_filters, file=output)
        print("night: ", self.night, file=output)
        print("wind_speed: ", self.wind_speed, file=output)
        print("wind_direction: ", self.wind_direction, file=output)
        print(
            "len(scheduled_observations): ",
            len(self.scheduled_observations),
            file=output,
        )
        print("len(queue): ", len(self.queue), file=output)
        print("moonPhase: ", self.moonPhase, file=output)
        print("bulk_cloud: ", self.bulk_cloud, file=output)
        print("targets_of_opportunity: ", self.targets_of_opportunity, file=output)
        print("season_modulo: ", self.season_modulo, file=output)
        print("season_max_season: ", self.season_max_season, file=output)
        print("season_length: ", self.season_length, file=output)
        print("season_floor: ", self.season_floor, file=output)
        print("cumulative_azimuth_rad: ", self.cumulative_azimuth_rad, file=output)

        positions = [
            {
                "name": "sun",
                "alt": self.sunAlt,
                "az": self.sunAz,
                "RA": self.sunRA,
                "decl": self.sunDec,
            }
        ]
        positions.append(
            {
                "name": "moon",
                "alt": self.moonAlt,
                "az": self.moonAz,
                "RA": self.moonRA,
                "decl": self.moonDec,
            }
        )
        for planet_name in ("venus", "mars", "jupiter", "saturn"):
            positions.append(
                {
                    "name": planet_name,
                    "RA": np.asscalar(self.planet_positions[planet_name + "_RA"]),
                    "decl": np.asscalar(self.planet_positions[planet_name + "_dec"]),
                }
            )
        positions.append(
            {
                "name": "telescope",
                "alt": self.telAlt,
                "az": self.telAz,
                "RA": self.telRA,
                "decl": self.telDec,
                "rot": self.rotTelPos,
            }
        )
        positions = pd.DataFrame(positions).set_index("name")
        print(file=output)
        print("Positions (radians)", file=output)
        print("-------------------", file=output)
        print(positions.to_markdown(), file=output)

        positions_deg = np.degrees(positions)
        print(file=output)
        print("Positions (degrees)", file=output)
        print("-------------------", file=output)
        print(positions_deg.to_markdown(), file=output)

        events = (
            "mjd_start",
            "mjd",
            "sunset",
            "sun_n12_setting",
            "sun_n18_setting",
            "sun_n18_rising",
            "sun_n12_rising",
            "sunrise",
            "moonrise",
            "moonset",
            "sun_0_setting",
            "sun_0_rising",
        )
        event_rows = []
        for event in events:
            mjd = getattr(self, event)
            time = pd.to_datetime(mjd + 2400000.5, unit="D", origin="julian")
            event_rows.append({"event": event, "MJD": mjd, "date": time})
        event_df = pd.DataFrame(event_rows).set_index("event").sort_values(by="MJD")
        print("", file=output)
        print("Events", file=output)
        print("------", file=output)
        print(event_df.to_markdown(), file=output)

        map_stats = []
        for map_name in ("ra", "dec", "slewtime", "airmass"):
            values = getattr(self, map_name)
            map_stats.append(
                {
                    "map": map_name,
                    "nside": hp.npix2nside(len(values)),
                    "min": np.nanmin(values),
                    "max": np.nanmax(values),
                    "median": np.nanmedian(values),
                }
            )

        for base_map_name in ("skybrightness", "FWHMeff"):
            for band in "ugrizy":
                values = getattr(self, base_map_name)[band]
                map_name = f"{base_map_name}_{band}"
                map_stats.append(
                    {
                        "map": map_name,
                        "nside": hp.npix2nside(len(values)),
                        "min": np.nanmin(values),
                        "max": np.nanmax(values),
                        "median": np.nanmedian(values),
                    }
                )
        maps_df = pd.DataFrame(map_stats).set_index("map")
        print("", file=output)
        print("Maps", file=output)
        print("----", file=output)
        print(maps_df.to_markdown(), file=output)

        result = output.getvalue()
        return result

    def _repr_markdown_(self):
        return str(self)


class BaseSurvey(rubin_sim.scheduler.surveys.BaseSurvey):
    def __repr__(self):
        return f"<{self.__class__.__name__} survey_name='{self.survey_name}' at {hex(id(self))}>"

    def make_reward_df(self, conditions):
        feasibility = []
        accum_reward = []
        bf_reward = []
        bf_label = []
        basis_functions = []
        for basis_function in self.basis_functions:
            basis_functions.append(basis_function)
            test_survey = deepcopy(self)
            test_survey.basis_functions = basis_functions
            bf_label.append(basis_function.label())
            bf_reward.append(np.nanmax(basis_function(conditions)))
            feasibility.append(basis_function.check_feasibility(conditions))
            try:
                accum_reward.append(
                    np.nanmax(test_survey.calc_reward_function(conditions))
                )
            except IndexError:
                accum_reward.append(None)

        reward_df = pd.DataFrame(
            {
                "basis_function": bf_label,
                "feasible": feasibility,
                "basis_reward": bf_reward,
                "accum_reward": accum_reward,
            }
        )
        return reward_df

    def reward_changes(self, conditions):
        reward_values = []
        basis_functions = []
        for basis_function in self.basis_functions:
            test_survey = deepcopy(self)
            basis_functions.append(basis_function)
            test_survey.basis_functions = basis_functions
            try:
                reward_values.append(
                    np.nanmax(test_survey.calc_reward_function(conditions))
                )
            except IndexError:
                reward_values.append(None)

        bf_names = [bf.__class__.__name__ for bf in self.basis_functions]
        return list(zip(bf_names, reward_values))


class BaseMarkovDF_survey(rubin_sim.scheduler.surveys.BaseMarkovDF_survey):
    def make_reward_df(self, conditions):
        feasibility = []
        accum_reward = []
        bf_reward = []
        bf_label = []
        basis_functions = []
        basis_weights = []
        for (weight, basis_function) in zip(self.basis_weights, self.basis_functions):
            basis_functions.append(basis_function)
            basis_weights.append(weight)
            test_survey = deepcopy(self)
            test_survey.basis_functions = basis_functions
            test_survey.basis_weights = basis_weights
            bf_label.append(basis_function.label())
            bf_reward.append(np.nanmax(basis_function(conditions)))
            feasibility.append(basis_function.check_feasibility(conditions))
            try:
                accum_reward.append(
                    np.nanmax(test_survey.calc_reward_function(conditions))
                )
            except IndexError:
                accum_reward.append(None)

        reward_df = pd.DataFrame(
            {
                "basis_function": bf_label,
                "feasible": feasibility,
                "basis_reward": bf_reward,
                "accum_reward": accum_reward,
            }
        )
        return reward_df

    def reward_changes(self, conditions):
        reward_values = []

        basis_functions = []
        basis_weights = []
        for (weight, basis_function) in zip(self.basis_weights, self.basis_functions):
            test_survey = deepcopy(self)
            basis_functions.append(basis_function)
            test_survey.basis_functions = basis_functions
            basis_weights.append(weight)
            test_survey.basis_weights = basis_weights
            try:
                reward_values.append(
                    np.nanmax(test_survey.calc_reward_function(conditions))
                )
            except IndexError:
                reward_values.append(None)

        bf_names = [bf.label() for bf in self.basis_functions]
        return list(zip(bf_names, reward_values))


class Deep_drilling_survey(rubin_sim.scheduler.surveys.Deep_drilling_survey):
    def __repr__(self):
        repr_start = f"<{self.__class__.__name__} survey_name='{self.survey_name}'"
        repr_end = f", RA={self.ra}, dec={self.dec} at {hex(id(self))}>"
        return repr_start + repr_end


class Base_basis_function(rubin_sim.scheduler.basis_functions.Base_basis_function):
    def label(self):
        label = self.__class__.__name__.replace("_basis_function", "")
        return label


class Slewtime_basis_function(
    rubin_sim.scheduler.basis_functions.Slewtime_basis_function
):
    def label(self):
        label = f"{self.__class__.__name__.replace('_basis_function', '')} {self.maxtime} {self.filtername}"
        return label


rubin_sim.scheduler.basis_functions.Slewtime_basis_function.label = (
    Slewtime_basis_function.label
)
rubin_sim.scheduler.basis_functions.Base_basis_function.label = (
    Base_basis_function.label
)

rubin_sim.scheduler.schedulers.core_scheduler.Core_scheduler.get_basis_functions = (
    Core_scheduler.get_basis_functions
)
rubin_sim.scheduler.schedulers.core_scheduler.Core_scheduler.get_healpix_maps = (
    Core_scheduler.get_healpix_maps
)
rubin_sim.scheduler.schedulers.core_scheduler.Core_scheduler.__repr__ = (
    Core_scheduler.__repr__
)
rubin_sim.scheduler.schedulers.core_scheduler.Core_scheduler.__str__ = (
    Core_scheduler.__str__
)
rubin_sim.scheduler.schedulers.core_scheduler.Core_scheduler.surveys_df = (
    Core_scheduler.surveys_df
)
rubin_sim.scheduler.schedulers.core_scheduler.Core_scheduler.make_reward_df = (
    Core_scheduler.make_reward_df
)

rubin_sim.scheduler.schedulers.core_scheduler.Core_scheduler._repr_markdown_ = (
    Core_scheduler._repr_markdown_
)

rubin_sim.scheduler.surveys.BaseSurvey.__repr__ = BaseSurvey.__repr__

rubin_sim.scheduler.surveys.Deep_drilling_survey.__repr__ = (
    Deep_drilling_survey.__repr__
)

rubin_sim.scheduler.features.conditions.Conditions.__str__ = Conditions.__str__
rubin_sim.scheduler.features.conditions.Conditions._repr_markdown_ = (
    Conditions._repr_markdown_
)

rubin_sim.scheduler.surveys.BaseMarkovDF_survey.reward_changes = (
    BaseMarkovDF_survey.reward_changes
)
rubin_sim.scheduler.surveys.BaseSurvey.reward_changes = BaseSurvey.reward_changes

rubin_sim.scheduler.surveys.BaseSurvey.make_reward_df = BaseSurvey.make_reward_df
rubin_sim.scheduler.surveys.BaseMarkovDF_survey.make_reward_df = (
    BaseMarkovDF_survey.make_reward_df
)
