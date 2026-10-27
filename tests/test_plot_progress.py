"""Synthetic model and real-browser checks for standalone progress plots."""

import re
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
from schedview.plot.colors import make_band_cmap
from schedview.plot.progress import SOURCE_STYLES, make_metric_line_plots, make_summary_progress_plot


def records(*specifications):
    """Build valid records without a Rubin simulation or database."""
    rows = []
    for index, spec in enumerate(specifications):
        source = spec.get("visit_source", "consdb")
        date = pd.Timestamp(spec.get("date", "2026-01-01"))
        label = spec.get("metric_info_label", f"{source}_g")
        band = (
            label[len(source) + 1 :] if isinstance(label, str) and label.startswith(f"{source}_") else "all"
        )
        if band not in ("u", "g", "r", "i", "z", "y", "all"):
            band = "all"
        row = dict(
            metric_id=index,
            stat_id=index,
            run_name=f"{source}_{date:%Y%m%d}",
            metric_name="A metric",
            slicer_name="UniSlicer",
            sql_constraint="",
            metric_info_label=label,
            summary_metric="Mean",
            summary_value=1.0,
            visit_source=source,
            dayobs=int(date.strftime("%Y%m%d")),
            band=band,
            date=date,
        )
        row.update(spec)
        rows.append(row)
    return pd.DataFrame(rows, columns=SUMMARY_COLUMNS)


def model(layout, name):
    return layout.select_one({"name": name})


def test_models_validation_serialization_and_layout():
    frame = records({"summary_value": np.inf}, {"date": pd.Timestamp("2026-01-03"), "summary_value": np.nan})
    frame["harmless"] = "extra"
    before = frame.copy(deep=True)
    layout = make_summary_progress_plot(frame.iloc[::-1])
    pd.testing.assert_frame_equal(frame, before)
    controls = layout.children[0].children
    assert [control.name for control in controls] == [
        "progress_metric",
        "progress_source",
        "progress_label",
        "progress_summary",
    ]
    assert isinstance(controls[0], bokeh.models.Select)
    assert all(isinstance(control, bokeh.models.MultiSelect) for control in controls[1:])
    callback = controls[0].js_property_callbacks["change:value"][0]
    assert all(control.js_property_callbacks["change:value"][0] is callback for control in controls)
    assert callback.args["url"] is None
    assert all(row["summary_value"] is None for row in callback.args["records"])
    assert callback.args["records"][1]["date"] == 1767225600000
    assert callback.args["records"][0]["harmless"] == "extra"
    figure = model(layout, "summary_progress_figure")
    assert type(figure.y_scale).__name__ == "ProgressLinearScale"
    assert len(figure.renderers) == 2
    assert isinstance(figure.renderers[0].glyph, bokeh.models.MultiLine)
    scatter = figure.renderers[1].glyph
    assert scatter.size == 8 and scatter.fill_alpha == 0.6
    hovered = figure.renderers[1].hover_glyph
    assert hovered.fill_color == "black" and hovered.fill_alpha == 1
    hover = figure.select_one(bokeh.models.HoverTool)
    assert [field for _, field in hover.tooltips] == [
        "@run_name",
        "@metric_name",
        "@metric_info_label",
        "@summary_metric",
        "@summary_value",
    ]
    assert not list(figure.select(bokeh.models.Legend))
    assert [child.name for child in layout.children[-3:]] == [
        "progress_source_legend",
        "progress_band_legend",
        "progress_summary_legend",
    ]
    assert all(isinstance(child, bokeh.models.Div) for child in layout.children[-3:])
    assert "Bokeh" in file_html(layout, INLINE)
    notebook_js, notebook_div, _ = notebook_content(layout)
    assert "ProgressLinearScale" in notebook_js
    assert 'data-root-id="' in notebook_div
    with pytest.raises(ValueError, match="missing required columns"):
        make_summary_progress_plot(frame.drop(columns="band"))
    with pytest.raises(ValueError, match="duplicate"):
        make_summary_progress_plot(pd.concat([frame, frame]))
    assert make_summary_progress_plot(frame.iloc[:0]) is not None


def test_direct_frame_gap_diagnostic_and_values_preserved():
    frame = records(
        {"summary_value": None},
        {"date": pd.Timestamp("2026-01-02"), "summary_value": np.nan},
        {"date": pd.Timestamp("2026-01-03"), "summary_value": np.inf},
        {"date": pd.Timestamp("2026-01-04"), "summary_value": -np.inf},
        {"date": pd.Timestamp("2026-01-05"), "summary_value": 1e308},
    )
    before = frame.copy(deep=True)
    with pytest.warns(UserWarning, match=r"4 missing/non-finite.*2 missing, 2 non-finite"):
        layout = make_summary_progress_plot(frame)
    pd.testing.assert_frame_equal(frame, before)
    callback = model(layout, "progress_metric").js_property_callbacks["change:value"][0]
    assert [row["summary_value"] for row in callback.args["records"]] == [None] * 4 + [1e308]


def test_url_is_not_read_in_python_and_palette_is_deterministic():
    layout = make_summary_progress_plot("./not-created.json?token=test")
    callback = model(layout, "progress_metric").js_property_callbacks["change:value"][0]
    assert callback.args["records"] is None
    assert callback.args["url"] == "./not-created.json?token=test"
    assert (
        callback.args["styles"]
        == SOURCE_STYLES
        == {"consdb": (1, 1.0), "chimera": (2, 0.8), "baseline": (3, 0.6)}
    )
    bands = ("u", "g", "r", "i", "z", "y", "all")
    first = make_band_cmap(bands=bands)["transform"]
    second = make_band_cmap(bands=bands)["transform"]
    assert tuple(first.factors) == tuple(second.factors) == bands
    assert first.palette == second.palette
    assert len(set(first.palette)) == 7
    assert callback.args["colors"] == dict(zip(first.factors, first.palette))
    assert callback.args["dashes"] == list(bokeh.core.enums.LineDash)


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
    """Skip explicitly when the optional browser executable is unavailable."""
    playwright = pytest.importorskip("playwright.sync_api")
    with playwright.sync_playwright() as runtime:
        try:
            instance = runtime.chromium.launch()
        except playwright.Error as error:
            pytest.skip(f"Chromium unavailable; run playwright install chromium: {error}")
        yield instance
        instance.close()


@pytest.fixture
def served():
    """Serve in-memory pages/JSON; shut down and join on every outcome."""
    content = {}
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            item = content.get(self.path.split("?")[0])
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


def open_plot(browser, served, data, timezone="UTC", resources=INLINE):
    content, _, origin = served
    content["/pages/plot.html"] = file_html(make_summary_progress_plot(data), resources)
    page = browser.new_page(timezone_id=timezone)
    errors = []
    console_errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on(
        "console", lambda message: console_errors.append(message.text) if message.type == "error" else None
    )
    page.goto(origin + "/pages/plot.html")
    try:
        wait_updated(page)
    except Exception:
        diagnostics = page.evaluate(
            "JSON.stringify({bokeh: !!window.Bokeh, documents: window.Bokeh?.documents.length})"
        )
        page.close()
        pytest.fail(
            f"Browser initialization failed: {errors}; console: {console_errors}; state: {diagnostics}"
        )
    assert errors == []
    return page


def wait_updated(page):
    """Wait for committed selector/plot state, not an early control setter."""
    page.wait_for_function("""() => {
        if (!window.Bokeh?.documents.length) return false;
        const doc = Bokeh.documents[0];
        const status = doc.get_model_by_name('progress_status');
        const state = status?._progress_state;
        if (!state || state.busy) return false;
        const names = ['metric', 'source', 'label', 'summary'];
        return state.selection === JSON.stringify(names.map(name =>
            doc.get_model_by_name('progress_' + name).value));
    }""")


def state(page):
    wait_updated(page)
    return page.evaluate("""() => {
        const get = name => Bokeh.documents[0].get_model_by_name('progress_' + name);
        const plot = Bokeh.documents[0].get_model_by_name('summary_progress_figure');
        const result = {status: get('status').text, lines: get('lines').data, points: get('points').data};
        for (const name of ['metric', 'source', 'label', 'summary']) {
            const control = get(name);
            result[name] = {value: control.value, options: control.options, disabled: control.disabled};
        }
        result.ranges = [plot.x_range.start, plot.x_range.end, plot.y_range.start, plot.y_range.end];
        result.reset = [plot.x_range.reset_start, plot.x_range.reset_end,
                        plot.y_range.reset_start, plot.y_range.reset_end];
        result.legends = ['source', 'band', 'summary'].map(name => get(name + '_legend').text);
        return result;
    }""")


def select(page, index, values):
    """Use native widget events, not model assignment or callback calls."""
    page.locator("select").nth(index).select_option(values)
    page.wait_for_function(
        """([index, values]) => {
        const names = ['metric','source','label','summary'];
        const value = Bokeh.documents[0].get_model_by_name('progress_' + names[index]).value;
        return JSON.stringify(index === 0 ? [value] : [...value].sort()) ===
            JSON.stringify([...values].sort());
    }""",
        arg=[index, [values] if isinstance(values, str) else values],
    )
    wait_updated(page)


def test_browser_cascade_union_retention_fallback_and_explicit_empty(browser, served):
    frame = records(
        {"visit_source": "baseline", "summary_metric": "Baseline"},
        {"visit_source": "consdb", "summary_metric": "Mean"},
        {"visit_source": "chimera", "summary_metric": "Total"},
        {"metric_name": "Z metric", "metric_info_label": "special", "summary_metric": "Other"},
        {"metric_info_label": None, "summary_metric": "Null"},
        {"date": pd.Timestamp("2026-01-04"), "metric_info_label": "", "summary_metric": "Null"},
        {"metric_info_label": "(no label)", "summary_metric": "Literal"},
    )
    page = open_plot(browser, served, frame)
    try:
        initial = state(page)
        assert initial["metric"]["value"] == "A metric"
        assert initial["source"]["value"] == ["baseline", "chimera", "consdb"]
        assert set(initial["summary"]["options"]) == {"Baseline", "Mean", "Total", "Null", "Literal"}
        assert ['""', "(no label)"] in initial["label"]["options"]
        assert ['"(no label)"', '"(no label)"'] in initial["label"]["options"]
        assert len({text for _, text in initial["label"]["options"]}) == len(initial["label"]["options"])
        assert len(initial["lines"]["xs"]) == 5  # Null and empty form one sequence.
        select(page, 1, ["consdb", "chimera"])
        assert set(state(page)["summary"]["options"]) == {"Mean", "Total", "Null", "Literal"}
        select(page, 2, ['"consdb_g"'])
        assert state(page)["summary"]["value"] == ["Mean"]
        select(page, 0, "Z metric")
        current = state(page)
        assert current["source"]["value"] == ["consdb"]
        assert current["label"]["value"] == ['"special"']
        assert current["summary"]["value"] == ["Other"]
        select(page, 1, [])
        current = state(page)
        assert current["source"]["value"] == []
        assert current["label"]["disabled"] and current["summary"]["disabled"]
        assert current["points"]["date"] == []
        assert "No finite data" in current["status"]
        select(page, 1, ["consdb"])
        select(page, 3, [])
        assert state(page)["summary"]["value"] == []
        assert "No finite data" in state(page)["status"]
        select(page, 3, ["Other"])
        select(page, 2, [])
        current = state(page)
        assert current["label"]["value"] == []
        assert current["summary"]["disabled"]
        assert current["points"]["date"] == [] and current["lines"]["xs"] == []
        assert "No finite data" in current["status"]
    finally:
        page.close()


def test_browser_cap_replacement_and_stable_style_slots(browser, served):
    capacity = len(bokeh.core.enums.LineDash)
    names = [f"S{index:02}" for index in range(capacity + 2)]
    page = open_plot(browser, served, records(*[{"summary_metric": name} for name in names]))
    try:
        initial = state(page)
        assert initial["summary"]["options"] == names
        assert initial["summary"]["value"] == names[:capacity]
        assert "at most" in initial["status"]
        before = dict(zip(initial["points"]["summary_metric"], initial["lines"]["dash"]))
        assert re.findall(r'stroke-dasharray="([^"]*)"', initial["legends"][2]) == [
            "",
            "3 2",
            "2 1",
            "2 4 6 4",
            "6 4 2 4",
        ]
        page.locator("select").nth(3).select_option(names)
        page.wait_for_function("""() => Bokeh.documents[0].get_model_by_name('progress_status')
            .text.includes('Selection limit')""")
        assert state(page)["summary"]["value"] == names[:capacity]
        page.wait_for_timeout(100)
        assert "Selection limit" in state(page)["status"]
        replacement = names[1:capacity] + [names[-1]]
        select(page, 3, replacement)
        after = state(page)
        styles = dict(zip(after["points"]["summary_metric"], after["lines"]["dash"]))
        assert all(styles[name] == before[name] for name in names[1:capacity])
        assert styles[names[-1]] == before[names[0]]
        assert names[-1] in after["legends"][2] and names[0] not in after["legends"][2]
    finally:
        page.close()


@pytest.mark.parametrize("timezone", ["Pacific/Honolulu", "Asia/Tokyo"])
def test_browser_gaps_styles_finite_ranges_calendar_and_reset(browser, served, timezone):
    frame = records(
        {"date": pd.Timestamp("2026-01-01"), "summary_value": 10.0},
        {"date": pd.Timestamp("2026-01-03"), "summary_value": np.nan},
        {"date": pd.Timestamp("2026-01-08"), "summary_value": 20.0},
        {"visit_source": "chimera", "summary_value": np.inf},
        {"visit_source": "baseline", "summary_value": -np.inf},
        {"metric_name": "Z constant", "summary_value": 7.0},
    )
    page = open_plot(browser, served, frame, timezone)
    try:
        current = state(page)
        assert len(current["points"]["date"]) == 2
        assert "3 missing/non-finite measurements shown as gaps" in current["status"]
        assert sorted(map(len, current["lines"]["xs"])) == [1, 1, 3]
        sequence = next(values for values in current["lines"]["ys"] if len(values) == 3)
        assert sequence[0] == 10 and np.isnan(sequence[1]) and sequence[2] == 20
        assert sorted(zip(current["lines"]["width"], current["lines"]["alpha"])) == [
            (1, 1.0),
            (2, 0.8),
            (3, 0.6),
        ]
        assert current["points"]["date"] == [1767225600000, 1767830400000]
        assert current["ranges"][2:] == [9.5, 20.5]
        assert current["ranges"] == current["reset"]
        assert all(np.isfinite(current["ranges"]))
        assert all(current["legends"])
        assert page.evaluate("""() => {
            const plot = Bokeh.documents[0].get_model_by_name('summary_progress_figure');
            const axis = plot.below.find(model => model.type === 'DatetimeAxis');
            return axis.formatter.doFormat([1767225600000, 1767830400000], {loc: 0});
        }""") == ["2026-01-01", "2026-01-08"]
        select(page, 1, ["chimera"])
        assert state(page)["ranges"] == [0, 86400000, 0, 1]
        assert "No finite data" in state(page)["status"]
        select(page, 0, "Z constant")
        current = state(page)
        assert current["ranges"] == [1767139200000, 1767312000000, 6, 8]
        zoom(page)
        assert state(page)["ranges"] != current["ranges"]
        zoomed = state(page)["ranges"]
        page.set_viewport_size({"width": 1000, "height": 800})
        page.wait_for_timeout(100)
        assert state(page)["ranges"] == zoomed
        page.locator("[title='Reset']").click()
        assert state(page)["ranges"] == current["ranges"]
        zoom(page)
        select(page, 0, "A metric")
        assert state(page)["ranges"] == state(page)["reset"]
        assert state(page)["ranges"] != zoomed
    finally:
        page.close()


def json_records(frame):
    clean = frame.copy()
    clean["summary_value"] = clean["summary_value"].replace([np.inf, -np.inf], np.nan)
    return clean.to_json(orient="records", date_format="epoch", date_unit="ms", double_precision=15)


def test_browser_external_reload_expands_every_catalog_and_fetch_failure(browser, served):
    content, requests, _ = served
    content["/pages/data.json"] = json_records(records({}))
    page = open_plot(browser, served, "./data.json")
    try:
        assert len(state(page)["points"]["date"]) == 1
        updated = records(
            {"summary_value": 42.0},
            {"date": pd.Timestamp("2026-02-01"), "visit_source": "baseline", "summary_metric": "New"},
            {"visit_source": "chimera", "metric_info_label": "new label", "summary_metric": "Extra"},
            {"metric_name": "Z added"},
        )
        content["/pages/data.json"] = json_records(updated)
        select(page, 3, [])
        select(page, 3, ["Mean"])
        assert state(page)["points"]["summary_value"] == [1]
        assert requests.count("/pages/data.json") == 1
        page.reload()
        page.wait_for_function("""() => Bokeh.documents[0].get_model_by_name('progress_metric')
            .options.includes('Z added')""")
        current = state(page)
        assert current["metric"]["options"] == ["A metric", "Z added"]
        assert current["source"]["options"] == ["baseline", "chimera", "consdb"]
        assert '"new label"' in current["label"]["value"]
        assert current["summary"]["options"] == ["Extra", "Mean", "New"]
        assert 42 in current["points"]["summary_value"]
        assert max(current["points"]["date"]) == 1769904000000
        assert current["ranges"][1] > 1769904000000
        assert requests.count("/pages/data.json") == 2
        del content["/pages/data.json"]
        page.reload()
        page.wait_for_function("""() => Bokeh.documents[0].get_model_by_name('progress_status')
            .text.includes('Failed to load')""")
        current = state(page)
        assert "./data.json" in current["status"] and "HTTP 404" in current["status"]
        assert current["points"]["date"] == [] and current["lines"]["xs"] == []
        assert all(current[name]["disabled"] for name in ("metric", "source", "label", "summary"))
        content["/pages/data.json"] = "not JSON"
        page.reload()
        page.wait_for_function("""() => Bokeh.documents[0].get_model_by_name('progress_status')
            .text.includes('Failed to load')""")
        assert "./data.json" in state(page)["status"]
    finally:
        page.close()


@pytest.mark.parametrize("external", [False, True])
def test_browser_empty_and_two_independent_plots(browser, served, external):
    page = open_plot(browser, served, records())
    try:
        current = state(page)
        assert "No finite data" in current["status"]
        assert all(current[name]["disabled"] for name in ("metric", "source", "label", "summary"))
    finally:
        page.close()
    first_frame = records({"metric_name": "First", "summary_value": 13.0})
    second_frame = records({"metric_name": "Second", "visit_source": "chimera", "summary_value": 29.0})
    content, requests, origin = served
    content["/first.json"] = json_records(first_frame)
    content["/second.json"] = json_records(second_frame)
    first = make_summary_progress_plot("./first.json" if external else first_frame)
    second = make_summary_progress_plot("./second.json" if external else second_frame)
    content["/two.html"] = file_html(bokeh.layouts.column(first, second), INLINE)
    page = browser.new_page()
    try:
        page.goto(origin + "/two.html")
        page.locator("select").nth(4).wait_for()
        page.wait_for_function("""() => Bokeh.documents[0].roots()[0].children.every(layout =>
            layout.select_one('progress_status')._progress_state?.selection != null &&
            !layout.select_one('progress_status')._progress_state.busy)""")
        before = page.evaluate("""() => Bokeh.documents[0].roots()[0].children.map(layout =>
            layout.select_one('progress_points').data.summary_value)""")
        assert before == [[13], [29]]
        page.locator("select").nth(1).select_option([])
        page.wait_for_function("""() => Bokeh.documents[0].roots()[0].children[0]
            .select_one('progress_points').data.date.length === 0""")
        assert page.locator("select").nth(5).input_value() == "chimera"
        assert page.locator("select").nth(4).input_value() == "Second"
        assert page.evaluate("""() => Bokeh.documents[0].roots()[0].children[1]
            .select_one('progress_points').data.summary_value""") == [29]
        page.locator("select").nth(1).select_option(["consdb"])
        page.locator("select").nth(5).select_option([])
        page.wait_for_function("""() => {
            const [first, second] = Bokeh.documents[0].roots()[0].children;
            return first.select_one('progress_points').data.summary_value[0] === 13 &&
                second.select_one('progress_points').data.date.length === 0;
        }""")
        assert requests.count("/first.json") == requests.count("/second.json") == int(external)
    finally:
        page.close()


def test_browser_external_loading_and_network_rejection(browser, served):
    content, _, origin = served
    content["/pages/plot.html"] = file_html(make_summary_progress_plot("./data.json"), INLINE)
    page = browser.new_page()
    pending = []
    page.route("**/data.json", lambda route: pending.append(route))
    try:
        page.goto(origin + "/pages/plot.html")
        page.wait_for_function("""() => Bokeh.documents[0].get_model_by_name('progress_status')
            .text === 'Loading ./data.json...'""")
        current = page.evaluate("""() => {
            const get = name => Bokeh.documents[0].get_model_by_name('progress_' + name);
            return {points: get('points').data, ...Object.fromEntries(
                ['metric', 'source', 'label', 'summary'].map(name =>
                    [name, {disabled: get(name).disabled}]))};
        }""")
        assert all(current[name]["disabled"] for name in ("metric", "source", "label", "summary"))
        assert current["points"]["date"] == []
        assert len(pending) == 1
        pending.pop().fulfill(status=200, content_type="application/json", body=json_records(records({})))
        page.wait_for_function("""() => Bokeh.documents[0].get_model_by_name('progress_status')
            .text.includes('finite measurements')""")
        assert state(page)["points"]["summary_value"] == [1]
        page.reload()
        page.wait_for_function("""() => Bokeh.documents[0].get_model_by_name('progress_status')
            .text === 'Loading ./data.json...'""")
        assert len(pending) == 1
        pending.pop().abort("failed")
        page.wait_for_function("""() => Bokeh.documents[0].get_model_by_name('progress_status')
            .text.includes('Failed to load ./data.json')""")
        current = state(page)
        assert "Failed to fetch" in current["status"]
        assert current["points"]["date"] == [] and current["lines"]["xs"] == []
        assert all(current[name]["disabled"] for name in ("metric", "source", "label", "summary"))
    finally:
        page.close()


def test_browser_startup_concurrent_compilation_fetches_once(browser, served):
    layout = make_summary_progress_plot("./data.json")
    plot = model(layout, "summary_progress_figure")
    status = model(layout, "progress_status")
    callback = model(layout, "progress_metric").js_property_callbacks["change:value"][0]
    startup = bokeh.models.CustomJS(
        args=dict(callback=callback, status=status, plot=plot),
        code="""
        if (status._startup_test) return;
        status._startup_test = true;
        status._compile_count = 0;
        const compile = callback._compile_module.bind(callback);
        callback._compile_module = async () => {
            status._compile_count++;
            return compile();
        };
        status._startup_done = Promise.all(Array.from({length: 8}, () => callback.execute(plot)));
        """,
    )
    plot.js_property_callbacks["change:inner_width"].insert(0, startup)
    content, _, origin = served
    content["/pages/plot.html"] = file_html(layout, INLINE)
    page = browser.new_page()
    pending = []
    page.route("**/data.json", lambda route: pending.append(route))
    try:
        page.goto(origin + "/pages/plot.html")
        page.wait_for_function("""() => Bokeh.documents[0].get_model_by_name('progress_status')
            .text === 'Loading ./data.json...'""")
        assert page.evaluate("""() => Bokeh.documents[0].get_model_by_name('progress_status')
            ._compile_count""") >= 8
        assert len(pending) == 1
        pending.pop().fulfill(status=200, content_type="application/json", body=json_records(records({})))
        wait_updated(page)
        page.evaluate("""async () => await Bokeh.documents[0].get_model_by_name('progress_status')
            ._startup_done""")
        assert state(page)["points"]["summary_value"] == [1]
        assert pending == []
        select(page, 3, [])
        select(page, 3, ["Mean"])
        assert pending == []
    finally:
        page.close()


def test_browser_notebook_bundle_custom_scale(browser, served):
    layout = make_summary_progress_plot(
        records({"summary_value": -1e308}, {"date": pd.Timestamp("2026-01-02"), "summary_value": 1e308})
    )
    script, div, _ = notebook_content(layout)
    content, _, origin = served
    bundle = bundle_for_objs_and_resources(None, INLINE)
    content["/notebook.html"] = bundle.scripts(tag=True) + div + f"<script>{script}</script>"
    page = browser.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
    try:
        page.goto(origin + "/notebook.html")
        page.wait_for_function(
            """id => {
                const status = window.Bokeh?.documents[0]?.get_model_by_id(id);
                return status?._progress_state?.selection != null && !status._progress_state.busy;
            }""",
            arg=model(layout, "progress_status").id,
        )
        page.wait_for_function(
            """id => {
            const doc = Bokeh.documents[0];
            const view = doc.views_manager.find_one(doc.get_model_by_id(id));
            const y = view.renderer_views.get(view.model.renderers[1]).glyph.sy;
            return y?.length === 2 && Number.isFinite(y[0]) && Number.isFinite(y[1]) && y[0] - y[1] > 100;
        }""",
            arg=model(layout, "summary_progress_figure").id,
        )
        assert errors == []
        assert page.evaluate(
            "id => Bokeh.documents[0].get_model_by_id(id).data.summary_value",
            model(layout, "progress_points").id,
        ) == [-1e308, 1e308]
    finally:
        page.close()


def zoom(page):
    """Drive the actual wheel-zoom tool over the rendered plotting canvas."""
    before = state(page)["ranges"]
    page.locator("[title='Wheel Zoom']").click()
    position = page.evaluate("""() => {
        const doc = Bokeh.documents[0];
        const view = doc.views_manager.find_one(doc.get_model_by_name('summary_progress_figure'));
        const box = view.canvas_view.events_el.getBoundingClientRect();
        return [box.x + box.width / 2, box.y + box.height / 2];
    }""")
    page.mouse.move(*position)
    page.mouse.wheel(0, -200)
    page.wait_for_function(
        """before => {
        const plot = Bokeh.documents[0].get_model_by_name('summary_progress_figure');
        return plot.x_range.start !== before[0] && plot.y_range.start !== before[2];
    }""",
        arg=before,
    )


def test_browser_all_bands_and_distinct_same_band_labels(browser, served):
    bands = ("u", "g", "r", "i", "z", "y", "all")
    frame = records(
        *[{"metric_info_label": f"consdb_{band}"} for band in bands],
        {"metric_info_label": "region one"},
        {"metric_info_label": "region two", "summary_value": 2.0},
    )
    page = open_plot(browser, served, frame)
    try:
        current = state(page)
        assert len(current["lines"]["xs"]) == len(current["points"]["date"]) == 9
        cmap = make_band_cmap(bands=bands)["transform"]
        expected = dict(zip(cmap.factors, cmap.palette))
        by_label = dict(zip(current["points"]["metric_info_label"], current["points"]["color"]))
        assert all(by_label[f"consdb_{band}"] == expected[band] for band in bands)
        assert by_label["region one"] == by_label["region two"] == expected["all"]
        assert set(current["lines"]["color"]) == set(expected.values())
        select(page, 2, ['"region two"', '"region one"'])
        current = state(page)
        assert len(current["lines"]["xs"]) == 2
        assert current["lines"]["ys"] == [[1], [2]]
        assert set(current["points"]["metric_info_label"]) == {"region one", "region two"}
    finally:
        page.close()


def test_browser_actual_canvas_gaps_and_irregular_connections(browser, served):
    frame = records(
        {"date": pd.Timestamp("2026-01-08"), "summary_value": 8.0},
        {"date": pd.Timestamp("2026-01-01"), "summary_value": 1.0},
        {"date": pd.Timestamp("2026-01-03"), "summary_value": np.nan},
        {"date": pd.Timestamp("2026-01-20"), "summary_value": 20.0},
    )
    page = open_plot(browser, served, frame)
    try:
        page.evaluate("""() => {
            const doc = Bokeh.documents[0];
            const view = doc.views_manager.find_one(doc.get_model_by_name('summary_progress_figure'));
            const glyph = view.renderer_views.get(view.model.renderers[0]).glyph;
            const paint = glyph._paint;
            window.progressPaint = [];
            glyph._paint = function(ctx, indices, data) {
                const commands = [];
                const proxy = new Proxy(ctx, {
                    get(target, key) {
                        if (key === 'moveTo' || key === 'lineTo') return (...args) => {
                            commands.push([key, ...args]);
                            return target[key](...args);
                        };
                        const value = target[key];
                        return typeof value === 'function' ? value.bind(target) : value;
                    },
                    set(target, key, value) {target[key] = value; return true;},
                });
                paint.call(this, proxy, indices, data);
                window.progressPaint.push(commands);
            };
            view.request_paint();
        }""")
        page.wait_for_function("() => window.progressPaint.length > 0")
        commands = page.evaluate("window.progressPaint.at(-1)")
        assert [command[0] for command in commands] == ["moveTo", "moveTo", "lineTo"]
        assert commands[0][1] < commands[1][1] < commands[2][1]
        current = state(page)
        assert len(current["lines"]["xs"][0]) == 4
        assert len(current["points"]["date"]) == 3
    finally:
        page.close()


@pytest.mark.parametrize("values", [(-1e308, 1e308), (-1.79e308, 1.79e308), (1.79e308,), (-1.79e308,)])
def test_browser_finite_extreme_extent(browser, served, values):
    page = open_plot(
        browser,
        served,
        records(
            *[
                {"date": pd.Timestamp("2026-01-01") + pd.Timedelta(days=index), "summary_value": value}
                for index, value in enumerate(values)
            ]
        ),
    )
    try:
        current = state(page)
        assert all(np.isfinite(current["ranges"]))
        assert current["ranges"][2] < current["ranges"][3]
        assert current["ranges"][2] <= min(values) <= max(values) <= current["ranges"][3]
        assert current["ranges"] == current["reset"]
        assert "finite measurements" in current["status"]
        assert current["points"]["summary_value"] == list(values)
        page.wait_for_function("""() => {
            const doc = Bokeh.documents[0];
            const view = doc.views_manager.find_one(doc.get_model_by_name('summary_progress_figure'));
            return view.renderer_views.get(view.model.renderers[1]).glyph.sy?.length > 0;
        }""")
        screen = page.evaluate("""() => {
            const doc = Bokeh.documents[0];
            const view = doc.views_manager.find_one(doc.get_model_by_name('summary_progress_figure'));
            const renderer = view.renderer_views.get(view.model.renderers[1]);
            const glyph = renderer.glyph;
            return {y: Array.from(glyph.sy), lineY: Array.from(
                view.renderer_views.get(view.model.renderers[0]).glyph.sys.get(0)),
                bounds: [view.frame.bbox.top, view.frame.bbox.bottom],
                inverse: Array.from(glyph.sy, y => renderer.yscale.invert(y))};
        }""")
        assert all(np.isfinite(screen["y"])) and all(np.isfinite(screen["lineY"]))
        assert all(screen["bounds"][0] <= y <= screen["bounds"][1] for y in screen["y"])
        np.testing.assert_allclose(screen["inverse"], values, rtol=1e-5, err_msg=str(screen))
        if len(values) > 1:
            assert screen["y"][0] - screen["y"][1] > 100
            assert screen["lineY"][0] - screen["lineY"][1] > 100
    finally:
        page.close()
