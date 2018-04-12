#!/bin/bash

#####################################
#           Clean up venv           #
#####################################

set -xe
if [ ! -z "$VIRTUAL_ENV" ]; then
    deactivate
fi

if [ -L ~/libvirt-ci-latest-venv ]; then
    if [ -d ~/libvirt-ci-latest-venv ]; then
        rm -rf `readlink -f ~/libvirt-ci-latest-venv`
    fi
    rm -rf ~/libvirt-ci-latest-venv
fi
ln -sf $VENV_PATH ~/libvirt-ci-latest-venv
