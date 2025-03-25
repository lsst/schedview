Pre-night simulation generation
===============================

Daily prenight briefing simulations are currently kicked off by a cron job on ``sdfcron001.sdf.slac.stanford.edu`` as user ``neilsen``.

This runs the script at ``/sdf/data/rubin/shared/scheduler/packages/SP-2004/rubin_scheduler/batch/run_prenight_sims.sh`` as a slurm job at 8:15am Pacific time every morning, and takes about 10 minutes to run.
The ``rubin_sim`` project holds this script in ``batch/run_prenight_sims.sh``.

The ``run_prenight_sims.sh`` script does the following:
 - activates the prenight conda environment from the scheduler shared environment (``/sdf/data/rubin/shared/scheduler/envs/prenight``)
 - Creates a working directory in this format:

   - ``/sdf/data/rubin/shared/scheduler/prenight/work/run_prenight_sims/%Y-%m-%dT%H%M%S``
   - The time in the directory name is in UTC.
 - Queries the EFD for the most recently loaded versions of ts_ocs_config and rubin_scheduler, and installs them in the packages subdirectory of the worknig directory.
 - Finds the highest tagged semantic version number of ts_ocs_utils and installs that in the packages subdirectory of the working directory. (The loaded version of ts_ocs_utils is not available in the EFD as of the time this document is being written.)
 - Runs the following command:

   - ``prenight_sim --scheduler auxtel.pickle.xz --opsim None --script ${SCHEDULER_CONFIG_SCRIPT}``
   - In the above, ``SCHEDULER_CONFIG_SCRIPT`` holds the script name queried from the EFD.
   - This command creates an instance of a scheduler pickle using the scripts specified by the EFD, and then runs set of prenight simulations using this scheduler, performing the following actions:

     - Runs a series of 2 night simulations starting with the upcoming night. The simulations include:
       - A completely nominal simulation, starting at the nominal time with nominal overhead between exposures.
       - Simulations with start times delayed by 1, 10, and 60 minutes (with nominal overhead between exposures).
       - Simulations that start at the nominal time, with random scatter in the overhead time using two different seeds for the random number generator used.
     - Saves the results in the pre-night simulation archive in the ``s3://rubin:rubin-scheduler-prenight/opsim/`` bucket. Although these scripts are tracked in the rubin_scheduler github product, the versions called by the cron job are not those from the active conda environment. This allows these scripts to be updated independently of the version of the scheduler used to run the simulation.

To update the driving script, update the path to the script to point to the ``run_prenight_sims`` script in the required checked-out revision of ``rubin_sim`` , installed under ``/sdf/data/rubin/shared/scheduler/packages``. (When installing a new one, follow the instructions for naming the directory and installing into it in ``/sdf/data/rubin/shared/scheduler/README.txt``.)

For reference, the crontab that kicks off the simulation on ``sdfcron001.sdf.slac.stanford.edu`` is:

::

    SHELL=/bin/bash
    15 8 * * * /opt/slurm/slurm-curr/bin/sbatch /sdf/data/rubin/shared/scheduler/packages/SP-2004/rubin_sim/batch/run_prenight_sims.sh  2>&1 >> /sdf/data/rubin/shared/scheduler/prenight/daily/daily_auxtel_cron.out
    22 12 * * * /opt/slurm/slurm-curr/bin/sbatch 2>& /sdf/data/rubin/shared/scheduler/packages/SP-2004/rubin_sim/batch/compile_prenight_metadata_cache.sh 2>&1 >> /sdf/data/rubin/shared/scheduler/prenight/compile_metadata/compile_prenight_metadata_cron.out

The second command in the cron job updates a cache of simulation metadata in the archive.
