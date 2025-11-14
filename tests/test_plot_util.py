import base64
import re
import unittest
import xml.etree.ElementTree as ET
from io import BytesIO

import matplotlib
import matplotlib.pyplot as plt

from schedview.plot.util import mpl_fig_to_html

# Use the Agg backend to avoid the need for a display
matplotlib.use("Agg")


class TestUtil(unittest.TestCase):

    def test_mpl_fig_to_html(self):
        # Make a trivial figure
        fig, ax = plt.subplots()
        ax.plot([0, 1], [0, 1])

        html = mpl_fig_to_html(fig)
        plt.close(fig)

        # Parse the HTML and verify that it is an image tag
        element = ET.fromstring(html)
        assert element.tag == "img"

        # Extract the src from the image tag and verify it has the right form
        image_src = element.attrib.get("src", "")
        match = re.match(r"data:image/png;base64,([A-Za-z0-9+/=]+)", image_src)
        assert match is not None

        # Extract the base64 encoded png data, convert it first into bytes,
        # then to an image array.
        image_data_base64 = match.group(1)
        image_data_bytes = base64.b64decode(image_data_base64)
        image_array = plt.imread(BytesIO(image_data_bytes))

        # Verify that it looks like image data
        assert len(image_array.shape) == 3
        assert image_array.shape[2] == 4
        assert image_array.shape[0] >= 10
        assert image_array.shape[1] >= 10


if __name__ == "__main__":
    unittest.main()
