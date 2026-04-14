"""Functions for converting data to HTML representations.

This module provides utility functions for converting various data structures
(such as pandas Series, DataFrames, and mappings) to HTML fragments for
inclusion in reports, dashboards, and interactive notebook displays.

The main conversion function `convert_to_html` handles multiple input types
and can optionally wrap content in collapsible ``<details>`` elements.
Additional convenience functions are provided for specific data types:
simulation metadata, night events, sun and moon positions, overhead summaries,
and survey visit summaries.
"""

from collections.abc import Mapping
from typing import Any, Sequence

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
) -> str:
    """Convert supported content objects into an HTML fragment.

    This function accepts either pre-rendered HTML text or several supported
    Python objects and converts them to HTML. The resulting HTML can be
    returned directly, wrapped under a heading, or wrapped in a collapsible
    ``<details>`` section.

    Parameters
    ----------
    content : `str` or `pandas.Series` or `pandas.DataFrame` or
        `matplotlib.figure.Figure` or `pandas.io.formats.style.Styler`
        Content to convert to HTML.

        - `str`: assumed to already be HTML content.
        - `pandas.Series`: converted to a one-column table and styled with
          left-aligned text.
        - `pandas.DataFrame` or `pandas.io.formats.style.Styler`: rendered via
          ``to_html`` under the configured pandas option context.
        - `matplotlib.figure.Figure`: converted via
          `schedview.plot.mpl_fig_to_html`.
    title : `str`, optional
        Title text to use in the section header or ``<summary>`` element.
        Required when ``collapsed`` is `True`.
    collapsed : `bool`, optional
        If `True`, wrap content in ``<details>``/``<summary>``. If `False`,
        return content directly when ``title`` is empty, or prepend an HTML
        heading when ``title`` is provided.
    heading_level : `int`, optional
        Heading level to use for non-collapsed titled output. Must be one of
        ``1`` through ``6``.
    pd_context_options : sequence, optional
        Positional arguments passed to `pandas.option_context` while rendering
        `pandas.DataFrame` and `pandas.io.formats.style.Styler` inputs. If
        `None`, `DEFAULT_PD_CONTEXT_OPTIONS` is used.

    Returns
    -------
    result : `str`
        HTML fragment containing the converted content and optional wrapper
        markup.

    Raises
    ------
    ValueError
        Raised if ``collapsed`` is `True` and ``title`` is empty.
    AssertionError
        Raised if final argument validation fails (for example, unsupported
        ``heading_level`` values).

    Notes
    -----
    Pandas display options are applied only within a local
    `pandas.option_context` block during DataFrame and Styler conversion.
    Generated HTML is returned as-is and is not sanitized by this function.
    """
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
    sim_index_info: pd.Series,
    shown_values: Sequence[str] = (
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
    collapsed: bool = True,
) -> str:
    """Convert simulation index information to an HTML representation.

    Parameters
    ----------
    sim_index_info : `pandas.Series`
        Simulation index information as returned by
        `rubin_sim.sim_archive.prenightindex.get_sim_index_info`.
        Must contain at least the fields in ``shown_values``.
    shown_values : sequence of `str`, optional
        Field names to include in the HTML representation. Default is a
        standard set of metadata fields including UUID, day observation,
        visit sequence label, telescope, URLs, and tags.
    collapsed : `bool`, optional
        If `True`, wrap the output in a ``<details>``/``<summary>`` element
        with the visit sequence label and telescope as the summary text.
        If `False`, return the content without collapsible wrapping.

    Returns
    -------
    html_representation : `str`
        HTML string containing the simulation index information.

    Notes
    -----
    The ``sim_index_info`` Series is expected to contain fields such as
    ``visitseq_uuid``, ``sim_creation_day_obs``, ``daily_id``,
    ``visitseq_label``, ``creation_time``, ``telescope``, ``visitseq_url``,
    ``config_url``, and ``tags``. The ``visitseq_label`` and ``telescope``
    fields are used to construct the summary title when ``collapsed=True``.
    """
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


def markup_additional_sim_files(
    sim_index_info: pd.Series,
    collapsed: bool = True,
) -> str:
    """Convert simulation additional files information to an HTML representation.

    Parameters
    ----------
    sim_index_info : `pandas.Series`
        Simulation index information as returned by
        `rubin_sim.sim_archive.prenightindex.get_sim_index_info`.
        Must contain a ``files`` attribute mapping file names to URIs.
    collapsed : `bool`, optional
        If `True`, wrap the output in a ``<details>``/``<summary>`` element
        with "Additional files available" as the summary text.
        If `False`, return the content without collapsible wrapping.

    Returns
    -------
    html_representation : `str`
        HTML string containing the list of additional files with their URIs.

    Notes
    -----
    The ``sim_index_info.files`` attribute is expected to be a dictionary-like
    mapping where keys are file names (e.g., "rewards", "scheduler_pickle") and
    values are URIs or paths to the files.
    """
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


def markup_sim_comments(
    sim_info: pd.Series,
    collapsed: bool = True,
) -> str:
    """Convert comments on a simulation to an HTML representation.

    Parameters
    ----------
    sim_info : `pandas.Series`
        Simulation index information as returned by
        `rubin_sim.sim_archive.prenightindex.get_sim_index_info`.
        Must contain a ``comments`` attribute mapping timestamps to comment
        content strings.
    collapsed : `bool`, optional
        If `True`, wrap the output in a ``<details>``/``<summary>`` element
        with "Comments recorded in the simulation metadata database" as the
        summary text. If `False`, return the content without collapsible
        wrapping.

    Returns
    -------
    html_representation : `str`
        HTML string containing the simulation comments with timestamps.

    Notes
    -----
    The ``sim_info.comments`` attribute is expected to be a dictionary-like
    mapping where keys are timestamp strings and values are comment content
    strings.
    """
    comment_content = ""
    for comment_time, comment_content in sim_info.comments.items():
        comment_content = comment_content + f"<h4>{comment_time}</h4><p>{comment_content}</p> "

    html_representation = convert_to_html(
        comment_content, "Comments recorded in the simulation metadata database", collapsed=collapsed
    )
    return html_representation


def markup_night_events(
    night_events: pd.DataFrame,
    collapsed: bool = True,
) -> str:
    """Convert a DataFrame of night astronomical events to HTML.

    Parameters
    ----------
    night_events : `pandas.DataFrame`
        A DataFrame of night astronomical events as returned by
        `schedview.compute.astro.night_events`. Must contain the following
        index values: 'sunset', 'sunrise', 'sun_n12_setting', 'sun_n12_rising',
        'night_middle'. Must contain the following columns: 'UTC'.
    collapsed : `bool`, optional
        If `True`, wrap the output in a ``<details>``/``<summary>`` element
        with a summary showing the times of key astronomical events.
        If `False`, return the content without collapsible wrapping.

    Returns
    -------
    html_representation : `str`
        HTML string containing the night events table, optionally wrapped in
        a collapsible details/summary element.
    """
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


def markup_sun_moon_positions(sun_moon_positions: Mapping[str, float], collapsed: bool = True) -> str:
    """Convert sun and moon position data to an HTML representation.

    Parameters
    ----------
    sun_moon_positions : `~collections.abc.Mapping` [`str`, `float`]
        Sun and moon position data as returned by
        ``ModelObservatory.almanac.get_sun_moon_positions(mjd)``.
        Must contain the following keys for the sun: ``sun_RA``, ``sun_dec``,
        ``sun_alt``, ``sun_az``.
        Must contain the following keys for the moon: ``moon_RA``, ``moon_dec``,
        ``moon_alt``, ``moon_az``, ``moon_phase``.
        Values are angles in radians (except phase which is in percent).
    collapsed : `bool`, optional
        If `True`, wrap the output in a ``<details>``/``<summary>`` element
        with a summary showing the approximate RA and dec of the sun and moon.
        If `False`, return the content without collapsible wrapping.

    Returns
    -------
    html_representation : `str`
        HTML string containing the sun and moon positions table, optionally
        wrapped in a collapsible details/summary element.

    Notes
    -----
    The position data is converted from radians to degrees in the resulting
    table. The table has two rows (sun and moon) and four columns (RA, dec,
    alt, az) plus a phase column for the moon.

    See Also
    --------
    schedview.compute.astro.compute_sun_moon_positions
        A similar function that returns a DataFrame of sun and moon positions.
    """
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


def markup_mapping_with_format(
    data: Mapping[str, Any],
    stat_name: Mapping[str, str],
    stat_str_template: Mapping[str, str],
    summary_fields: Sequence[str],
    title: str,
    collapsed: bool = True,
) -> str:
    """Convert a mapping of formatted statistics to an HTML representation.

    This function formats values from a data mapping using string templates,
    creates a DataFrame with the formatted values, and returns an HTML
    representation that can be wrapped in collapsible elements.

    Parameters
    ----------
    data : `~collections.abc.Mapping` [`str`, `Any`]
        Mapping of statistic keys to their values. These values will be
        formatted using the provided templates.
    stat_name : `~collections.abc.Mapping` [`str`, `str`]
        Mapping of statistic keys to display names used as the index in
        the resulting HTML table.
    stat_str_template : `~collections.abc.Mapping` [`str`, `str`]
        Mapping of statistic keys to Python string format templates.
        Each template should contain a single format specifier (e.g., ``"{}"``,
        ``"{:5.2f}"``) that will be filled with the corresponding data value.
    summary_fields : sequence of `str`
        List of statistic keys to include in the summary text when
        ``collapsed=True``. These must match keys in ``stat_name``.
    title : `str`
        Base title for the HTML representation. When ``collapsed=True``,
        this is overridden by a summary built from ``summary_fields``.
    collapsed : `bool`, optional
        If `True`, wrap the output in a ``<details>``/``<summary>`` element
        with a summary built from ``summary_fields``. If `False`, return
        the content without collapsible wrapping.

    Returns
    -------
    html_representation : `str`
        HTML string containing the formatted statistics table, optionally
        wrapped in a collapsible details/summary element.

    Notes
    -----
    The function processes each key in ``data`` by:
    1. Looking up the display name in ``stat_name``
    2. Formatting the value using ``stat_str_template``
    3. Creating a DataFrame with these formatted values

    This function is typically called indirectly via wrapper functions such as
    `markup_overhead_summary` and `markup_survey_visit_summary`.
    """
    index_values = [stat_name[k] for k in data]
    value_str = [stat_str_template[k].format(data[k]) for k in data]
    content = pd.DataFrame({"value": value_str}, index=index_values)
    if collapsed:
        title = ", ".join([f"{f}: {content.loc[f, 'value']}" for f in summary_fields])

    html_representation = convert_to_html(content.to_html(header=False), title, collapsed=collapsed)
    return html_representation


def markup_overhead_summary(overhead_summary: Mapping[str, Any], collapsed: bool = True) -> str:
    """Convert overhead summary statistics to an HTML representation.

    Parameters
    ----------
    overhead_summary : `~collections.abc.Mapping` [`str`, `Any`]
        Mapping of overhead statistic keys to their values. Expected keys are
        ``relative_start_time``, ``relative_end_time``, ``total_time``,
        ``num_exposures``, ``total_exptime``, ``mean_gap_time``,
        ``median_gap_time``.
    collapsed : `bool`, optional
        If `True`, wrap the output in a ``<details>``/``<summary>`` element
        with a summary built from key statistics. If `False`, return the
        content without collapsible wrapping.

    Returns
    -------
    html_representation : `str`
        HTML string containing the overhead summary statistics table,
        optionally wrapped in a collapsible details/summary element.
    """
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
    title = "Time on sky"
    summary_fields = ["Number of exposures", "Mean gap time", "Median gap time"]
    html_representation = markup_mapping_with_format(
        overhead_summary, stat_name, stat_str_template, summary_fields, title, collapsed=collapsed
    )
    return html_representation


def markup_survey_visit_summary(survey_visit_summary: Mapping[str, Any], collapsed: bool = True) -> str:
    """Convert survey visit summary statistics to an HTML representation.

    Parameters
    ----------
    survey_visit_summary : `~collections.abc.Mapping` [`str`, `Any`]
        Mapping of survey visit statistic keys to their values. Expected keys
        are ``n12_night_time``, ``n_survey_visits``, ``n_pairs_started``,
        ``n_pairs_finished``, ``ddfs_observed``, ``too_observed``.
    collapsed : `bool`, optional
        If `True`, wrap the output in a ``<details>``/``<summary>`` element
        with a summary built from key statistics. If `False`, return the
        content without collapsible wrapping.

    Returns
    -------
    html_representation : `str`
        HTML string containing the survey visit summary statistics table,
        optionally wrapped in a collapsible details/summary element.
    """
    stat_name = {
        "n12_night_time": "Time between 12 degree evening and morning twilights",
        "n_survey_visits": "Number of survey visits in night",
        "n_pairs_started": "Number of pairs started",
        "n_pairs_finished": "Number of pairs finished",
        "ddfs_observed": "DDFs Observed",
        "too_observed": "ToOs Observed",
    }
    stat_str_template = {
        "n12_night_time": "{:5.2f} hours",
        "n_survey_visits": "{}",
        "n_pairs_started": "{}",
        "n_pairs_finished": "{}",
        "ddfs_observed": "{}",
        "too_observed": "{}",
    }
    title = "Survey visit counts"
    summary_fields = ["Number of survey visits in night", "DDFs Observed", "ToOs Observed"]
    html_representation = markup_mapping_with_format(
        survey_visit_summary, stat_name, stat_str_template, summary_fields, title, collapsed=collapsed
    )
    return html_representation
