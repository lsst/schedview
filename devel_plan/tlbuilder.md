# Scope

## Identification

**Title:** Timeline Builder (tlbuilder) - A New API for Nightly Timeline Visualization
**Abbreviation:** tlbuilder

## Document overview

This document describes the Timeline Builder (tlbuilder) system, a new implementation of the timeline visualization functionality in the `schedview` library for the Rubin Observatory LSST scheduler.
The intended audience for this document includes:

- Scientists and operators who use timeline visualizations to inspect scheduler state and nightly observing plans
- Software developers maintaining and extending the schedview library
- Project managers and technical leads overseeing the development of visualization tools

This document outlines the shortcomings of the current timeline implementation (`schedview.plot.timeline`) and describes the design and operational concepts for the new `schedview.plot.tlbuilder` module, which will be implemented using a builder pattern to provide a cleaner, more flexible API.

## System overview

The Timeline Builder is a Python library component that provides tools for creating interactive timeline visualizations of events and visit parameters during a night of observations at the Rubin Observatory. The system takes as input time-series data (such as visit catalogs, sky brightness models, and astronomical event timings) and produces interactive Bokeh-based visualizations that can be displayed in Jupyter notebooks, embedded in HTML reports, or shown in web dashboards.

The system is part of the larger schedview visualization ecosystem, which follows a data flow pattern of:

```
collect → compute → plot → report
```

The tlbuilder component sits in the "plot" layer, consuming data from the "collect" and "compute" layers to produce visual outputs.

# Referenced documents

1. IEEE Std 1362-1998 (R2007) - Guide for Information Technology—System Definition—Concept of Operations (ConOps) Document
2. AGENTS.md - Guidance for AI coding assistants working with the schedview repository
3. schedview.plot.timeline module source code - Current timeline implementation
4. schedview.collect.visits module - Visit data collection
5. schedview.compute.astro module - Astronomical computations
6. rubin_scheduler package - Scheduler simulation and observation planning
7. Bokeh documentation - Interactive visualization library
8. Panel documentation - Web dashboard framework
9. RTN-092 (draft) - overview of schedview

# Current system or situation

## Background, objectives, and scope

The current timeline visualization system in `schedview.plot.timeline` (primarily the `TimelinePlotter` base class and `make_multitimeline` function) has accumulated several issues that make it increasingly difficult to maintain and extend:

1. **Overly complex and obscure API** - The current API uses a class inheritance pattern where users must define subclasses with class attributes to customize behavior. This is not intuitive for new users and makes the code difficult to understand and use.

2. **Limited layout flexibility** - The `make_multitimeline` function creates parallel timelines that share a common time axis, but there is no clean way to overlay different types of data (e.g., scatter plots with color-encoded stripes) on the same vertical space.

3. **Difficulty aligning events across plots** - When plotting visit parameters alongside non-visit parameters, the current implementation places them side-by-side rather than stacked with a common x-axis, making it difficult to correlate events.

4. **Dead code** - Several features in the current implementation are no longer used (e.g., some TimelinePlotter subclasses for specialized log event types that have been replaced by other tools).

The objective of the tlbuilder project is to create a new, clean-slate implementation that:

- Uses a fluent builder pattern for intuitive, step-by-step plot construction
- Supports stacked plots with a common x-axis for proper event alignment
- Provides a consistent API for different data types (scatters, stripes, visits)
- Is easier to maintain and extend

## Operational policies and constraints

1. The system must run on the same platforms as the rest of schedview (Linux, macOS).
2. The output must be compatible with the existing Bokeh/Panel ecosystem used throughout schedview.
3. The implementation must be compatible with both Python 3.11+ (current schedview requirement).
4. The system must work in Jupyter notebooks, static HTML generation, and Panel web dashboards.
5. Must coexist with the existing `schedview.plot.timeline` module during the transition period.

## Description of the current system or situation

The current timeline system is implemented in `schedview/plot/timeline.py` and consists of:

1. **TimelinePlotter** - A base class that creates generic timeline plots from Bokeh ColumnDataSources or pandas DataFrames. Subclasses customize behavior through class attributes like `key`, `time_column`, `factor`, and `glyph_class`.

2. **Subclasses** - Specialized plotter classes for different data types:
   - `LogMessageTimelinePlotter` - For log messages
   - `SchedulerDependenciesTimelinePlotter` - For scheduler dependency events
   - `BlockStatusTimelinePlotter` - For block status changes
   - `VisitTimelinePlotter` - For visit data with band-colored bars
   - `SunTimelinePlotter` - For sun events (sunset, sunrise, twilight)
   - `ModelSkyTimelinePlotter` - For model sky brightness
   - And more...

3. **make_multitimeline** - A function that takes multiple data sources as keyword arguments and creates a combined plot with parallel timelines. The keyword argument names map to the `key` attribute of TimelinePlotter subclasses.

4. **make_timeline_scatterplots** - A higher-level function that creates side-by-side plots of a timeline and a scatter plot of visit parameters vs. time.

The current system has these characteristics:

- Uses `bokeh.plotting.figure` for plot creation
- Uses `bokeh.models.ColumnDataSource` for data binding
- Uses `bokeh.models.plots.Plot` for the core plot object
- Relies on `bokeh.transform` for color mapping and axis transformations

## Modes of operation for the current system or situation

The current system can operate in the following modes:

1. **Jupyter notebook mode** - Plots displayed in Jupyter notebooks with interactive widgets (zoom, pan, hover tooltips). This includes generation of static HTML pages for static reports, or through Times Square.

2. **Static HTML mode** - Plots rendered to HTML files using `bokeh.embed.file_html()`.

3. **Dashboard mode** - Plots embedded in Panel web dashboards using `panel.pane.Bokeh`.

# Justification for and nature of changes

## Justication of changes

The current timeline implementation has several deficiencies that justify a complete rewrite:

1. **API Complexity** - The class-based approach with inheritance is not intuitive. New users must understand class attributes, method overriding, and the relationship between different subclasses. This creates a steep learning curve.

2. **Layout Limitations** - The inability to stack different plot types with a common x-axis forces workarounds that are fragile and difficult to maintain. Users frequently request the ability to show visit scatters with overlaid color stripes for context.

3. **Code Maintainability** - The inheritance hierarchy makes it difficult to add new features. Each new plot type requires creating a new subclass with all the boilerplate that entails.

4. **Dead Code** - Several TimelinePlotter subclasses are no longer used but remain in the codebase, adding to maintenance burden and confusing new users.

The desired changes will provide:

- A cleaner, more intuitive API using the builder pattern
- Better layout capabilities with stacked plots
- Easier maintenance.

## Description of desired changes

The new tlbuilder module (`schedview.plot.tlbuilder`) will implement:

1. **TimelineBuilder class** - A fluent API where users add elements to a plot using a sequence of method calls:

   ```python
   builder = TimelineBuilder(dayobs)
   builder.add_scatter(...)
   builder.add_visits(...)
   builder.add_color_stripe(...)
   plot = builder.build()
   ```

2. **Stacked plot support** - Multiple plots sharing a common x-axis, allowing different data types to be vertically stacked while maintaining temporal alignment.

3. **Visit data support** - Special handling for pandas DataFrames from `schedview.collect.visits.read_visits()` with:
   - Configurable time column (default: `observationStartMJD`)
   - Optional band column for color encoding
   - Configurable plot parameters (alpha, marker, etc.)
   - Visibility toggles for multiple visit sets

4. **Color stripe support** - For background color mapping of continuous quantities:
   - Sun elevation
   - Moon elevation
   - Sky brightness
   - Custom data series

5. **Interactive controls** - Built-in widgets for:
   - Y-axis column selection for scatter plots
   - Visit set visibility toggles
   - Zoom/pan interactions

6. **CLI tool** - A command-line interface for generating standalone HTML files:
   ```bash
   buildtl --num-scatter=2 --visits baseline1.db --visits baseline2.db --background sun_alt --sbstripe --moon-el-stripe
   ```

## Priorities among changes

**Essential features:**

1. Builder pattern API with fluent method chaining
2. Support for pandas DataFrame visit data
3. Stacked plots with common x-axis
4. Color stripe background for continuous quantities
5. Y-axis column selector for scatter plots
6. Visit set visibility toggles
7. Test suite with comprehensive coverage

**Desirable features:**

1. CLI tool for HTML generation
2. Support for custom color maps
3. Hover tooltip customization
4. Export to PNG/PDF

## Changes considered but not included

1. **Complete removal of the old timeline module** - The old `schedview.plot.timeline` will remain in place during the transition period to avoid breaking existing code. A deprecation warning will be added to guide users toward the new API.

2. **Full compatibility with all existing TimelinePlotter subclasses** - The new API will not support all the specialized plotter types (e.g., SchedulerDependenciesTimelinePlotter) that are no longer used. Users of these will be directed to alternative approaches.

3. **Configuration file support** - Initial implementation will focus on programmatic API. Configuration file support may be added later if needed.

4. **Custom JavaScript callbacks** - The initial implementation will use Bokeh's built-in interactive tools rather than custom callbacks, to maintain simplicity and compatibility.

# Concepts for the proposed system

## Background, objectives, and scope

The proposed tlbuilder system is a complete rewrite of the timeline visualization functionality in schedview. It is designed to address the limitations of the existing implementation by adopting a modern builder pattern and providing better support for stacked, aligned visualizations.

The system will be implemented in a new module `schedview.plot.tlbuilder` to allow coexistence with the existing implementation during the transition. Once the new API is stable and all users have migrated, the old module can be deprecated and eventually removed.

## Operational policies and constraints

1. The new implementation must use the same underlying Bokeh library as the existing code.
2. All plot elements must be compatible with Panel dashboards.
3. The API must be documented following the LSST numpydoc style.
4. All public functions and classes must have test coverage.
5. The implementation must not break existing code that depends on `schedview.plot.timeline`.

## Description of the proposed system

The proposed system consists of:

1. **TimelineBuilder** - The main class that provides the builder API. Users create an instance, add plot elements using methods like `add_scatter()`, `add_visits()`, and `add_color_stripe()`, then call `build()` to produce the final Bokeh layout.

2. **Builder methods** - Each method adds a specific type of element to the plot:
   - `add_scatter()` - Add a scatter plot with y-axis selector
   - `add_visits()` - Add visit data as scatter points with optional band coloring
   - `add_color_stripe()` - Add a thin horizontal bar for color-coded data
   - `add_solar_elevation()` - Convenience method for sun elevation background
   - `add_lunar_elevation()` - Convenience method for moon elevation background
   - `add_visit_visibility_selector()` - Add a widget to toggle visit set visibility

3. **Data types supported**:
   - `pandas.DataFrame` with time column (default: `observationStartMJD`)
   - `pandas.Series` with MJD index for continuous data (e.g., sky brightness)
   - Data from `schedview.compute.astro.night_events()` for sun/moon events
   - Data from `rubin_scheduler.site_models.Almanac.get_sun_moon_positions()` for astronomical positions

4. **Output formats**:
   - Bokeh layout for embedding in notebooks and dashboards
   - HTML file for standalone reports
   - Panel components for interactive dashboards

## Modes of operation

The proposed system supports the same operational modes as the current system:

1. **Notebook mode** - Plots created in Jupyter notebooks with interactive widgets
2. **HTML export mode** - Plots saved to HTML files using `bokeh.embed.file_html()`
3. **Dashboard mode** - Plots embedded in Panel web dashboards
4. **CLI mode** - Standalone HTML files generated from command line

## Support environment

The system will run in the same environments as schedview:

- Jupyter notebooks (local and remote)
- Panel web dashboards
- Command-line tools
- HTML reports generated by nbconvert

# Operational scenarios

## Generation of a stand-alone figure in html

A user wants to generate a standalone HTML timeline report for a specific night:

1. The user runs the CLI command:

   ```bash
   buildtl 2026-05-23 --num-scatter=2 --visits baseline_v1.db --visits baseline_v2.db --background sun_alt --sbstripe --moon-el-stripe --output timeline_2026-05-23.html
   ```

2. The command:
   - Collects the date from the command line
   - Determines the DayObs for the date
   - Collects visit data from the specified OpSim databases
   - Computes sun/moon positions and sky brightness
   - Builds the timeline using the default configuration
   - Saves the HTML file using Bokeh's embedding tools

3. The user can share the HTML file with collaborators, who can open it in any modern web browser without needing Python or Jupyter.

## Generation of a figure in a jupyter notebook

A user wants to create an interactive timeline visualization in a Jupyter notebook:

1. The user imports the necessary modules:

   ```python
   from schedview.plot.tlbuilder import TimelineBuilder
   from schedview.dayobs import DayObs
   from schedview.collect.visits import read_visits
   ```

2. The user creates a DayObs and builds the timeline:

   ```python
   dayobs = DayObs.from_date('2026-05-23')
   builder = TimelineBuilder(dayobs)

   # Add scatter plots with y-axis selector
   builder.add_scatter(y_column='fieldRA', name='ra_plot', offered_columns=['HA', 'fieldRA', 'fieldDec'])
   builder.add_scatter(y_column='fiveSigmaDepth', name='depth_plot')

   # Add visit data
   visits_v1 = read_visits(dayobs, 'baseline_v1')
   builder.add_visits(visits_v1, label='v1')

   visits_v2 = read_visits(dayobs, 'baseline_v2')
   builder.add_visits(visits_v2, label='v2', alpha=0.5)

   # Add background color stripes
   sky = get_median_model_sky(dayobs)
   builder.add_color_stripe(height=20, name='sky_brightness')
   builder.add_color_background(sky['g'], 'sky_brightness')

   # Build and display the plot
   p = builder.build()
   from bokeh.io import show
   show(p)
   ```

3. The notebook cell displays an interactive plot with:
   - Multiple stacked plots with aligned time axes
   - Y-axis dropdowns for scatter plot column selection
   - Visit visibility toggles
   - Full Bokeh interactivity (zoom, pan, hover)

## Inclusion of a timeline in an interactive dashboard

A user wants to include a timeline visualization in a Panel dashboard:

1. The user creates a Panel dashboard with interactive controls:

   ```python
   import panel as pn
   pn.extension()

   dayobs_selector = pn.widgets.DatePicker(name='Day Obs')
   visit_source_selector = pn.widgets.Select(name='Visit Source', options=['baseline_v1', 'baseline_v2'])

   @pn.depends(dayobs_selector, visit_source_selector)
   def create_timeline(dayobs_date, visit_source):
       if dayobs_date is None:
           return pn.pane.Markdown("Please select a date")

       dayobs = DayObs.from_date(str(dayobs_date))
       builder = TimelineBuilder(dayobs)

       # ... build timeline using visit_source ...

       return pn.pane.Bokeh(builder.build())

   dashboard = pn.Column(
       pn.Row(dayobs_selector, visit_source_selector),
       pn.panel(create_timeline)
   )
   dashboard.servable()
   ```

2. The dashboard is served using `panel serve` and can be accessed via a web browser.

3. Users can interactively change the day obs and visit source, and the timeline updates automatically.

# Analysis of the proposed system

## Summary of improvements

The proposed tlbuilder system provides the following improvements over the current implementation:

1. **Simpler API** - The builder pattern is more intuitive than class inheritance. Users write a sequence of method calls rather than defining subclasses.

2. **Better layout** - Stacked plots with common x-axis allow proper alignment of events across different data types.

3. **More flexible** - The fluent API allows users to easily combine different plot types and customize their appearance.

4. **Better visit support** - Special handling for visit DataFrames with automatic band coloring and configurable parameters.

5. **Easier maintenance** - The new codebase will be cleaner and more modular, making it easier to add new features.

6. **CLI tool** - Standalone HTML generation without needing to write Python code.

## Disadvantages and limitations

1. **Migration cost** - Existing code using `schedview.plot.timeline` will need to be updated to use the new API.

2. **Learning curve** - While simpler than the old API, users still need to learn the new builder pattern.

3. **Limited feature parity** - Some specialized TimelinePlotter subclasses may not have direct equivalents in the new API.

4. **Bokeh dependencies** - The system remains dependent on Bokeh, which can be large and complex.

# Notes

## Acronyms and abbreviations

- **MJD** - Modified Julian Date
- **OpSim** - Observation simulation database
- **LSST** - Legacy Survey of Space and Time
- **Rubin** - Rubin Observatory (formerly LSST)
- **Bokeh** - Interactive visualization library for Python
- **Panel** - Web dashboard framework for Python
- **ConOps** - Concept of Operations

## Additional information

This ConOps document was created using the IEEE Std 1362-1998 format for Concept of Operations documents.

The tlbuilder implementation will follow the schedview coding conventions as documented in AGENTS.md, including:

- NumPy-style docstrings
- 110 character line length
- Black and isort for formatting
- Ruff for linting
- Comprehensive test coverage

# Time handling

The tlbuilder uses Modified Julian Date (MJD) values from the scheduler for time input, but Bokeh requires datetime types for proper time-axis handling. The conversion and formatting follow Bokeh's conventions:

- **Input**: Time data comes as MJD (float) from `schedview.collect.visits.read_visits()` and `schedview.compute.astro` functions
- **Internal conversion**: MJD values are converted to `numpy.datetime64` type when creating `ColumnDataSource` objects
- **X-axis type**: Bokeh figures use `x_axis_type="datetime"` for proper time-axis rendering
- **Tick formatting**: The x-axis uses `DatetimeTickFormatter` with `hours="%H:%M"` to display time of day in HH:MM format

# Design

## TimelineBuilder Class API

### Overview

The `TimelineBuilder` class provides a fluent builder API for creating interactive timeline visualizations. Users construct plots by calling a sequence of `add_*` methods, then call `build()` to produce the final Bokeh layout.

Time data is provided as Modified Julian Date (MJD) values but is converted to `datetime64` for Bokeh compatibility. The x-axis displays time in HH:MM format using Bokeh's `DatetimeTickFormatter`.

```python
from schedview.plot.tlbuilder import TimelineBuilder
from schedview.dayobs import DayObs

dayobs = DayObs.from_date('2026-05-23')
builder = TimelineBuilder(dayobs)
builder.add_scatter(y_column='altitude', offered_columns=['HA', 'fieldRA', 'altitude'])
builder.add_visits(visits_df, label='baseline')
plot = builder.build()
```

### Core API

```python
class TimelineBuilder:
    """Build interactive timeline visualizations for Rubin Observatory observing nights.

    Parameters
    ----------
    dayobs : `DayObs`
        The day of observing to visualize.
    """

    def __init__(self, dayobs: DayObs) -> None:
        """Initialize the TimelineBuilder for a specific day of observing.

        Parameters
        ----------
        dayobs : `DayObs`
            The day of observing to visualize.
        """
        # Store the dayobs for time range calculations
        self._dayobs = dayobs
        # List of plot elements (ScatterPlotConfig or ColorStripeConfig)
        self._elements: list[ScatterPlotConfig | ColorStripeConfig] = []
        # Shared x-axis range for all plots (datetime type for Bokeh)
        self._shared_x_range: bokeh.models.ranges.Range1d | None = None
        # Track visit data sets for visibility toggles
        self._visit_sets: dict[str, VisitDataSet] = {}
        # Track color stripe data series
        self._color_stripes: dict[str, ColorStripeConfig] = {}
        # Configuration options
        self._figure_kwargs: dict = {"width": 1000}
        self._plot_heights: dict[str, int] = {}
```

```python
    def add_scatter(
        self,
        y_column: str,
        offered_columns: Iterable[str] = (),
        name: str = "scatter",
        height: int | None = None,
        tooltips: list | None = None,
        **figure_kwargs,
    ) -> Self:
        """Add a scatter plot with y-axis column selector.

        Parameters
        ----------
        y_column : `str`
            The initial column to plot on the y-axis.
        offered_columns : `Iterable`[`str`], optional
            Columns to offer in the y-axis selector dropdown.
        name : `str`, optional
            Identifier for this scatter plot.
        height : `int`, optional
            Height of the plot in pixels. Defaults to 200 if None.
        tooltips : `list` or None, optional
            Hover tooltips; defaults to visit tooltips if None.
        **figure_kwargs
            Additional arguments to pass to bokeh.plotting.figure.

        Returns
        -------
        Self
            Returns self for method chaining.

        High-level pseudocode:
        1. Create ScatterPlotConfig with provided parameters (no height stored here)
        2. Store height in _plot_heights[name] if height provided
        3. Add to self._elements list
        4. If first element, create shared x-range from dayobs start/end times
        5. Return self for chaining
        """
        # Pseudocode implementation:
        # if self._shared_x_range is None:
        #     # Convert DayObs times to datetime for Bokeh compatibility
        #     self._shared_x_range = bokeh.models.Range1d(
        #         start=self._dayobs.start.datetime, end=self._dayobs.end.datetime
        #     )
        # scatter_config = ScatterPlotConfig(
        #     name=name,
        #     y_column=y_column,
        #     offered_columns=offered_columns,
        #     tooltips=tooltips,
        #     figure_kwargs=figure_kwargs
        # )
        # self._elements.append(scatter_config)
        # if height is not None:
        #     self._plot_heights[name] = height
        # return self
```

```python
    def add_visits(
        self,
        visits: pd.DataFrame,
        label: str = "visits",
        alpha: float = 1.0,
        marker: str = "circle",
        color_by_band: bool = True,
        show_visibility_toggle: bool = True,
        **scatter_kwargs,
    ) -> Self:
        """Add visit data as scatter points with optional band coloring.

        Parameters
        ----------
        visits : `pandas.DataFrame`
            Visit data from schedview.collect.visits.read_visits().
        label : `str`, optional
            Identifier for this visit set (used for toggling visibility).
        alpha : `float`, optional
            Point transparency (0.0 to 1.0).
        marker : `str`, optional
            Bokeh marker type (e.g., 'circle', 'square', 'diamond').
        color_by_band : `bool`, optional
            Color points by filter band if True.
        show_visibility_toggle : `bool`, optional
            Add a toggle control for this visit set.
        **scatter_kwargs
            Additional arguments passed to scatter plot.

        Returns
        -------
        Self
            Returns self for method chaining.

        High-level pseudocode:
        1. Create ColumnDataSource from visits DataFrame
        2. Add band-based coloring if color_by_band is True
        3. Store visit set with alpha and marker in VisitDataSet
        4. Create ScatterPlotConfig with label for visit data (no alpha/marker)
        5. Add to self._elements list
        6. Store height in _plot_heights[label] if provided
        7. Return self for chaining
        """
        # Pseudocode implementation:
        # from bokeh.models import ColumnDataSource
        # source = ColumnDataSource(visits)
        # if color_by_band and 'band' in visits.columns:
        #     source.data['color'] = make_band_cmap(visits['band'])
        # scatter_config = ScatterPlotConfig(
        #     name=label,
        #     y_column='altitude',  # default, can be overridden
        #     offered_columns=(),
        # )
        # self._elements.append(scatter_config)
        # if 'height' in scatter_kwargs:
        #     self._plot_heights[label] = scatter_kwargs['height']
        # self._visit_sets[label] = VisitDataSet(
        #     source=source, label=label, alpha=alpha, marker=marker, color_by_band=color_by_band
        # )
        # return self
```

```python
    def add_color_stripe(
        self,
        data: pd.Series | pd.DataFrame,
        name: str,
        height: int | None = None,
        colormap: str = "Cividis256",
        value_range: tuple[float, float] | None = None,
    ) -> Self:
        """Add a horizontal color stripe for continuous data background.

        Parameters
        ----------
        data : `pandas.Series` or `pandas.DataFrame`
            Time-series data with MJD index (Series) or time column (DataFrame).
        name : `str`
            Identifier for this color stripe (used for toggling).
        height : `int`, optional
            Height of the stripe in pixels. Defaults to 20 if None.
        colormap : `str`, optional
            Name of Bokeh colormap.
        value_range : `tuple`[`float`, `float`] or None, optional
            (min, max) values for colormap normalization; auto-computed if None.

        Returns
        -------
        Self
            Returns self for method chaining.

        High-level pseudocode:
        1. Convert Series to DataFrame if needed with time column
        2. Ensure time column is datetime type
        3. Create ColumnDataSource from data
        4. Compute value_range if not provided
        5. Create ColorStripeConfig with source and colormap
        6. Add to self._elements list
        7. Store height in _plot_heights[name] if height provided
        8. Return self for chaining
        """
        # Pseudocode implementation:
        # from bokeh.models import ColumnDataSource
        # if isinstance(data, pd.Series):
        #     df = data.to_frame(name='value')
        #     df.index.name = 'time'
        #     df = df.reset_index()
        # else:
        #     df = data.copy()
        # # Ensure time column is datetime
        # if not np.issubdtype(df['time'].dtype, np.datetime64):
        #     df['time'] = Time(df['time']).datetime64
        # source = ColumnDataSource(df)
        # if value_range is None:
        #     value_range = (float(df['value'].min()), float(df['value'].max()))
        # stripe_config = ColorStripeConfig(
        #     name=name,
        #     source=source,
        #     colormap=colormap,
        #     value_range=value_range
        # )
        # self._elements.append(stripe_config)
        # if height is not None:
        #     self._plot_heights[name] = height
        # return self
```

```python
    def add_solar_elevation_stripe(
        self,
        name: str = "sun_elevation",
        height: int | None = None,
        colormap: str = "RdBu_r",
    ) -> Self:
        """Add sun elevation as a color stripe background.

        Convenience method that computes sun elevation from DayObs
        and calls add_color_stripe().

        Parameters
        ----------
        name : `str`, optional
            Identifier for this stripe.
        height : `int`, optional
            Stripe height in pixels. Defaults to `_default_height` if None.
        colormap : `str`, optional
            Colormap name (default: RdBu_r for blue-red centered at 0).

        Returns
        -------
        Self
            Returns self for method chaining.
        """
```

```python
    def add_lunar_elevation_stripe(
        self,
        name: str = "moon_elevation",
        height: int | None = None,
        colormap: str = "Viridis256",
    ) -> Self:
        """Add moon elevation as a color stripe background.

        Parameters
        ----------
        name : `str`, optional
            Identifier for this stripe.
        height : `int`, optional
            Stripe height in pixels. Defaults to 20 if None.
        colormap : `str`, optional
            Colormap name.

        Returns
        -------
        Self
            Returns self for method chaining.
        """
```

```python
    def add_visit_visibility_selector(self) -> Self:
        """Add a widget to toggle visibility of visit sets.

        Creates a MultiChoice widget that allows users to show/hide
        different visit data sets that were added with show_visibility_toggle=True.

        Returns
        -------
        Self
            Returns self for method chaining.

        High-level pseudocode:
        1. Get list of visit set labels from self._visit_sets
        2. Create MultiChoice widget with these labels as options
        3. Create JavaScript callback to toggle visibility of visit data
        4. Store widget in self._visibility_selector
        5. Return self for chaining
        """
        # Pseudocode implementation:
        # options = list(self._visit_sets.keys())
        # self._visibility_selector = MultiChoice(value=options, options=options)
        # callback_code = '''
        #     for (const set of Object.values(visit_sets)) {
        #         set.visible = this.value.includes(set.label);
        #         set.source.change.emit();
        #     }
        # '''
        # self._visibility_selector.js_on_change('value', CustomJS(args={visit_sets: self._visit_sets}, code=callback_code))
        # return self
```

```python
    def build(self) -> bokeh.models.ui.ui_element.UIElement:
        """Build and return the final Bokeh layout.

        Returns
        -------
        element : `bokeh.models.ui.ui_element.UIElement`
            The complete layout containing all plots and widgets.

        High-level pseudocode:
        1. Create shared x-axis range from dayobs start/end times (if not already created)
        2. Group elements by type (scatter vs color stripe)
        3. For each scatter element:
           a. Create figure with shared x_range
           b. Add scatter glyph with appropriate color mapping
           c. Add y-axis selector if offered_columns provided
        4. For each color stripe element:
           a. Create figure with shared x_range and no y-axis
           b. Add rectangle glyphs for each time interval
        5. Arrange all figures vertically using column layout
        6. Add visibility selector if configured
        7. Return the complete layout
        """
        # Pseudocode implementation:
        # if self._shared_x_range is None:
        #     # Convert DayObs times to datetime for Bokeh compatibility
        #     self._shared_x_range = bokeh.models.Range1d(
        #         start=self._dayobs.start.datetime, end=self._dayobs.end.datetime
        #     )
        # figures = []
        # for element in self._elements:
        #     if isinstance(element, ScatterPlotConfig):
        #         height = self._plot_heights.get(element.name)
        #         if height is None:
        #             height = 200  # default for scatter
        #         # Get alpha and marker from VisitDataSet if this is a visit plot
        #         alpha = 1.0
        #         marker = "circle"
        #         if element.name in self._visit_sets:
        #             visit_set = self._visit_sets[element.name]
        #             alpha = visit_set.alpha
        #             marker = visit_set.marker
        #         fig = self._create_scatter_figure(element, height=height, alpha=alpha, marker=marker)
        #         # Set x-axis tick format to HH:MM
        #         fig.xaxis[0].formatter = bokeh.models.DatetimeTickFormatter(hours="%H:%M")
        #         figures.append(fig)
        #     elif isinstance(element, ColorStripeConfig):
        #         height = self._plot_heights.get(element.name)
        #         if height is None:
        #             height = 20  # default for stripe
        #         fig = self._create_color_stripe_figure(element, height=height)
        #         fig.xaxis[0].formatter = bokeh.models.DatetimeTickFormatter(hours="%H:%M")
        #         figures.append(fig)
        #
        # layout_components = figures
        # if hasattr(self, '_visibility_selector'):
        #     layout_components.insert(0, self._visibility_selector)
        #
        # return column(*layout_components)
```

### Data Dictionary

#### TimelineBuilder Class Members

| Member                 | Type                           | Purpose                                                                                 |
| ---------------------- | ------------------------------ | --------------------------------------------------------------------------------------- | -------------------------------------------- |
| `_dayobs`              | `DayObs`                       | The observation day being visualized; used for time range and astronomical calculations |
| `_elements`            | `list[ScatterPlotConfig        | ColorStripeConfig]`                                                                     | List of plot elements (scatters and stripes) |
| `_shared_x_range`      | `bokeh.models.ranges.Range1d`  | Shared x-axis range for all plots (datetime type for Bokeh)                             |
| `_visit_sets`          | `dict[str, VisitDataSet]`      | Dictionary mapping visit set labels to their data sources and configuration             |
| `_color_stripes`       | `dict[str, ColorStripeConfig]` | Dictionary mapping stripe names to their config (same as in `_elements`)                |
| `_figure_kwargs`       | `dict`                         | Default keyword arguments passed to `bokeh.plotting.figure()`                           |
| `_plot_heights`        | `dict[str, int]`               | Map of plot/stripe names to their heights                                               |
| `_visibility_selector` | `MultiChoice` or `None`        | Widget for toggling visit set visibility (created by `add_visit_visibility_selector`)   |

#### ScatterPlotConfig

| Member            | Type              | Purpose                              |
| ----------------- | ----------------- | ------------------------------------ |
| `name`            | `str`             | Identifier for this scatter plot     |
| `y_column`        | `str`             | Initial column for y-axis            |
| `offered_columns` | `tuple[str, ...]` | Columns available in y-axis selector |
| `figure_kwargs`   | `dict`            | Additional figure configuration      |

#### VisitDataSet

| Member          | Type               | Purpose                                              |
| --------------- | ------------------ | ---------------------------------------------------- |
| `source`        | `ColumnDataSource` | Data source containing visit data                    |
| `label`         | `str`              | Identifier for this visit set                        |
| `alpha`         | `float`            | Point transparency (same for all points in this set) |
| `marker`        | `str`              | Bokeh marker type (same for all points in this set)  |
| `color_by_band` | `bool`             | Whether to color by filter band                      |
| `visible`       | `bool`             | Whether this set is currently visible                |

#### ColorStripeConfig

| Member         | Type                  | Purpose                                      |
| -------------- | --------------------- | -------------------------------------------- |
| `name`         | `str`                 | Identifier for this color stripe             |
| `source`       | `ColumnDataSource`    | Time-series data with time and value columns |
| `colormap`     | `str`                 | Bokeh colormap name                          |
| `value_range`  | `tuple[float, float]` | (min, max) for colormap normalization        |
| `color_mapper` | `LinearColorMapper`   | Bokeh color mapper instance                  |
| `height`       | `int`                 | Stripe height in pixels                      |

#### Local Variables in Key Methods

**`add_scatter()`**
| Variable | Type | Purpose |
|----------|------|---------|
| `scatter_config` | `ScatterPlotConfig` | Configuration for the scatter plot being added |
| `column_selector` | `Select` or `None` | Y-axis column selector widget if offered_columns provided |

**`add_visits()`**
| Variable | Type | Purpose |
|----------|------|---------|
| `source` | `ColumnDataSource` | Bokeh data source for visit data |
| `band_column` | `str` or `None` | Column name for band-based coloring |
| `color_mapper` | `FactorColorMapper` | Maps band values to colors |

**`add_color_stripe()`**
| Variable | Type | Purpose |
|----------|------|---------|
| `source` | `ColumnDataSource` | Bokeh data source for time-series data |
| `color_mapper` | `LinearColorMapper` | Maps value range to colormap |

**`build()`**
| Variable | Type | Purpose |
|----------|------|---------|
| `x_range` | `bokeh.models.ranges.Range1d` | Shared time axis for all plots (datetime type) |
| `plots` | `list[Plot]` | List of constructed plot figures |
| `layout_components` | `list[UIElement]` | Final layout elements in display order |

**Time conversion notes:**

- All time values are converted from MJD (float) to `numpy.datetime64` when creating `ColumnDataSource`
- Bokeh figures use `x_axis_type="datetime"` for datetime x-axes
- X-axis ticks are formatted as HH:MM using `DatetimeTickFormatter(hours="%H:%M")`
