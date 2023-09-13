import hvplot
from astropy.time import Time

# Imported to help sphinx make the link
from rubin_sim.scheduler.model_observatory import ModelObservatory  # noqa F401

import schedview.collect.opsim
import schedview.compute.astro


def plot_visits(visits):
    """Instantiate an explorer to interactively examine a set of visits.

    Parameters
    ----------
    visits : `pandas.DataFrame`
        One row per visit, as created by `schedview.collect.opsim.read_opsim`

    Returns
    -------
    figure : `hvplot.ui.hvDataFrameExplorer`
        The figure itself.
    """
    visit_explorer = hvplot.explorer(visits, kind="scatter", x="start_date", y="airmass", by=["note"])
    return visit_explorer


def create_visit_explorer(visits, night_date, observatory=None, timezone="Chile/Continental"):
    """Create an explorer to interactively examine a set of visits.

    Parameters
    ----------
    visits : `str` or `pandas.DataFrame`
        One row per visit, as created by `schedview.collect.opsim.read_opsim`,
        or the name of a file from which such visits should be loaded.
    night_date : `datetime.date`
        The calendar date in the evening local time.
    observatory : `ModelObservatory`, optional
        Provides the location of the observatory, used to compute
        night start and end times.
        By default None.
    timezone : `str`, optional
        _description_, by default "Chile/Continental"

    Returns
    -------
    figure : `hvplot.ui.hvDataFrameExplorer`
        The figure itself.
    data : `dict`
        The arguments used to produce the figure using
        `plot_visits`.
    """
    site = None if observatory is None else observatory.location
    night_events = schedview.compute.astro.night_events(night_date=night_date, site=site, timezone=timezone)
    start_time = Time(night_events.loc["sunset", "UTC"])
    end_time = Time(night_events.loc["sunrise", "UTC"])

    # Collect
    if isinstance(visits, str):
        visits = schedview.collect.opsim.read_opsim(visits, Time(start_time).iso, Time(end_time).iso)

    # Plot
    data = {"visits": visits}
    visit_explorer = plot_visits(visits)

    return visit_explorer, data
