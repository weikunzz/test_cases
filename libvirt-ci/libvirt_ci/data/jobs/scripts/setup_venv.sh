#!/bin/bash

#####################################
#         Setup Virtual ENV         #
#####################################

set -xe

VENV_PATH=`mktemp -d -p ~/ -t .libvirt-ci-venv-{venv_dir}-XXXXXX`

virtualenv -p `which python2` $VENV_PATH

source $VENV_PATH/bin/activate

# Copy selinux package from global to virtualenv. See:
# https://dmsimard.com/2016/01/08/selinux-python-virtualenv-chroot-and-ansible-dont-play-nice/
if [ -n "$VIRTUAL_ENV" ]; then
    ls -d $VIRTUAL_ENV/lib*/python*/site-packages | xargs -n 1 cp -r /usr/lib*/python*/site-packages/selinux
fi

# Install six again in the venv as the system site package is not visible inside
pip install six
