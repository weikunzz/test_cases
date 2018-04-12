"""
Create a subscription to the CI message bus.
"""
import logging
import sys
import signal
import stomp
import os

from libvirt_ci.data import CERT_PATH

LOGGER = logging.getLogger(__name__)

MSG_LIBVIRT_KEY = os.path.join(CERT_PATH, 'msg-libvirt-ci-key.pem')
MSG_LIBVIRT_CERT = os.path.join(CERT_PATH, 'msg-libvirt-ci-cert.pem')
MSG_REDHAT_KEY = os.path.join(CERT_PATH, 'redhat.pem')
UMB_HOSTS = [('messaging-devops-broker01.web.prod.ext.phx2.redhat.com', 61612),
             ('messaging-devops-broker02.web.prod.ext.phx2.redhat.com', 61612)]


def parse(parser):
    """
    Parse arguments for subscribe message bus
    """
    parser.add_argument(
        '--selector',
        dest='selector',
        metavar='<JMS selector>',
        help='JMS selector for filtering messages.'
    )
    parser.add_argument(
        '--topic',
        dest='topic',
        metavar='<topic>',
        default='VirtualTopic.qe.ci',
        help='Virtual topic to listen to, for brew, use VirtualTopic.eng.brew.'
    )


def run(params):
    """
    Create a subscription to the message bus.
    """
    def _signal_handler(_signal, _message):
        """
        Handler on signal
        """
        LOGGER.info('Terminating subscription.')
        conn.disconnect()
        sys.exit(0)

    class CIListener(object):
        """
        CIListener handler Class
        """
        def on_error(self, headers, message):
            """
            Handler on error
            """
            LOGGER.info("=" * 72)
            LOGGER.error('RECEIVED AN ERROR.')
            LOGGER.error('Message headers:\n%s', headers)
            LOGGER.error('Message body:\n%s', message)

        def on_message(self, headers, message):
            """
            Handler on message
            """
            LOGGER.info("=" * 72)
            LOGGER.info('Message headers:\n%s', headers)
            LOGGER.info('Message body:\n%s', message)

    conn = stomp.Connection(UMB_HOSTS)
    conn.set_listener('Libvirt_CI Listener', CIListener())
    conn.set_ssl(for_hosts=UMB_HOSTS,
                 cert_file=MSG_LIBVIRT_CERT,
                 key_file=MSG_LIBVIRT_KEY,
                 ca_certs=MSG_REDHAT_KEY)
    conn.start()
    conn.connect()

    LOGGER.info("Subscribed to Consumer.libvirt-ci.*.%s", params.topic)
    conn.subscribe(
        destination="Consumer.libvirt-ci.*.%s" % params.topic,
        ack='auto',
        id=1,
    )

    LOGGER.info('Press Ctrl+C to exit.')
    signal.signal(signal.SIGINT, _signal_handler)
    signal.pause()
