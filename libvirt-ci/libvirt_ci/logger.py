"""
Generate a logger for a module
"""
import logging

MAX_LOG_LINE_LENGTH = 10000


class CustomFormatter(logging.Formatter):
    def __init__(self, fmt=None, datefmt=None, width=None):
        logging.Formatter.__init__(self, fmt, datefmt)
        self.width = width or MAX_LOG_LINE_LENGTH

    def format(self, record):
        s = logging.Formatter.format(self, record)
        if self.width and len(s) > self.width:
            notice = '... output is too long (%d), truncate to %d ...' % (len(s), self.width)
            s = s[:self.width / 2] + notice + s[-self.width / 2:]
        return s


def setup_root_logger(width=None):
    """
    Setup logger to do proper logging
    """
    # Set root logger to level INFO to log info from external libs
    # eg. pip
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    # Set libvirt_ci logger to level INFO and disable propagate
    # for some library will add extra handler to root logger
    # so stop propagating and output the log at this level
    logger = logging.getLogger('libvirt_ci')
    logger.setLevel(logging.INFO)
    logger.propagate = False
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = CustomFormatter(
        '%(asctime)s | %(levelname)-8s | %(name)s [%(threadName)s] - %(message)s', width=width)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
