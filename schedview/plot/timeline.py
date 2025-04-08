"""Module for creating timelines.

Tools for creating timelines of sequences of events.

Notes
-----

The ``TimelinePlotter`` base class creates a generic timeline from a
``bokeh.models.ColumnDataSource`` or a ``pandas.DataFrame``, ``dict``, or
``list`` that can be converted to ``bokeh.models.ColumnDataSource`` by the
`ColumnDataSource constructor`_. It must contain a ``time`` column, and it
produces a simple timeline where each row is represented by a diamond on a
timeline.

.. _`ColumnDataSource constructor`:
    https://docs.bokeh.org/en/latest/docs/reference/models/sources.html#bokeh.models.ColumnDataSource

Subclasses of ``TimelinePlotter`` tune the timeline plots to different kinds
of data.  Some customizations are simple: changing the factor used to
represent timeline (vertical horizontal line on the plot), the columns used
for time and any hovertext, the bokeh glyph used to represent the data,
and parameter used by that glyph are all specified by simple class attributes
that can be overriden by child classes; see the docstrings for the attributes
of the ``TimelinePlotter`` base class.

More complex changes can be achieved through overriding methods of
``TimelinePlotter``, including replacing how the
``bokeh.models.ColumnDataSource`` is derived from the data argument, how
hovertext is constructed, setting glyph keyword arguments based on data values,
and splitting data from a single source across multiple factors (resulting
in multiple parallel timelines on the same plot).
"""

import json
import pprint
from functools import cached_property

import bokeh
import bokeh.layouts
import bokeh.models
import bokeh.plotting
import bokeh.transform
import numpy as np
import pandas as pd
from astropy.time import Time
from bokeh.models import ColumnDataSource
from bokeh.models.plots import Plot

import schedview.compute.nightreport
import schedview.plot.nightreport

from .colors import make_band_cmap


class TimelinePlotter:
    """A base and generic class for bokeh timeline plot creation.

    Parameters
    ----------
    data : pd.DataFrame | ColumnDataSource | dict | list
        Data which can be used to create a bokeh ColumnDataSource.
    plot : `Plot` or `None`
        The ``bokeh.models.Plot`` instance on which to put the timeline.

    Notes
    -----
    The initializer does most of the work, creating (or maybe reusing, in the
    case of ``plot``) the ``plot``, ``glyph``, and ``renderer`` members, which
    are the relevant instances of ``bokeh.models.plots.Plot``,
    ``bokeh.models.glyph.Glyph``, and
    ``bokeh.models.renderers.renderer.Renderer``, respectively.

    Although the class itself can be used for simple timelines, in most
    cases it will be used as a base class for subclasses specialized for
    the plot desired.
    """

    key = "events"
    """Used by ``make_multitimeline`` to identify a class to use to instantiate
    a timeline plot: the key attribute of a subclass of TimelinePlotter
    becomes a keyword argument to ``make_multitimeline``."""

    hovertext_column: str = "hovertext"
    """Column name for hovertext text."""

    time_column: str = "time"
    """Column used to place points along the timeline. Some subclasses
    with different kinds of placement may ignore this."""

    factor_column: str = "factor"
    """When multiple timelines are placed on the same factor plot, this
    this column determines the factor. If the column does not exist,
    the _make_factors method may create it."""

    factor = "Events"
    """The factor name, if the factor column does not exist and the
    default implementation of _make_factors is not overriden."""

    glyph_class: type = bokeh.models.Scatter
    """The ``bokeh.models.glyph.Glyph``` subclass to be used to represent
    the data."""

    jitter: bool = False
    jitter_width: float = 0.2
    default_figure_kwargs: dict = {
        "x_axis_type": "datetime",
    }

    def __init__(
        self, data: pd.DataFrame | ColumnDataSource | dict | list, plot: Plot | None = None, **kwargs
    ):
        self.plot: Plot = plot if plot is not None else self._create_plot()

        # Many queries return lists of dicts, which ColumnDataSource cannot
        # handle directly.
        # Detect when we get one, and convert it to a pandas.DataFrame,
        # which it can handle.
        if isinstance(data, list):
            if len(data) > 0:
                assert isinstance(data[0], dict)
            data = pd.DataFrame(data)

        self.source: ColumnDataSource = (
            data if isinstance(data, ColumnDataSource) else self._create_source(data)
        )
        self._update_factors()

        glyph_kwargs = self._make_glyph_kwargs
        glyph_kwargs.update(kwargs)
        self.glyph = self.glyph_class(**glyph_kwargs)

        self.renderer = self.plot.add_glyph(self.source, self.glyph)

    @classmethod
    def _create_plot(cls) -> Plot:
        """Instantiate a ``bokeh.models.plots.Plot`` onto which to put
        the timeline.
        """

        figure_kwargs = {"y_range": bokeh.models.FactorRange()}
        figure_kwargs.update(cls.default_figure_kwargs)
        if cls.hovertext_column is not None and "tooltips" not in figure_kwargs:
            figure_kwargs["tooltips"] = "@" + cls.hovertext_column
        plot = bokeh.plotting.figure(**figure_kwargs)
        return plot

    @classmethod
    def _make_hovertext(cls, row_data: pd.Series) -> str:
        """Create the content for hovertext.

        Parameters
        ----------
        row_data : `pd.Series`
            Fields for one row of the column data source.

        Returns
        -------
        hovertext : `str`
            The content of the hovertext, marked up with html.
        """
        return row_data.to_frame().to_html(header=False)

    @classmethod
    def _create_source(cls, *args, **kwargs) -> ColumnDataSource:
        """Wrapper around the ``ColumnDataSource`` constructor that adds
        any additional columns needed.

        Parameters
        ----------
        See ``ColumnDataSource``.

        Returns
        -------
        source : `ColumnDataSource`
            The data source to use for the plot.
        """

        source: ColumnDataSource = ColumnDataSource(*args, **kwargs)

        # Create the hovertext if necessary
        if cls.hovertext_column is not None and cls.hovertext_column not in source.data:
            hovertext = []
            for _, row_data in source.to_df().iterrows():
                hovertext.append(cls._make_hovertext(row_data))
            source.data[cls.hovertext_column] = hovertext

        cls._make_factors(source)

        # Convert type of time column if necessary
        time_data = source.data[cls.time_column]
        if isinstance(time_data, np.ndarray):
            time_is_datetime64 = np.issubdtype(time_data.dtype, np.datetime64)
        else:
            time_is_datetime64 = False

        if not time_is_datetime64:
            try:
                # If given a type astropy.time.Time can handle directly, do...
                source.data[cls.time_column] = Time(time_data).datetime64
            except ValueError:
                # ... otherwise try converting it to a string first.
                source.data[cls.time_column] = Time([str(t) for t in time_data]).datetime64

        return source

    @classmethod
    def _make_factors(cls, source: ColumnDataSource):
        """If it does not alread exist, fill out the factor column (set by the
        ``factor_column`` attribute) in the data source.

        Parameters
        ----------
        source : `ColumnDataSource`
            The source to supplement with factors.
        """
        # Create the factor column in the source data table if it is not
        # already there.
        if cls.factor_column is not None and cls.factor_column not in source.data:
            num_events = len(source.data[cls.time_column])
            source.data[cls.factor_column] = [cls.factor] * num_events

    def _update_factors(self):
        """Update the y axis of the ``bokeh.models.plot.Plot`` in the ``plot``
        attribute to include all the factors used in this timeline.
        """
        # Make sure this timeline is included in the y range
        try:
            factors = self.plot.y_range.factors
        except AttributeError:
            raise ValueError("supplied plot instance y_range must be FactorRange.")

        if isinstance(self.source.data[self.factor_column][0], list):
            # Our factor column has offsets
            factor_values = [f[0] for f in self.source.data[self.factor_column]]
        else:
            factor_values = self.source.data[self.factor_column]

        needed_factors = sorted(list(set(factor_values)))

        for needed_factor in needed_factors:
            if needed_factor not in factors:
                factors.append(needed_factor)

        self.plot.y_range.update(factors=factors)

    @property
    def _make_glyph_kwargs(self) -> dict:
        """Set the keyword argumentns used to instantiate the timeline's
        ``bokeh.models.glyph.Glyph``. This dictionary will be used as arguments
        for the constructor of the class specified in the ``glyph_class``
        attribute."""
        if self.jitter:
            y = bokeh.transform.jitter(self.factor_column, width=self.jitter_width, range=self.plot.y_range)
        else:
            y = self.factor_column

        glyph_kwargs = {"x": self.time_column, "y": y, "size": 10, "marker": "diamond"}

        return glyph_kwargs


class LogMessageTimelinePlotter(TimelinePlotter):
    """Plot generator for the narrative log.

    Parameters
    ----------
    `data`: `list`
        As produced by
        ``schedview.collect.get_night_narrative``

    Examples
    --------

    > import bokeh.plotting
    > from schedview.dayobs import DayObs
    > from schedview.collect import get_night_narrative
    > from schedview.plot.timeline import LogMessageTimelinePlotter
    >
    > day_obs = DayObs.from_date('2024-12-10')
    > telescope = "Simonyi"
    > messages = get_night_narrative(day_obs, telescope)
    > timeline = LogMessageTimelinePlotter(messages)
    > bokeh.plotting.save(timeline.plot, filename='myplot.html')
    """

    key: str = "log_messages"
    time_column: str = "date_added"
    factor: str = "Log messages"

    @classmethod
    def _make_hovertext(cls, row_data: pd.Series) -> str:
        return f"<pre>{row_data['message_text']}</pre>"

    @classmethod
    def _make_factor_data(cls, source):
        factor_data = []
        for id in range(len(source.data[cls.time_column])):
            message = {k: source.data[k][id] for k in source.data}
            time_lost_type = "" if message["time_lost_type"] == "None" else message["time_lost_type"]
            writer = "Human" if message["is_human"] else "Automated "
            components = message["components"]
            if len(components) == 1:
                component = components[0]
            else:
                component = " & ".join([", ".join(components[:-1]), components[-1]])
            factor_data.append(f"{writer} log message ({component} {time_lost_type})")
        return factor_data

    @classmethod
    def _make_factors(cls, source: ColumnDataSource):
        # Create the factor column in the source data table if it is not
        # already there.
        if cls.factor_column is not None and cls.factor_column not in source.data:
            source.data[cls.factor_column] = cls._make_factor_data(source)


class LogMessageTimelineSpanPlotter(LogMessageTimelinePlotter):
    key: str = "message_spans"
    glyph_class: type = bokeh.models.HBar
    height: float = 0.1
    vertical_offset: float = -0.15

    @classmethod
    def _create_source(cls, *args, **kwargs) -> ColumnDataSource:
        source = super()._create_source(*args, **kwargs)
        for col in ("date_begin", "date_end"):
            source.data[col] = Time([str(t) for t in source.data[col]]).datetime64

        return source

    @classmethod
    def _make_factors(cls, source: ColumnDataSource):
        # Create the factor column in the source data table if it is not
        # already there.
        if cls.factor_column is not None and cls.factor_column not in source.data:
            source.data[cls.factor_column] = [[f, cls.vertical_offset] for f in cls._make_factor_data(source)]

    @property
    def _make_glyph_kwargs(self) -> dict:

        if self.jitter:
            y = bokeh.transform.jitter(self.factor_column, width=self.jitter_width, range=self.plot.y_range)
        else:
            y = self.factor_column

        glyph_kwargs = {
            "y": y,
            "left": "date_begin",
            "right": "date_end",
            "line_color": "#00babc",
            "fill_color": "#00babc",
            "line_alpha": 0.5,
            "fill_alpha": 0.5,
            "height": self.height,
        }
        return glyph_kwargs


class SchedulerDependenciesTimelinePlotter(TimelinePlotter):
    key: str = "scheduler_dependencies"
    factor: str = "Scheduler dependencies"


class SchedulerConfigurationTimelinePlotter(TimelinePlotter):
    key: str = "scheduler_configuration"
    factor: str = "Scheduler configuration"


class SchedulerStapshotTimelinePlotter(TimelinePlotter):
    key: str = "scheduler_snapshots"
    factor: str = "Scheduler snapshots"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.plot.add_tools(
            bokeh.models.TapTool(
                renderers=[self.renderer],
                callback=bokeh.models.OpenURL(url="@url"),
            )
        )


class BlockStatusTimelinePlotter(TimelinePlotter):
    key: str = "block_status"
    factor: str = "Block status"

    @classmethod
    def _make_hovertext(cls, row_data: pd.Series) -> str:
        definition = pprint.pformat(json.loads(row_data["definition"]))
        table = row_data.drop("definition").to_frame().to_html()
        hovertext = f"<h1>Block</h1>{table}<h2>Definition</h2><pre>{definition}</pre>"
        return hovertext

    @cached_property
    def _color_map(self):
        status_values = ["STARTED", "EXECUTING", "COMPLETED", "ERRER"]
        status_values = status_values + list(set(np.unique(self.source.data["status"])) - set(status_values))
        color_map = bokeh.transform.factor_cmap(
            "status",
            palette=bokeh.palettes.Colorblind[len(status_values)],
            factors=status_values,
        )
        return color_map

    @property
    def _make_glyph_kwargs(self) -> dict:

        if self.jitter:
            y = bokeh.transform.jitter(self.factor_column, width=self.jitter_width, range=self.plot.y_range)
        else:
            y = self.factor_column

        glyph_kwargs = {
            "y": y,
            "x": self.time_column,
            "line_color": self._color_map,
            "fill_color": self._color_map,
            "size": 10,
            "marker": "diamond",
        }

        return glyph_kwargs


class BlockSpanTimelinePlotter(BlockStatusTimelinePlotter):
    key: str = "block_spans"
    glyph_class: type = bokeh.models.HBar
    height: float = 0.1
    vertical_offset: float = -0.15

    @property
    def _make_glyph_kwargs(self) -> dict:

        glyph_kwargs = {
            "y": self.factor_column,
            "left": "start_time",
            "right": "end_time",
            "line_color": self._color_map,
            "fill_color": self._color_map,
            "line_alpha": 0.5,
            "fill_alpha": 0.5,
            "height": 0.1,
        }
        return glyph_kwargs

    @classmethod
    def _make_factors(cls, source: ColumnDataSource):
        # Create the factor column in the source data table if it is not
        # already there.
        if cls.factor_column is not None and cls.factor_column not in source.data:
            num_events = len(source.data[cls.time_column])
            source.data[cls.factor_column] = [[cls.factor, cls.vertical_offset]] * num_events

    @classmethod
    def _make_hovertext(cls, row_data: pd.Series) -> str:
        definition = pprint.pformat(json.loads(row_data["definition"]))
        dropped_columns = ["definition", "end", "start_time", "end_time"]
        table = row_data.to_frame().drop(dropped_columns).to_html()
        hovertext = f"<h1>Block</h1>{table}<h2>Definition</h2><pre>{definition}</pre>"
        return hovertext


class VisitTimelinePlotter(TimelinePlotter):
    key: str = "visit_timeline"
    factor: str = "Visits"
    glyph_class: type = bokeh.models.HBar
    time_column: str = "obs_start"
    height: float = 0.025
    hovertext_rows: list[str] = [
        "visit_id",
        "exposure_name",
        "seq_num",
        "physical_filter",
        "band",
        "s_ra",
        "s_dec",
        "sky_rotation",
        "azimuth",
        "altitude",
        "zenith_distance",
        "airmass",
        "exp_time",
        "shut_time",
        "dark_time",
        "img_type",
        "science_program",
        "observation_reason",
        "target_name",
    ]
    alt_scale = 0.4 / 90.0

    @property
    def _make_glyph_kwargs(self) -> dict:
        band_cmap = make_band_cmap()

        glyph_kwargs = {
            "y": self.factor_column,
            "left": "obs_start",
            "right": "obs_end",
            "line_color": band_cmap,
            "fill_color": band_cmap,
            "line_alpha": 1.0,
            "fill_alpha": 0.5,
            "height": "scaled_alt",
        }
        return glyph_kwargs

    @classmethod
    def _make_hovertext(cls, row_data: pd.Series) -> str:
        return row_data[cls.hovertext_rows].to_frame().to_html(header=False)

    @classmethod
    def _create_source(cls, *args, **kwargs) -> ColumnDataSource:
        source = super()._create_source(*args, **kwargs)
        source.data["scaled_alt"] = cls.alt_scale * source.data["altitude"]
        return source

    @classmethod
    def foo_make_factors(cls, source):
        # Create the factor column in the source data table if it is not
        # already there.
        factor_values = []
        if cls.factor_column is not None and cls.factor_column not in source.data:
            for alt in source.data["altitude"]:
                if isinstance(alt, float) and 0 < alt < 90:
                    factor_values.append([cls.factor, (alt - 90) * cls.alt_scale])
                else:
                    factor_values.append([cls.factor, 0])

            source.data[cls.factor_column] = factor_values


class SunTimelinePlotter(TimelinePlotter):
    key: str = "sun"
    factor: str = "Sun"
    glyph_class: type = bokeh.models.HBar
    height: float = 0.2

    @classmethod
    def _create_source(cls, night_events) -> ColumnDataSource:
        sun_events = [
            "sunset",
            "sun_n12_setting",
            "sun_n18_setting",
            "sun_n18_rising",
            "sun_n12_rising",
            "sunrise",
        ]
        period_names = [
            "civil & nautical twilight",
            "astronomical twilight",
            "night",
            "astronomical twilight",
            "civil & nautical twilight",
        ]

        source = ColumnDataSource(
            data={
                "start_time": night_events.loc[sun_events[:-1], "UTC"].values,
                "end_time": night_events.loc[sun_events[1:], "UTC"].values,
                "period": period_names,
                "factor": [cls.factor] * 5,
            },
        )

        source.data[cls.hovertext_column] = [
            f"""<h2>{r['period']}</h2>
            <table><tr><th>Start</th><td>{r['start_time'].strftime("%Y-%m-%d %H:%M:%SZ")}</td></tr>
            <tr><th>End</th><td>{r['end_time'].strftime("%Y-%m-%d %H:%M:%SZ")}</td></tr></table>"""
            for _, r in source.to_df().iterrows()
        ]

        return source

    @property
    def _make_glyph_kwargs(self) -> dict:

        cmap = bokeh.transform.factor_cmap(
            "period",
            palette=["lightblue", "blue", "black"],
            factors=["civil & nautical twilight", "astronomical twilight", "night"],
        )

        glyph_kwargs = {
            "y": self.factor_column,
            "left": "start_time",
            "right": "end_time",
            "line_color": cmap,
            "fill_color": cmap,
            "height": self.height,
        }
        return glyph_kwargs


class ScriptQueueLogeventScriptTimelinePlotter(TimelinePlotter):
    key: str = "script_queue_logevent_script"
    factor: str = "Script queue"
    time_column: str = "first_logevent_time"

    @classmethod
    def _create_source(cls, data, *args, **kwargs) -> ColumnDataSource:
        for col in tuple(data.keys()):
            if col.startswith("timestamp"):
                data[col.removeprefix("timestamp")] = Time(data[col], format="unix_tai").datetime64

        # Import here rather than up top so we can import the module even
        # if lsst.ts.xml.enums.Script in missing.
        from lsst.ts.xml.enums.Script import ScriptState

        data["scriptStateName"] = data["scriptState"].map({int(k): ScriptState(k).name for k in ScriptState})

        source = super()._create_source(data, *args, **kwargs)
        return source

    @property
    def _make_glyph_kwargs(self) -> dict:

        # Import here rather than up top so we can import the module even
        # if lsst.ts.xml.enums.Script in missing.
        from lsst.ts.xml.enums.Script import ScriptState

        script_states = [ScriptState(k).name for k in ScriptState]

        if len(script_states) <= 8:
            palette = bokeh.palettes.Colorblind[len(script_states)]
        else:
            palette = bokeh.palettes.Category20[len(script_states)]

        color_map = bokeh.transform.factor_cmap(
            "scriptStateName",
            palette=palette,
            factors=script_states,
        )

        glyph_kwargs = {
            "x": self.time_column,
            "y": self.factor_column,
            "size": 10,
            "marker": "diamond",
            "line_color": color_map,
            "fill_color": color_map,
            "fill_alpha": 0.5,
        }
        return glyph_kwargs


class ScriptQueueLogeventScriptSpanTimelinePlotter(ScriptQueueLogeventScriptTimelinePlotter):
    key: str = "script_queue_logevent_script_span"
    glyph_class: type = bokeh.models.HBar
    height: float = 0.1
    vertical_offset: float = -0.15

    @classmethod
    def _make_factors(cls, source: ColumnDataSource):
        # Create the factor column in the source data table if it is not
        # already there.
        if cls.factor_column is not None and cls.factor_column not in source.data:
            num_events = len(source.data[cls.time_column])
            source.data[cls.factor_column] = [[cls.factor, cls.vertical_offset]] * num_events

    @property
    def _make_glyph_kwargs(self) -> dict:

        stages = ["Congifure", "Process"]
        palette = ["red", "blue"]

        color_map = bokeh.transform.factor_cmap(
            "stage",
            palette=palette,
            factors=stages,
        )

        glyph_kwargs = {
            "y": self.factor_column,
            "left": "start_time",
            "right": "end_time",
            "line_color": color_map,
            "fill_color": color_map,
            "fill_alpha": 0.5,
            "height": self.height,
        }
        return glyph_kwargs


class ModelSkyTimelinePlotter(TimelinePlotter):
    key: str = "model_sky"
    factor: str = "Med. model sky"
    glyph_class: type = bokeh.models.HBar
    height: float = 0.2
    band: str = "r"
    alt_scale = 0.2 / 90.0

    @property
    def _make_glyph_kwargs(self) -> dict:

        cmap = bokeh.transform.linear_cmap(
            self.band,
            palette=bokeh.palettes.Cividis256,
            low=21.5,
            high=19.5,
        )

        glyph_kwargs = {
            "y": self.factor_column,
            "left": "begin_time",
            "right": "end_time",
            "line_color": cmap,
            "fill_color": cmap,
            "height": self.height,
        }
        return glyph_kwargs

    @classmethod
    def _make_factors(cls, source):
        # Create the factor column in the source data table if it is not
        # already there.
        factor_values = []
        if cls.factor_column is not None and cls.factor_column not in source.data:
            for alt in source.data["moon_alt"]:
                if isinstance(alt, float) and -90 <= alt <= 90:
                    factor_values.append([cls.factor, alt * cls.alt_scale])
                else:
                    factor_values.append([cls.factor, 0])

            source.data[cls.factor_column] = factor_values


def make_multitimeline(plot: Plot | None = None, **kwargs) -> Plot:
    """Create a plot with multiple parallel timelines.

    Parameters
    ----------
    plot : `Plot` | `None`, optional
        Instance of `bokeh.models.Plot` onto which to put the plots,
        by default ``None``.
    **kwargs : `dict`:
        Keyword arguments suppled to this function map supply tho data
        to be plotted as timelines. Each keyword maps directly to the `key`
        member of subclasses of `schedview.plot.Timeline`. For example,
        if you assign data to the `foo` keyword argument of this function,
        it will search for a subclass of
        `schedview.plot.timeline.TimelinePlotter` with `foo` as the value of
        it`s `key` attribute, and use that to create the timeline for that
        data.

    Returns
    -------
    plot : `Plot`
        Instance of `bokeh.models.Plot` with the plots.

    Examples
    --------

    ``make_multitimeline`` creates plots using the ``TimelinePlotter``
    class or one of its subclasses. Arguments to ``make_multitimeline`` provide
    the data for these timelines. The names of these arguments (that is,
    keys of ``**kwargs``) determine which sublclasse of ``TimelinePlotter``
    gets used by ``make_timelineplotter`` to plot the assigned data.

    For example, let's plot ``egg`` and ``ham`` event data. Begin by
    importing the necessary modules:

    >>> from schedview.plot.timeline import TimelinePlotter, make_multitimeline
    >>> from astropy.time import Time
    >>> import pandas as pd
    >>> import bokeh.plotting


    Now, create some egg and hame data:
    >>> egg_data = pd.DataFrame({
    ...     'time': Time(
    ...         [61000.2, 61000.22, 61000.45], format='mjd').datetime64,
    ...     'n': [1, 2, 42]
    ... })
    >>> ham_data = pd.DataFrame({
    ...    'ham_time': Time(
    ...        [61000.3, 61000.35, 61000.37], format='mjd').datetime64,
    ...     'm': [10, 20, 33]
    ... })


    Create some costom subclasses of ``TimelinePlotter`` for plotting ``egg``
    and ``ham`` data:
    >>> class EggTimelinePlotter(TimelinePlotter):
    ...     key = 'eggs'
    ...     factor = 'Egg events'
    ...
    >>> class HamTimelinePlotter(TimelinePlotter):
    ...     key = 'ham'
    ...     factor = 'Ham events'
    ...     time_column = 'ham_time'
    ...

    Now, we can call ``make_multitimeline`` to create a plot in which there
    are two parallel horizontal timelines, one for eggs, and one for ham, with
    each of these horizontal timelines named with the string assigned to
    the ``factor`` class attribute in the above defined subclasses of
    ``TimelinePlotter``: ``Egg events`` and ``Ham events``, for ham and egg
    data, respectively.
    >>> p = make_multitimeline(eggs=egg_data, ham=ham_data)
    >>> bokeh.plotting.output_file('/tmp/egg_ham_timelines.html')
    >>> bokeh.plotting.save(p)
    '/tmp/egg_ham_timelines.html'

    Note the that keyword arguments to ``make_multitimeline`` correspond to the
    ``key`` attributes of ``EggTimelinePlotter`` and ``HamTimelinePlotter``.
    """
    # Map keyword arguments to the classes we will use to plot them

    # Recursive utility to get all descendents of the base class, not
    # just direct children.
    def get_descendents(cls):
        found_descendents = set(cls.__subclasses__())
        for direct_descendent in cls.__subclasses__():
            found_descendents.update(get_descendents(direct_descendent))
        return found_descendents

    plotter_classes = {c.key: c for c in get_descendents(TimelinePlotter)}

    # Iterate over keyword arguments, using the appropriate classes to
    # add timelines to our plot.
    # Reverse the order in the dictionary so the "top down" order in the
    # argument list matches the "top down" order in the plot.
    for key in reversed(kwargs.keys()):
        data = kwargs[key]
        if len(data) < 1:
            # If there is no data, don't add it.
            continue
        try:
            cls = plotter_classes[key]
        except KeyError:
            # If we have not defined a subclass, attempt to use the
            # generic one.
            print(f"GENERIC for {key}!")
            cls = TimelinePlotter
        timeline_plotter = cls(data, plot=plot)
        plot = timeline_plotter.plot

    return plot


def make_timeline_scatterplots(visits, visits_column="altitude", user_param_plot_kwargs=None, **kwargs):
    """Create a figure with a timeline plot (as created by
    `schedview.plot.timeline.make_multitimeline`) and a visit scatterplot
    (as created by `schedview.plot.visits.plot_visit_param_vs_time`)
    side-by-side.

    Parameters
    ----------
    `visits`: `pandas.DataFrame`
        One row per visit, as created by `schedview.collect.read_opsim`.
    `column_name`: `str`
        The name of the column to plot against time.
    **kwargs : `dict`:
        Keyword arguments suppled to this function map directly to the `key`
        member of subclasses of `schedview.plot.Timeline`. For example,
        if you assign data to the `foo` keyword argument of this function,
        it will search for a subclass of
        `schedview.plot.timeline.TimelinePlotter` with `foo` as the value of
        it`s `key` attribute, and use that to create the timeline for that
        data.

    Returns
    -------
    element : `bokeh.models.ui.ui_element.UIElement`
        The bokeh UI element with the side-by-side plots.
    """

    timeline_plot = make_multitimeline(**kwargs)

    figure_kwargs = {"y_axis_label": visits_column, "x_axis_label": "Time (UTC)", "name": "visit"}
    try:
        figure_kwargs["x_range"] = timeline_plot.x_range
    except AttributeError:
        # If there was no timeline data, timeline_plot.x_range
        # would not have been set.
        pass

    visit_plot = bokeh.plotting.figure(**figure_kwargs)

    param_plot_kwargs = {"size": 10, "show_column_selector": True}
    if user_param_plot_kwargs is not None:
        param_plot_kwargs.update(user_param_plot_kwargs)

    visit_param_vs_time = schedview.plot.plot_visit_param_vs_time(
        visits, visits_column, plot=visit_plot, **param_plot_kwargs
    )

    ui_element = bokeh.layouts.gridplot([[timeline_plot, visit_param_vs_time]])

    return ui_element
