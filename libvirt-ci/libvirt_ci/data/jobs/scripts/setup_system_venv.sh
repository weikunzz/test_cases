#!/bin/bash

########################################################
# Setup Virtual ENV with access to all system packages #
########################################################

# Remember to call either clean_venv or keep_latest_venv

set -xe

VENV_PATH=`mktemp -d -p ~/ -t .libvirt-ci-venv-{venv_dir}-XXXXXX`

virtualenv -p `which python2` --system-site-packages $VENV_PATH

source $VENV_PATH/bin/activate
