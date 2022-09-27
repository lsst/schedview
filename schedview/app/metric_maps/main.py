from schedview.app.metric_maps.metric_maps import add_metric_app
import bokeh

doc = bokeh.plotting.curdoc()
add_metric_app(doc)
