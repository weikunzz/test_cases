#!/bin/bash

###########################################
# Report test result to libvirt-dashboard #
###########################################

set -xe

if [ $ROOT_BUILD_CAUSE = MANUALTRIGGER ] && [ $FORCE_DASHBOARD != true ]
then
    echo "Skipping reporting to Dashboard"
else
    echo "Reporting to Dashboard..."
    if [ "{dashboard-auto-submit}" == "true" ]; then
        EXTRA_PARAM="--auto-submit-to-polarion"
    fi
    for file in result_rhev.xml result_rhel.xml; do
        if [ -f $file ]; then
            ci report-to-dashboard --junit $file\
            --description "CI Test Run, Generated with Junit file $file" \
            --tags "{dashboard-tags}" \
            $EXTRA_PARAM \
            || echo "Report to Dashboard failed, failure ignored."
        else
            echo "$file not found, skipping..."
        fi
    done
fi
