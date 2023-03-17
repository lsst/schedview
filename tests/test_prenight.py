import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
import bokeh.plotting
import bokeh.io

from schedview.app.prenight.prenight import prenight_app


class test_prenight(unittest.TestCase):
    def test_prenight_app(self):
        app = prenight_app()
        app_bokeh_model = app.get_root()
        with TemporaryDirectory() as dir:
            out_path = Path(dir)
            saved_html_fname = out_path.joinpath("test_page.html")
            bokeh.plotting.output_file(filename=saved_html_fname, title="Test Page")
            bokeh.plotting.save(app_bokeh_model)


if __name__ == "__main__":
    unittest.main()
