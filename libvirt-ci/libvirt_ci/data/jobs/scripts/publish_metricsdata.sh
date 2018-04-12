#!/bin/bash

#################################
# Publish a CI metricsdata message #
#################################

set -xe

if [ "$FORCE_METRICS" != "true" ]; then
    echo "Skip publishing metrics data by default"
else
    if [ "{trigger-by-tree}" = "true" ] ; then
        echo "Skip publishing metrics data for tree trigger."
    else
        if [ -f result_rhev.xml ]
        then
            ci publish-metricsdata --xunit result_rhev.xml
        fi

        if [ -f result_rhel.xml ]
        then
            ci publish-metricsdata --xunit result_rhel.xml
        fi
    fi
fi
