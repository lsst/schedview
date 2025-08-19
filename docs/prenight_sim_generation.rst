Pre-night simulation generation
===============================

Daily prenight briefing simulations are currently kicked off by a cron job on ``sdfcron001.sdf.slac.stanford.edu`` as user ``neilsen``.

This runs the script at ``/sdf/data/rubin/shared/scheduler/packages/rubin_sim/batch/run_prenight_sims.sh`` as a slurm job at 8:15am Pacific time every morning, and takes about 10 minutes to run.
The ``rubin_sim`` project holds this script in ``batch/run_prenight_sims.sh``.

Additional documentation can be found in the `docs` for `rubin_sim`.
