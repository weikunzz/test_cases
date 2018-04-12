#!/bin/bash

######################################################
# Check libvirt-ci code when gerrit change submitted #
######################################################

set -xe

pushd libvirt-auto-doc

make all
