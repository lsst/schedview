import itertools

import bokeh
import numpy as np
from astropy.time import Time
from rubin_sim.scheduler.model_observatory import ModelObservatory


def _extract_night(df, mjd_column, night, observatory=None):
    if observatory is None:
        observatory = ModelObservatory()

    # Add 1, so we use the date of the pm of the night instead of the am
    # as our reference.
    mjd = Time(night.isoformat()).mjd + 1
    sun_info = observatory.almanac.get_sunset_info(mjd)
    sunset = sun_info["sunset"]
    sunrise = sun_info["sunrise"]

    limited_df = df.query(f"{sunset} <= {mjd_column} <= {sunrise}").copy()

    mjd_limits = (sunset, sunrise)

    return limited_df, mjd_limits


def plot_rewards(
    reward_df,
    tier_label,
    night,
    observatory=None,
    obs_rewards=None,
    surveys=None,
    basis_function="Total",
    plot_kwargs={},
):
    """Create the plot showing reward values by survey.

    Parameters
    ----------
    reward_df : `pandas.DataFrame`
        The rewards by survey, as recorded by the `scheduler` instance
        when running the simulation.
    tier_label : `str`
        The label for the tier to plot.
    night : `astropy.time.Time`
        The night to plot.
    observatory : `ModelObservatory`
        The model observatory to use.
    obs_rewards : `pandas.DataFrame`
        The mapping between scheduler calls and simulated observations,
        as recorded by the `scheduler` instance.
    surveys : `list` [`str`], optional
        A list of the survey names to plot. Default to all surveys in the tier.
    basis_funtions : `list` [`str`], optional
        A list of names of basis function to plot. Defaults to all
        basis functions in the tier.
    plot_kwards : `dict`
        A dictionary of keyword parameters passed to
        `bokeh.plotting.figure`.

    Returns
    -------
    app : `bokeh.plotting.figure`
        The figure itself.
    """

    tier_reward_df = reward_df.set_index("tier_label").loc[tier_label, :].set_index("survey_label")
    # If surveys is set, only show listed surveys
    if surveys is not None:
        tier_reward_df = tier_reward_df.loc[surveys, :]

    # Show only the night in question
    tier_reward_df, mjd_limits = _extract_night(tier_reward_df, "queue_start_mjd", night, observatory)

    survey_labels = tier_reward_df.index.unique()
    num_surveys = len(survey_labels)
    if num_surveys < 1:
        plot = bokeh.plotting.figure(
            title="Reward",
            x_axis_label="MJD",
            y_axis_label="Reward",
            x_range=mjd_limits,
            **plot_kwargs,
        )
        message = bokeh.models.Label(
            x=10,
            y=70,
            x_units="screen",
            y_units="screen",
            text="No surveys selected for plotting",
        )
        plot.add_layout(message)
        return plot

    if num_surveys <= 10:
        colors = bokeh.palettes.Category10[max(4, num_surveys - 1)]
    else:
        colors = itertools.cycle(bokeh.palettes.Category20[min(num_surveys, 20)])

    if basis_function != "Total":
        try:
            y_column = "max_basis_reward"
            plot_title = f"Value of {basis_function}"
            y_axis_label = f"{basis_function} value"
            tier_value_df = (
                tier_reward_df.set_index("basis_function", append=True)
                .reorder_levels(["basis_function", "survey_label"])
                .loc[basis_function, :]
            ).drop_duplicates()
        except KeyError:
            # The basis fuction was not applicable to any selected surveys.
            plot = bokeh.plotting.figure(
                title=plot_title,
                x_axis_label="MJD",
                y_axis_label=y_axis_label,
                x_range=mjd_limits,
                **plot_kwargs,
            )
            message = bokeh.models.Label(
                x=10,
                y=70,
                x_units="screen",
                y_units="screen",
                text="No selected surveys have the selected basis function",
            )
            plot.add_layout(message)
            return plot

    if basis_function == "Total":
        y_column = "survey_reward"
        plot_title = "Total reward"
        y_axis_label = "Total reward returned for survey"
        tier_value_df = tier_reward_df.loc[
            :, ["queue_start_mjd", "queue_fill_mjd_ns", y_column]
        ].drop_duplicates()

    plot = bokeh.plotting.figure(
        title=plot_title,
        x_axis_label="MJD",
        y_axis_label=y_axis_label,
        x_range=mjd_limits,
        **plot_kwargs,
    )

    for survey_label, color in zip(tier_value_df.index.unique(), colors):
        this_survey_reward_df = tier_value_df.loc[[survey_label], :]

        survey_reward_ds = bokeh.models.ColumnDataSource(this_survey_reward_df)
        plot.scatter(
            x="queue_start_mjd",
            y=y_column,
            color=color,
            legend_label=survey_label,
            source=survey_reward_ds,
        )
        if obs_rewards is None:
            plot.line(
                x="queue_start_mjd",
                y=y_column,
                color=color,
                legend_label=survey_label,
                source=survey_reward_ds,
            )
        else:
            fill_mjds = set(this_survey_reward_df["queue_fill_mjd_ns"])
            fill_obs_mjds = obs_rewards.reset_index().set_index("queue_fill_mjd_ns")
            for fill_mjd in fill_mjds:
                try:
                    obs_mjds = fill_obs_mjds.loc[fill_mjd, "mjd"]
                except KeyError:
                    # The scheduler was called, but no visits chosen by the
                    # call were observed.
                    continue

                reward = this_survey_reward_df.query(f"queue_fill_mjd_ns=={fill_mjd}")[y_column][0]
                if not np.isfinite(reward):
                    continue

                if np.ndim(obs_mjds) == 0:
                    fill_source = bokeh.models.ColumnDataSource(
                        data={"obs_mjd": [obs_mjds], "reward": [reward]}
                    )
                else:
                    fill_source = bokeh.models.ColumnDataSource(
                        data={
                            "obs_mjd": obs_mjds,
                            "reward": np.full_like(obs_mjds, reward),
                        }
                    )
                plot.line(x="obs_mjd", y="reward", color=color, source=fill_source)

    plot.add_layout(plot.legend[0], "left")
    return plot


def plot_infeasible(reward_df, tier_label, night, observatory=None, surveys=None, plot_kwargs={}):
    """Create a plot showing infeasible basis functions.

    Parameters
    ----------
    reward_df : `pandas.DataFrame`
        The rewards by survey, as recorded by the `scheduler` instance
        when running the simulation.
    tier_label : `str`
        The label for the tier to plot.
    night : `astropy.time.Time`
        The night to plot.
    observatory : `ModelObservatory`
        The model observatory to use.
    surveys : `list` [`str`], optional
        A list of the survey names to plot. Default to all surveys in the tier.
    plot_kwards : `dict`
        A dictionary of keyword parameters passed to
        `bokeh.plotting.figure`.

    Returns
    -------
    app : `bokeh.plotting.figure`
        The figure itself.
    """
    tier_df = (reward_df.reset_index().set_index("tier_label").loc[tier_label, :]).query("not feasible")

    if surveys is not None:
        available_surveys = [s for s in surveys if s in tier_df.survey_label.unique()]
        if len(available_surveys) == 0:
            # None of the selected surveys have infeasible basis functions
            plot = bokeh.plotting.figure(
                title="Infeasible",
                x_axis_label="MJD",
                y_axis_label="Basis function",
                **plot_kwargs,
            )
            message = bokeh.models.Label(
                x=10,
                y=70,
                x_units="screen",
                y_units="screen",
                text="No surveys with infeasible basis functions selected",
            )
            plot.add_layout(message)
            return plot
        else:
            tier_df = tier_df.set_index("survey_label").loc[available_surveys, :].reset_index()

    tier_df, mjd_limits = _extract_night(tier_df, "queue_start_mjd", night, observatory)

    tier_df["survey_bf"] = list(zip(tier_df.survey_label, tier_df.basis_function))

    categories = (
        tier_df.sort_values(["survey_index", "basis_function"])
        .drop_duplicates("survey_bf")["survey_bf"]
        .values
    )
    factor_range = bokeh.models.FactorRange(*[tuple(c) for c in categories])

    # Keep bokeh from complaining about having to truncate the integer
    tier_df["queue_fill_mjd_ns"] = tier_df["queue_fill_mjd_ns"].astype(np.float64)
    infeasible_ds = bokeh.models.ColumnDataSource(tier_df)

    plot = bokeh.plotting.figure(
        title="Infeasible",
        x_axis_label="MJD",
        y_axis_label="Basis function",
        y_range=factor_range,
        x_range=mjd_limits,
        **plot_kwargs,
    )

    plot.scatter(x="queue_start_mjd", y="survey_bf", source=infeasible_ds)

    plot.yaxis.group_label_orientation = "horizontal"

    return plot
