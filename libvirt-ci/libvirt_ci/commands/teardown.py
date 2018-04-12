from __future__ import absolute_import

import logging
import os

from lxml import etree as et
from bkr.common.hub import HubProxy
from bkr.common.pyconfig import PyConfigParser

from libvirt_ci import utils

from novaclient import client as nova_client

LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['python-krbV']


def _cleanup_system(hosts):
    LOGGER.info("Cleanup hosts before returning")
    utils.run_playbook('cleanup_system', hosts=hosts,
                       private_key='libvirt-jenkins',
                       debug=True, ignore_fail=True)


def teardown_bkr(_params):
    if 'BEAKER_JOBID' not in os.environ:
        exit("Can't find BEAKER_JOBID in env")

    job_id = os.environ['BEAKER_JOBID']
    job_url = "https://beaker.engineering.redhat.com/jobs/" + job_id[2:]

    conf = PyConfigParser()
    conf.load_from_file('/etc/beaker/client.conf')
    hub = HubProxy(conf=conf)

    LOGGER.info("Checking status of job %s", job_url)
    active_job_xml = et.fromstring(hub.taskactions.to_xml(job_id))

    hosts = []
    for recipe in active_job_xml.xpath('//recipe[@system]'):
        hosts.append(recipe.get('system'))
    LOGGER.info("Found %s system(s): %s", len(hosts), hosts)
    _cleanup_system(hosts)
    LOGGER.info("Stopping beaker job %s", job_url)
    hub.taskactions.stop(job_id, 'cancel', "Returned by teardown job")
    return 0


def teardown_ciosp(params):
    node_ids = params.node_ids or filter(None, [os.getenv("CIOSP_NODEID")])
    node_names = params.node_names or filter(None, [os.getenv("JSLAVENAME")])

    creds = {
        'url': 'https://ci-rhos.centralci.eng.rdu2.redhat.com:13000/v2.0/',
        'user': 'gsun',
        'pass': 'Redhat_Libvirt',
        'tenant': 'libvirt-jenkins',
        'keypair': 'libvirt-jenkins',
        'net': 'libvirt-jenkins-1',
    }

    nova = nova_client.Client(
        '2',
        username=creds['user'],
        password=creds['pass'],
        project_name=creds['tenant'],
        auth_url=creds['url'],
        service_type='compute')

    nodes = filter(None, nova.servers.list())

    if node_ids:
        nodes = [n for n in nodes if getattr(n, "id") in node_ids]

    if node_names:
        nodes = [n for n in nodes if getattr(n, "name") in node_names]

    if not nodes:
        LOGGER.error("Failed to find a osp node with given condition:"
                     "id: %s, name: %s", node_ids, node_names)
        return 1
    elif len(nodes) > 1 and not params.bulk:
        LOGGER.error("Found multiple node! detail: %s", nodes)
        return 1

    for node in nodes:
        (ip_ip, ip_id), = [(n.ip, n.id) for n in nova.floating_ips.list()
                           if n.instance_id == node.id]

        _cleanup_system([ip_ip])
        task_state = getattr(node, 'OS-EXT-STS:task_state', None)
        LOGGER.info('Cleaning node: %s - %s/%s - created %s - %s',
                    node.name, node.status, task_state, node.created,
                    ','.join([','.join(node.networks[net])
                              for net in node.networks]),
                    )
        try:
            node.delete()

            def _node_deleted():
                nodes = nova.servers.list()
                # pylint: disable=cell-var-from-loop
                return node.id not in [getattr(n, "id") for n in nodes]

            node = utils.wait_for(_node_deleted, 20.0 * 60.0, 0, 5.0,
                                  "Waiting for node to be deleted...")

            LOGGER.info('delete floating IP %s, id: %s', ip_ip, ip_id)
            nova.floating_ips.delete(ip_id)
        except Exception:
            LOGGER.error('Failed teardown machine!')
            raise
        LOGGER.info('Done!')
    return 0


# pylint: disable=unused-argument
def run(params):
    """
    Prepare environment a host for testing
    """
    if params.target == 'bkr':
        ret = teardown_bkr(params)
    elif params.target == 'ci-osp':
        ret = teardown_ciosp(params)
    else:
        LOGGER.error("Unsupported target: %s", params.target)

    if ret:
        LOGGER.info('All Done!')
        return ret

    LOGGER.info('All Done!')


def parse(parser):
    """
    Parse arguments for preparing host environment
    """
    shared_group = parser.add_argument_group('Common options')
    shared_group.add_argument(
        '--target', dest='target', action='store', default='bkr',
        help='Teardown target, ci-osp or bkr')
    shared_group.add_argument(
        '--node-name', dest='node_names', action='append', default=[],
        help='Node name requied for teardown of openstack machines')
    shared_group.add_argument(
        '--node-id', dest='node_ids', action='append', default=[],
        help='Node id for teardown of openstack machines')
    shared_group.add_argument(
        '--bulk', dest='bulk', action='store_true',
        help='Allow to teardown multiple machines at once')
