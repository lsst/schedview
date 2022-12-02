from astropy.time import Time
import schedview.collect.opsim
import schedview.compute.astro
import hvplot


def plot_visits(visits):
    visit_explorer = hvplot.explorer(
        visits, kind="scatter", x="start_date", y="airmass", by=["note"]
    )
    return visit_explorer


def create_visit_explorer(
    visits, night_date, observatory=None, timezone="Chile/Continental"
):
    site = None if observatory is None else observatory.location
    night_events = schedview.compute.astro.night_events(
        night_date=night_date, site=site, timezone=timezone
    )
    start_time = Time(night_events.loc["sunset", "UTC"])
    end_time = Time(night_events.loc["sunrise", "UTC"])

    # Collect
    if isinstance(visits, str):
        visits = schedview.collect.opsim.read_opsim(
            visits, Time(start_time).iso, Time(end_time).iso
        )

    # Plot
    data = {"visits": visits}
    visit_explorer = plot_visits(visits)

    return visit_explorer, data
