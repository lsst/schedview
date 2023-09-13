import importlib.resources
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import bokeh.io
import bokeh.plotting

from schedview.app.prenight.prenight import prenight_app


class TestPrenight(unittest.TestCase):
    def test_prenight_app(self):
        sample_data_dir = importlib.resources.files("schedview").joinpath("data")

        sample_opsim_db = str(sample_data_dir.joinpath("sample_opsim.db"))
        sample_scheduler_pickle = str(sample_data_dir.joinpath("sample_scheduler.pickle.xz"))
        sample_rewards_h5 = str(sample_data_dir.joinpath("sample_rewards.h5"))

        # Use a separate test custom settings file from the sample, because
        # some of the settings in the sample file work well when tested with
        # a interactive browser, but do not work as part of the test.
        custom_hvplot_tabs = str(sample_data_dir.joinpath("test_prenight_custom_hvplots.json"))

        app = prenight_app(
            opsim_db=sample_opsim_db,
            scheduler=sample_scheduler_pickle,
            rewards=sample_rewards_h5,
            custom_hvplot_tab_settings_file=custom_hvplot_tabs,
        )
        app_bokeh_model = app.get_root()
        with TemporaryDirectory() as dir:
            out_path = Path(dir)
            saved_html_fname = out_path.joinpath("test_page.html")
            bokeh.plotting.output_file(filename=saved_html_fname, title="Test Page")
            bokeh.plotting.save(app_bokeh_model)


if __name__ == "__main__":
    unittest.main()
