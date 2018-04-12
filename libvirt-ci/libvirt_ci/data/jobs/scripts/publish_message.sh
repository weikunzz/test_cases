#!/bin/bash

#################################
# Publish a specific CI message #
#################################

set -xe

ci publish --type $MESSAGE_TYPE --header-package $PACKAGE \
    --header-version $VERSION --header-release $RELEASE \
    --header-arch $ARCH --header-target $TARGET \
    --header-owner $OWNER --header-scratch $SCRATCH
