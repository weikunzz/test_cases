#!/bin/bash

#####################################
# Build guest image and update tree #
#####################################

set -xe

if [ -z $URL_PREFIX ]; then
    if [[ $PROVISION_LOCATION == "CN" ]] || [[ `hostname` == *"pek2"* ]]; then
        URL_PREFIX=http://download.eng.pek2.redhat.com/pub/rhel/rel-eng/
    elif [[ $PROVISION_LOCATION == "US" ]] || [[ `hostname` != *"pek2"* ]]; then
        URL_PREFIX=http://download.eng.bos.redhat.com/rel-eng/
    else
        exit 1
    fi
fi

ci build-guest-image --ci-message "$CI_MESSAGE" --url-prefix "$URL_PREFIX" \
    --product {product} --version {version} --arch {arch} --distro "$DISTRO"

ci update-tree --ci-message "$CI_MESSAGE" --product {product} \
    --version {version} --distro "$DISTRO"

# VERSION is distro name and RELEASE is the distro tag, they were
# injected in env after ci update-tree
ci publish \
    --type "image-uploaded" \
    --headers 'product:{product},version:{version},arch:{arch},location:{location}' \
    --header-release '' \
    --header-target '' \
    --header-package '' \
    --header-method '' \
    --body-file tree.json

if [ "{product}" = "RHEL" ] && [ "{arch}" = "x86_64" ] || [ "{arch}" = "ppc64" ] || [ "{arch}" = "ppc64le" ]; then
    ci update-installation-source --ci-message "$CI_MESSAGE" \
        --url-prefix "$URL_PREFIX" --product {product} \
        --version {version} --arch {arch} --distro "$DISTRO"
fi

if [ "{product}" = "RHEL-ALT" ] && [ "{arch}" = "ppc64le" ]; then
    ci update-installation-source --ci-message "$CI_MESSAGE" \
        --url-prefix "$URL_PREFIX" --product {product} \
        --version {version} --arch {arch} --distro "$DISTRO"
fi
