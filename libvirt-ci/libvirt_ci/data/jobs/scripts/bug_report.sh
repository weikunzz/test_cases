#!/bin/bash

####################################
# Report PPC and S390 bugs to JIRA #
###################################

set -xe

# kinit to get ticket
kinit -k -t $KEYTAB $PRINCIPAL

# Find bugs and report to jira
ci bug-report --arch ppc
ci bug-report --arch s390
