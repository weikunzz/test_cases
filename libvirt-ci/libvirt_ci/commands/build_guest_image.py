#!/usr/bin/env python
"""
Update libvirt CI product related parameters.
"""

import logging
import json
import os

from libvirt_ci import utils

from libvirt_ci.data import RESOURCE_PATH

LOGGER = logging.getLogger(__name__)


def create_kickstart(product, version, distro, arch, url_prefix):
    """
    Create kickstart file for install OS in guest image.
    """
    if '.' in version:
        major, _ = version.split('.')
    else:
        major = version
    file_name = 'guest-%s-%s.cfg' % (product, major)
    template_path = os.path.join(RESOURCE_PATH, 'kickstarts', file_name)
    with open(template_path) as template_fp:
        ks_template = template_fp.read()

    post = ''
    if 'pek2' in url_prefix:
        post = (
            "cat > /etc/profile.d/setup_proxy.sh << EOF\n"
            "export http_proxy=http://squid.apac.redhat.com:3128\n"
            "export https_proxy=http://squid.apac.redhat.com:3128\n"
            "export no_proxy=.redhat.com\n"
            "EOF\n")

    url = url_prefix + '%s/compose/Server/%s/os/' % (distro, arch)
    libvirt_ci_url = 'http://download.libvirt.redhat.com/'
    libvirt_ci_url += 'libvirt-CI-repos/RHEL/%s/%s/' % (version, arch)
    ks_str = ks_template.format(url=url, post=post,
                                libvirt_ci_url=libvirt_ci_url)
    ks_path = '/tmp/ks.cfg'
    with open(ks_path, 'w') as ks_fp:
        ks_fp.write(ks_str)


def run(params):
    """
    Main function for updating product related parameters.
    """
    distro = params.distro
    product = params.product
    version = params.version
    arch = params.arch
    url_prefix = params.url_prefix

    if params.ci_message:
        data = json.loads(params.ci_message)
        LOGGER.info("CI message:")
        for line in json.dumps(data, indent=4).splitlines():
            LOGGER.info(line)

        product = data['product']
        version = data['version']
        arches = data['arches']
        distro = data['build']
        if params.arch not in arches:
            LOGGER.error('Target arch %s not found in CI message')
            exit(1)
    else:
        if not all(bool(p) for p in [distro, product, version, arch]):
            LOGGER.error("Neither --ci-message nor all of --distro, "
                         "--product, --version and --arch are specified.")
            exit(1)

    create_kickstart(product, version, distro, arch, url_prefix)

    utils.run_playbook('guest_image_builder', private_key='libvirt-jenkins',
                       debug=True, distro=distro, product=product,
                       version=version, arch=arch, url_prefix=url_prefix,
                       timeout=180000)


def parse(parser):
    """
    Parse arguments for updating product related parameters.
    """
    parser.add_argument(
        '--ci-message', dest='ci_message', action='store',
        default='',
        help='JSON formatted CI message get from central CI message bus')
    parser.add_argument(
        '--url-prefix', dest='url_prefix', action='store', required=True,
        help='URL prefix of product yum tree')
    parser.add_argument(
        '--distro', dest='distro', action='store', default='',
        help='Distro of updating image')
    parser.add_argument(
        '--product', dest='product', action='store', default='',
        help='Image of which product to be update')
    parser.add_argument(
        '--version', dest='version', action='store', default='',
        help='Version of updating product')
    parser.add_argument(
        '--arch', dest='arch', action='store', default='',
        help='CPU architecture version of which image to be updated')
