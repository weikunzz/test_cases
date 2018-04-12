"""
Helper functions for get/set data in postgresql database
"""
import logging
import os
import psycopg2
import petl

from . import metadata

LOGGER = logging.getLogger(__name__)


class Psycopg2Driver(metadata.MetadataBackendInterface):
    """
    Class for using postgresql as data storage, and use psycopg2 and
    petl to help to load and push data
    """
    def __init__(self, table):
        # Only accept lower name
        self.table = table
        self._build_valid_name()
        self.conn = None
        self.user = None
        self.passwd = None
        self.database = None
        self.host = None
        self.port = 5432
        self._load_from_env()
        try:
            self._connect()
        except metadata.BackendErrorException:
            raise metadata.BackendUnsupportException

    def _build_valid_name(self):
        self.table = self.table.lower()
        self.table = self.table.replace('-', '_')
        self.table = self.table.replace(' ', '_')

    def _load_from_env(self):
        # TODO
        env = os.environ
        self.user = env.get('DB_USER', 'ci')
        self.passwd = env.get('DB_PASSWD', 'Redhat_Libvirt')
        self.database = env.get('DB_DBNAME', 'libvirtcidatabase')
        self.host = env.get('DB_HOST', 'dell-per730-24.lab.eng.pek2.redhat.com')
        self.port = env.get('DB_PORT', 8834)

    def _connect(self):
        try:
            self.conn = psycopg2.connect(user=self.user,
                                         password=self.passwd,
                                         database=self.database,
                                         host=self.host,
                                         port=self.port)
        except psycopg2.OperationalError as e:
            LOGGER.error('Fail to connect to database: %s', e)
            raise metadata.BackendErrorException

    def create_table(self):
        """
        Create a new table in database
        """
        cur = self.conn.cursor()
        try:
            cur.execute("""CREATE TABLE %s()""" % self.table)
        except psycopg2.ProgrammingError:
            self.conn.rollback()
        finally:
            cur.close()

    def fetch(self):
        """
        Fetch data/table from DB
        """
        table = petl.fromdb(self.conn, 'SELECT * FROM %s' % self.table)
        return metadata.DataTable(table)

    # pylint: disable=no-member
    def push(self, data):
        """
        Push data/table to DB
        """
        obj_data = petl.fromdicts(data)
        obj_data = obj_data.cutout('row')
        self.create_table()
        petl.todb(obj_data.tol(), self.conn, self.table, create=True, drop=True)


class Psycopg2ReadOnlyDriver(Psycopg2Driver):
    """
    A read only version Psycopg2Driver
    """
    def push(self, data):
        raise metadata.BackendErrorException('This driver is not support write')
