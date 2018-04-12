#!/usr/bin/env python
"""
Update installation files on specified storages servers
"""

import logging
import json
import tempfile
import shutil

from libvirt_ci import utils

LOGGER = logging.getLogger(__name__)


def run(params):
    """
    Main function to update installation files
    """
    product = params.product
    version = params.version
    arch = params.arch
    url_prefix = params.url_prefix

    if params.distro:
        distro = params.distro
    elif params.ci_message:
        data = json.loads(params.ci_message)
        LOGGER.info("CI message:")
        for line in json.dumps(data, indent=4).splitlines():
            LOGGER.info(line)

        distro = data['build']
    else:
        if not all(bool(p) for p in [distro, product, version, arch]):
            LOGGER.error("Neither --ci-message nor all of --distro, "
                         "--product, --version and --arch are specified.")
            exit(1)

    host = ['download.libvirt.redhat.com']
    dirpath = tempfile.mkdtemp()
    if 'RHEL' in product and '7.' in version:
        if 'ppc64le' in arch:
            file_path = "rhel7_newest_ppc64le"
            utils.run_playbook('update_installation_file', host, arch="ppc64le",
                               private_key='libvirt-jenkins', distro=distro,
                               file_path=file_path, dirpath=dirpath,
                               url_prefix=url_prefix, debug=True)
            file_path = "rhel7_newest_ppc64"
            utils.run_playbook('update_installation_file', host, arch="ppc64",
                               private_key='libvirt-jenkins', distro=distro,
                               file_path=file_path, dirpath=dirpath,
                               url_prefix=url_prefix, debug=True)

        else:
            file_path = "rhel7_newest"
            utils.run_playbook('update_installation_file', host, arch=arch,
                               private_key='libvirt-jenkins', distro=distro,
                               file_path=file_path, dirpath=dirpath,
                               url_prefix=url_prefix, debug=True)

    elif 'RHEL' in product and '6.' in version:
        if 'ppc64' in arch:
            file_path = "rhel6_newest_ppc64"
            utils.run_playbook('update_installation_file', host, arch='ppc64',
                               private_key='libvirt-jenkins', distro=distro,
                               file_path=file_path, dirpath=dirpath,
                               url_prefix=url_prefix, debug=True)

        else:
            file_path = "rhel6_newest_x86_64"
            utils.run_playbook('update_installation_file', host, arch='x86_64',
                               private_key='libvirt-jenkins', distro=distro,
                               file_path=file_path, dirpath=dirpath,
                               url_prefix=url_prefix, debug=True)

            file_path = "rhel6_newest_i386"
            utils.run_playbook('update_installation_file', host, arch='i386',
                               private_key='libvirt-jenkins', distro=distro,
                               file_path=file_path, dirpath=dirpath,
                               url_prefix=url_prefix, debug=True)

    elif 'RHEL-ALT' in product:
        file_path = "rhel_alt7_newest_ppc64le"
        utils.run_playbook('update_installation_file', host, arch=arch,
                           private_key='libvirt-jenkins', distro=distro,
                           file_path=file_path, dirpath=dirpath,
                           url_prefix=url_prefix, debug=True)

    else:
        file_path = "%s%s_%s" % (product, version, arch)

    shutil.rmtree(dirpath)


def parse(parser):
    """
    Parse arguments for updating installation files
    """
    parser.add_argument(
        '--ci-message', dest='ci_message', action='store',
        default='',
        help='JSON formatted CI message get from central CI message bus')
    parser.add_argument(
        '--url-prefix', dest='url_prefix', action='store', required=True,
        help='URL prefix of product tree')
    parser.add_argument(
        '--version', dest='version', action='store',
        default='7.3',
        required=True,
        help='Product version of which installation file to be updated')
    parser.add_argument(
        '--product', dest='product', action='store',
        default='RHEL',
        required=True,
        help='Product of which installation file to be updated')
    parser.add_argument(
        '--distro', dest='distro', action='store',
        default='',
        help='Distro of updating product')
    parser.add_argument(
        '--arch', dest='arch', action='store', default='',
        help='CPU architecture version of which image to be updated')
