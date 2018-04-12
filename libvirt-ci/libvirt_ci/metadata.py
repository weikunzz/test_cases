"""
Helper functions for get/set testing related metadata.
"""
import logging
import abc
import collections
import petl
import copy

from . import importer

LOGGER = logging.getLogger(__name__)


# This is a default backend for Metadata
DEFAULT_BACKEND = [('gdata', 'GData'),
                   ('db_helper', 'Psycopg2ReadOnlyDriver')]


def load_backends(backend_infos):
    """
    Helper to load Metadata backends
    """
    clss = []
    for module, class_name in backend_infos:
        module_name = 'libvirt_ci.' + module
        service_mod = importer.import_module(module_name)
        cls = getattr(service_mod, class_name)
        clss.append(cls)
    return clss


class MetadataBackendInterface(object):
    """
    A Interface class of Metadata Backend
    All the backend need be a child class of this class
    """
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def fetch(self):
        raise NotImplementedError

    @abc.abstractmethod
    def push(self, data):
        raise NotImplementedError


class Metadata(object):
    """
    Class to manage metadata with different backend
    """
    _data = None
    # TODO: save this in a soft way
    _backends = []

    def __init__(self, table, backend_infos=None):
        self._driver = []
        if not backend_infos:
            backend_infos = DEFAULT_BACKEND
        self._backends = load_backends(backend_infos)
        for backend in self._backends:
            try:
                driver = backend(table)
                if driver:
                    self._driver.append(driver)
            # pylint: disable=broad-except
            except Exception:
                LOGGER.debug('Fail to init driver %s', backend)

    def __enter__(self):
        self.fetch()
        return self._data

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.push()

    def fetch(self):
        """
        Fetch data from google spreadsheet to instance
        """
        for driver in self._driver:
            try:
                self._data = driver.fetch()
                return self._data
            # pylint: disable=broad-except
            except Exception:
                LOGGER.info('Fail to fetch data from %s', driver.__class__)

        raise Exception('Fail to fetch the data from all backends')

    def push(self, data=None):
        """
        Push current data to google spreadsheet
        """
        if not data:
            data = self._data

        for driver in self._driver:
            try:
                driver.push(data)
                return
            # pylint: disable=broad-except
            except Exception:
                LOGGER.info('Fail to push data from %s', driver.__class__)

    def get(self, key):
        """
        Retrieve one data by key
        """
        if not self._data:
            self.fetch()
        return self._data[key]

    def set(self, key, value):
        """
        Set local key value pair
        """
        if not self._data:
            self.fetch()
        self._data[key] = value

    def data(self):
        """
        Retrieve all data as a ordered dict
        """
        if not self._data:
            self.fetch()
        return self._data


def get_product_data():
    """
    Get product related metadata.
    """
    LOGGER.warning('get_product_data is deprecated. '
                   'Please use Metadata class instead', )
    return Metadata('Products').fetch()


def get_hosts():
    """
    Get hosts related metadata.
    """
    LOGGER.warning('get_hosts is deprecated. '
                   'Please use Metadata class instead', )
    return Metadata('Hosts').fetch()


def get_features():
    """
    Get features related metadata.
    """
    return get_groups(['feature'])


def get_groups(types=None):
    """
    Get metadata filtered by 'Type'.
    """
    types = types if types else ['feature']
    features = collections.OrderedDict()
    for group_id, group in Metadata('Groups').fetch().items():
        if group['Type'] in types:
            features[group_id] = group
    return features


class BackendUnsupportException(Exception):
    """ TODO """


class BackendErrorException(Exception):
    """ TODO """


class DataTable(object):
    """
    This is a standerd class to store data which from different
    backend(like GData, Psycopg2ReadOnlyDriver). Every driver
    need transfer datas to this object when fetch data, or push data.
    """
    def __init__(self, list_data):
        data = petl.cat(list_data).addrownumbers()
        self._org_data = data.dicts().list()
        self._cur_data = copy.deepcopy(self._org_data)
        self._keys = list_data[0]
        self._dict_table = None
        self._dict_able = self._check_dict_able()

    def _check_dict_able(self):
        first_key = self._keys[0]
        first_values = [data[first_key] for data in self._org_data]
        if len(set(first_values)) != len(first_values):
            return False

        self._dict_table = {}
        for data in self._cur_data:
            self._dict_table[data[first_key]] = data
        return True

    def _data_check(self):
        if not self._dict_able:
            raise Exception('The data cannot be used as a dict')

    # pylint: disable=no-member
    def filter(self, **kargs):
        keys = kargs.keys()
        values = kargs.values()
        data = petl.fromdicts(self._cur_data)
        dict_table = data.dictlookup(tuple(keys))
        if len(values) == 1:
            return dict_table.get(values[0], [])
        else:
            return dict_table.get(tuple(values), [])

    def __setitem__(self, key, item):
        if isinstance(key, int):
            self._cur_data[key] = item
        else:
            self._data_check()
            if not isinstance(item, dict):
                raise Exception('Only support passing a dict')
            data = self._dict_table[key]
            for k, v in item.items():
                data[k] = v
            self._cur_data = petl.fromdicts(self._dict_table.values()).dicts

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._cur_data[key]
        else:
            self._data_check()
            return self._dict_table[key]

    def items(self):
        self._data_check()
        return self._dict_table.items()

    def keys(self):
        self._data_check()
        return self._dict_table.keys()

    def values(self):
        self._data_check()
        return self._dict_table.values()

    def __iter__(self):
        for elem in self._cur_data:
            yield elem

    def append(self, data_dict):
        if not isinstance(data_dict, dict):
            raise Exception('Only support passing a dict')

        if 'row' not in data_dict:
            next_row = self._cur_data[-1]['row'] + 1
            data_dict['row'] = next_row

        self._cur_data.append(data_dict)

    # pylint: disable=no-member
    def diff(self, refresh=True):
        """
        Return the diff of the current data table with the orginal table
        """
        new_obj = petl.fromdicts(self._cur_data).sortheader()
        old_obj = petl.fromdicts(self._org_data).sortheader()
        add, sub = old_obj.diff(new_obj)
        if refresh:
            self._org_data = copy.deepcopy(self._cur_data)

        return add.dicts(), sub.dicts()

    def getkeys(self):
        return self._keys
