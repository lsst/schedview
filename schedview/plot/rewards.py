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
    user_plot_kwargs={},
    user_rect_dict={},
    cmap=None,
):

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

    plot_kwargs = {
        "x_axis_label": "Time",
        "x_axis_type": "datetime",
        "y_range": factor_range,
    }
    plot_kwargs.update(user_plot_kwargs)
    plot = bokeh.plotting.figure(**plot_kwargs)

    plot.xaxis[0].formatter = bokeh.models.DatetimeTickFormatter(hours="%H:%M")

    # Make the reward limit range slider
    values = df[value_column].values
    values_in_range = values[np.isfinite(values) & (values >= value_range_min) & (values <= value_range_max)]
    value_range_min = np.min(values_in_range)
    value_range_max = np.max(values_in_range)
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
            nan_color="red",
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

    # Put rectangles on the plot
    rect_kwargs = dict(
        x="datetime",
        y=factor_column,
        width=30.0 / (24 * 60 * 60),
        height=height_map,
        color=cmap,
        source=data_source,
    )
    rect_kwargs.update(user_rect_dict)
    rectangles = plot.rect(**rect_kwargs)

    infeasible = np.isneginf(df[value_column])
    if "feasible" in df:
        infeasible = np.logical_or(infeasible, np.logical_not(df.feasible))

    plot.scatter(
        x="datetime",
        y=factor_column,
        marker="x",
        color="red",
        size=10,
        source=data_source,
        view=bokeh.models.CDSView(filter=bokeh.models.BooleanFilter(infeasible)),
    )

    plot.scatter(
        x="datetime",
        y=factor_column,
        marker="triangle",
        color="black",
        alpha=0.5,
        size=10,
        source=data_source,
        view=bokeh.models.CDSView(filter=bokeh.models.BooleanFilter(np.isposinf(df[value_column]))),
    )

    plot.yaxis.group_label_orientation = "horizontal"

    # Add the color bar
    colorbar = rectangles.construct_color_bar()
    plot.add_layout(colorbar, "below")

    # Combine the range selection slider and the plot
    col = bokeh.layouts.column([plot, value_limit_selector])
    return col


def reward_timeline_for_tier(rewards_df, tier, day_obs_mjd, **figure_kwargs):
    rewards_df = rewards_df.query(
        f'tier_label == "tier {tier}" and floor(queue_start_mjd-0.5)=={day_obs_mjd}'
    ).copy()
    rewards_df.loc[~rewards_df.feasible, "max_basis_reward"] = np.nan
    rewards_df["tier_survey_bf"] = list(
        zip(rewards_df.tier_label, rewards_df.survey_label, rewards_df.basis_function)
    )
    rewards_df.sort_index(ascending=False, inplace=True)

    plot_kwargs = {
        "title": "Maximum values of basis functions",
        "y_axis_label": "basis function",
        "height": max(256, 15 * len(rewards_df.tier_survey_bf.unique())),
        "width": 1024,
    }
    plot = make_timeline_bars(rewards_df, "tier_survey_bf", "max_basis_reward", user_plot_kwargs=plot_kwargs)
    return plot


def reward_timeline_for_surveys(rewards_df, day_obs_mjd, **figure_kwargs):
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
        "title": "Survey rewards",
        "y_axis_label": "survey",
        "height": max(256, 20 * len(survey_rewards_df.tier_survey.unique())),
        "width": 1024,
    }
    plot = make_timeline_bars(
        survey_rewards_df, "tier_survey", "survey_reward", value_range_max=100, user_plot_kwargs=plot_kwargs
    )
    return plot
