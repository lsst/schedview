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


class TimelinePlotter:
    key = "events"
    hovertext_column: str | None = None
    time_column: str = "time"
    factor_column: str = "factor"
    factor = "Events"
    glyph_class: type = bokeh.models.Scatter
    jitter: bool = True
    jitter_width: float = 0.2
    default_figure_kwargs: dict = {
        "x_axis_type": "datetime",
        "y_range": bokeh.models.FactorRange(),
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

        glyph_kwargs = self.default_glyph_kwargs
        glyph_kwargs.update(kwargs)
        self.glyph = self.glyph_class(**glyph_kwargs)

        self.plot.add_glyph(self.source, self.glyph)

    @classmethod
    def _create_plot(cls) -> Plot:
        figure_kwargs = {}
        figure_kwargs.update(cls.default_figure_kwargs)
        if cls.hovertext_column is not None and "tooltips" not in figure_kwargs:
            figure_kwargs["tooltips"] = "@" + cls.hovertext_column
        plot = bokeh.plotting.figure(**figure_kwargs)
        return plot

    @classmethod
    def _make_hovertext(cls, row_data: pd.Series) -> str:
        return row_data.to_frame().to_html()

    @classmethod
    def _create_source(cls, *args, **kwargs) -> ColumnDataSource:
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
    def _make_factors(cls, source):
        # Create the factor column in the source data table if it is not
        # already there.
        if cls.factor_column is not None and cls.factor_column not in source.data:
            num_events = len(source.data[cls.time_column])
            source.data[cls.factor_column] = [cls.factor] * num_events

    def _update_factors(self):
        # Make sure this timeline is included in the y range
        try:
            factors = self.plot.y_range.factors
        except AttributeError:
            raise ValueError("supplied plot instance y_range must be FactorRange.")

        needed_factors = sorted(list(set(self.source.data[self.factor_column])))
        for needed_factor in needed_factors:
            if needed_factor not in factors:
                factors.append(needed_factor)

        self.plot.y_range.update(factors=factors)

    @property
    def default_glyph_kwargs(self) -> dict:

        if self.jitter:
            y = bokeh.transform.jitter(self.factor_column, width=self.jitter_width, range=self.plot.y_range)
        else:
            y = self.factor_column

        glyph_kwargs = {"x": self.time_column, "y": y, "size": 5}

        return glyph_kwargs


class LogMessageTimelinePlotter(TimelinePlotter):
    key: str = "log_messages"
    hovertext_column: str | None = "html"
    time_column: str = "date_added"
    factor: str = "Log messages"

    @classmethod
    def _make_hovertext(cls, row_data: pd.Series) -> str:
        return f"<pre>{row_data['message_text']}</pre>"

    @classmethod
    def _make_factors(cls, source):
        # Create the factor column in the source data table if it is not
        # already there.
        if cls.factor_column is not None and cls.factor_column not in source.data:
            # build factor labels for each message
            factor_data = []
            for id in range(len(source.data[cls.time_column])):
                message = {k: source.data[k][id] for k in source.data}
                time_lost_type = "" if message["time_lost_type"] == "None" else message["time_lost_type"]
                writer = "Human" if message["is_human"] else "Automated "
                components = message["components"]
                if len(components) == 1:
                    component = components[0]
                else:
                    component = " & ".join(", ".join([components[:-1], components[-1]]))
                factor_data.append(f"{writer} log message ({component} {time_lost_type})")

            source.data[cls.factor_column] = factor_data


class LogMessageTimelineSpanPlotter(LogMessageTimelinePlotter):
    key: str = "message_spans"
    glyph_class: type = bokeh.models.HBar
    height: float = 0.2

    @classmethod
    def _create_source(cls, *args, **kwargs) -> ColumnDataSource:
        source = super()._create_source(*args, **kwargs)
        for col in ("date_begin", "date_end"):
            source.data[col] = Time([str(t) for t in source.data[col]]).datetime64

        return source

    @cached_property
    def _color(self):
        status_values = list(set(np.unique(self.source.data["time_lost_type"])))
        if len(status_values) == 1:
            color = "red"
        else:
            color = bokeh.transform.factor_cmap(
                "time_lost_type",
                palette=bokeh.palettes.Colorblind[len(status_values)],
                factors=status_values,
            )
        return color

    @property
    def default_glyph_kwargs(self) -> dict:
        glyph_kwargs = {
            "y": self.factor_column,
            "left": "date_begin",
            "right": "date_end",
            "line_color": self._color,
            "fill_color": self._color,
            "line_alpha": 0.5,
            "fill_alpha": 0.5,
            "height": self.height,
        }
        return glyph_kwargs


class SchedulerDependenciesTimelinePlotter(TimelinePlotter):
    key: str = "scheduler_dependencies"
    factor: str = "Scheduler dependencies"
    hovertext_column: str | None = "html"


class SchedulerConfigurationTimelinePlotter(TimelinePlotter):
    key: str = "scheduler_configuration"
    factor: str = "Scheduler configuration"
    hovertext_column: str | None = "html"


class BlockStatusTimelinePlotter(TimelinePlotter):
    key: str = "block_status"
    factor: str = "Block status"
    hovertext_column: str | None = "html"
    jitter: bool = True

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
    def default_glyph_kwargs(self) -> dict:

        if self.jitter:
            y = bokeh.transform.jitter(self.factor_column, width=self.jitter_width, range=self.plot.y_range)
        else:
            y = self.factor_column

        glyph_kwargs = {
            "y": y,
            "x": self.time_column,
            "line_color": "black",
            "fill_color": self._color_map,
            "size": 5,
        }

        return glyph_kwargs


class BlockSpanTimelinePlotter(BlockStatusTimelinePlotter):
    key: str = "block_spans"
    glyph_class: type = bokeh.models.HBar
    height: float = 0.2

    @property
    def default_glyph_kwargs(self) -> dict:

        glyph_kwargs = {
            "y": self.factor_column,
            "left": "start_time",
            "right": "end_time",
            "line_color": self._color_map,
            "fill_color": self._color_map,
            "line_alpha": 0.5,
            "fill_alpha": 0.5,
            "height": self.height,
        }
        return glyph_kwargs

    @classmethod
    def _make_hovertext(cls, row_data: pd.Series) -> str:
        definition = pprint.pformat(json.loads(row_data["definition"]))
        dropped_columns = ["definition", "end", "start_time", "end_time"]
        table = row_data.to_frame().drop(dropped_columns).to_html()
        hovertext = f"<h1>Block</h1>{table}<h2>Definition</h2><pre>{definition}</pre>"
        return hovertext


def make_multitimeline(plot: Plot | None = None, **kwargs) -> Plot:

    # Map keyword arguments to the classes we will use to plot them

    # Recursive utility to get all descendents of the base class, not
    # just direct childer.
    def get_descendents(cls):
        found_descendents = set(cls.__subclasses__())
        for direct_descendent in cls.__subclasses__():
            found_descendents.update(get_descendents(direct_descendent))
        return found_descendents

    plotter_classes = {c.key: c for c in get_descendents(TimelinePlotter)}

    # Iterate over keyword arguments, using the appropriate classes to
    # add timelines to our plot.
    for key in kwargs:
        try:
            cls = plotter_classes[key]
        except KeyError:
            # If we have not defined a subclass, attempt to use the
            # generic one.
            cls = TimelinePlotter
        timeline_plotter = cls(kwargs[key], plot=plot)
        plot = timeline_plotter.plot

    return plot


def make_timeline_scatterplots(visits, visits_column="seeingFwhmEff", **kwargs):
    timeline_plot = make_multitimeline(**kwargs)

    visit_plot = bokeh.plotting.figure(
        x_range=timeline_plot.x_range, y_axis_label=visits_column, x_axis_label="Time (UTC)", name="visit"
    )
    visit_param_vs_time = schedview.plot.plot_visit_param_vs_time(
        visits, visits_column, show_column_selector=True, plot=visit_plot
    )

    ui_element = bokeh.layouts.gridplot([[timeline_plot, visit_param_vs_time]])

    return ui_element
