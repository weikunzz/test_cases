#!/bin/bash

###########################################
# Report test result to ResultsDB #
###########################################

set -xe

if [ $ROOT_BUILD_CAUSE = MANUALTRIGGER ] && [ $FORCE_RESULTSDB != true ]
then
    echo "Skipping reporting to ResultsDB"
else
    echo "Reporting to ResultsDB..."

    for file in result_rhev.xml result_rhel.xml; do
        #TODO: remove this after we splitted rhev/rhel job.
        if [ -f $file ]; then
            ci report-to-resultsdb --junit $file --tags "{dashboard-tags}" \
            || echo "Report to ResultsDB failed, failure ignored."
        else
            echo "$file not found, skipping..."
        fi
    done
fi
