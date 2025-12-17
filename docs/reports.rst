===================
`schedview` Reports
===================

Introduction
============

`schedview` can be used to generate a any of several reports.
Most of these reports are built from `jupyter` notebooks, either using `Times Square <https://rsp.lsst.io/v/usdfprod/guides/times-square/index.html>`__ or `nbconvert <https://nbconvert.readthedocs.io>`__.

Times Square `schedview` notebooks
==================================

The Times Square schedview notebooks can be found at `https://usdf-rsp.slac.stanford.edu/times-square/github/lsst/schedview_notebooks/nightly/scheduler-nightsum <https://usdf-rsp.slac.stanford.edu/times-square/github/lsst/schedview_notebooks/nightly/scheduler-nightsum>`__.
Times Square reports are generated on demand, but cached after the first time they are executed.
Because the `schedview` notebooks can be slow to execute, this is sometimes incovenient, or can fail altogether.

Pre-generated reports
=====================

Introduction
------------

To avoid requiring humans to wait for notebooks to be executed, a `cron` job at the USDF uses submits a set of batch jobs that use `nbconvert` to create a set of `html` pages.
These scripts are found in the `batch` directory of the `schedview_notebooks` repository: `batch/prenight.sh` and `batch/scheduler_nightsum.sh`.
Each of these scripts builds an environment in which to convert the notebook, executes the conversion, and updates a corresponding index it include the new reports.
There are currently two indexes of reports.
One index lists publicly accessible, which are served from `https://s3df.slac.stanford.edu/data/rubin/sim-data/schedview/reports/ <https://s3df.slac.stanford.edu/data/rubin/sim-data/schedview/reports/>`__.
Currently, the public reports are limited to a brief night summary.

Additional reports, currently requiring logging to the the USDF, can be found at `https://usdf-rsp-int.slac.stanford.edu/schedview-static-pages/ <https://usdf-rsp-int.slac.stanford.edu/schedview-static-pages/>`__.

Job sumbission
--------------

The `cron` job runs the reports with the following entries::

    15 5 * * * /opt/slurm/slurm-curr/bin/sbatch /sdf/data/rubin/shared/scheduler/packages/schedview_notebooks/batch/scheduler_nightsum.sh 2>&1 >> /sdf/data/rubin/shared/scheduler/schedview/scheduler_nightsum/scheduler_nightsum.out
    30 7 * * * /opt/slurm/slurm-curr/bin/sbatch /sdf/data/rubin/shared/scheduler/packages/schedview_notebooks/batch/prenight.sh 2>&1 >> /sdf/data/rubin/shared/scheduler/schedview/prenight/prenight.out

If necessary, these cron jobs can be stopped from doing anything, even a user that does not own the cron job, if they have write access to ``/sdf/data/rubin/shared/scheduler/cron_gates/${SCRIPT}``.
This is accomplished using gate files: early in each script, the script checks for the existence of a file with name ``/sdf/data/rubin/shared/scheduler/cron_gates/${SCRIPT_NAME}/${USER}`` and aborts if it does not exist.
Any user with write access to ``/sdf/data/rubin/shared/scheduler/cron_gates/${SCRIPT_NAME}`` can create or remove files in that directory, so a user can cause these scripts to immediately abort
when started by a cron job owned by a different user by removing ``/sdf/data/rubin/shared/scheduler/cron_gates/${SCRIPT_NAME}/${CRON_JOB_USER}``.

So, to stop the `scheduler_nightsum.sh`` cron job owned by user ``neilsen``, remove the file ``/sdf/data/rubin/shared/scheduler/cron_gates/scheduler_nightsum/neilsen``,
and to stop the ``prenight.sh`` cron job owned by user ``neilsen``, remove the file ``/sdf/data/rubin/shared/scheduler/cron_gates/prenight/neilsen``.

The logs of the cron jobs (and any other executions of these scripts submitted using ``sbatch``) can be found in:
* ``/sdf/data/rubin/shared/scheduler/schedview/sbatch/scheduler_nightsum_%A_%a.out`` and
* ``/sdf/data/rubin/shared/scheduler/schedview/sbatch/prenight_%A_%a.out``
where ``%A`` is the slurm "Job array's master job allocation number" and ``%a`` is the slum "Job array ID (index) number".

The environment
---------------

The conda environment provided in the jupyter aspect of the USDF RSP,
and therefore alse Time Square, differs somewhat from the "lsst" environment
available on the development nodes.

To get these batch scripts to execute as they would on a jupyter aspect
notebook or on Times Square, the conda environment there needs to be
duplicated somewhere it can be activated from the slurm job.

Begin by starting a USDF notebook-aspect jupyter lab, making careful note
of which image you select.

From within that jupyterlab, start a terminal, and record the contents
of the environment provided. In the example used below, this was w2025_36,
and the `schedview_notebooks` repository was checked-out into
`/sdf/data/rubin/user/neilsen/devel/schedview_notebooks` .

So, recording the conda environment we want to replicate::

    setup lsst_sitcom
    cd /sdf/data/rubin/user/neilsen/devel/schedview_notebooks/batch
    conda list --explicit > like_rsp_w2025_36_spec.txt

Then log into a USDF development node, go to the directory where
you saved the spec file above, and create an environment in the
shared scheduler space::

    cd /sdf/data/rubin/user/neilsen/devel/schedview_notebooks/batch
    source /sdf/group/rubin/sw/w_latest/loadLSST.sh
    conda create --prefix /sdf/data/rubin/shared/scheduler/envs/like_rsp_w2025_36 --file  like_rsp_w2025_36_spec.txt


The batch script that generates the prenight briefing reeport requeires a version of schedview newer than currently on the RSP, so make a variant with the new schedview added::

    conda create \
        --prefix /sdf/data/rubin/shared/scheduler/envs/prenight_like_rsp_w2025_36 \
        --clone /sdf/data/rubin/shared/scheduler/envs/like_rsp_w2025_36
    conda activate /sdf/data/rubin/shared/scheduler/envs/prenight_like_rsp_w2025_36
    pip install git+https://github.com/lsst/schedview.git@v0.19.0.dev1


Finally, update the bash scripts that need it (``batch/prenight.sh`` and ``batch/scheduler_nightsum.sh``),
for example::

    source /sdf/group/rubin/sw/w_latest/loadLSST.sh
    conda activate /sdf/data/rubin/shared/scheduler/envs/like_rsp_w2025_36

Even though we aren't using the environment provided by the source of `loadLSST.sh` above,
it's still needed to get `conda` into our path.


Updating the version of `schedview_notebooks` used by the `cron` job
--------------------------------------------------------------------

The scripts submitted by the cron job supplied above use the version of schedview in ``/sdf/data/rubin/shared/scheduler/packages/schedview_notebooks``, which is itsef a link to a directory for a specific version, e.g. ``/sdf/data/rubin/shared/scheduler/packages/schedview_notebooks-v0.1.0``.

To tag and install a new version to be used, start by deciding on a tag. Get sorted existing tags with::

    curl -s https://api.github.com/repos/lsst/schedview_notebooks/tags \
        | jq -r '.[].name' \
        | egrep '^v[0-9]+.[0-9]+.[0-9]+.*$' \
        | sort -V

Make and push a new tag (with the base of a checked-out `schedview_notebooks` as the current working directory)::

    NEWTAG="v0.1.0.dev2"
    echo "New tag is ${NEWTAG}"
    echo ""
    git tag ${NEWTAG}
    git push origin tag ${NEWTAG}

Then install it in `/sdf/data/rubin/shared/scheduler/packages`::

    git archive \
        --format=tar \
        --prefix schedview_notebooks-${NEWTAG}/ ${NEWTAG} \
        | tar -x --directory /sdf/data/rubin/shared/scheduler/packages

Replace the symlink to point to your new one::

    if test -L /sdf/data/rubin/shared/scheduler/packages/schedview_notebooks ; then
      rm /sdf/data/rubin/shared/scheduler/packages/schedview_notebooks
    fi
    ln -s /sdf/data/rubin/shared/scheduler/packages/schedview_notebooks-${NEWTAG} /sdf/data/rubin/shared/scheduler/packages/schedview_notebooks

Updating other software used by the jobs
----------------------------------------

The jupyter notebooks used to generate the reports import ``schedview`` and related packages from subtirectories of ``/sdf/data/rubin/shared/scheduler/packages``.
New version should be added there to make them available.

Begin by determining the next available tag.

Get sorted existing tags with::

    MODULENAME="schedview"
    MODULEUSER="lsst"
    curl -s https://api.github.com/repos/${MODULEUSER}/${MODULENAME}/tags \
        | jq -r '.[].name' \
        | egrep '^v[0-9]+.[0-9]+.[0-9]+.*$' \
        | sort -V

Make and push a new tag (with the base of the repository as the current working directory)::

    NEWVERSION="0.1.0.dev2"
    NEWTAG=v${NEWVERSION}
    echo "New version is ${NEWVERSION} with tag ${NEWTAG}"
    echo ""
    git tag ${NEWTAG}
    git push origin tag ${NEWTAG}

Then install it in ``/sdf/data/rubin/shared/scheduler/packages``::

    PACKAGEDIR="/sdf/data/rubin/shared/scheduler/packages"
    TARGETDIR="${PACKAGEDIR}/${MODULENAME}-${NEWVERSION}"
    PIPORIGIN="git+https://github.com/${MODULEUSER}/${MODULENAME}.git@${NEWTAG}"
    echo "Installing from ${PIPORIGIN} to ${TARGETDIR}"
    echo ""
    pip install \
        --no-deps \
        --target=${TARGETDIR} \
        ${PIPORIGIN}

Replace the symlink to point to your new version::

    if test -L ${PACKAGEDIR}/${MODULENAME} ; then
      rm ${PACKAGEDIR}/${MODULENAME}
    fi
    ln -s ${TARGETDIR} ${PACKAGEDIR}/${MODULENAME}


Hand generation of reports
==========================

The `schedview_notebooks` `github repository <https://github.com/lsst/schedview_notebooks/>`__ contains the notebooks themselves.
Execution of the notebooks requires installation `schedview` and its dependencies, following the `schedview intallation documentation <https://schedview.lsst.io/installation.html>`__.
These can be run directly with a user's `jupyter` instance, or converted to `html` using `nbconvert`.
The notebooks themselves containt documentation about how to do this conversion.
The general pattern followed by these instructions is:

#. Setup the python environment.
#. Assign a set of environment variables. These variables map to the parameters used when the notebooks are run using Times Square.
#. Call `nbconvert` with a command that looks similar to this::

    jupyter nbconvert \
        --to html \
        --execute \
        --no-input \
        --ExecutePreprocessor.kernel_name=python3 \
        --ExecutePreprocessor.startup_timeout=3600 \
        --ExecutePreprocessor.timeout=3600 \
        whatever_notebook.ipynb
