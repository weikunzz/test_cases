#!/bin/bash

##############################
# Report x86-64 bugs to JIRA #
##############################

set -xe

# kinit to get ticket
kinit -k -t $KEYTAB $PRINCIPAL

# Find x86 ON_QA bugs and report to jira
ci x86-bug-report --sqlfile=$WORKSPACE/libvirt-ci/libvirt_ci/data/psql/RHEL-libvirt-x86-open-bugs.sql
