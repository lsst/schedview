from schedview.app.sched_maps.sched_maps import add_scheduler_map_app
import bokeh

doc = bokeh.plotting.curdoc()
add_scheduler_map_app(doc)
