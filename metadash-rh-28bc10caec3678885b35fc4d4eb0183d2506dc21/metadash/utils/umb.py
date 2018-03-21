
"""
Create a subscription to the CI message bus.
"""
import logging
import sys
import signal
import stomp
import os

logger = logging.getLogger(__name__)

MSG_KEY = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'key.pem')
MSG_CERT = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'cert.pem')
MSG_CA_CERT = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'ca.pem')
UMB_HOSTS = [('messaging-devops-broker01.web.prod.ext.phx2.redhat.com', 61612),
             ('messaging-devops-broker02.web.prod.ext.phx2.redhat.com', 61612)]


def make_connection(on_message_fn=None, on_error_fn=None):
    """
    Create a subscription to the message bus.
    """
    class CIListener(object):
        """
        CIListener handler Class
        """
        def on_error(self, headers, message):
            """
            Handler on error
            """
            on_error_fn and on_error_fn(self, headers, message)
            logger.info("=" * 72)
            logger.error('RECEIVED AN ERROR.')
            logger.error('Message headers:\n%s', headers)
            logger.error('Message body:\n%s', message)

        def on_message(self, headers, message):
            """
            Handler on message
            """
            on_message_fn and on_message_fn(self, headers, message)
            logger.debug("=" * 72)
            logger.debug('Message headers:\n%s', headers)
            logger.debug('Message body:\n%s', message)

    conn = stomp.Connection(UMB_HOSTS)
    conn.set_listener('Metadash Listener', CIListener())
    conn.set_ssl(for_hosts=UMB_HOSTS,
                 key_file=MSG_KEY,
                 cert_file=MSG_CERT,
                 ca_certs=MSG_CA_CERT)
    conn.start()
    conn.connect()

    return conn


def quick_subscribe(client, topic, on_message=None, on_error=None):
    """
    Make a connection and subscribe, will start a long running thread
    TODO: Selector?
    """

    def _signal_handler(_signal, _message):
        """
        Handler on signal
        """
        logger.info('Terminating subscription.')
        conn.disconnect()
        sys.exit(0)

    conn = make_connection(on_error_fn=on_error, on_message_fn=on_message)

    logger.info("Subscribing to Consumer.libvirt-ci.%s.VirtualTopic.%s", client, topic)

    conn.subscribe(
        destination="Consumer.libvirt-ci.%s.VirtualTopic.%s" % (client, topic),
        ack='auto',
        id=1,
    )

    logger.info("Subscribed to Consumer.libvirt-ci.%s.VirtualTopic.%s", client, topic)

    # Auto disconnect on exit
    signal.signal(signal.SIGINT, _signal_handler)
    signal.pause()

    return conn


def quick_send(topic, headers, body, destination):
    """
    Send a message then disconnect
    """

    conn = make_connection()

    conn.send(message=body, headers=headers,
              destination=destination)

    conn.disconnect()

    return conn
