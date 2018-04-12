"""
Send message to the message bus
"""
import os
import logging
import json
import stomp

from libvirt_ci.data import CERT_PATH

LOGGER = logging.getLogger(__name__)

MSG_LIBVIRT_KEY = os.path.join(CERT_PATH, 'msg-libvirt-ci-key.pem')
MSG_LIBVIRT_CERT = os.path.join(CERT_PATH, 'msg-libvirt-ci-cert.pem')
MSG_REDHAT_KEY = os.path.join(CERT_PATH, 'redhat.pem')
UMB_HOSTS = [('messaging-devops-broker01.web.prod.ext.phx2.redhat.com', 61612),
             ('messaging-devops-broker02.web.prod.ext.phx2.redhat.com', 61612)]

TYPES = [
    'pull-request',
    'code-quality-checks-done',
    'security-checks-done',
    'peer-review-done',
    'component-build-done',
    'tier-0-testing-done',
    'unit-test-coverage-done',
    'tier-1-testing-done',
    'update-defect-status',
    'test-coverage-done',
    'tier-2-integration-testing-done',
    'product-build-done',
    'tier-2-validation-testing-done',
    'product-test-coverage-done',
    'early-performance-testing-done',
    'early-security-testing-done',
    'functional-testing-done',
    'tier-3-testing-done',
    'nonfunctional-testing-done',
    'product-accepted-for-release-testing',
    'product-build-in-staging',
    'ootb-testing-done',
    'image-uploaded',
    'testing-started',
    'testing-completed'
]

DATA = {
    "build": {
        "weight": 0.2,
        "parent": 'null',
        "awaited": 'null',
        "label": 'null',
        "waiting": 'false',
        "owner_name": "libvirt-ci",
        "package_name": "libvirt",
        "nvr": "libvirt-1.3.5-1",
        "task_id": "null",
        "id": "null",
        "version": "1.3.5",
        "release": "1",
        "arch": "noarch",
        "method": "build",
        "result": 'null'
    },
    "tag": {"name": "1.3.5-1"},
    "attribute": "state",
    "old": "OPEN",
    "new": "CLOSED"
}


def parse(parser):
    """
    Parse arguments for send message to message bus.
    """
    parser.add_argument(
        '--type',
        dest='ci_type',
        metavar='<ci type>',
        default='tier-0-testing-done',
        choices=TYPES,
        help='Message type to publish.'
    )
    parser.add_argument(
        '--destination',
        dest='destination',
        metavar='<destination>',
        default='/topic/VirtualTopic.qe.ci.libvirt',
        help='Virtual topic to bus topic/subscription.'
    )

    group = parser.add_argument_group('Headers')
    group.add_argument(
        '--header-method',
        dest='method',
        metavar='<header method>',
        default='build',
        help='Method to include in message header.'
    )
    group.add_argument(
        '--header-package',
        dest='package',
        metavar='<header package>',
        default='ci-test',
        help='Package name to include in message header.'
    )
    group.add_argument(
        '--header-version',
        dest='version',
        metavar='<header version>',
        default='3.9.0',
        help='Package version to include in message header.'
    )
    group.add_argument(
        '--header-release',
        dest='release',
        metavar='<header release>',
        default='1',
        help='Package release number to include in message header.'
    )
    group.add_argument(
        '--header-arch',
        dest='arch',
        metavar='<header arch>',
        default='noarch',
        help='Package arch to include in message header.'
    )
    group.add_argument(
        '--header-target',
        dest='target',
        metavar='<header target>',
        default='rhel-7.5-candidate',
        help='Target of the package to include in message header.'
    )
    group.add_argument(
        '--header-owner',
        dest='owner',
        metavar='<header owner>',
        default='libvirt-ci',
        help='Owner to include in message header.'
    )
    group.add_argument(
        '--header-scratch',
        dest='scratch',
        metavar='<header scratch>',
        default='TRUE',
        help='Package scratch (TRUE or FALSE) to include in message header.'
    )
    group.add_argument(
        '--header-ci-name',
        dest='ci_name',
        metavar='<header ci_name>',
        default='libvirt-ci',
        help='CI_NAME to include in message header.'
    )
    group.add_argument(
        '--header-location',
        dest='location',
        metavar='<header location>',
        default='',
        help='location to include in message header for provision.'
    )
    group.add_argument(
        '--headers',
        dest='headers',
        metavar='<headers>',
        default='',
        help='Customized headers in json format'
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        '--body',
        dest='body',
        metavar='<body>',
        help='Body of message.'
    )
    group.add_argument(
        '--body-file',
        dest='bodyfile',
        metavar='<body-file>',
        help='File to use as body of message.'
    )


def run(params):
    """
    Publish a message on the message bus.
    """
    headers = {'method': params.method}
    headers["CI_TYPE"] = params.ci_type
    headers['package'] = params.package
    headers['target'] = params.target
    headers['owner'] = params.owner
    headers['scratch'] = params.scratch
    headers['CI_NAME'] = params.ci_name
    if params.location:
        headers['location'] = params.location

    # Override headers with custom headers in parameter
    if params.headers:
        items = params.headers.split(',')
        try:
            for item in items:
                key, value = item.split(':')
                headers[key] = value
        except ValueError as details:
            raise ValueError("Malformed header '%s': %s" %
                             (params.headers, details))

    DATA['build']['method'] = params.method
    DATA['build']['package_name'] = params.package
    DATA['build']['owner_name'] = params.owner
    nvr = '-'.join((params.package, params.version, params.release))
    DATA['build']['nvr'] = nvr
    DATA['build']['version'] = params.version
    DATA['build']['release'] = params.release
    DATA['build']['arch'] = params.arch
    tag = '-'.join((params.version, params.release))
    DATA['tag']['name'] = tag
    json_msg = json.dumps(DATA, indent=4)

    body = json_msg
    if params.body:
        body = params.body
    if params.bodyfile:
        with open(params.bodyfile, "r") as body_fp:
            body = body_fp.read()

    conn = stomp.Connection(UMB_HOSTS)
    conn.set_ssl(for_hosts=UMB_HOSTS,
                 cert_file=MSG_LIBVIRT_CERT,
                 key_file=MSG_LIBVIRT_KEY,
                 ca_certs=MSG_REDHAT_KEY)
    conn.start()
    conn.connect()

    LOGGER.info("Publish to %s", params.destination)

    if stomp.__version__[0] < 4:
        # Silent a pylint false positive
        # pylint: disable=no-value-for-parameter
        conn.send(message=body, headers=headers,
                  destination=params.destination)
    else:
        conn.send(body=body, headers=headers,
                  destination=params.destination)
    conn.disconnect()
    LOGGER.info('Message sent.')
