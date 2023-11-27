# Follow https://micromamba-docker.readthedocs.io/en/latest/

# Base container
FROM mambaorg/micromamba:1.5.1

# Container construction
COPY --chown=$MAMBA_USER:$MAMBA_USER . /home/${MAMBA_USER}/schedview
COPY --chown=$MAMBA_USER:$MAMBA_USER /tmp/rubin_sim_data /home/${MAMBA_USER}/rubin_sim_data
RUN micromamba install -y -n base -f /home/${MAMBA_USER}/schedview/container_environment.yaml && \
    micromamba clean --all --yes
ARG MAMBA_DOCKERFILE_ACTIVATE=1
RUN python -m pip install /home/$MAMBA_USER/schedview --no-deps

# Container execution
ENV RUBIN_SIM_DATA_DIR=/home/${MAMBA_USER}/rubin_sim_data
CMD prenight --port 8080
