#!/bin/bash

##################################################
# Report test result to Metadash unconditionally #
##################################################

set -xe

for file in result_rhev.xml result_rhel.xml; do
    if [ -f $file ]; then
        ci report-to-metadash --junit $file || echo 'Failed reporting to Metadash'
    else
        echo "$file not found, skipping..."
    fi
done
