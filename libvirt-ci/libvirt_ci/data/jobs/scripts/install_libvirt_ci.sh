#!/bin/bash

#####################################
# Install/Update libvirt-ci package #
#####################################

set -xe

pip install --use-wheel --upgrade --force-reinstall \
    git+http://git.host.prod.eng.bos.redhat.com/git/libvirt-ci@$LIBVIRT_CI_BRANCH
