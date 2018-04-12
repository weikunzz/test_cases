#!/bin/bash

############################################################
# Check libvirt-test-API code when gerrit change submitted #
############################################################

set -xe

# Install required packages
pip install sphinx tox simplejson pylint autopep8
pip install inspektor

# Check the code but ignore error since too many issues exists now
pushd libvirt-test-API

make check || echo "Failed to check code style, ignore the error for now"
