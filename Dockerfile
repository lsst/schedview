# Follow https://micromamba-docker.readthedocs.io/en/latest/

# Base container
FROM mambaorg/micromamba:1.5.1

# Container construction
COPY --chown=$MAMBA_USER:$MAMBA_USER . /home/${MAMBA_USER}/schedview
RUN micromamba install -y -n base -f /home/${MAMBA_USER}/schedview/container_environment.yaml && \
    micromamba clean --all --yes
ARG MAMBA_DOCKERFILE_ACTIVATE=1
RUN python -m pip install /home/$MAMBA_USER/schedview --no-deps
ARG TEST_DATA_DIR=/home/${MAMBA_USER}/schedview/test_data
ARG TEST_DATA_INDEX=https://s3df.slac.stanford.edu/data/rubin/sim-data/sched_pickles/test_snapshots.html
RUN mkdir -p ${TEST_DATA_DIR} && \
    wget --no-parent --directory-prefix=${TEST_DATA_DIR} --no-directories --recursive ${TEST_DATA_INDEX}

# Container execution
ENV RUBIN_SIM_DATA_DIR=/home/${MAMBA_USER}/schedview/rubin_sim_data
CMD prenight --port 8080
