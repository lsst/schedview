def best_night_report(night_reports) -> dict:
    """From among a list of versions of a night report, return the best.

    Parameters
    ----------
    night_reports: `list[dict]`
        A list of dictionaries of night reports, as returned by
        `schedview.collect.get_night_report`.

    Returns
    -------
    report: `dict`
        A dictionary with night report data for the best version found.
    """

    if len(night_reports) == 0:
        return {}

    best_night_report = night_reports[0]
    for night_report in night_reports[1:]:
        is_valid = night_report.get("is_valid", False)
        date_sent = night_report.get("date_sent", None)
        date_added = night_report.get("date_added", None)
        best_is_valid = best_night_report.get("is_valid", False)
        best_date_sent = best_night_report.get("date_sent", None)
        best_date_added = best_night_report.get("date_added", None)

        if is_valid and not best_is_valid:
            best_night_report = night_report
        if best_date_sent is None and date_sent is not None:
            best_night_report = night_report
        if date_sent is not None and best_date_sent is not None and best_date_sent > date_sent:
            best_night_report = night_report
        if best_date_added is None and date_added is not None:
            best_night_report = night_report
        if date_added is not None and best_date_added is not None and best_date_added > date_added:
            best_night_report = night_report

    return best_night_report
