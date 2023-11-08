# Follow https://micromamba-docker.readthedocs.io/en/latest/
FROM mambaorg/micromamba:1.5.1
COPY --chown=$MAMBA_USER:$MAMBA_USER container_environment.yaml /tmp/container_environment.yaml
COPY rubin_sim_data /home/${MAMBA_USER}/rubin_sim_data
RUN micromamba install -y -n base -f /tmp/container_environment.yaml && \
    micromamba clean --all --yes
ARG MAMBA_DOCKERFILE_ACTIVATE=1
ENV RUBIN_SIM_DATA_DIR=/home/${MAMBA_USER}/rubin_sim_data
CMD prenight --port 8080
