#!/usr/bin/env python
"""
libvirt continuous integration project.
"""

import glob
import pip
import sys
import os

from setuptools import setup, find_packages

import libvirt_ci

with open('requirements.txt') as requirements_file:
    # Just in case, We can also do some python 2.6 compatibility
    # check here
    install_requirements = requirements_file.read().splitlines()
    if not install_requirements:
        print("Unable to read requirements from the requirements.txt file")
        sys.exit(2)
    if sys.version_info[0] < 3 and sys.version_info[1] < 7:
        # Wheel 0.30 dropped support for Python 2.6 (And Python 3.2)
        pip.main(['install', 'wheel==0.29.0'])

def find_package_data(path):
    ret = []
    for dirpath, dirname, filenames in os.walk(path):
        ret.append('%s/*' % dirpath)
    return ret

setup(
    name='libvirt_ci',
    description='Libvirt continuous integration project',
    version=libvirt_ci.__version__,
    url=('https://code.engineering.redhat.com/gerrit/#/admin/projects/libvirt-ci'),
    license='GNU General Public License v2',
    author='Libvirt QE',
    author_email='gsun@redhat.com',
    long_description=__doc__,
    scripts=glob.glob('bin/*'),
    packages=find_packages(exclude=['test']),
    package_data={
        'libvirt_ci.data': find_package_data('libvirt_ci/data'),
        'libvirt_ci.config': find_package_data('libvirt_ci/config')
    },
    install_requires=install_requirements,
    include_package_data=True
)
