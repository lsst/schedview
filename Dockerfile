# Follow https://micromamba-docker.readthedocs.io/en/latest/
FROM mambaorg/micromamba:1.5.1
COPY --chown=$MAMBA_USER:$MAMBA_USER container_environment.yaml /tmp/container_environment.yaml
RUN micromamba install -y -n base -f /tmp/container_environment.yaml && \
    micromamba clean --all --yes
ARG MAMBA_DOCKERFILE_ACTIVATE=1
RUN rs_download_data --force --tdqm_disable --dirs tests,maps,site_models,scheduler,throughputs
RUN rs_download_data --force --tdqm_disable --dirs skybrightness_pre
ENV RUBIN_SIM_DATA_DIR=/home/${MAMBA_USER}/rubin_sim_data
CMD prenight --port 8080
