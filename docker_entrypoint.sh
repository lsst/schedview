#!/bin/bash

# The point of having an entrypoint here is to makes sure
# conda gets setup in the environment before the requested
# command is executed.
source /etc/profile.d/conda.sh

exec "$@"
