import datetime
import email.utils
import hashlib
import os
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pandas as pd
from rubin_scheduler.site_models import Almanac

from schedview.compute.smallsum import compute_tinysum, format_band_breakdown

RSS_DESC_FORMAT = """
Total visits: {total};
Science visits: {science};
Median FWHM: {fwhm};
Mean visit rate: {visit_rate} visits/hour;
Total eff_time / total exp_time: {mean_norm_teff};
Total eff_time / total night time: {teff_rate};
Science targets: {targets}
"""


def find_reports(
    report_dir: str = "/sdf/data/rubin/shared/scheduler/reports",
    url_base: str = "https://usdf-rsp-int.slac.stanford.edu/schedview-static-pages",
) -> pd.DataFrame:
    """Find static schedview reports by walking the report directory.

    Parameters
    ----------
    report_dir : `str`
        The root path of the directory with the reports
    urs_base : `str`
        The base of the that serves files in the report dir

    Returns
    -------
    reports : `pandas.DataFrame`
        A `pandas.DataFrame` with the following columns:

        ``night``
            The local calendar date of the night start (`datetime.date`).
        ``dayobs``
            The SITCOMTN-032 dayobs of the night (`int`).
        ``report``
            The report name (`str`).
        ``instrument``
            The instrument (`str`).
        ``url``
            The URL for the report (`str`).
        ``report_time``
            The file creation time for the report (`datetime.datetime`).
        ``fname``
            The filename of the report.
    """

    report_list = []
    for dir_path, dir_names, file_names in os.walk(report_dir):
        this_path = Path(dir_path)
        for file_name in file_names:
            if file_name.endswith(".html"):
                file_path = str(this_path.joinpath(file_name))
                relative_path = file_path[len(report_dir) + 1 :]
                file_parts = relative_path.split("/")
                if len(file_parts) == 6:
                    report, instrument, year_str, month_str, day_str, _ = file_parts
                    dayobs = year_str + month_str + day_str
                    night_iso = "-".join([year_str, month_str, day_str])
                    night_date = datetime.date.fromisoformat(night_iso)
                    url = "/".join([url_base, relative_path])
                    link = f'<a href="{url}" target="_blank" rel="noopener noreferrer">{report}</a>'
                    mtime = datetime.datetime.fromtimestamp(
                        Path(file_path).stat().st_mtime, datetime.UTC
                    ).isoformat()
                    report_list.append(
                        pd.Series(
                            dict(
                                night=night_date,
                                dayobs=dayobs,
                                report=report,
                                instrument=instrument,
                                url=url,
                                link=link,
                                report_time=mtime,
                                fname=file_name,
                            )
                        )
                    )

    reports = (
        pd.DataFrame(report_list).set_index(["instrument", "dayobs"]).sort_values("night", ascending=False)
    )

    return reports


INT_SUMMARY_COLUMNS = [
    "Total",
    "science",
]

FLOAT_SUMMARY_COLUMNS = [
    "night_hours",
    "median FWHM",
    "total eff_time/total exp_time",
]

SUMMARY_COLUMNS = INT_SUMMARY_COLUMNS + FLOAT_SUMMARY_COLUMNS


def make_report_link_table(
    reports: pd.DataFrame,
    report_columns=("prenight", "multiprenight", "nightsum", "compareprenight"),
    visits: pd.DataFrame | None = None,
) -> str:
    """Generate an html table of links to reports.

    Parameters
    ----------
    reports : `pd.DataFrame`
        A DataFrame of report metadata, as returned by `find_reports`.
    report_columns : `tuple`
        A list of names of reports.
    visits : `pd.DataFrame` or `None`, optional
        A DataFrame of visits as returned by
        `schedview.collect.visits.cached_read_visits`. If supplied, a short
        per-night summary is computed via
        `schedview.compute.smallsum.compute_tinysum` and the resulting
        columns are joined onto the ``lsstcam`` rows of the table.
        Non-``lsstcam`` rows receive ``NA`` for these columns.
        Defaults to ``None``, in which case no summary columns are added.

    Returns
    -------
    report_table_html : `str`
        The HTML formatted table with links.
    """

    report_links = (
        reports.reset_index()
        .pivot(index=("night", "instrument"), columns="report", values="link")
        .sort_values("night", ascending=False)
        .fillna("")
        .reindex(columns=list(report_columns))
    )

    if visits is not None:
        almanac = Almanac()
        tinysum = compute_tinysum(visits, almanac=almanac)[SUMMARY_COLUMNS]
        tinysum.index = pd.to_datetime(tinysum.index.astype(str), format="%Y%m%d").date
        tinysum.index.name = "night"

        # Build a mask for lsstcam rows and extract their nights
        lsstcam_mask = report_links.index.get_level_values("instrument") == "lsstcam"
        _ = report_links.index[lsstcam_mask].get_level_values("night")

        # Map tinysum by night onto the full report_links index, then join.
        # Reindex to the full index (non-lsstcam rows and missing nights get
        # NA) so that dtypes (including Int64) are preserved through
        # the assignment.
        summary_full = tinysum.reindex(report_links.index.get_level_values("night"))
        summary_full.index = report_links.index
        # Only lsstcam rows should receive values; blank out the rest
        summary_full.loc[~lsstcam_mask] = None
        for col in SUMMARY_COLUMNS:
            report_links[col] = summary_full[col]

    # Round float columns to 2 decimal places, then convert all summary
    # columns to object dtype so fillna("") works uniformly regardless of
    # whether pandas chose Int64, Float64, etc.
    summary_cols_present = [c for c in SUMMARY_COLUMNS if c in report_links.columns]
    float_cols_present = [c for c in FLOAT_SUMMARY_COLUMNS if c in report_links.columns]
    for col in float_cols_present:
        report_links[col] = report_links[col].round(2)
    for col in summary_cols_present:
        report_links[col] = report_links[col].astype(object)

    report_table_html = report_links.fillna("").to_html(escape=False)
    return report_table_html


def _format_summary_desc(tinysum: pd.DataFrame, dayobs: int, report: str, instrument: str, night) -> str:
    """Format an RSS item description from a ``compute_tinysum`` row.

    Parameters
    ----------
    tinysum : `pandas.DataFrame`
        Per-night summary as returned by
        `schedview.compute.smallsum.compute_tinysum`.
    dayobs : `int`
        The dayobs (YYYYMMDD) of the night, used to index ``tinysum``.
    report : `str`
        The report name (e.g. ``"nightsum"`` or ``"prenight"``).
    instrument : `str`
        The instrument name.
    night : `datetime.date`
        The local calendar date of the night start.

    Returns
    -------
    desc : `str`
        The formatted ``RSS_DESC_FORMAT`` text for the night.
    """
    try:
        teff_rate = np.round(tinysum.loc[dayobs, "teff/night duration"], 2)
    except TypeError:
        teff_rate = np.nan
    row = tinysum.loc[dayobs]
    total_bands = format_band_breakdown(row, suffix="")
    science_bands = format_band_breakdown(row, suffix=" science")
    total_str = f"{row['Total']}" + (f" ({total_bands})" if total_bands else "")
    science_str = f"{row['science']}" + (f" ({science_bands})" if science_bands else "")
    return RSS_DESC_FORMAT.format(
        report=report,
        instrument=instrument,
        night=night,
        total=total_str,
        science=science_str,
        fwhm=np.round(tinysum.loc[dayobs, "median FWHM"], 2),
        visit_rate=np.round(tinysum.loc[dayobs, "visits/hour"], 2),
        mean_norm_teff=np.round(tinysum.loc[dayobs, "total eff_time/total exp_time"], 2),
        teff_rate=teff_rate,
        targets=tinysum.loc[dayobs, "science targets"],
    )


def make_report_rss_feed(
    reports: pd.DataFrame,
    fname: str | None = None,
    max_days: int = 1,
    visits: pd.DataFrame | None = None,
    title: str = "schedview reports",
    description: str = "Statically generated reports on Rubin Observatory/LSST scheduler status and progress",
    prenight_visits: pd.DataFrame | None = None,
) -> ET.ElementTree:
    """Generate an rss feed of recent schedview reports.

     Parameters
     ----------
     reports : `pd.DataFrame`
         A DataFrame of report metadata, as returned by `find_reports`.
     fname : `str` or `None`
         The file in which to write the RSS, if any. `None` to not write
         a file at all. Defaults to `None`.
     max_days : `int`
         How many days worth of reports to include in the feed.
     visits : `pd.DataFrame` or `None`, optional
         A DataFrame of visits as returned by
         `schedview.collect.visits.cached_read_visits`. If supplied, a short
         per-night summary is computed via
         `schedview.compute.smallsum.compute_tinysum` and used to populate the
         ``<description>`` of ``lsstcam`` ``nightsum`` items.
         Defaults to ``None``, in which case nightsum descriptions are blank.
    title: `str`, optional
         The channel title, defaults to ``schedview reports``
     prenight_visits : `pd.DataFrame` or `None`, optional
         A DataFrame of visits from the **prenight simulation** of the night,
         used to populate the ``<description>`` of ``lsstcam`` ``prenight``
         items.  No schedview helper fetches these; the caller is responsible
         for selecting and reading the appropriate simulation, e.g. via
         ``rubin_sim.sim_archive``::

             from rubin_sim.sim_archive.prenightindex import (
                 get_prenight_index, select_latest_prenight_sim)
             from rubin_sim.sim_archive import vseqarchive
             from schedview.collect.visits import NIGHT_STACKERS

             sims = get_prenight_index(day_obs, telescope="simonyi")
             sim = select_latest_prenight_sim(sims)
             prenight_visits = vseqarchive.get_visits(
                 sim["visitseq_url"],
                 query=f"floor(observationStartMJD-0.5)=={day_obs_mjd}",
                 stackers=NIGHT_STACKERS,
             )

         (See ``schedview.collect.multisim.read_multiple_prenights`` for a
         working example of this sequence.)  These simulation visits carry the
         columns ``t_eff`` and ``visitExposureTime`` rather than
         ``eff_time_median``/``exp_time``; those names are passed through to
         ``compute_tinysum``, so the visits should be supplied **unmodified**.
         All prenight visits are counted as science visits (the simulator only
         simulates science visits), so the science counts equal the totals.
         If the supplied visits contain no visits for a given night, that
         night's ``prenight`` description is left completely blank.
         Defaults to ``None``, in which case prenight descriptions are blank.


     Returns
     -------
     rss : `ET.ElementTree`
         The RSS XML itself.
    """
    almanac = Almanac() if (visits is not None or prenight_visits is not None) else None
    tinysum = compute_tinysum(visits, almanac=almanac) if visits is not None else None
    prenight_tinysum = (
        compute_tinysum(
            prenight_visits,
            almanac=almanac,
            eff_time_column="t_eff",
            exp_time_column="visitExposureTime",
            all_science=True,
        )
        if prenight_visits is not None
        else None
    )

    rss = ET.Element("rss", attrib={"version": "2.0"})
    channel = ET.SubElement(rss, "channel")
    channel_title_elem = ET.SubElement(channel, "title")
    channel_title_elem.text = title
    desc = ET.SubElement(channel, "description")
    desc.text = description
    for row_index, report_row in reports.iterrows():
        if (datetime.date.today() - report_row.night).days > max_days:
            # To make sure we keep the feed a reasonable size,
            # don't include older stuff.
            continue
        instrument, dayobs_str = row_index
        dayobs = int(dayobs_str)

        item = ET.SubElement(channel, "item")
        item_title_elem = ET.SubElement(item, "title")
        item_title_elem.text = f"{report_row.report} for {instrument} on {report_row.night}"
        # It's traditional to put a summary of the content in "description"
        # and we could eventually have things like total numbers
        # of visits in each band, stats on the seeing, etc. here.
        # We can do this when our activities at night are no
        # longer secret.
        desc = ET.SubElement(item, "description")
        if instrument == "lsstcam" and report_row.report == "nightsum" and tinysum is not None:
            if dayobs in tinysum.index:
                desc.text = _format_summary_desc(
                    tinysum, dayobs, report_row.report, instrument, report_row.night
                )
            else:
                desc.text = "No visits on this night"
        elif instrument == "lsstcam" and report_row.report == "prenight" and prenight_tinysum is not None:
            # Unlike nightsum, a prenight night with no matching simulation
            # visits gets a completely blank description (no fallback text).
            if dayobs in prenight_tinysum.index:
                desc.text = _format_summary_desc(
                    prenight_tinysum, dayobs, report_row.report, instrument, report_row.night
                )
            else:
                desc.text = ""
        else:
            desc.text = ""
        link = ET.SubElement(item, "link")
        link.text = report_row.url
        guid = ET.SubElement(item, "guid", attib={"isPermaLink": "false"})
        guid.text = item_title_elem.text + hashlib.sha1(desc.text.encode("utf-8")).hexdigest()[:6]
        category = ET.SubElement(item, "category")
        category.text = f"{instrument}_{report_row.report}"
        pubdate = ET.SubElement(item, "pubDate")
        pubdate.text = email.utils.format_datetime(datetime.datetime.fromisoformat(report_row.report_time))
    ET.indent(rss, space=".   ", level=0)

    rss_tree = ET.ElementTree(rss)
    if fname is not None:
        rss_tree.write(fname)

    return rss_tree
