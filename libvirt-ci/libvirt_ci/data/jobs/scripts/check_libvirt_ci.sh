#!/bin/bash

######################################################
# Check libvirt-ci code when gerrit change submitted #
######################################################

set -xe
# This is a work around for importer dependency issue and should
# be removed later
pip install --upgrade --force-reinstall setuptools pip requests==2.14.2

# Check style and test jenkins-job-builder configuration
pushd libvirt-ci

make check
make docs
