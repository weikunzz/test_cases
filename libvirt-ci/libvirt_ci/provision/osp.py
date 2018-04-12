"""
Module for osp provision
"""
from __future__ import absolute_import

import logging

# pylint:disable=import-error
from novaclient import client as nova_client
from glanceclient import client as glance_client
from keystoneclient.v2_0 import client as keystone_client
from neutronclient.v2_0 import client as neutron_client

from libvirt_ci import utils

LOGGER = logging.getLogger(__name__)


def reserve_openstack_systems(params):
    creds = {
        'url': 'https://ci-rhos.centralci.eng.rdu2.redhat.com:13000/v2.0/',
        'user': 'gsun',
        'pass': 'Redhat_Libvirt',
        'tenant': 'libvirt-jenkins',
        'keypair': 'libvirt-jenkins',
        'net': 'libvirt-jenkins-1',
    }

    # Prepare OpenStack clients
    keystone = keystone_client.Client(
        username=creds['user'],
        password=creds['pass'],
        tenant_name=creds['tenant'],
        auth_url=creds['url'])
    token = keystone.auth_token
    glance_url = keystone.service_catalog.url_for(
        service_type='image',
        endpoint_type='publicURL')
    glance = glance_client.Client('1', glance_url, token=token)
    neutron = neutron_client.Client(
        username=creds['user'],
        password=creds['pass'],
        tenant_name=creds['tenant'],
        auth_url=creds['url'])
    nova = nova_client.Client(
        '2',
        username=creds['user'],
        password=creds['pass'],
        project_name=creds['tenant'],
        auth_url=creds['url'],
        service_type='compute')

    # Retrieve image ID from image name
    image_id = [im.id for im in glance.images.list()
                if im.name == params.cios_image][0]
    LOGGER.info('Using image %s (id: %s)', params.cios_image, image_id)

    # Retrieve flavor ID from flavor name
    flavor_id = nova.flavors.find(name=params.flavor).id
    LOGGER.info('Using flavor %s (id: %s)', params.flavor, flavor_id)

    # Retrieve network ID from flavor name
    net_id = nova.networks.find(label=creds['net']).id
    LOGGER.info('Using network %s (id: %s)', creds['net'], net_id)

    LOGGER.info('Creating instance %s', params.worker_name)
    node = nova.servers.create(
        name=params.worker_name, image=image_id, flavor=flavor_id,
        key_name=creds['keypair'], nics=[{'net-id': net_id}])
    LOGGER.info('Created instance (id: %s)', node.id)

    node_id = node.id

    def wait_for_node_building():
        nodes = nova.servers.list()
        for node in nodes:
            n = getattr(node, 'id', None)
            if n == node_id:
                if node.status != "BUILD":
                    return node
                LOGGER.info('Node status "%s"', node.status)
                return None
        LOGGER.info('Node with id "%s" not showing up!', node_id)
        return None

    node = utils.wait_for(wait_for_node_building, 20.0 * 60.0, 0, 5.0,
                          "Waiting for node to finish builing...")

    if node.status != 'ACTIVE':
        raise Exception('Unexpected node status "%s"' % node.status)
    LOGGER.info('Node building finished')

    port = [x for x in neutron.list_ports()['ports']
            if x['device_id'] == node_id][0]
    LOGGER.info('Using port (id: %s)', port['id'])

    routers_list = neutron.list_routers(retreive_all=True)
    router = routers_list['routers'][0]
    LOGGER.info('Using router (id: %s)', router['id'])

    neutron_net = router['external_gateway_info']['network_id']
    LOGGER.info('Using network (id: %s)', neutron_net)
    fipargs = {
        'floating_network_id': neutron_net,
        'port_id': port['id'],
    }
    fip_obj = neutron.create_floatingip({'floatingip': fipargs})
    float_ip = fip_obj['floatingip']['floating_ip_address']
    LOGGER.info('Using floating IP %s', float_ip)

    return {node_id: {"system": float_ip}}
