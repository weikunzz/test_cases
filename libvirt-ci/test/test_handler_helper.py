# pylint:disable=missing-docstring

import copy
import pytest
import dateutil.parser

from libvirt_ci.env.helper import mark_timestamp_recursive, filter_timestamp_recursive

class MagicTimestamp(object):
    """
    Magic class, equals to any string timestamp.
    """
    def __cmp__(self, another):
        if isinstance(another, str):
            try:
                dateutil.parser.parse(another)
            except Exception:
                return 1
            return 0
        return 1
    def __eq__(self, another):
        return not self.__cmp__(another)

param = {
    "d1": {
        "dd1": "value",
        "dd2": "value",
    },
    "l1": [
        "value1",
        "value2",
    ]
}

param_origin = copy.deepcopy(param)

target = {
    "d1": {
        "dd1": {
            "value": "value",
            "timestamp": MagicTimestamp()
        },
        "dd2": {
            "value": "value",
            "timestamp": MagicTimestamp()
        }
    },
    "l1": [
        {
            "value": "value1",
            "timestamp": MagicTimestamp()
        },
        {
            "value": "value2",
            "timestamp": MagicTimestamp()
        }
    ]
}

def test_timestamp_marker():
    param_timestamped = mark_timestamp_recursive(param)
    print target
    print param_timestamped

    assert param == param_origin
    assert target == param_timestamped
    assert param_timestamped == target

def test_timestamp_filter():
    param_timestamped = mark_timestamp_recursive(param)
    param_timestamped_filter_nooutdate = filter_timestamp_recursive(
        param_timestamped,
        expire=float('inf'))
    param_timestamped_filter_alloutdate = filter_timestamp_recursive(
        param_timestamped)

    assert param == param_origin
    assert param_timestamped_filter_nooutdate == {}
    assert param_timestamped_filter_alloutdate == param
