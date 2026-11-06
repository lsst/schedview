"""Public plotting smoke checks and a few real-browser user journeys."""

import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import bokeh.core.enums
import bokeh.layouts
import bokeh.models
import numpy as np
import pandas as pd
import pytest
from bokeh.embed import file_html
from bokeh.embed.bundle import bundle_for_objs_and_resources
from bokeh.embed.notebook import notebook_content
from bokeh.resources import INLINE

from schedview.collect.progress import SUMMARY_COLUMNS
from schedview.plot.progress import make_metric_line_plots, make_summary_progress_plot


def records(*specifications):
    """Build small valid frames with explicit per-row overrides."""
    rows = []
    for index, spec in enumerate(specifications):
        source = spec.get("visit_source", "consdb")
        date = pd.Timestamp(spec.get("date", "2026-01-01"))
        row = dict(
            metric_id=index,
            stat_id=index,
            run_name=f"{source}_{date:%Y%m%d}",
            metric_name="A metric",
            slicer_name="UniSlicer",
            sql_constraint="",
            metric_info_label=f"{source}_g",
            summary_metric="Mean",
            summary_value=1.0,
            visit_source=source,
            dayobs=int(date.strftime("%Y%m%d")),
            band="g",
            date=date,
        )
        row.update(spec)
        row["date"] = date
        rows.append(row)
    return pd.DataFrame(rows, columns=SUMMARY_COLUMNS)


@pytest.mark.parametrize("empty", [False, True])
def test_plot_constructs_and_serializes(empty):
    frame = records() if empty else records({"metric_name": "Serializable metric"})
    layout = make_summary_progress_plot(frame)
    assert isinstance(layout, bokeh.models.UIElement)
    html = file_html(layout, INLINE)
    assert "Bokeh" in html
    if not empty:
        assert "Serializable metric" in html


def test_plot_rejects_invalid_frame():
    with pytest.raises(ValueError, match="band"):
        make_summary_progress_plot(records({}).drop(columns="band"))


def test_legacy_metric_line_plots_remains_separate():
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-01", "2026-01-08"]),
            "baseline": [1.0, 2.0],
            "snapshot": [0.5, 1.5],
            "chimera": [1.8, 1.9],
        }
    )
    layout = make_metric_line_plots("Legacy", frame)
    assert isinstance(layout, bokeh.layouts.Row)
    assert [len(plot.renderers) for plot in layout.children] == [3, 3]
    ray = layout.children[1].renderers[0]
    assert isinstance(ray.glyph, bokeh.models.Ray)
    assert ray.glyph.y == 2.0


@pytest.fixture(scope="module")
def browser():
    if os.environ.get("ENABLE_PLAYWRIGHT_TESTS", "false").lower() in ("", "0", "f", "false"):
        pytest.skip("Playwright tests disabled; set ENABLE_PLAYWRIGHT_TESTS=1 to enable")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as runtime:
        instance = runtime.chromium.launch()
        try:
            yield instance
        finally:
            instance.close()


@pytest.fixture
def page(browser):
    page = browser.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        yield page
        assert not errors, errors
    finally:
        page.close()


@pytest.fixture
def served():
    """Serve replaceable in-memory HTML/JSON with deterministic cleanup."""
    content = {}
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            item = content.get(self.path)
            self.send_response(200 if item is not None else 404)
            self.send_header(
                "Content-Type", "application/json" if self.path.endswith(".json") else "text/html"
            )
            self.end_headers()
            if item is not None:
                self.wfile.write(item.encode())

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield content, requests, f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def open_plot(page, served, data):
    content, _, origin = served
    content["/pages/plot.html"] = file_html(make_summary_progress_plot(data), INLINE)
    page.goto(origin + "/pages/plot.html")
    page.locator("select").first.wait_for()


def wait_values(page, values):
    """Wait for rendered-point data after the asynchronous widget callback."""
    page.wait_for_function(
        """values => {
            const points = window.Bokeh?.documents[0]?.get_model_by_name('progress_points');
            return points && JSON.stringify(points.data.summary_value) === JSON.stringify(values);
        }""",
        arg=values,
    )


def plot_data(page, name="points"):
    return page.evaluate("name => Bokeh.documents[0].get_model_by_name('progress_' + name).data", name)


def ranges(page):
    return page.evaluate("""() => {
        const plot = Bokeh.documents[0].get_model_by_name('summary_progress_figure');
        return [plot.x_range.start, plot.x_range.end, plot.y_range.start, plot.y_range.end];
    }""")


def test_browser_selection_cascades_and_can_be_cleared(page, served):
    frame = records(
        {"visit_source": "baseline", "summary_metric": "Total", "summary_value": 2},
        {"summary_value": 3},
        {"metric_name": "Z metric", "summary_value": 9},
    )
    open_plot(page, served, frame)
    wait_values(page, [2, 3])
    page.locator("select").nth(1).select_option(["consdb"])
    wait_values(page, [3])
    from playwright.sync_api import expect

    expect(page.locator("select").nth(3).locator("option")).to_have_text(["Mean"])
    page.locator("select").nth(0).select_option("Z metric")
    wait_values(page, [9])
    page.locator("select").nth(1).select_option([])
    wait_values(page, [])
    expect(page.get_by_text("No finite data", exact=False)).to_be_visible()
    page.locator("select").nth(1).select_option(["consdb"])
    wait_values(page, [9])


def test_browser_summary_limit_and_replacement(page, served):
    capacity = len(bokeh.core.enums.LineDash)
    names = [f"S{index:02}" for index in range(capacity + 1)]
    open_plot(
        page, served, records(*[{"summary_metric": name, "summary_value": i} for i, name in enumerate(names)])
    )
    wait_values(page, list(range(capacity)))
    page.locator("select").nth(3).select_option(names)
    from playwright.sync_api import expect

    expect(page.get_by_text("Selection limit", exact=False)).to_be_visible()
    assert len(plot_data(page)["summary_metric"]) == capacity
    page.locator("select").nth(3).select_option(names[1:])
    wait_values(page, list(range(1, capacity + 1)))
    assert plot_data(page)["summary_metric"] == names[1:]


def zoom(page):
    """Drive wheel zoom over the canvas without inspecting glyph internals."""
    before = ranges(page)
    page.locator("[title='Wheel Zoom']").click()
    box = page.locator("canvas").first.bounding_box()
    assert box is not None
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.wheel(0, -200)
    page.wait_for_function(
        """before => {
            const plot = Bokeh.documents[0].get_model_by_name('summary_progress_figure');
            return plot.x_range.start !== before[0] && plot.y_range.start !== before[2];
        }""",
        arg=before,
    )


def test_browser_gaps_selection_ranges_and_reset(page, served):
    frame = records(
        {"summary_value": 10},
        {"date": "2026-01-03", "summary_value": np.nan},
        {"date": "2026-01-08", "summary_value": 20},
        {"date": "2026-01-20", "summary_value": 30},
        {"metric_name": "Z constant", "summary_value": 7},
    )
    open_plot(page, served, frame)
    wait_values(page, [10, 20, 30])
    sequence = plot_data(page, "lines")["ys"][0]
    assert sequence[0] == 10 and np.isnan(sequence[1]) and sequence[2] == 20
    assert sequence[3] == 30
    assert len(plot_data(page, "lines")["xs"][0]) == 4
    points = plot_data(page)
    initial = ranges(page)
    assert all(np.isfinite(initial))
    assert initial[0] < min(points["date"]) < max(points["date"]) < initial[1]
    assert initial[2] < 10 < 30 < initial[3]
    page.locator("select").first.select_option("Z constant")
    wait_values(page, [7])
    selected = ranges(page)
    assert all(np.isfinite(selected)) and selected[2] < 7 < selected[3]
    assert selected != initial
    zoom(page)
    page.locator("[title='Reset']").click()
    page.wait_for_function(
        """expected => {
            const plot = Bokeh.documents[0].get_model_by_name('summary_progress_figure');
            return JSON.stringify([plot.x_range.start, plot.x_range.end,
                plot.y_range.start, plot.y_range.end]) === JSON.stringify(expected);
        }""",
        arg=selected,
    )


def json_records(frame):
    return frame.to_json(orient="records", date_format="epoch", date_unit="ms", double_precision=15)


def test_browser_external_data_updates_only_on_reload_and_reports_failure(page, served):
    content, requests, _ = served
    content["/pages/data.json"] = json_records(records({}))
    open_plot(page, served, "./data.json")
    wait_values(page, [1])
    content["/pages/data.json"] = json_records(records({"summary_value": 42}, {"metric_name": "Z added"}))
    page.locator("select").nth(3).select_option([])
    wait_values(page, [])
    page.locator("select").nth(3).select_option(["Mean"])
    wait_values(page, [1])
    assert requests.count("/pages/data.json") == 1
    page.reload()
    wait_values(page, [42])
    from playwright.sync_api import expect

    expect(page.locator("select").first.locator("option")).to_have_text(["A metric", "Z added"])
    assert requests.count("/pages/data.json") == 2
    del content["/pages/data.json"]
    page.reload()
    expect(page.get_by_text("Failed to load ./data.json: HTTP 404", exact=False)).to_be_visible()
    wait_values(page, [])


def test_browser_separate_notebook_outputs_are_independent(page, browser, served):
    """Notebook outputs must not capture other plots' data or interactions."""
    content, requests, origin = served
    layouts = [make_summary_progress_plot(f"./data{index}.json") for index in range(2)]
    bundle = bundle_for_objs_and_resources(None, INLINE).scripts(tag=True)
    for index, layout in enumerate(layouts):
        content[f"/data{index}.json"] = json_records(records({"summary_value": index + 1}))
        script, div, _ = notebook_content(layout)
        content[f"/output{index}.html"] = bundle + div + f"<script>{script}</script>"
    page.goto(origin + "/output0.html")
    wait_values(page, [1])
    assert requests.count("/data0.json") == 1 and "/data1.json" not in requests
    other = browser.new_page()
    try:
        other.goto(origin + "/output1.html")
        wait_values(other, [2])
        page.locator("select").nth(3).select_option([])
        wait_values(page, [])
        assert plot_data(other)["summary_value"] == [2]
        page.locator("select").nth(3).select_option(["Mean"])
        wait_values(page, [1])
        other.locator("select").nth(3).select_option([])
        wait_values(other, [])
        assert plot_data(page)["summary_value"] == [1]
        assert requests.count("/data0.json") == requests.count("/data1.json") == 1
    finally:
        other.close()


def test_browser_inactive_tab_initializes_before_reveal(page, served):
    """An inactive tab must populate its plot without waiting for a resize."""
    content, requests, origin = served
    content["/data.json"] = json_records(records({"summary_value": 4}))
    layout = make_summary_progress_plot("./data.json")
    tabs = bokeh.models.Tabs(
        tabs=[
            bokeh.models.TabPanel(title="Other", child=bokeh.models.Div(text="Other tab")),
            bokeh.models.TabPanel(title="Progress", child=layout),
        ]
    )
    content["/tab.html"] = file_html(tabs, INLINE)
    page.goto(origin + "/tab.html")
    wait_values(page, [4])
    page.get_by_text("Progress", exact=True).click()
    from playwright.sync_api import expect

    expect(page.locator("select").first).to_be_visible()
    page.locator("select").nth(3).select_option([])
    wait_values(page, [])
    page.locator("select").nth(3).select_option(["Mean"])
    wait_values(page, [4])
    assert requests.count("/data.json") == 1


def test_browser_pending_fetch_does_not_block_another_plot(page, served):
    """A pending fetch must not block another plot in the same document."""
    first = make_summary_progress_plot("./first.json")
    second = make_summary_progress_plot("./second.json")
    first_points = first.select_one({"name": "progress_points"}).id
    second_points = second.select_one({"name": "progress_points"}).id
    content, _, origin = served
    content["/second.json"] = json_records(records({"summary_value": 29}))
    content["/two.html"] = file_html(bokeh.layouts.column(first, second), INLINE)
    pending = []
    page.route("**/first.json", lambda route: pending.append(route))
    page.goto(origin + "/two.html")
    page.wait_for_function(
        """id => window.Bokeh?.documents[0]?.get_model_by_id(id).data.summary_value[0] === 29""",
        arg=second_points,
    )
    from playwright.sync_api import expect

    expect(page.get_by_text("Loading ./first.json...", exact=True)).to_be_visible()
    assert len(pending) == 1
    pending.pop().fulfill(content_type="application/json", body=json_records(records({"summary_value": 13})))
    page.wait_for_function(
        "id => Bokeh.documents[0].get_model_by_id(id).data.summary_value[0] === 13",
        arg=first_points,
    )
