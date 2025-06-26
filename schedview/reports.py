import datetime
import email.utils
import os
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd


def find_reports(
    report_dir: str = "/sdf/data/rubin/shared/scheduler/reports",
    url_base: str = "https://usdf-rsp-int.slac.stanford.edu/schedview-static-pages",
) -> pd.DataFrame:
    """Find staticic schedview reports by walking the report directory.

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


def make_report_link_table(reports: pd.DataFrame) -> str:
    """Generate an html table of links to reports.

    Parameters
    ----------
    reports : `pd.DataFrame`
        A DataFrame of report metadata, as returned by `find_reports`.

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
        .reindex(columns=["prenight", "multiprenight", "nightsum", "compareprenight"])
    )

    report_table_html = report_links.to_html(escape=False)
    return report_table_html


def make_report_rss_feed(
    reports: pd.DataFrame, fname: str | None = None, max_days: int = 7
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

    Returns
    -------
    rss : `ET.ElementTree`
        The RSS XML itself.
    """
    rss = ET.Element("rss", attrib={"version": "2.0"})
    channel = ET.SubElement(rss, "channel")
    title = ET.SubElement(channel, "title")
    title.text = "schedview reports"
    desc = ET.SubElement(channel, "description")
    desc.text = "Statically generated reports on Rubin Observatory/LSST scheduler status and progress"
    for row_index, report_row in reports.iterrows():
        if (datetime.date.today() - report_row.night).days > max_days:
            # To make sure we keep the feed a reasonable size,
            # don't include older stuff.
            continue
        instrument, dayobs = row_index
        item = ET.SubElement(channel, "item")
        title = ET.SubElement(item, "title")
        title.text = f"{report_row.report} report for {instrument} on {report_row.night}"
        # It's traditional to put a summary of the content in "description"
        # and we could eventually have things like total numbers
        # of visits in each band, stats on the seeing, etc. here.
        # We can do this when our activities at night are no
        # longer secret.
        desc = ET.SubElement(item, "description")
        desc.text = f"{report_row.report} report for {instrument} on {report_row.night}"
        link = ET.SubElement(item, "link")
        link.text = report_row.url
        guid = ET.SubElement(item, "guid", attib={"isPermaLink": "false"})
        guid.text = title.text + f", generated {report_row.report_time}"
        category = ET.SubElement(item, "category")
        category.text = f"{instrument}_{report_row.report}"
        pubdate = ET.SubElement(item, "pubDate")
        pubdate.text = email.utils.format_datetime(datetime.datetime.fromisoformat(report_row.report_time))
    ET.indent(rss, space=".   ", level=0)

    rss_tree = ET.ElementTree(rss)
    if fname is not None:
        rss_tree.write(fname)

    return rss_tree
