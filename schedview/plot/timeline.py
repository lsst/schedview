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
    jitter_width: float = 0.05
    default_figure_kwargs: dict = {
        "x_axis_type": "datetime",
        "y_range": bokeh.models.FactorRange(),
    }

    def __init__(
        self, data: pd.DataFrame | ColumnDataSource | dict | list, plot: Plot | None = None, **kwargs
    ):
        self.plot = plot if plot is not None else self._create_plot()

        # Many queries return lists of dicts, which ColumnDataSource cannot
        # handle directly.
        # Detect when we get one, and convert it to a pandas.DataFrame,
        # which it can handle.
        if isinstance(data, list):
            if len(data) > 0:
                assert isinstance(data[0], dict)
            data = pd.DataFrame(data)

        self.source = data if isinstance(data, ColumnDataSource) else self._create_source(data)
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
        return f"<pre>{str(row_data)}</pre>"

    @classmethod
    def _create_source(cls, *args, **kwargs) -> ColumnDataSource:
        source: ColumnDataSource = ColumnDataSource(*args, **kwargs)

        # Create the hovertext if necessary
        if cls.hovertext_column is not None and cls.hovertext_column not in source.data:
            hovertext = []
            for _, row_data in source.to_df().iterrows():
                hovertext.append(cls._make_hovertext(row_data))
            source.data[cls.hovertext_column] = hovertext

        # Create the factor column if necessary
        if cls.factor_column is not None and cls.factor_column not in source.data:
            num_events = len(source.data[cls.time_column])
            source.data[cls.factor_column] = [cls.factor] * num_events

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

        glyph_kwargs = {"x": self.time_column, "y": y}

        return glyph_kwargs


class LogMessageTimelinePlotter(TimelinePlotter):
    key: str = "log_messages"
    hovertext_column: str | None = "html"
    time_column: str = "date_added"
    factor = "Log messages"

    @classmethod
    def _make_hovertext(cls, row_data: pd.Series) -> str:
        return f"<pre>{row_data['message_text']}</pre>"


def make_multitimeline(plot=None, **kwargs):

    # Map keyword arguments to the classes we will use to plot them
    plotter_classes = {c.key: c for c in TimelinePlotter.__subclasses__()}

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
    visit_param_vs_time = schedview.plot.plot_visit_param_vs_time(
        visits,
        visits_column,
        show_column_selector=True,
    )

    ui_element = bokeh.layouts.gridplot([[timeline_plot, visit_param_vs_time]])

    return ui_element
