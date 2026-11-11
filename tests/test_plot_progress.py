"""Readable unittest stories for progress pages and browser interactions."""

import json
import math
import os
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import StringIO
from threading import Lock, Thread

import bokeh.core.enums
import bokeh.layouts
import bokeh.models
import pandas as pd
from bokeh.embed import file_html
from bokeh.embed.bundle import bundle_for_objs_and_resources
from bokeh.embed.notebook import notebook_content
from bokeh.resources import INLINE

from schedview.collect.progress import SUMMARY_COLUMNS, validate_summary_metrics
from schedview.plot.progress import make_metric_line_plots, make_summary_progress_plot


def records(*specifications):
    """Supply required provenance fields for small, explicit story records."""
    rows = []
    for index, specification in enumerate(specifications):
        source = specification.get("visit_source", "consdb")
        date = pd.Timestamp(specification.get("date", "2026-01-01"))
        band = specification.get("band", "g")
        row = dict(
            metric_id=index,
            stat_id=index,
            run_name=f"{source}_{date:%Y%m%d}",
            metric_name="Coverage",
            slicer_name="UniSlicer",
            sql_constraint="",
            metric_info_label=f"{source}_{band}",
            summary_metric="Mean",
            summary_value=1.0,
            visit_source=source,
            dayobs=int(date.strftime("%Y%m%d")),
            band=band,
            date=date,
        )
        row.update(specification)
        row["date"] = date
        rows.append(row)
    return pd.DataFrame(rows, columns=SUMMARY_COLUMNS)


def coverage_catalog():
    """The user's observed and simulated comparisons, including one gap."""
    catalog_csv = """\
metric_name, visit_source, band, summary_metric,       date, summary_value
   Coverage,       consdb,    g,           Mean, 2026-01-01,            10
   Coverage,       consdb,    g,           Mean, 2026-01-03,
   Coverage,       consdb,    g,           Mean, 2026-01-08,            20
   Coverage,       consdb,    g,           Mean, 2026-01-20,            30
   Coverage,       consdb,    g,         Median, 2026-01-01,             9
   Coverage,       consdb,    g,         Median, 2026-01-08,            18
   Coverage,       consdb,    g,         Median, 2026-01-20,            27
   Coverage,       consdb,    r,           Mean, 2026-01-20,             5
   Coverage,      chimera,    g,           Mean, 2026-01-20,            40
   Coverage,      chimera,    g,         Median, 2026-01-20,            35
   Coverage,     baseline,    g,           Mean, 2026-01-20,            50
   Coverage,     baseline,    g,         Median, 2026-01-20,            45
     Visits,       consdb,    r,          Total, 2026-01-20,             7
"""
    specifications = pd.read_csv(StringIO(catalog_csv), skipinitialspace=True)
    return records(*specifications.to_dict(orient="records"))


def json_records(frame, *, reference_sim_tag="baseline"):
    """Publish validated records in the external-data contract."""
    validate_summary_metrics(frame, reference_sim_tag=reference_sim_tag)
    return frame.to_json(orient="records", date_format="epoch", date_unit="ms", double_precision=15)


class TestProgressPlotPage(unittest.TestCase):
    """Page-generation checks that never require Playwright."""

    def test_invalid_input_can_be_corrected(self):
        # Intent: The user wants to create a page from their summary records.
        # Action: They try a frame missing band, then restore that column.
        # Response: The API rejects bad input and accepts the correction.
        valid_frame = records({})
        with self.assertRaisesRegex(ValueError, "band"):
            make_summary_progress_plot(valid_frame.drop(columns="band"))
        layout = make_summary_progress_plot(valid_frame)
        self.assertIsInstance(layout, bokeh.models.UIElement)

        comparison = records({"visit_source": "comparison"})
        layout = make_summary_progress_plot(comparison, reference_sim_tag="comparison")
        self.assertIn("comparison_20260101", file_html(layout, INLINE))
        with self.assertRaisesRegex(ValueError, "Invalid run_name"):
            make_summary_progress_plot(comparison)
        with self.assertRaisesRegex(ValueError, "baseline_20260101"):
            make_summary_progress_plot(records({"visit_source": "baseline"}), reference_sim_tag="comparison")
        for tag in ("", None, 42, "consdb", "chimera"):
            for source in (records(), "./data.json"):
                with self.subTest(reference_sim_tag=tag, input=type(source).__name__):
                    with self.assertRaisesRegex(ValueError, "reference_sim_tag"):
                        make_summary_progress_plot(source, reference_sim_tag=tag)

    def test_plot_constructs_and_serializes(self):
        # Intent: The user wants to export a page containing measured records.
        # Action: They create and serialize a populated progress plot.
        # Response: A Bokeh page contains their distinctive metric name.
        with self.subTest(input="populated"):
            layout = make_summary_progress_plot(records({"metric_name": "Serializable metric"}))
            self.assertIsInstance(layout, bokeh.models.UIElement)
            html = file_html(layout, INLINE)
            self.assertIn("Bokeh", html)
            self.assertIn("Serializable metric", html)

        # Intent: The user also wants to export a valid empty selection.
        # Action: They serialize a frame with columns but no records.
        # Response: Empty input still produces serializable Bokeh page content.
        with self.subTest(input="empty"):
            layout = make_summary_progress_plot(records())
            self.assertIsInstance(layout, bokeh.models.UIElement)
            self.assertIn("Bokeh", file_html(layout, INLINE))

    def test_legacy_metric_line_plots_remains_separate(self):
        # Intent: The user wants the older snapshot report to work.
        # Action: They create it with the legacy metric-line plotting API.
        # Response: Both panels and the final-baseline reference remain.
        frame = pd.DataFrame(
            dict(
                date=pd.to_datetime(["2026-01-01", "2026-01-08"]),
                baseline=[1.0, 2.0],
                snapshot=[0.5, 1.5],
                chimera=[1.8, 1.9],
            )
        )
        layout = make_metric_line_plots("Legacy", frame)
        self.assertIsInstance(layout, bokeh.layouts.Row)
        self.assertEqual([len(plot.renderers) for plot in layout.children], [3, 3])
        ray = layout.children[1].renderers[0]
        self.assertIsInstance(ray.glyph, bokeh.models.Ray)
        self.assertEqual(ray.glyph.y, 2.0)


class TestProgressPlotStory(unittest.TestCase):
    """Independent journeys with their own browsers and served content."""

    def setUp(self):
        if os.environ.get("ENABLE_PLAYWRIGHT_TESTS", "false").lower() in ("", "0", "f", "false"):
            self.skipTest("Set ENABLE_PLAYWRIGHT_TESTS=1 to run browser stories")
        from playwright.sync_api import sync_playwright

        self.content = {}
        self.requests = []
        self.lock = Lock()
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                with owner.lock:
                    owner.requests.append(self.path)
                    body = owner.content.get(self.path)
                self.send_response(200 if body is not None else 404)
                self.send_header(
                    "Content-Type", "application/json" if self.path.endswith(".json") else "text/html"
                )
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                if body is not None:
                    self.wfile.write(body.encode())

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.addCleanup(server.server_close)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join)
        self.addCleanup(server.shutdown)
        self.origin = f"http://127.0.0.1:{server.server_port}"

        runtime = sync_playwright().start()
        self.addCleanup(runtime.stop)
        browser = runtime.chromium.launch()
        self.addCleanup(browser.close)
        self.context = browser.new_context(viewport={"width": 1200, "height": 900})
        self.addCleanup(self.context.close)
        self.page = self.new_page()
        # Bokeh's four native selects occur in the documented cascade order.
        self.metric, self.source, self.label, self.summary = [
            self.page.locator("select").nth(index) for index in range(4)
        ]

    def new_page(self):
        page = self.context.new_page()
        self.addCleanup(page.close)
        page.set_default_timeout(10000)
        errors = []

        def record_page_error(error):
            errors.append(str(error))

        page.on("pageerror", record_page_error)
        self.addCleanup(self.assertEqual, errors, [], "Uncaught browser errors")
        return page

    def publish(self, path, body):
        with self.lock:
            self.content[path] = body

    def request_count(self, path):
        with self.lock:
            return self.requests.count(path)

    def data(self, name="points", page=None, model_id=None):
        """Read canvas data without modifying models or private state."""
        return (page or self.page).evaluate(
            """({name, id}) => {
                const doc = Bokeh.documents[0];
                const model = id ? doc.get_model_by_id(id) : doc.get_model_by_name('progress_' + name);
                return JSON.parse(JSON.stringify(model.data));
            }""",
            dict(name=name, id=model_id),
        )

    def wait_values(self, values, page=None, model_id=None):
        """Wait for finite measurements, ignoring series insertion order."""
        (page or self.page).wait_for_function(
            """({values, id}) => {
                const doc = window.Bokeh?.documents[0];
                const points = id ? doc?.get_model_by_id(id) : doc?.get_model_by_name('progress_points');
                const ordered = array => [...array].sort((a, b) => a - b);
                return points && JSON.stringify(ordered(points.data.summary_value)) ===
                    JSON.stringify(ordered(values));
            }""",
            arg=dict(values=values, id=model_id),
        )
        self.assertCountEqual(self.data(page=page, model_id=model_id)["summary_value"], values)

    def status(self, text, page=None):
        locator = (page or self.page).get_by_text(text, exact=False)
        locator.wait_for(state="visible")
        self.assertTrue(locator.is_visible(), f"Expected visible status: {text}")

    def options(self, control):
        return control.locator("option").evaluate_all("options => options.map(option => option.value)")

    def selected(self, control):
        return control.evaluate("control => Array.from(control.selectedOptions, option => option.value)")

    def ranges(self):
        return self.page.evaluate("""() => {
            const plot = Bokeh.documents[0].get_model_by_name('summary_progress_figure');
            return [plot.x_range.start, plot.x_range.end, plot.y_range.start, plot.y_range.end];
        }""")

    def assert_padded_ranges(self):
        points = self.data()
        bounds = self.ranges()
        self.assertTrue(all(math.isfinite(value) for value in bounds), "Ranges must stay finite")
        self.assertLess(bounds[0], min(points["date"]))
        self.assertGreater(bounds[1], max(points["date"]))
        self.assertLess(bounds[2], min(points["summary_value"]))
        self.assertGreater(bounds[3], max(points["summary_value"]))
        return bounds

    def legend_entries(self):
        """Read the visible HTML swatches, not the callback's legend state."""
        swatches = self.page.locator("svg").filter(has=self.page.locator("line"))
        for swatch in swatches.all():
            self.assertTrue(swatch.is_visible(), "Legend swatches must be visible")
        return [text.strip() for text in swatches.locator("..").all_text_contents()]

    def test_user_recovers_from_bad_data_and_explores_progress(self):
        # Intent: The user wants a page for their progress measurements.
        # Action: They pass records whose required band column is missing.
        # Response: The API reports the missing field, without creating a page.
        corrected_frame = coverage_catalog()
        with self.assertRaisesRegex(ValueError, "band"):
            make_summary_progress_plot(corrected_frame.drop(columns="band"))

        # Intent: The user wants to retry with complete summary records.
        # Action: They restore band, generate the page, and open it.
        # Response: The page offers the initial observed/simulated comparison.
        self.publish("/pages/plot.html", file_html(make_summary_progress_plot(corrected_frame), INLINE))
        self.page.goto(self.origin + "/pages/plot.html")
        self.wait_values([10, 20, 30, 9, 18, 27, 5, 40, 35, 50, 45])
        self.assertEqual(self.options(self.metric), ["Coverage", "Visits"])
        self.assertEqual(self.selected(self.metric), ["Coverage"])
        self.assertEqual(self.options(self.source), ["chimera", "baseline", "consdb"])
        self.assertEqual(self.selected(self.source), ["chimera", "baseline", "consdb"])
        self.assertEqual(self.selected(self.label), ["g", "r"])
        self.assertTrue(self.page.get_by_text("Band", exact=True).first.is_visible())
        self.assertEqual(self.selected(self.summary), ["Mean", "Median"])
        for control in (self.metric, self.source, self.label, self.summary):
            self.assertTrue(control.is_enabled())
        self.assertEqual(len(self.data("lines")["xs"]), 7)
        self.status("11 finite measurements.")
        self.status("1 missing/non-finite")
        self.assertEqual(self.page.get_by_text("Failed to load", exact=False).count(), 0)

        # Intent: The user wants observed g-band progress, not simulations.
        # Action: They select consdb, then retain only the g band.
        # Response: Options cascade; matching Mean and Median series remain.
        self.source.select_option(["consdb"])
        self.wait_values([10, 20, 30, 9, 18, 27, 5])
        labels = ["g", "r"]
        self.assertEqual(self.options(self.label), labels)
        self.assertEqual(self.selected(self.label), labels)
        self.assertEqual(self.options(self.summary), ["Mean", "Median"])
        self.label.select_option(["g"])
        self.wait_values([10, 20, 30, 9, 18, 27])
        points = self.data()
        identities = list(
            zip(
                *(
                    points[field]
                    for field in [
                        "metric_name",
                        "run_name",
                        "metric_info_label",
                        "summary_metric",
                        "summary_value",
                    ]
                )
            )
        )
        self.assertCountEqual(
            identities,
            [
                ("Coverage", "consdb_20260101", "consdb_g", "Mean", 10),
                ("Coverage", "consdb_20260108", "consdb_g", "Mean", 20),
                ("Coverage", "consdb_20260120", "consdb_g", "Mean", 30),
                ("Coverage", "consdb_20260101", "consdb_g", "Median", 9),
                ("Coverage", "consdb_20260108", "consdb_g", "Median", 18),
                ("Coverage", "consdb_20260120", "consdb_g", "Median", 27),
            ],
        )
        self.assertEqual(len(self.data("lines")["xs"]), 2)
        self.assertCountEqual(self.legend_entries(), ["consdb", "g", "Mean", "Median"])

        # Intent: The user wants the Mean trend without hiding missing data.
        # Action: They select only Mean.
        # Response: Three points remain; the recorded gap breaks one line.
        self.summary.select_option(["Mean"])
        self.wait_values([10, 20, 30])
        dates = [pd.Timestamp(f"2026-01-{day}").value // 1000000 for day in ["01", "03", "08", "20"]]
        self.assertEqual(self.data()["date"], [dates[0], dates[2], dates[3]])
        self.assertEqual(self.data("lines")["xs"], [dates])
        self.assertEqual(self.data("lines")["ys"], [[10, None, 20, 30]])
        self.status("3 finite measurements.")
        self.status("1 missing/non-finite")
        coverage_ranges = self.assert_padded_ranges()

        # Intent: The user wants to hide this comparison without changing data.
        # Action: They clear Summary, then select Mean again.
        # Response: The empty choice is honored and the series can be restored.
        self.summary.select_option([])
        self.wait_values([])
        self.status("No finite data")
        self.assertEqual(self.selected(self.summary), [])
        self.assertEqual(self.options(self.summary), ["Mean", "Median"])
        self.assertTrue(self.summary.is_enabled())
        self.assertEqual(self.data("lines")["xs"], [])
        self.summary.select_option(["Mean"])
        self.wait_values([10, 20, 30])
        self.assertEqual(self.data("lines")["ys"], [[10, None, 20, 30]])

        # Intent: The user wants visit totals after investigating Coverage.
        # Action: They choose Visits.
        # Response: consdb survives; invalid downstream choices are replaced.
        self.metric.select_option("Visits")
        self.wait_values([7])
        for control, expected in (
            (self.source, ["consdb"]),
            (self.label, ["r"]),
            (self.summary, ["Total"]),
        ):
            self.assertEqual(self.options(control), expected)
            self.assertEqual(self.selected(control), expected)
        self.assertEqual(self.data()["metric_name"], ["Visits"])
        self.assertEqual(self.data()["date"], [dates[3]])
        self.assertEqual(self.data("lines")["ys"], [[7]])
        self.assertCountEqual(self.legend_entries(), ["consdb", "r", "Total"])

        # Intent: The user wants to temporarily hide every Visits source.
        # Action: They clear Source, then select consdb again.
        # Response: Downstream controls empty, then the comparison is restored.
        self.source.select_option([])
        self.wait_values([])
        self.status("No finite data")
        self.assertEqual(self.selected(self.source), [])
        self.assertEqual(self.data("lines")["xs"], [])
        for control in (self.label, self.summary):
            self.assertEqual(self.options(control), [])
            self.assertEqual(self.selected(control), [])
            self.assertTrue(control.is_disabled())
        self.source.select_option(["consdb"])
        self.wait_values([7])
        self.assertEqual(self.selected(self.label), ["r"])
        self.assertEqual(self.selected(self.summary), ["Total"])
        visits_ranges = self.assert_padded_ranges()
        self.assertNotEqual(visits_ranges, coverage_ranges)

        # Intent: The user wants a closer look, then the Visits overview.
        # Action: After switching metrics, they use Wheel Zoom and click Reset.
        # Response: Reset restores Visits bounds, not the Coverage bounds.
        self.page.locator("[title='Wheel Zoom']").click()
        box = self.page.locator("canvas").first.bounding_box()
        self.assertIsNotNone(box, "Wheel Zoom needs a visible plot canvas")
        self.page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        self.page.mouse.wheel(0, -200)
        self.page.wait_for_function(
            """before => {
            const plot = Bokeh.documents[0].get_model_by_name('summary_progress_figure');
            return plot.x_range.end - plot.x_range.start < before[1] - before[0] &&
                plot.y_range.end - plot.y_range.start < before[3] - before[2];
        }""",
            arg=visits_ranges,
        )
        self.assertLess(self.ranges()[1] - self.ranges()[0], visits_ranges[1] - visits_ranges[0])
        self.wait_values([7])
        self.page.locator("[title='Reset']").click()
        self.page.wait_for_function(
            """expected => {
            const plot = Bokeh.documents[0].get_model_by_name('summary_progress_figure');
            const actual = [plot.x_range.start, plot.x_range.end, plot.y_range.start, plot.y_range.end];
            return actual.every((value, index) => Math.abs(value - expected[index]) < 0.001);
        }""",
            arg=visits_ranges,
        )
        for actual, expected in zip(self.ranges(), visits_ranges):
            self.assertAlmostEqual(actual, expected, delta=0.001)
        self.assertNotEqual(self.ranges(), coverage_ranges)
        self.wait_values([7])

    def test_user_selects_bands_across_sources_and_returns_to_original_labels(self):
        # Intent: The user has band labels and a custom simulation label.
        # Action: They open the comparison, then remove the custom source.
        # Response: Labels become ordered bands for the remaining sources.
        frame = records(
            *[
                dict(band=band, summary_value=index + 1)
                for index, band in enumerate(["y", "z", "i", "r", "g", "u", "all"])
            ],
            dict(visit_source="comparison", band="g", summary_value=20),
            dict(visit_source="chimera", metric_info_label="custom", band="all", summary_value=30),
            dict(metric_name="Special", metric_info_label="consdb_G", band="all", summary_value=40),
            dict(metric_name="Special", metric_info_label=None, band="all", summary_value=50),
            dict(metric_name="Special", metric_info_label="comparison_g", band="all", summary_value=60),
        )
        self.publish(
            "/pages/plot.html",
            file_html(make_summary_progress_plot(frame, reference_sim_tag="comparison"), INLINE),
        )
        self.page.goto(self.origin + "/pages/plot.html")
        self.wait_values([1, 2, 3, 4, 5, 6, 7, 20, 30])
        self.assertEqual(self.options(self.source), ["chimera", "comparison", "consdb"])
        self.assertTrue(self.page.get_by_text("Metric info label", exact=True).is_visible())
        self.label.select_option([json.dumps("consdb_g"), json.dumps("comparison_g")])
        self.wait_values([5, 20])
        self.source.select_option(["consdb", "comparison"])
        self.wait_values([5, 20])
        self.assertTrue(self.page.get_by_text("Band", exact=True).first.is_visible())
        self.assertEqual(self.options(self.label), ["all", "u", "g", "r", "i", "z", "y"])
        self.assertEqual(self.selected(self.label), ["g"])
        self.assertCountEqual(self.data()["metric_info_label"], ["consdb_g", "comparison_g"])
        self.assertEqual(len(self.data("lines")["xs"]), 2)

        # Intent: The user wants to toggle every source's g band together.
        # Action: They deselect g, select all, and then restore g.
        # Response: Clearing stays empty; all means the literal all-band label.
        self.label.select_option([])
        self.wait_values([])
        self.status("No finite data")
        self.assertEqual(self.selected(self.label), [])
        self.label.select_option(["all"])
        self.wait_values([7])
        self.assertEqual(self.data()["metric_info_label"], ["consdb_all"])
        self.label.select_option(["g"])
        self.wait_values([5, 20])

        # Intent: The user wants their custom simulation and label metric.
        # Action: They add chimera, select custom, and switch metrics and back.
        # Response: Bands translate to labels; nonstandard labels never become
        # bands, including case variants, nulls and wrong sources.
        self.source.select_option(["consdb", "comparison", "chimera"])
        self.wait_values([5, 20])
        self.assertTrue(self.page.get_by_text("Metric info label", exact=True).is_visible())
        self.assertCountEqual(self.selected(self.label), [json.dumps("consdb_g"), json.dumps("comparison_g")])
        self.label.select_option([json.dumps("custom")])
        self.wait_values([30])
        self.metric.select_option("Special")
        self.wait_values([40, 50, 60])
        self.assertEqual(self.options(self.source), ["consdb"])
        self.assertEqual(
            self.options(self.label), [json.dumps(value) for value in ["", "comparison_g", "consdb_G"]]
        )
        self.assertTrue(self.page.get_by_text("Metric info label", exact=True).is_visible())
        self.metric.select_option("Coverage")
        self.wait_values([1, 2, 3, 4, 5, 6, 7])
        self.assertEqual(self.options(self.source), ["chimera", "comparison", "consdb"])
        self.assertEqual(self.options(self.label), ["all", "u", "g", "r", "i", "z", "y"])

    def test_user_replaces_a_summary_at_the_selection_limit(self):
        capacity = len(bokeh.core.enums.LineDash)
        names = [f"S{index:02}" for index in range(capacity + 1)]

        # Intent: The user wants to compare one metric's summaries.
        # Action: They open a page with more summaries than fit together.
        # Response: All options exist; the first capacity are selected.
        frame = records(*[dict(summary_metric=name, summary_value=index) for index, name in enumerate(names)])
        self.publish("/pages/plot.html", file_html(make_summary_progress_plot(frame), INLINE))
        self.page.goto(self.origin + "/pages/plot.html")
        self.wait_values(list(range(capacity)))
        self.assertEqual(self.options(self.summary), names)
        self.assertEqual(self.selected(self.summary), names[:capacity])
        self.status(f"Select at most {capacity} summaries")

        # Intent: The user wants to add the remaining summary.
        # Action: They select everything without removing an existing choice.
        # Response: Existing choices survive and a visible limit explains why.
        self.summary.select_option(names)
        self.status("Selection limit")
        self.wait_values(list(range(capacity)))
        self.assertEqual(self.selected(self.summary), names[:capacity])
        self.assertCountEqual(self.data()["summary_metric"], names[:capacity])

        # Intent: The user wants the remaining comparison instead of S00.
        # Action: They deselect S00 and select the other summaries.
        # Response: The replacement is selected and plotted within the limit.
        self.summary.select_option(names[1:])
        self.wait_values(list(range(1, capacity + 1)))
        self.assertEqual(self.selected(self.summary), names[1:])
        self.assertCountEqual(self.data()["summary_metric"], names[1:])

    def test_user_reloads_published_data_and_sees_fetch_failure(self):
        # Intent: The user wants the currently published measurements.
        # Action: They open a page referencing a sibling JSON file.
        # Response: Coverage value 1 loads from the page-relative URL.
        self.publish(
            "/pages/data.json",
            json_records(records({"visit_source": "comparison"}), reference_sim_tag="comparison"),
        )
        self.publish(
            "/pages/plot.html",
            file_html(make_summary_progress_plot("./data.json", reference_sim_tag="comparison"), INLINE),
        )
        self.page.goto(self.origin + "/pages/plot.html")
        self.wait_values([1])
        self.status("Source: ./data.json")
        self.assertEqual(self.selected(self.source), ["comparison"])
        self.assertEqual(self.selected(self.label), ["g"])
        self.assertEqual(self.data()["run_name"], ["comparison_20260101"])
        self.assertEqual(self.data("lines")["width"], [5])
        self.assertEqual(self.data("lines")["alpha"], [0.3])
        self.assertCountEqual(self.legend_entries(), ["comparison", "g", "Mean"])
        stroke = self.page.locator("svg").filter(has=self.page.locator("line")).first.locator("line")
        self.assertEqual(stroke.get_attribute("stroke-width"), "5")
        self.assertEqual(stroke.get_attribute("opacity"), "0.3")
        self.assertEqual(self.request_count("/pages/data.json"), 1)
        self.assertEqual(self.request_count("/data.json"), 0)

        # Intent: The publisher wants an update without replacing HTML.
        # Action: They replace JSON; the user clears and restores Mean.
        # Response: The open page still uses value 1 without fetching again.
        self.publish(
            "/pages/data.json",
            json_records(
                records(
                    {
                        "visit_source": "comparison",
                        "metric_info_label": "review",
                        "band": "all",
                        "summary_value": 42,
                    },
                    {"metric_name": "Visits", "summary_value": 7},
                    {"metric_name": "Visits", "visit_source": "chimera", "summary_value": 8},
                ),
                reference_sim_tag="comparison",
            ),
        )
        self.summary.select_option([])
        self.wait_values([])
        self.status("No finite data")
        self.summary.select_option(["Mean"])
        self.wait_values([1])
        self.assertEqual(self.options(self.metric), ["Coverage"])
        self.assertEqual(self.request_count("/pages/data.json"), 1)

        # Intent: The user wants the publisher's newer measurements.
        # Action: They reload the same page and inspect the new Visits metric.
        # Response: Coverage is 42 and Visits appears, using one new fetch.
        self.page.reload()
        self.wait_values([42])
        self.assertEqual(self.selected(self.source), ["comparison"])
        self.assertEqual(self.selected(self.label), [json.dumps("review")])
        self.assertTrue(self.page.get_by_text("Metric info label", exact=True).is_visible())
        self.assertEqual(self.data("lines")["width"], [5])
        self.assertEqual(self.data("lines")["alpha"], [0.3])
        self.assertEqual(self.options(self.metric), ["Coverage", "Visits"])
        self.status("Source: ./data.json")
        self.assertEqual(self.request_count("/pages/data.json"), 2)
        self.metric.select_option("Visits")
        self.wait_values([7, 8])
        self.assertEqual(self.options(self.source), ["chimera", "consdb"])
        self.assertEqual(self.data()["metric_name"], ["Visits", "Visits"])
        self.assertEqual(self.request_count("/pages/data.json"), 2)

        # Intent: The user wants to return after the data file disappears.
        # Action: The publisher removes JSON; the user reloads.
        # Response: A visible HTTP 404 replaces the stale measurements.
        with self.lock:
            del self.content["/pages/data.json"]
        self.page.reload()
        self.status("Failed to load ./data.json: HTTP 404")
        self.wait_values([])
        self.assertEqual(self.data("lines")["xs"], [])
        for control in (self.metric, self.source, self.label, self.summary):
            self.assertTrue(control.is_disabled())
        self.assertEqual(self.request_count("/pages/data.json"), 3)
        self.assertEqual(self.legend_entries(), [])

    def test_notebook_outputs_keep_user_selections_independent(self):
        # Intent: The user wants to compare two independent notebook outputs.
        # Action: They open one output, then the other in a second page.
        # Response: Each loads only its own measurement.
        bundle = bundle_for_objs_and_resources(None, INLINE).scripts(tag=True)
        for index, tag in enumerate(("baseline", "comparison")):
            layout = make_summary_progress_plot(f"./data{index}.json", reference_sim_tag=tag)
            script, div, _ = notebook_content(layout)
            self.publish(
                f"/pages/data{index}.json",
                json_records(
                    records({"visit_source": tag, "summary_value": index + 1}), reference_sim_tag=tag
                ),
            )
            self.publish(f"/pages/output{index}.html", bundle + div + f"<script>{script}</script>")
        self.page.goto(self.origin + "/pages/output0.html")
        self.wait_values([1])
        self.assertEqual(self.selected(self.source), ["baseline"])
        self.assertEqual(self.data("lines")["width"], [5])
        self.assertEqual(self.data("lines")["alpha"], [0.3])
        self.assertEqual(self.request_count("/pages/data0.json"), 1)
        self.assertEqual(self.request_count("/pages/data1.json"), 0)
        other = self.new_page()
        other.goto(self.origin + "/pages/output1.html")
        self.wait_values([2], page=other)
        self.assertEqual(self.selected(other.locator("select").nth(1)), ["comparison"])
        self.assertEqual(self.data(page=other)["run_name"], ["comparison_20260101"])
        self.assertEqual(self.data("lines", page=other)["width"], [5])
        self.assertEqual(self.data("lines", page=other)["alpha"], [0.3])
        self.assertEqual(self.request_count("/pages/data1.json"), 1)

        # Intent: The user wants to adjust the notebook comparisons separately.
        # Action: They clear/restore the first, then clear the second.
        # Response: Each action affects only that output without another fetch.
        self.summary.select_option([])
        self.wait_values([])
        self.status("No finite data")
        self.wait_values([2], page=other)
        self.summary.select_option(["Mean"])
        self.wait_values([1])
        self.wait_values([2], page=other)
        other.locator("select").nth(3).select_option([])
        self.wait_values([], page=other)
        self.status("No finite data", page=other)
        self.wait_values([1])
        self.assertEqual(self.request_count("/pages/data0.json"), 1)
        self.assertEqual(self.request_count("/pages/data1.json"), 1)

    def test_user_reveals_an_already_initialized_progress_tab(self):
        # Intent: The user wants progress ready when they switch tabs.
        # Action: They open a page with Progress initially inactive.
        # Response: The hidden plot loads without requiring a resize.
        self.publish("/pages/data.json", json_records(records({"summary_value": 4})))
        tabs = bokeh.models.Tabs(
            tabs=[
                bokeh.models.TabPanel(title="Other", child=bokeh.models.Div(text="Other tab")),
                bokeh.models.TabPanel(title="Progress", child=make_summary_progress_plot("./data.json")),
            ]
        )
        self.publish("/pages/tab.html", file_html(tabs, INLINE))
        self.page.goto(self.origin + "/pages/tab.html")
        self.wait_values([4])
        self.assertEqual(self.request_count("/pages/data.json"), 1)

        # Intent: The user wants to interact with the prepared comparison.
        # Action: They reveal Progress and clear/restore its summary.
        # Response: Controls work immediately without fetching again.
        self.page.get_by_text("Progress", exact=True).click()
        self.metric.wait_for(state="visible")
        self.assertTrue(self.metric.is_visible())
        self.summary.select_option([])
        self.wait_values([])
        self.status("No finite data")
        self.summary.select_option(["Mean"])
        self.wait_values([4])
        self.assertEqual(self.request_count("/pages/data.json"), 1)

    def test_pending_data_does_not_block_another_plot(self):
        # Intent: The user wants one comparison while another source is slow.
        # Action: They open two plots while the first request remains pending.
        # Response: The second initializes; the first still shows Loading.
        first = make_summary_progress_plot("./first.json")
        second = make_summary_progress_plot("./second.json")
        first_id = first.select_one({"name": "progress_points"}).id
        second_id = second.select_one({"name": "progress_points"}).id
        self.publish("/pages/second.json", json_records(records({"summary_value": 29})))
        self.publish("/pages/two.html", file_html(bokeh.layouts.column(first, second), INLINE))
        pending = []

        def abort_pending():
            for route in pending:
                route.abort()

        def hold_first_response(route):
            pending.append(route)

        self.addCleanup(abort_pending)
        self.page.route("**/first.json", hold_first_response)
        self.page.goto(self.origin + "/pages/two.html", wait_until="domcontentloaded")
        self.wait_values([29], model_id=second_id)
        self.wait_values([], model_id=first_id)
        self.status("Loading ./first.json...")
        self.assertEqual(len(pending), 1)

        # Intent: The user wants the slower comparison once its data arrive.
        # Action: The first response is released with measurement 13.
        # Response: The first completes and the second still shows 29.
        route = pending[0]
        route.fulfill(content_type="application/json", body=json_records(records({"summary_value": 13})))
        pending.remove(route)
        self.wait_values([13], model_id=first_id)
        self.wait_values([29], model_id=second_id)
        self.status("1 finite measurements. Source: ./first.json")
        self.status("1 finite measurements. Source: ./second.json")


if __name__ == "__main__":
    unittest.main()
