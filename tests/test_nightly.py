import importlib.resources
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import bokeh
import pandas as pd
from rubin_sim.scheduler.model_observatory import ModelObservatory
from rubin_sim.scheduler.utils import SchemaConverter

import schedview
import schedview.plot.nightly


def _load_sample_visits():
    visits_path = importlib.resources.files(schedview).joinpath("data").joinpath("sample_opsim.db")
    visits = pd.DataFrame(SchemaConverter().opsim2obs(visits_path))
    if "observationStartMJD" not in visits.columns and "mjd" in visits.columns:
        visits["observationStartMJD"] = visits["mjd"]

    visits["start_date"] = pd.to_datetime(
        visits["observationStartMJD"] + 2400000.5, origin="julian", unit="D", utc=True
    )
    return visits


def _create_almanac(night):
    site = ModelObservatory().location
    timezone = "Chile/Continental"
    almanac_events = schedview.compute.astro.night_events(night, site, timezone)
    return almanac_events


class TestNightly(unittest.TestCase):
    def test_plot_airmass_vs_time(self):
        visits = _load_sample_visits()
        almanac_events = _create_almanac(visits["start_date"].dt.date[0])

        fig = schedview.plot.nightly.plot_airmass_vs_time(visits, almanac_events)

        with TemporaryDirectory() as dir:
            out_path = Path(dir)
            saved_html_fname = out_path.joinpath("test_page.html")
            bokeh.plotting.output_file(filename=saved_html_fname, title="Test Page")
            bokeh.plotting.save(fig)


if __name__ == "__main__":
    unittest.main()
