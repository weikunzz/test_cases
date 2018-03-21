"""
Wrapper module to manager email sending
"""
import logging
import logging
import smtplib

from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)


def send(to_addrs, from_addr='libvirt-jenkins@redhat.com', author="libvirt CI",
         subject=None, text=None, separate=True, mimetype='plain', attachments=None):
    """
    Send email to recipients in the identities of libvirt CI
    return True on success
    """

    if isinstance(to_addrs, str):
        to_addrs = [addr.strip() for addr in to_addrs.split(',')]

    to_addrs = [addr if '@' in addr else addr + '@redhat.com'
                for addr in to_addrs]

    message = MIMEMultipart()
    message.attach(MIMEText(text, mimetype))

    message['Subject'] = subject
    message['From'] = '"%s" <%s>' % (author, from_addr)

    for attachment in attachments or []:
        name, text = attachment
        attach_part = MIMEApplication(text, name)
        attach_part['Content-Disposition'] = 'attachment; filename="%s"' % name
        message.attach(attach_part)

    try:
        server = smtplib.SMTP("smtp.corp.redhat.com")
    except Exception:
        logger.critical("Connected to local SMTP server")
        return False

    try:
        message['To'] = ', '.join(to_addrs)
        server.sendmail(from_addr, to_addrs, message.as_string())
        return True
    finally:
        server.quit()

    return True
