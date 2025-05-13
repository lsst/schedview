# Base
FROM almalinux:9-minimal

# Config
WORKDIR /work

# Container construction

# When run in the schedview github action, the "." directory comes from
# a cache that includes schedview and rubin_sim_data
COPY . schedview

# Install conda, then use it to install everything but schedview itself
RUN curl -sSL https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh -o miniforge.sh && \
  chmod +x miniforge.sh && \
  ./miniforge.sh -b -p /work/miniconda && \
  source /work/miniconda/bin/activate && \
  conda init --system
RUN source /work/miniconda/bin/activate && \
  conda config --set solver libmamba && \
  conda env update --file /work/schedview/container_environment.yaml && \
  conda clean --all --yes

# Install schedview itself using pip to get the version copied into the
# the container, in the COPY clause above, so it matches the branch or tag
# on which the github action to build the container is run, rather than
# a version of schedview from the conda channel.
# Note that dependency versions can be set the container_environment.yaml
# file above, as defined in the same branch or tag version of schedview.
RUN source /work/miniconda/bin/activate && \
  python -m pip install /work/schedview --no-deps

# Container execution
ENV RUBIN_SIM_DATA_DIR=/work/schedview/rubin_sim_data
ENV SCHEDULER_SNAPSHOT_DASHBOARD_PORT=8080
ENV LSST_DISABLE_BUCKET_VALIDATION=1
ENV LSST_S3_USE_THREADS=False
ENV S3_ENDPOINT_URL=https://s3dfrgw.slac.stanford.edu
ENV SIMS_SKYBRIGHTNESS_DATA=https://s3df.slac.stanford.edu/groups/rubin/static/sim-data/sims_skybrightness_pre/h5_2023_09_12_small/
ENTRYPOINT ["/work/schedview/docker_entrypoint.sh"]
CMD ["scheduler_dashboard", "--lfa"]
