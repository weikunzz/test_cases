#!/bin/bash

#####################################
#           Clean up venv           #
#####################################

set -xe
if [ ! -z "$VIRTUAL_ENV" ]; then
    deactivate
fi

rm -rf $VENV_PATH
