#!/bin/bash

###########################################################################
# Deploy a provisioner host on RHOSP and connect it to Jenkins as a slave #
###########################################################################

set -xe

ci provision --provisioner
