Here is the **ready‑to‑paste instruction block**, containing _exactly_ the Phase A prompt you requested—concise, bounded, and safe to paste directly into Claude Code, Cursor, or any LLM coding environment.

---

# **📦 PHASE A INSTRUCTION BLOCK (PASTE INTO CLAUDE/CURSOR)**

You are implementing **Phase A** of the `tlbuilder` system for schedview.

Your task:

1. **Write the full Phase A pytest test suite FIRST.**
2. Then implement the minimal Phase A code until all tests pass (using your own internal reasoning).
3. Produce only the Phase A code (tests + implementation).
4. Implement _nothing_ from later phases.

================================================================================

# **PHASE A SCOPE**

Phase A must implement ONLY:

- Core builder infrastructure
- Scatter plot support
- Shared datetime x‑axis
- Correct MJD → datetime64 conversion using `astropy.time.Time`
- Vertical stacking of scatter figures
- Minimal CLI v1 (scatter only)

DO NOT IMPLEMENT:

- Visits
- Color stripes
- Widgets
- Visibility toggles
- Y‑axis selectors
- Panel integration
- Any of the old TimelinePlotter subclasses
- Anything from Phase B or Phase C

================================================================================

# **REQUIRED PUBLIC CLASSES**

### **ScatterPlotConfig**

Simple data holder with:

- `name: str`
- `y_column: str`
- `offered_columns: Iterable[str]`
- `figure_kwargs: dict`

### **ColorStripeConfig**

Stub class; must exist; does nothing.

### **VisitDataSet**

Stub class; must exist; does nothing.

================================================================================

# **TIMELINEBUILDER — PHASE A ONLY**

### **Constructor**

`TimelineBuilder(dayobs)` must create:

```
self._dayobs
self._elements = []
self._visit_sets = {}
self._color_stripes = {}
self._shared_x_range = None
self._figure_kwargs = {"width": 1000}
self._plot_heights = {}
```

### **add_scatter(...)**

Signature:

```
add_scatter(
    self,
    y_column: str,
    offered_columns: Iterable[str] = (),
    name: str = "scatter",
    height: int | None = None,
    tooltips: list | None = None,
    **figure_kwargs
) -> Self
```

Requirements:

- Create and store a `ScatterPlotConfig`.
- Append it to `self._elements`.
- Store `height` in `self._plot_heights[name]` if provided.
- Initialize shared x‑range on first use:
  - Convert DayObs start/end MJD → datetime64 (`Time(...).datetime64`)
  - Use `Range1d(start=…, end=…)`
- Return `self`.

### **build()**

Build only scatter plots:

- One Bokeh figure **per ScatterPlotConfig**.
- All figures share identical `self._shared_x_range`.
- Each figure must have:
  - `x_axis_type="datetime"`
  - A scatter glyph using:
    - `x = "time"`
    - `y = config.y_column`
  - Datetime tick formatter: `DatetimeTickFormatter(hours="%H:%M")`
- Return a `bokeh.layouts.column` of all figures.

No other plot elements allowed.

================================================================================

# **TIME CONVERSION REQUIREMENTS**

All MJD values must be converted to numpy.datetime64 via:

```
from astropy.time import Time
Time(mjd).datetime64
```

================================================================================

# **CLI v1 REQUIREMENTS**

Provide a minimal CLI named `buildtl` that:

- Accepts:
  ```
  buildtl --scatter y1 --scatter y2 --output out.html
  ```
- Creates a DayObs from date argument.
- Creates a TimelineBuilder.
- Adds a scatter layer per `--scatter`.
- Calls `build()`.
- Saves HTML via `file_html` or equivalent.

No visits, no stripes, no widgets.

Tests must mock file write operations.

================================================================================

# **TEST SUITE REQUIREMENTS (WRITE FIRST)**

Tests must verify:

## **Config classes**

- ScatterPlotConfig stores all fields correctly.
- ColorStripeConfig + VisitDataSet exist as stubs.

## **TimelineBuilder initialization**

- `_dayobs` stored
- `_elements`, `_visit_sets`, `_color_stripes` empty
- `_shared_x_range` initially `None`

## **add_scatter**

- Returns `self`
- Appends a ScatterPlotConfig
- Height stored if provided
- Shared x‑range created on first scatter
- Shared x‑range bounds are datetime64 converted from DayObs

## **Time conversion**

- MJD → datetime64 conversion is correct

## **build()**

- Returns a Bokeh `column`
- One figure per scatter config
- All figures share _the same Range1d object_
- Each figure contains:
  - Exactly one scatter renderer
  - x = “time”
  - y = config.y_column
- Datetime tick formatting applied

## **CLI**

- Parses arguments correctly
- Instantiates TimelineBuilder
- Calls add_scatter for each `--scatter`
- Mocks HTML write
- Does _not_ use visits/stripes/widgets

================================================================================

# **DELIVERABLES**

Produce:

1. **Complete Phase A pytest test suite**
2. **Complete Phase A implementation**
   (config classes, TimelineBuilder, time conversion, build(), CLI v1)

Everything must strictly conform to Phase A boundaries.

---

**Begin by generating the full Phase A pytest test suite.**

---
