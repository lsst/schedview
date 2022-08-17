import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
import bokeh.plotting
import bokeh.io
from schedview.app.sched_maps import SchedulerDisplayApp
from schedview.collect import sample_pickle

NSIDE = 8


class test_sched_maps(unittest.TestCase):
    def test_sched_maps(self):
        scheduler_app = SchedulerDisplayApp(nside=NSIDE)

        render_figure(scheduler_app)

        scheduler_app.bokeh_models["file_input_box"].value = sample_pickle(
            "baseline22_start.pickle.gz"
        )
        scheduler_app.disable_controls()


def render_figure(scheduler_app):
    fig = scheduler_app.make_figure()
    with TemporaryDirectory() as dir:
        out_path = Path(dir)
        saved_html_fname = out_path.joinpath("test_page.html")
        bokeh.plotting.output_file(filename=saved_html_fname, title="Test Page")
        bokeh.plotting.save(fig)
        saved_png_fname = out_path.joinpath("test_fig.png")
        bokeh.io.export_png(fig, filename=saved_png_fname)


if __name__ == "__main__":
    unittest.main()
