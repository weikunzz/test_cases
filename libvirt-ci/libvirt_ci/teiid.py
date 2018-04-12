"""
Class of teiid service operation
"""
import logging
import sys
import psycopg2

LOGGER = logging.getLogger(__name__)


class Teiid(object):
    """
    Teiid query class
    """

    def __init__(self, **args):
        self.dbname = args.get('dbname', 'public')
        self.username = args.get('username', 'libvirt-jenkins')
        self.hostname = args.get('hostname', 'virtualdb.engineering.redhat.com')
        self.port = args.get('port', 5433)
        self.cursor = None
        self.conn = None

    def connect(self):
        """
        Init connect with Kerberos / GSSAPI
        Need run kinit first for use kerberos gssapi authorization
        """
        connect_option = "dbname=%s user=%s " % (self.dbname, self.username)
        connect_option += "sslmode=require krbsrvname=postgres "
        connect_option += "host=%s port=%s" % (self.hostname, self.port)
        LOGGER.info("Connecting to Teiid server %s", self.hostname)

        try:
            self.conn = psycopg2.connect(connect_option)
            self.conn.set_isolation_level(0)
            self.cursor = self.conn.cursor()
        except psycopg2.Error as e:
            LOGGER.error("failed to connect to Teiid:\n%s", e)
            sys.exit(1)

    def run_sql_cmd(self, sql_cmd):
        """
        Run sql cmd and return result
        """
        if not self.cursor:
            self.connect()
        try:
            LOGGER.debug("Running SQL command: %s", sql_cmd)
            self.cursor.execute(sql_cmd)
            ret = self.cursor.fetchall()
            LOGGER.debug("Fetched %s entries", len(ret))
            return ret
        except psycopg2.OperationalError, e:
            LOGGER.warning("Command skipped: %s", e)

    def run_sql_file(self, sql_file):
        """
        Run sql from file and return result
        """
        with open(sql_file, 'r') as f:
            sql_commands = f.read().split(';')

        result = []
        for command in sql_commands[:-1]:
            if command:
                result.append(self.run_sql_cmd(command))
        return result
