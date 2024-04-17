import warnings

import bokeh
import colorcet
import holoviews as hv
import numpy as np
import pandas as pd
from astropy.time import Time

# Imported to help sphinx make the link
from rubin_scheduler.scheduler.model_observatory import ModelObservatory  # noqa F401

import schedview.collect.opsim
import schedview.collect.scheduler_pickle
import schedview.compute.astro
import schedview.compute.scheduler

__all__ = [
    "plot_survey_rewards",
    "create_survey_reward_plot",
    "reward_timeline_for_tier",
    "area_timeline_for_tier",
    "reward_timeline_for_surveys",
]


def plot_survey_rewards(rewards):
    """Plot survey rewards as a function of time.

    Parameters
    ----------
    rewards : `pandas.DataFrame`
        Data with at least these columns:

        ``"survey_name"``
            The name of the survey (`str`).
        ``"time"``
            The sample time for the reward (`datetime64[ns]`).
        ``"reward"``
            The reward (`float`).

    Returns
    -------
    reward_plot : `bokeh.plotting.figure`
        The figure.
    """
    reward_plot = (
        rewards.replace([np.inf, -np.inf], np.nan)
        .loc[:, ["survey_name", "time", "reward"]]
        .hvplot(by=["survey_name"], x="time", y=["reward"], title="Rewards for each survey")
        .options({"Curve": {"color": hv.Cycle("Category20")}})
    )
    return reward_plot


def create_survey_reward_plot(
    scheduler,
    night_date,
    additional_visits=None,
    observatory=None,
    timezone="Chile/Continental",
):
    """Build a plot of rewards by survey for a time period.

    Parameters
    ----------
    scheduler : `rubin_scheduler.scheduler.schedulers.Core_scheduler` or `str`
        The scheduler with the surveys to evaluate, or the name of a file
        from which such a scheduler should be loaded.
    night_date : `astropy.time.Time`
        A time during the night to plot.
    additional_visits : `pandas.DataFrame` or `str`, optional
        Visits to add to the scheduler before reward evaluation,
        by default None
    observatory : `ModelObservatory`, optional
        Provides the location of the observatory, used to compute
        night start and end times.
        By default None
    timezone : `str`, optional
        Timezone for horizontal axis, by default "Chile/Continental"

    Returns
    -------
    figure : `bokeh.plotting.figure`
        The figure itself.
    data : `dict`
        The arguments used to produce the figure using
        `plot_survey_rewards`.
    """

    site = None if observatory is None else observatory.location

    # Collect
    if isinstance(scheduler, str):
        scheduler, conditions = schedview.collect.scheduler_pickle.read_scheduler(scheduler)
        scheduler.update_conditions(conditions)

    if isinstance(additional_visits, str):
        night_events = schedview.compute.astro.night_events(
            night_date=night_date, site=site, timezone=timezone
        )
        start_time = Time(night_events.loc["sunset", "UTC"])
        end_time = Time(night_events.loc["sunrise", "UTC"])
        additional_visits = schedview.collect.opsim.read_opsim(
            additional_visits, Time(start_time).iso, Time(end_time).iso
        )

    # Compute
    if additional_visits is not None:
        schedview.compute.scheduler.replay_visits(scheduler, additional_visits)

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=FutureWarning)
        rewards = schedview.compute.scheduler.compute_basis_function_rewards(scheduler)

    # Plot
    data = {"rewards": rewards}
    reward_plot = hv.render(plot_survey_rewards(**data))
    return reward_plot, data


def make_timeline_bars(
    df,
    factor_column,
    value_column,
    value_range_min=-np.inf,
    value_range_max=np.inf,
    user_infeasible_kwargs=None,
    user_max_kwargs=None,
    user_plot_kwargs={},
    user_rect_dict={},
    cmap=None,
):
    """Create a stacked set of timelines with vertical colored bars.

    Parameters
    ----------
    df : `pandas.DataFrame`
        The table of the data to plot.
    factor_column : `str`
        The name of the column determining the horizontal line on which
        values will be plotted.
    value_column : `str`
        The name of the column to map to bar height and color.
    value_range_min : `float`
        The low extreme value for height and color mapping.
        Defaults to `-numpy.inf`.
    value_range_max : `float`
        The high extreme value for height and color mapping.
        Defaults to `-numpy.inf`.
    user_infeasible_kwargs : `dict` or `None`
        Keyword arguments passed to `bokeh.plotting.figure.scatter` for
        points flagged infeasible. Defaults to `None`.
    user_max_kwargs : `dict` or `None`
        Keyword arguments passed to `bokeh.plotting.figure.scatter` for
        points with values higher than the range.
        Defaults to `None`.
    user_plot_kwargs : `dict` or `None`
        Keyword arguments passed to `bokeh.plotting.figure` when creating
        the instantiating it.
    user_rect_kwargs : `dict` or `None`
        Keyword arguments passed to `bokeh.plotting.figure.rect` for
        points within range.
    cmap : `Sequence` [`bokeh.colors.ColorLike`]
        The color map to use to color the rectangles.

    Returns
    -------
    `plot` : `bokeh.models.layouts.LayoutDOM`
        The plot that can be shown or saved.
    """
    # Make the data source
    data_source = bokeh.models.ColumnDataSource(df)
    data_source.data["datetime"] = pd.to_datetime(df.queue_start_mjd + 2400000.5, origin="julian", unit="D")

    # Make the figure
    if "y_range" not in user_plot_kwargs:
        factor_range = bokeh.models.FactorRange(
            *[tuple(c) for c in df[factor_column].drop_duplicates().values]
        )
    else:
        factor_range = user_plot_kwargs["y_range"]

    hover_tool = bokeh.models.HoverTool(
        tooltips=[
            ("Time", "@datetime{%Y-%m-%d %H:%M:%S}"),
            ("MJD", "@queue_start_mjd{00000.000}"),
            (value_column.replace("_", " "), f"@{value_column}"),
        ],
        formatters={"@datetime": "datetime"},
    )

    plot_kwargs = {
        "x_axis_label": "Time",
        "x_axis_type": "datetime",
        "y_range": factor_range,
        "tools": ["pan", "wheel_zoom", "box_zoom", "save", "reset", "help", hover_tool],
    }
    plot_kwargs.update(user_plot_kwargs)
    plot = bokeh.plotting.figure(**plot_kwargs)
    plot.xaxis[0].formatter = bokeh.models.DatetimeTickFormatter(hours="%H:%M")

    # Make the reward limit range slider
    values = df[value_column].values
    values_in_range = values[np.isfinite(values) & (values >= value_range_min) & (values <= value_range_max)]
    # Use nextafter so that the "high color" and "low color" are only
    # applied to value that actually fall outside the range, not
    # the ones actually on the limit (which do actually correspond
    # to the value on the scale).
    value_range_min = np.nextafter(np.min(values_in_range), -np.inf)
    value_range_max = np.nextafter(np.max(values_in_range), np.inf)
    if value_range_max == value_range_min:
        value_range_max = value_range_min + 1
        value_range_min = value_range_max - 2

    value_limit_selector = bokeh.models.RangeSlider(
        title="limits",
        width_policy="max",
        start=value_range_min,
        end=value_range_max,
        step=(value_range_max - value_range_min) / 100.0,
        value=(value_range_min, value_range_max),
    )

    # Make the color map
    if cmap is None:
        cmap = bokeh.transform.linear_cmap(
            field_name=value_column,
            palette=list(reversed(colorcet.palette["CET_I3"])),
            low=value_range_min,
            high=value_range_max,
            low_color="red",
            high_color="black",
            nan_color="magenta",
        )

    # Update the color map when the range slider changes
    value_limit_select_jscode = """
        const min_value = limit_select.value[0];
        const max_value = limit_select.value[1];
        color_map.transform.low = min_value;
        color_map.transform.high = max_value;
    """
    value_limit_change_callback = bokeh.models.CustomJS(
        args={"color_map": cmap, "limit_select": value_limit_selector}, code=value_limit_select_jscode
    )
    value_limit_selector.js_on_change("value", value_limit_change_callback)

    # Map the reward to the height
    height_transform_jscode = """
        const height = new Float64Array(xs.length);
        const low = limit_selector.value[0]
        const high = limit_selector.value[1]
        for (let i = 0; i < xs.length; i++) {
            if (xs[i] < low) {
                height[i] = min_height;
            } else if (xs[i] > high) {
                height[i] = max_height;
            } else {
                height[i] = min_height +  (xs[i]-low) * (max_height-min_height)/(high-low)
            }
        }
        return height
    """
    height_transform = bokeh.models.CustomJSTransform(
        args={"limit_selector": value_limit_selector, "min_height": 0.1, "max_height": 1.0},
        v_func=height_transform_jscode,
    )
    height_map = bokeh.transform.transform(value_column, height_transform)

    infeasible = np.isneginf(df[value_column])
    if "feasible" in df:
        infeasible = np.logical_or(infeasible, np.logical_not(df.feasible))

    # Put rectangles on the plot
    # Do not show infinite or infeasible values; the get their own symbols
    # implemented later on.

    rect_filter_data = ~np.logical_or(np.isposinf(df[value_column]), infeasible)
    if bokeh.__version__.startswith("3.3"):
        # Work around a bug in bokeh 3.3.x: https://github.com/bokeh/bokeh/issues/13660
        rect_filter_data = rect_filter_data.tolist()
    rect_filter = bokeh.models.BooleanFilter(rect_filter_data)
    rect_view = bokeh.models.CDSView(filter=rect_filter)

    rect_kwargs = dict(
        x="datetime",
        y=factor_column,
        width=pd.Timedelta(30, unit="s"),
        height=height_map,
        color=cmap,
        source=data_source,
        view=rect_view,
    )
    rect_kwargs.update(user_rect_dict)
    rectangles = plot.rect(**rect_kwargs)

    # Mark infeasible points

    infeasible_filter_data = infeasible
    if bokeh.__version__.startswith("3.3"):
        # Work around a bug in bokeh 3.3.x: https://github.com/bokeh/bokeh/issues/13660
        infeasible_filter_data = infeasible_filter_data.tolist()
    infeasible_filter = bokeh.models.BooleanFilter(infeasible_filter_data)
    infeasible_view = bokeh.models.CDSView(filter=infeasible_filter)

    infeasible_kwargs = {"marker": "x", "color": "red", "size": 10, "view": infeasible_view}
    if user_infeasible_kwargs is not None:
        infeasible_kwargs.update(user_infeasible_kwargs)
    plot.scatter(
        x="datetime",
        y=factor_column,
        source=data_source,
        **infeasible_kwargs,
    )

    # Mark infinite points
    infinite_filter_data = np.isposinf(df[value_column])
    if bokeh.__version__.startswith("3.3"):
        # Work around a bug in bokeh 3.3.x: https://github.com/bokeh/bokeh/issues/13660
        infinite_filter_data = infinite_filter_data.tolist()
    infinite_filter = bokeh.models.BooleanFilter(infinite_filter_data)
    infinite_view = bokeh.models.CDSView(filter=infinite_filter)

    max_kwargs = {"marker": "triangle", "color": "black", "alpha": 0.5, "size": 10, "view": infinite_view}
    if user_max_kwargs is not None:
        max_kwargs.update(user_max_kwargs)
    plot.scatter(
        x="datetime",
        y=factor_column,
        source=data_source,
        **max_kwargs,
    )

    plot.yaxis.group_label_orientation = "horizontal"

    # Add the color bar
    colorbar = rectangles.construct_color_bar()
    plot.add_layout(colorbar, "below")

    # Combine the range selection slider and the plot
    col = bokeh.layouts.column([plot, value_limit_selector])

    return col


def reward_timeline_for_tier(rewards_df, tier, day_obs_mjd, show=True, **figure_kwargs):
    """Plot the reward timeline for basis functions in a specified tier.

    Parameters
    ----------
    rewards_df : `pandas.DataFrame`
        The table of rewards data.
    tier : `int`
        The tier index, corresponding to the index of
        `rubin_scheduler.scheduler.schedulers.CoreScheduler.survey_lists`.
    day_obs_mjd : `int`
        The MJD of the day_obs of the night to plot.
    show : `bool`
        Actually show the plot? Defaults to `True`.
    **figure_kwargs
        Keyword arguments passed to `bokeh.plotting.figure`.

    Returns
    -------
    `plot` : `bokeh.models.layouts.LayoutDOM`
        The plot that can be shown or saved.
    """
    rewards_df = rewards_df.query(
        f'tier_label == "tier {tier}" and floor(queue_start_mjd-0.5)=={day_obs_mjd}'
    ).copy()
    rewards_df.loc[~rewards_df.feasible, "max_basis_reward"] = np.nan
    rewards_df["tier_survey_bf"] = list(
        zip(rewards_df.tier_label, rewards_df.survey_label, rewards_df.basis_function)
    )
    rewards_df.sort_index(ascending=False, inplace=True)

    plot_kwargs = {
        "title": "Basis function values (maximum over the sky)",
        "y_axis_label": "basis function",
        "height": max(256, 15 * len(rewards_df.tier_survey_bf.unique())),
        "width": 1024,
    }

    if plot_kwargs["height"] <= 4096:
        plot = make_timeline_bars(
            rewards_df, "tier_survey_bf", "max_basis_reward", user_plot_kwargs=plot_kwargs
        )
        if show:
            bokeh.io.show(plot)
    else:
        print(f"Too many basis functions to plot, would by {plot_kwargs['height']} high.")
        plot = None

    return plot


def area_timeline_for_tier(rewards_df, tier, day_obs_mjd, show=True, **figure_kwargs):
    """Plot the feasible area timeline for basis funcs in a specified tier.

    Parameters
    ----------
    rewards_df : `pandas.DataFrame`
        The table of rewards data.
    tier : `int`
        The tier index, corresponding to the index of
        `rubin_scheduler.scheduler.schedulers.CoreScheduler.survey_lists`.
    day_obs_mjd : `int`
        The MJD of the day_obs of the night to plot.
    show : `bool`
        Actually show the plot? Defaults to `True`.
    **figure_kwargs
        Keyword arguments passed to `bokeh.plotting.figure`.

    Returns
    -------
    `plot` : `bokeh.models.layouts.LayoutDOM`
        The plot that can be shown or saved.
    """
    rewards_df = rewards_df.query(
        f'tier_label == "tier {tier}" and floor(queue_start_mjd-0.5)=={day_obs_mjd}'
    ).copy()
    rewards_df.loc[~rewards_df.feasible, "basis_area"] = np.nan
    rewards_df["tier_survey_bf"] = list(
        zip(rewards_df.tier_label, rewards_df.survey_label, rewards_df.basis_function)
    )
    rewards_df.sort_index(ascending=False, inplace=True)
    # Mark "whole sky" (usually scalars) specially using "max" markers.
    rewards_df.loc[np.nextafter(rewards_df["basis_area"], np.inf) > 4 * 180 * 180 / np.pi, "basis_area"] = (
        np.inf
    )

    plot_kwargs = {
        "title": "Feasible area for basis function (sq. deg.)",
        "y_axis_label": "basis function",
        "height": max(256, 15 * len(rewards_df.tier_survey_bf.unique())),
        "width": 1024,
    }
    max_kwargs = {"color": "blue", "marker": "circle", "line_alpha": 1, "fill_alpha": 0, "size": 8}

    if plot_kwargs["height"] <= 4096:
        try:
            plot = make_timeline_bars(
                rewards_df,
                "tier_survey_bf",
                "basis_area",
                user_max_kwargs=max_kwargs,
                user_plot_kwargs=plot_kwargs,
            )

            if show:
                bokeh.io.show(plot)
        except ValueError:
            plot = None
    else:
        print(f"Too many surveys to plot, would by {plot_kwargs['height']} high.")
        plot = None

    return plot


def reward_timeline_for_surveys(rewards_df, day_obs_mjd, show=True, **figure_kwargs):
    """Plot the reward timeline for all surveys.

    Parameters
    ----------
    rewards_df : `pandas.DataFrame`
        The table of rewards data.
    day_obs_mjd : `int`
        The MJD of the day_obs of the night to plot.
    show : `bool`
        Actually show the plot? Defaults to `True`.
    **figure_kwargs
        Keyword arguments passed to `bokeh.plotting.figure`.

    Returns
    -------
    `plot` : `bokeh.models.layouts.LayoutDOM`
        The plot that can be shown or saved.
    """
    survey_rewards_df = (
        rewards_df.groupby(["list_index", "survey_index", "queue_start_mjd", "queue_fill_mjd_ns"])
        .agg(
            {
                "tier_label": "first",
                "survey_label": "first",
                "survey_class": "first",
                "survey_reward": "first",
                "feasible": "all",
            }
        )
        .loc[:, ["tier_label", "survey_label", "survey_class", "survey_reward", "feasible"]]
        .reset_index(level=["queue_start_mjd", "queue_fill_mjd_ns"])
        .query(f"floor(queue_start_mjd-0.5)=={day_obs_mjd}")
        .sort_index(ascending=False)
    )
    survey_rewards_df.loc[~survey_rewards_df.feasible, "survey_reward"] = np.nan
    survey_rewards_df["tier_survey"] = list(zip(survey_rewards_df.tier_label, survey_rewards_df.survey_label))
    plot_kwargs = {
        "title": "Survey rewards (maximum over the region of interest)",
        "y_axis_label": "survey",
        "height": max(256, 20 * len(survey_rewards_df.tier_survey.unique())),
        "width": 1024,
    }

    if plot_kwargs["height"] <= 4096:
        plot = make_timeline_bars(
            survey_rewards_df,
            "tier_survey",
            "survey_reward",
            value_range_max=100,
            user_plot_kwargs=plot_kwargs,
        )
        if show:
            bokeh.io.show(plot)
    else:
        print(f"Too many surveys to plot, would by {plot_kwargs['height']} high.")
        plot = None

    return plot
