#!/usr/bin/env python
"""
Update libvirt CI product related parameters.
"""

import re
import logging
import json

from libvirt_ci import metadata

LOGGER = logging.getLogger(__name__)


def run(params):
    """
    Main function for updating product related parameters.
    """
    distro = params.distro
    product = params.product
    version = params.version
    distro_tag = ''
    if params.ci_message:
        data = json.loads(params.ci_message)
        LOGGER.info("CI message:")
        for line in json.dumps(data, indent=4).splitlines():
            LOGGER.info(line)

        # Trust the message product name
        product = data['product']
        # Check product name with beaker distro
        distro = data['bkr_info']['distro_name']
        distro_product = re.match(r"^(\D+)-\d", distro)
        if not distro_product or (distro_product.group(1) != product):
            LOGGER.error("Product name %s not match with distro %s from "
                         "the message", product, distro)
            exit(1)
        distro_tag = data['bkr_info']['distro_tags'][-1]
    else:
        if not distro:
            LOGGER.error("Neither --ci-message nor --distro is specified.")
            exit(1)

    with metadata.Metadata('Products') as product_data:
        product_param = product_data[product + version]

        LOGGER.info("Previous product parameters:")
        for key, value in product_param.iteritems():
            LOGGER.info("    %-20s: %s", key, value)
        if distro == product_param['Beaker Distro']:
            LOGGER.info("Beaker distro parameter is latest: %s", distro)
        else:
            LOGGER.info("Update with new content: %s", distro)
            product_param['Beaker Distro'] = distro
            product_param['Tree Repo Name'] = distro
            product_data[product + version] = product_param

    # Write distro info into tree.json file
    distro_dict = {'name': distro}
    if distro_tag:
        distro_dict['tag'] = distro_tag
    with open('tree.json', 'a') as f:
        json.dump(distro_dict, f, indent=4)


def parse(parser):
    """
    Parse arguments for updating product related parameters.
    """
    parser.add_argument(
        '--ci-message', dest='ci_message', action='store',
        default='',
        help='JSON formatted CI message get from central CI message bus')
    parser.add_argument(
        '--product', dest='product', action='store',
        required=True,
        help='Name of updating product. Ex. RHEL, Fedora')
    parser.add_argument(
        '--version', dest='version', action='store',
        required=True,
        help='Version of updating product')
    parser.add_argument(
        '--distro', dest='distro', action='store',
        default='',
        help='Distro of updating product')
