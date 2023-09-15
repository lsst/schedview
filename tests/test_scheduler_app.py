import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import bokeh.io
import bokeh.plotting

from schedview.app.sched_maps.sched_maps import SchedulerDisplayApp
from schedview.collect import sample_pickle

NSIDE = 8


class TestSchedMaps(unittest.TestCase):
    def test_sched_maps(self):
        scheduler_app = SchedulerDisplayApp(None, nside=NSIDE)

        render_figure(scheduler_app)

        scheduler_app.bokeh_models["file_input_box"].value = sample_pickle("scheduler1_sample.pickle.gz")
        scheduler_app.disable_controls()


def render_figure(scheduler_app):
    fig = scheduler_app.make_figure()
    with TemporaryDirectory() as dir:
        out_path = Path(dir)
        saved_html_fname = out_path.joinpath("test_page.html")
        bokeh.plotting.output_file(filename=saved_html_fname, title="Test Page")
        bokeh.plotting.save(fig)


if __name__ == "__main__":
    unittest.main()
