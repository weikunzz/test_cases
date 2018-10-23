#!/usr/bin/env python
# coding:utf-8

import logging
import sys

CRITICAL = logging.CRITICAL
FATAL = logging.FATAL
ERROR = logging.ERROR
WARNING = logging.WARNING
WARN = logging.WARN
INFO = logging.INFO
DEBUG = logging.DEBUG
NOTSET = logging.NOTSET


def get_log(modle_name, level=logging.FATAL):
    """
    get a log handler
    :param modle_name:
    :param level:
    :return:
    """

    log = logging.getLogger(modle_name)
    log.setLevel(logging.DEBUG)

    # new log, write log to file "/var/log/icfs/icfs-cli.log" level=logging.DEBUG
    log.addHandler(__get_file_handler())

    # old log, print info to stdout, only filter info like this: "Error(xxx): xxxx xxx". use by ui. level=logging.ERROR
    log.addHandler(__get_stdout_handler())

    # new log, print info to stderr, not count info like: "Error(xxx): xxxx xxx". default level=logging.WARNING
    log.addHandler(__get_stderr_handler(level))

    return log


def __stdout_error_filter(record):
    """
    filter function
    :param record:
    :return:
    """
    msg = record.msg
    if str(msg).startswith("Error"):
        # print "stdout", record.levelname, msg
        return True
    else:
        return False


def __stderr_error_filter(record):
    """
    filter function
    :param record:
    :return:
    """
    msg = record.msg
    if str(msg).startswith("Error"):
        return False
    else:
        # print "stderr", record.levelname, msg
        return True


def __get_filter__(name):
    """
    get a filter
    :param name:
    :return:
    """
    if name not in ("stdout", "stderr"):
        return None
    _filter = logging.Filter(name)
    if name == "stdout":
        _filter.filter = __stdout_error_filter
    elif name == "stderr":
        _filter.filter = __stderr_error_filter
    return _filter


def __get_formater__(format_str=None):
    try:
        if format_str:
            return logging.Formatter(format_str)
        else:
            return logging.Formatter("%(asctime)s - %(filename)s~line:%(lineno)d function:%(funcName)s - pid:%(process)d-tid:%(thread)d- %(levelname)s : %(message)s")
    except:
        return logging.Formatter("%(asctime)s - %(filename)s~line:%(lineno)d function:%(funcName)s - pid:%(process)d-tid:%(thread)d- %(levelname)s : %(message)s")


def __get_file_handler():
    """
    get a file handler
    :return:
    """
    fh = logging.FileHandler("/var/log/icfs-cli.log", mode="a", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(__get_formater__())
    return fh


def __get_level__(level):
    try:
        level = int(level)
        if level > logging.CRITICAL:
            level = logging.CRITICAL
        elif level < logging.NOTSET:
            level = logging.NOTSET
        elif level % 10 != 0:
            level = 10 * (level / 10 + 1)
    except:
        level = logging.WARNING
    return level


def __get_stderr_handler(level=None):
    """
    get a handler which print info to stderr
    :return:
    """
    if not level:
        level = logging.FATAL
    else:
        level = __get_level__(level)
    sh = logging.StreamHandler()
    sh.setLevel(level)
    sh.addFilter(__get_filter__("stderr"))
    sh.setFormatter(__get_formater__())
    return sh


def __get_stdout_handler():
    """
    get a handler which print info to stdout
    :return:
    """
    sh = logging.StreamHandler(stream=sys.stdout)
    sh.addFilter(__get_filter__("stdout"))
    sh.setLevel(logging.ERROR)
    sh.setFormatter(__get_formater__("%(message)s"))
    return sh


# test
def __main__():
    log = get_log("test")
    log.warning("error info")
    log.error("Error(678): file not")
    log.warning("error info")

# test
if __name__ == "__main__":
    __main__()
