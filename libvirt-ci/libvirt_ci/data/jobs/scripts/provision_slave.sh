#!/bin/bash

#########################################
# Provision a Jenkins slave for testing #
#########################################

set -xe

ci provision --worker-name "{jslavename}"

# Save parameters
echo TEARDOWN_SLAVE="$TEARDOWN_SLAVE" >> $WORKSPACE/env.txt
echo FORCE_REPORT="$FORCE_REPORT" >> $WORKSPACE/env.txt
echo FORCE_DASHBOARD="$FORCE_DASHBOARD" >> $WORKSPACE/env.txt
echo FORCE_RESULTSDB="$FORCE_RESULTSDB" >> $WORKSPACE/env.txt
echo FORCE_METRICS="$FORCE_METRICS" >> $WORKSPACE/env.txt
echo CI_BREWTASK_ID="$CI_BREWTASK_ID" >> $WORKSPACE/env.txt
echo LIBVIRT_CI_BRANCH="$LIBVIRT_CI_BRANCH" >> $WORKSPACE/env.txt

cat $WORKSPACE/env.txt
