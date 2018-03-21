"""
A simple and hacky SQLAlchemy dialect for Teiid.
Not fully functional, SELECT, JOIN and some other simple query works.
"""
from __future__ import print_function

import re
import logging
from sqlalchemy.dialects.postgresql.psycopg2 import PGDialect_psycopg2
from sqlalchemy.dialects.postgresql.psycopg2 import PGCompiler_psycopg2
from sqlalchemy.sql import elements


logger = logging.getLogger('teiid')


class TeiidCompiler(PGCompiler_psycopg2):
    def visit_column(self, column, add_to_result_map=None,
                     include_table=True, **kwargs):
        name = orig_name = column.name
        if name is None:
            name = self._fallback_column_name(column)

        is_literal = column.is_literal
        if not is_literal and isinstance(name, elements._truncated_label):
            name = self._truncated_identifier("colident", name)

        if add_to_result_map is not None:
            add_to_result_map(
                name,
                orig_name,
                (column, name, column.key),
                column.type
            )

        if is_literal:
            name = self.escape_literal_column(name)
        else:
            name = self.preparer.quote(name)

        table = column.table
        if table is None or not include_table or not table.named_with_column:
            return name
        else:
            tablename = table.name
            if isinstance(tablename, elements._truncated_label):
                tablename = self._truncated_identifier("alias", tablename)

            return self.preparer.quote(tablename + "." + name)

    def _truncated_identifier(self, ident_class, name):
        if (ident_class, name) in self.truncated_names:
            return self.truncated_names[(ident_class, name)]

        anonname = name.apply_map(self.anon_map).replace(".", "_")

        if len(anonname) > self.label_length - 6:
            counter = self.truncated_names.get(ident_class, 1)
            truncname = anonname[0:max(self.label_length - 6, 0)] + \
                "_" + hex(counter)[2:]
            self.truncated_names[ident_class] = counter + 1
        else:
            truncname = anonname
        self.truncated_names[(ident_class, name)] = truncname
        return truncname


class TeiidDialect(PGDialect_psycopg2):
    statement_compiler = TeiidCompiler

    def __init__(self, *args, **kwargs):
        PGDialect_psycopg2.__init__(self, *args, **kwargs)
        self.supports_isolation_level = False

    def get_isolation_level(self, connection):
        return 'READ COMMITTED'

    def _get_server_version_info(self, connection):
        v = connection.execute("select version()").scalar()
        m = re.match(
            '.*(?:Teiid) '
            '(\d+)\.(\d+)(?:\.(\d+))?(?:\.\d+)?(?:devel)?',
            v)
        if not m:
            raise AssertionError(
                "Could not determine version from string '%s'" % v)
        return tuple([int(x) for x in m.group(1, 2, 3) if x is not None])
