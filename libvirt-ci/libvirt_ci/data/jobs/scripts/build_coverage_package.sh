#!/bin/bash

#####################################################
# Build a libvirt rpm package with coverage support #
#####################################################

set -xe

ci build-libvirt-rpm \
    --libvirt-repo {libvirt-repo} \
    --virtcov {virtcov} \
    --coverage-server "$CI_COVERAGE_SERVER" \
    --repo-path {repo-path} \
    --git-commit "$CI_GIT_COMMIT" \
    --patch-url "$CI_PATCH_URL"
