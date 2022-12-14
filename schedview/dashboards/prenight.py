import gzip
import pickle
import itertools
import warnings
import copy
from collections import namedtuple
from functools import partial

import numpy as np
import pandas as pd
import healpy as hp
import sqlite3
from astropy.time import Time
from astropy.timeseries import TimeSeries
from astropy.coordinates import EarthLocation
import bokeh
import bokeh.io
import bokeh.models
import bokeh.plotting
import bokeh.transform
import bokeh.palettes
import pickle
from copy import deepcopy
import astropy.units as u

from IPython.core.magic import register_cell_magic
from IPython.core.display import display, HTML, Javascript

import rubin_sim
from rubin_sim.scheduler.modelObservatory import Model_observatory
from rubin_sim import maf
from rubin_sim.maf.runComparison import archive
from rubin_sim.scheduler.utils import empty_observation

import hvplot.pandas
import geoviews
import geopandas
import shapely

import cartopy
from cartopy import crs
import healpy
import panel as pn
import holoviews as hv
import param
import hvplot
import hvplot.pandas

import schedview
import schedview.plot
import schedview.plot.SphereMap
import schedview.compute
import schedview.compute.astro
import schedview.compute.scheduler
import schedview.collect
import schedview.collect.stars
import schedview.collect.opsim
import schedview.collect.footprint
import schedview.collect.scheduler_pickle
import schedview.app.metric_maps
import schedview.app.sched_maps
import schedview.plot.scheduler
import schedview.plot.visitmap

def prenight_panel(scheduler_fname, night, visit_fname=rubin_sim.data.get_baseline(), timezone="Chile/Continental"):
    observatory = Model_observatory()

    # Build astronomical events table
    astro_events = schedview.compute.astro.night_events(
        night, observatory.location, timezone
    )
    
    sunset = Time(astro_events.loc["sunset", "UTC"])
    sunrise = Time(astro_events.loc["sunrise", "UTC"])
    night_middle = Time((sunset.mjd + sunrise.mjd)/2, format='mjd')
    
    # Compute basis function using the state at the start of the current night

    # Prepare the scheduler instance to calculate the rewards
    scheduler, conditions = schedview.collect.scheduler_pickle.read_scheduler(scheduler_fname)
    scheduler.update_conditions(conditions)
    old_visits = schedview.collect.opsim.read_opsim(visit_fname, Time(scheduler.conditions.mjd, format='mjd').iso, sunset.iso)
    schedview.compute.scheduler.replay_visits(scheduler, old_visits)

    observatory.mjd = night_middle.mjd
    conditions = observatory.return_conditions()
    scheduler.update_conditions(conditions)
    
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore', category=FutureWarning)
        night_rewards = schedview.compute.scheduler.compute_basis_function_rewards(scheduler)
        
    night_reward_plot = (
        night_rewards
        .replace([np.inf, -np.inf], np.nan)
        .hvplot(by=["survey_name"], x="time", y=["reward"], title="Rewards for each survey")
        .options({"Curve": {"color": hv.Cycle("Category20")}})
    )
    
    # Load visits up to the start of the night and create corresponding pane
    new_visits = schedview.collect.opsim.read_opsim(rubin_sim.data.get_baseline(), sunset.iso, sunrise.iso)
    
    visit_explorer = hvplot.explorer(new_visits, kind="scatter", x="start_date", y="airmass", by=["note"])
    
    # Visit map
    footprint = schedview.collect.footprint.get_greedy_footprint(scheduler)
    observatory.mjd = night_middle.mjd
    conditions = observatory.return_conditions()
    vmap = schedview.plot.visitmap.visit_skymaps(new_visits, footprint, conditions)
    
    # Combine the panes into a panel
    dashboard = pn.Column(
        f"<h1>Pre-night briefing for {night.iso.split()[0]}</h1>",
        "<h2>Astronomical Events</h2>",
        astro_events,
        "<h2>Rewards by survey, with time</h2>",
        night_reward_plot,
        "<h2>Simulated visits</h2>",
        visit_explorer,
        "<h2>Visit map</h2>",
        vmap,
    )

    return dashboard
