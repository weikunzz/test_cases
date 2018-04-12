#!/bin/bash

########################################################
# Update custom yum repo and start a server to monitor #
# new brew build                                       #
########################################################

set -xe

# Update custom yum repo
ci update-repo --email-notify
