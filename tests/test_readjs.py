import unittest
import schedview.plot.readjs

JS_FNAME = "update_map.js"


class Test_update_js(unittest.TestCase):
    def test_update_js(self):
        js_code = schedview.plot.readjs.read_javascript(JS_FNAME)
        self.assertGreater(len(js_code), 10)
        self.assertIsInstance(js_code, str)


if __name__ == "__main__":
    unittest.main()
