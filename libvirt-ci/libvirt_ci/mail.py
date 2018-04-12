"""
Wrapper module to manager email sending
"""

import errno
import logging
import smtplib
import socket
import time

from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart

from libvirt_ci import utils

LOGGER = logging.getLogger(__name__)


def send(to_addrs, from_addr='libvirt-jenkins@redhat.com', author="libvirt CI",
         subject=None, text=None, separate=True, mimetype='plain', attachments=None):
    """
    Send email to recipients in the identities of libvirt CI
    """

    if isinstance(to_addrs, (str, unicode)):
        to_addrs = [addr.strip() for addr in to_addrs.split(',')]

    to_addrs = [addr if '@' in addr else addr + '@redhat.com'
                for addr in to_addrs]

    message = MIMEMultipart()
    message.attach(MIMEText(text, mimetype))

    message['Subject'] = subject
    message['From'] = '"%s" <%s>' % (author, from_addr)

    for attachment in attachments:
        name, text = attachment
        attach_part = MIMEApplication(text, name)
        attach_part['Content-Disposition'] = 'attachment; filename="%s"' % name
        message.attach(attach_part)

    retry = 3
    while True:
        try:
            server = smtplib.SMTP("localhost")
            LOGGER.warning("Connected to local SMTP server")
            break
        except socket.error as err:
            if retry > 0 and err.errno == errno.ECONNREFUSED:
                LOGGER.warning("Failed to connect to SMTP server: %s", err)
                LOGGER.warning("Trying to start postfix daemon")
                utils.run("service postfix start")
            else:
                raise err
        time.sleep(1)
        retry -= 1

    if retry > 0:
        try:
            if separate:
                for to_addr in to_addrs:
                    message['To'] = to_addr
                    server.sendmail(from_addr, [to_addr], message.as_string())
            else:
                message['To'] = ', '.join(to_addrs)
                server.sendmail(from_addr, to_addrs, message.as_string())
        finally:
            server.quit()
