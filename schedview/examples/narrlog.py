import argparse
from io import StringIO
from typing import Literal

import schedview.collect.nightreport
from schedview.dayobs import DayObs


def make_narrative_log(
    iso_date: str,
    telescope: Literal["AuxTel", "Simonyi"],
    report: None | str = None,
) -> str:
    """Create a markdown report with narrative log entries.

    Parameters
    ----------
    iso_date : `str`
        Local calendar date of the evening on which the night starts,
        in YYYY-MM-DD (ISO 8601) format.
    visit_source : `str`
        Instrument or baseline version number.
    report : `None` | `str`, optional
        Report file name, by default ``None`` (to not write to a file).

    Returns
    -------
    report: `str`
        The narrative log text.
    """

    # Parameters
    day_obs: DayObs = DayObs.from_date(iso_date)

    # Collect
    narrative = schedview.collect.nightreport.get_night_narrative(day_obs, telescope)

    # Compute

    # Plot
    result_io = StringIO()
    print("# Narrative Log", file=result_io)
    print("", file=result_io)
    for message_entry in narrative:
        print(
            f"""## Log message at {message_entry["date_added"]}

{message_entry["message_text"]}

""",
            file=result_io,
        )
    result = result_io.getvalue()

    # Report
    if report is not None:
        with open(report, "w") as report_io:
            print(result, file=report_io)

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="narrlog", description="Make a narrative log for a night in markdown."
    )
    parser.add_argument("date", type=str, help="Evening YYYY-MM-DD")
    parser.add_argument("telescope", type=str, default="Simonyi", help="Instrument (Simonyi or AuxTel)")
    parser.add_argument("report", type=str, help="output file name")
    args = parser.parse_args()

    make_narrative_log(args.date, args.telescope, args.report)
