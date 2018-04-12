#!/bin/bash

#####################################
# Report failed test result to JIRA #
#####################################

set -xe

if [ $ROOT_BUILD_CAUSE = MANUALTRIGGER ] && [ $FORCE_REPORT != true ] || [ {enable-report} != true ]
then
    echo "Skipping reporting to Jira"
else
    if [ -f result_rhev.xml ]
    then
        ci report-to-jira --junit result_rhev.xml \
            --fail-priority {fail-priority} --skip-priority {skip-priority} \
            --fail-threshold {failure-thld} || echo "Report to JIRA failed, failure ignored"
    fi

    if [ -f result_rhel.xml ]
    then
        ci report-to-jira --junit result_rhel.xml \
            --fail-priority {fail-priority} --skip-priority {skip-priority} || echo "Report to JIRA failed, failure ignored"
    fi
fi
