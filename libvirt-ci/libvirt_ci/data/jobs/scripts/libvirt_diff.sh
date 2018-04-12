#!/bin/bash

###########################################################
# Update libvirt diff report according to latest git repo #
###########################################################

set -xe

# Run libvirt-diff to update database and generate PDF file
ci libvirt-diff
