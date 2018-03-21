"""
Example Plugin
Keep the __init__.py so plugins can access to top package

component/index.js: path have to be uniq among all registed plugins
plugin.json: name have to be uniq among all plugins
"""

from sqlalchemy.exc import OperationalError as SQLAlchemyOperationalError
from metadash.exceptions import RemoteAuthError
from metadash.exceptions import RemoteServerError
from metadash.exceptions import response_exception
import psycopg2


def regist(app):
    @app.errorhandler(SQLAlchemyOperationalError)
    def handler(error):
        if isinstance(error.orig, psycopg2.OperationalError):
            if any(["GSSAPI continuation error" in msg for msg in error.orig.args]):
                return response_exception(RemoteAuthError('global-kerberos', 'Teiid authentication failed!'))
            elif not error.orig.pgcode and not error.orig.pgerror:
                return response_exception(RemoteServerError("Teiid Server Error: {}".format("\n".join(error.orig.args))))
            else:
                # TODO: Exception for SQL error?
                raise error
