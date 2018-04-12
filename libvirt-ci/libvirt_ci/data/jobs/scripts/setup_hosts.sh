#!/bin/bash

##########################################################
# Setup hosts file to specify download URL automatically #
##########################################################

set -xe

STORE_IP=10.12.0.20
if [[ `hostname` =~ .*(nay|pek2).redhat.com$ ]]
then
    STORE_IP=10.66.4.102
fi
echo $STORE_IP download.libvirt.redhat.com >> /etc/hosts
