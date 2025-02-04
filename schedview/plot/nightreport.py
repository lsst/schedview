import urllib.parse
from io import StringIO

from astropy.time import Time

from schedview.dayobs import DayObs


def night_report_markdown(night_report: dict, heading_level=1) -> str:
    """Format a night report using Markdown

    Parameters
    ----------
    night_report : `dict`
        A night report, as retured as an element of the list returned by
        `schedview.collect.get_night_report`.
    heading_level : `int`, optional
        The markdown heading level for the highest level heading
        to use, by default 1

    Returns
    -------
    night_report : `str`
        The markdown of the report.
    """
    headhash = "#" * heading_level

    report = StringIO()
    print(f"{headhash} Night report", file=report, end="")
    if "telescope" in night_report:
        print(f" for the {night_report['telescope']} telescope", file=report, end="")
    if "day_obs" in night_report:
        day_obs = DayObs.from_date(night_report["day_obs"], int_format="yyyymmdd")
        print(f" on {day_obs}", file=report, end="")
    print("", file=report)

    if "observers_crew" in night_report:
        print(f"{headhash}# Observers", file=report)
        print(", ".join(night_report["observers_crew"]), file=report)
        print("", file=report)

    if "confluence_url" in night_report and len(night_report["confluence_url"]) > 0:
        night_plan_block = (
            "BLOCK" + urllib.parse.urlparse(night_report["confluence_url"]).fragment.split("BLOCK")[-1]
        )
        if night_plan_block == "BLOCK":
            night_plan_block = night_report["confluence_url"]
        print(f"{headhash}# Night plan", file=report)
        confluence_url = night_report["confluence_url"]
        print(
            f'<a href="{confluence_url}" target="_blank" rel="noreferrer noopener">{night_plan_block}</a>',
            file=report,
        )

    if "summary" in night_report:
        print(f"{headhash}# Summary", file=report)
        print("<pre>" + night_report["summary"] + "</pre>", file=report)

    if "telescope_status" in night_report:
        print(f"{headhash}# Telescope status", file=report)
        print(night_report["telescope_status"], file=report)

    return report.getvalue()


def narrative_message_markdown(message: dict, heading_level=1) -> str:
    """Format a narrative message using Markdown

    Parameters
    ----------
    message : `dict`
        A message, as retured as an element of the list returned by
        `schedview.collect.get_night_narrative`.
    heading_level : `int`, optional
        The markdown heading level for the highest level heading
        to use, by default 1

    Returns
    -------
    message_md : `str`
        The markdown of the message.
    """

    headhash = "#" * heading_level
    report = StringIO()

    print(f"{headhash} Log message", end="", file=report)
    if "date_begin" in message:
        print(f" at {Time(message['date_begin'])}", file=report)
    print("", file=report)

    # Use html markup for the table because the jupyter variant of markdown
    # does not allow tables without column headings.
    print("<table><tbody>", file=report)

    if "time_lost" in message:
        if "time_lost_type" in message:
            print(f"<tr><td> Time lost </td><td> {message['time_lost']}", end="", file=report)
            print(f"type: {message['time_lost_type']}) </td></tr>", file=report)
        else:
            print(f"<tr><td> Time lost </td><td> {message['time_lost']} </td></tr>", file=report)

    table_contents = (
        {"key": "components", "label": "Components", "list": True},
        {"key": "category", "label": "Category", "list": False},
        {"key": "systems", "label": "Systems", "list": True},
        {"key": "subsystems", "label": "Subsystems", "list": True},
        {"key": "cscs", "label": "CSCS", "list": True},
    )
    for row in table_contents:
        if row["key"] in message:
            if message[row["key"]] is None:
                continue
            elif isinstance(message[row["key"]], str):
                value = message[row["key"]]
            else:
                try:
                    value = ", ".join(message[row["key"]])
                except TypeError:
                    value = str(message[row["key"]])
            print(f"<tr><td> {row['label']} </td><td> {value} </td></tr>", file=report)

    print("</tbody></table>", file=report)
    print("", file=report)
    print(f"{headhash}# Message", file=report)
    print(message["message_text"].replace("\r\n", "\n").replace("\n\n", "\n").rstrip("\n"), file=report)

    return report.getvalue()


def narrative_message_html(message: dict, heading_level=1, scrolling=False) -> str:
    """Format a narrative message using HTML

    Parameters
    ----------
    message : `dict`
        A night report, as retured as an element of the list returned by
        `schedview.collect.get_night_report`.
    heading_level : `int`, optional
        The markdown heading level for the highest level heading
        to use, by default 1
    scrolling : `bool`, optional
        Use scrollbars for big text, by default False.

    Returns
    -------
    message_html : `str`
        The html of the message.
    """

    report = StringIO()

    if scrolling:
        print('<div id="" style="overflow:auto; height:512; width:512">', file=report)

    if heading_level is not None:
        begin_heading_markup = f"<h{heading_level}>"
        end_heading_markup = f"</h{heading_level}>"
    else:
        begin_heading_markup = ""
        end_heading_markup = ""

    print(f"{begin_heading_markup}Log message", end="", file=report)
    if "date_begin" in message:
        print(f" at {Time(message['date_begin'])}", file=report)
    print(end_heading_markup, file=report)

    # Use html markup for the table because the jupyter variant of markdown
    # does not allow tables without column headings.
    print("<table><tbody>", file=report)

    if "time_lost" in message:
        if "time_lost_type" in message:
            print(f"<tr><td> Time lost </td><td> {message['time_lost']}", end="", file=report)
            print(f" (type: {message['time_lost_type']}) </td></tr>", file=report)
        else:
            print(f"<tr><td> Time lost </td><td> {message['time_lost']} </td></tr>", file=report)

    table_contents = (
        {"key": "components", "label": "Components"},
        {"key": "category", "label": "Category"},
        {"key": "systems", "label": "Systems"},
        {"key": "subsystems", "label": "Subsystems"},
        {"key": "cscs", "label": "CSCS"},
    )
    for row in table_contents:
        if row["key"] in message:
            if message[row["key"]] is None:
                continue
            elif isinstance(message[row["key"]], str):
                value = message[row["key"]]
            else:
                try:
                    value = ", ".join(message[row["key"]])
                except TypeError:
                    value = str(message[row["key"]])
            print(f"<tr><td> {row['label']} </td><td> {value} </td></tr>", file=report)

    print("</tbody></table>", file=report)
    print("<h3></h3><pre>", file=report)
    print(message["message_text"].replace("\r\n", "\n").replace("\n\n", "\n").rstrip("\n"), file=report)
    print("</pre>", file=report)

    if scrolling:
        print("</div>", file=report)

    return report.getvalue()


def scrolling_narrative_messages_html(
    messages: list[dict], height: str = "400px", heading_level: int = 1
) -> str:
    """Format a narrative message using HTML

    Parameters
    ----------
    messages : `list`
        A night report, as retured as an element of the list returned by
        `schedview.collect.get_night_report`.
    height : `str`
        The height of the display.
    heading_level : `int`, optional
        The markdown heading level for the highest level heading
        to use, by default 1

    Returns
    -------
    messages_html : `str`
        The markdown of the message.
    """

    report = StringIO()
    print(f'<div id="" style="overflow:auto; height:{height};">', file=report)
    for message in messages:
        print(narrative_message_html(message, heading_level), file=report)
    print("<div>", file=report)
    return report.getvalue()
