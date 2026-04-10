from typing import Sequence

import matplotlib as mpl
import numpy as np
import pandas as pd
import pandas.io.formats.style

from . import mpl_fig_to_html

DEFAULT_PD_CONTEXT_OPTIONS = ("display.width", 300, "display.max_colwidth", None)


def convert_to_html(
    content: str | pd.Series | pd.DataFrame | mpl.figure.Figure | pd.io.formats.style.Styler,
    title: str = "",
    collapsed: bool = True,
    heading_level: int = 3,
    pd_context_options: Sequence | None = None,
):
    # If no pandas context options are specified, use the defaults
    if pd_context_options is None:
        pd_context_options = DEFAULT_PD_CONTEXT_OPTIONS

    pd_context_options = list(pd_context_options)

    # Convert recognized non-HTML to HTML
    if isinstance(content, pd.Series):
        content = content.to_frame().style.hide(axis="columns").set_properties(**{"text-align": "left"})

    if isinstance(content, pd.DataFrame) or isinstance(content, pd.io.formats.style.Styler):
        with pd.option_context(*pd_context_options):
            content = content.to_html()

    if isinstance(content, mpl.figure.Figure):
        content = mpl_fig_to_html(content)

    # After processing our arguments, make sure all the types are as expected.
    assert isinstance(content, str), f"content not a string, was {type(content)}"
    assert isinstance(pd_context_options, list), "context options not a list"
    assert heading_level in (1, 2, 3, 4, 5, 6), "heading level invalid"

    result: str
    if collapsed:
        if len(title) < 1:
            raise ValueError("If a section is collapsed, it must have a title")
        result = f"""
            <details>
            <summary><b>{title}</b>
            </summary>
            {content}
            </details>
        """
    else:
        if len(title) < 1:
            result = content
        else:
            result = f"""
                <h{heading_level}>{title}</h{heading_level}>
                {content}
            """

    return result


def markup_sim_index_info(
    sim_index_info,
    shown_values=(
        "visitseq_uuid",
        "sim_creation_day_obs",
        "daily_id",
        "visitseq_label",
        "creation_time",
        "telescope",
        "visitseq_url",
        "config_url",
        "tags",
    ),
    collapsed=True,
):
    content = (
        sim_index_info[list(shown_values)]
        .to_frame()
        .style.hide(axis="columns")
        .set_properties(**{"text-align": "left"})
        .to_html()
    )
    title = f"{sim_index_info['visitseq_label']} ({sim_index_info['telescope']})"
    html_representation = convert_to_html(content, title, collapsed=collapsed)
    return html_representation


def markup_additional_sim_files(sim_index_info, collapsed=True):
    content = (
        pd.Series(sim_index_info.files)
        .to_frame()
        .rename(columns={0: "URI"})
        .style.set_properties(**{"text-align": "left"})
        .to_html()
    )
    title = "Additional files available"
    html_representation = convert_to_html(content, title, collapsed=collapsed)
    return html_representation


def markup_sim_comments(sim_info, collapsed=True):
    comment_content = ""
    for comment_time, comment_content in sim_info.comments.items():
        comment_content = comment_content + f"<h4>{comment_time}</h4><p>{comment_content}</p> "

    html_representation = convert_to_html(
        comment_content, "Comments recorded in the simulation metadata database", collapsed=collapsed
    )
    return html_representation


def markup_night_events(night_events, collapsed=True):
    if collapsed:
        title = f"""
            Sunset: {night_events.loc['sunset', 'UTC'].isoformat()[11:19]}Z,
            evening 12&#176: {night_events.loc['sun_n12_setting', 'UTC'].isoformat()[11:19]}Z,
            morning 12&#176;: {night_events.loc['sun_n12_rising', 'UTC'].isoformat()[11:19]}Z,
            Sunrise: {night_events.loc['sunrise', 'UTC'].isoformat()[11:19]}Z
        """
    else:
        title = "Night events"

    html_representation = convert_to_html(night_events, title, collapsed=collapsed)
    return html_representation


def markup_sun_moon_positions(sun_moon_positions, collapsed=True):
    body_positions_wide = pd.DataFrame(sun_moon_positions)
    body_positions_wide.index.name = "r"
    body_positions_wide.reset_index(inplace=True)

    angle_columns = ["RA", "dec", "alt", "az"]
    all_columns = angle_columns + ["phase"]
    body_positions = (
        pd.wide_to_long(body_positions_wide, stubnames=("sun", "moon"), suffix=r".*", sep="_", i="r", j="")
        .droplevel("r")
        .T[all_columns]
    )
    body_positions[angle_columns] = np.degrees(body_positions[angle_columns])
    if collapsed:
        title = f"""
            Sun &alpha;={body_positions.loc['sun','RA'].round()}&#176,
            &delta;={body_positions.loc['sun','dec'].round()}&#176;
            Moon &alpha;={body_positions.loc['moon','RA'].round()}&#176,
            &delta;={body_positions.loc['moon','dec'].round()}&#176;
        """
    else:
        title = "Sun and moon"

    html_representation = convert_to_html(body_positions, title, collapsed=collapsed)
    return html_representation


def markup_overhead_summary(overhead_summary, collapsed=True):
    stat_name = {
        "relative_start_time": "Open shutter of first exposure",
        "relative_end_time": "Close shutter of last exposure",
        "total_time": "Total wall clock time",
        "num_exposures": "Number of exposures",
        "total_exptime": "Total open shutter time",
        "mean_gap_time": "Mean gap time",
        "median_gap_time": "Median gap time",
    }
    stat_str_template = {
        "relative_start_time": "{:5.2f} minutes after 12 degree evening twilight",
        "relative_end_time": "{:5.2f} minutes before 12 degree morning twilight",
        "total_time": "{:4.2f} hours",
        "num_exposures": "{}",
        "total_exptime": "{:4.2f} hours",
        "mean_gap_time": "{:7.2f} seconds",
        "median_gap_time": "{:7.2f} seconds",
    }
    index_values = [stat_name[k] for k in overhead_summary]
    value_str = [stat_str_template[k].format(overhead_summary[k]) for k in overhead_summary]
    content = pd.DataFrame({"value": value_str}, index=index_values)
    if collapsed:
        summary_fields = ["Number of exposures", "Mean gap time", "Median gap time"]
        title = ", ".join([f"{f}: {content.loc[f, 'value']}" for f in summary_fields])
    else:
        title = "Time on sky"

    html_representation = convert_to_html(content.to_html(header=False), title, collapsed=collapsed)
    return html_representation
