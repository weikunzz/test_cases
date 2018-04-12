#!/bin/bash

#################################################
# Update Jenkins jobs on libvirt-ci code change #
#################################################

set -xe

# This is a work around for importer dependency issue and should
# be removed later
pip install --upgrade --force-reinstall setuptools packaging pyparsing pip 'jinja2<2.9' jenkins-job-builder requests==2.14.2

# Update Jenkins jobs
pushd libvirt-ci

make install

ci update-jobs

ci build-docs
