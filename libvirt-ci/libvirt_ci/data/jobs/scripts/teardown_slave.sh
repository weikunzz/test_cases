#!/bin/bash

########################################
# Teardown specific slave from Jenkins #
########################################

set -xe

curl -X POST {teardown_srv_url} \
    --data '{{"node": "'$JOB_NAME'", "params": {{"BEAKER_JOBID": "'$BEAKER_JOBID'", "WORKEROSTNAME": "'$WORKEROSTNAME'", "WORKER_IPV4ADDR": "'$WORKER_IPV4ADDR'", "TARGET": "'$PROVISION_TARGET'", "CIOSP_NODEID": "'$CIOSP_NODEID'", "JSLAVENAME": "'$JSLAVENAME'"}}}}' \
    -H "Content-Type: application/json"
