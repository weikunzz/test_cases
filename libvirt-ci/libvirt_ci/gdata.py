"""
Use Google spreadsheet as data storage
"""
import os
import logging
import gspread
import oauth2client.service_account

from . import config
from . import utils
from . import metadata

LOGGER = logging.getLogger(__name__)


class GData(metadata.MetadataBackendInterface):
    """
    Class for using Google spreadsheet as data storage
    """
    def __init__(self, table,
                 key='1sJ6PlgmJjwrSCpqK332S0uwiWr4EcRwO74gN0YeI67g'):
        utils.check_set_gservice_broker()
        self.table = table
        self.worksheet = None
        self.gcredential = None
        self.document = None
        self.key = key
        self.authorize()

    def authorize(self):
        """
        Authorize to Google spreadsheet
        """
        scope = ['https://spreadsheets.google.com/feeds']
        json_key_path = os.path.join(config.PATH, 'google_service_key.json')
        credentials = oauth2client.service_account.ServiceAccountCredentials.from_json_keyfile_name(
            json_key_path, scope)
        self.gcredential = gspread.authorize(credentials)
        self.document = self.gcredential.open_by_key(self.key)
        self.worksheet = self.document.worksheet(self.table)

    def _worksheet_action(self, action, *args):
        """
        Wrap gspread worksheet actions to make sure no authorization issue
        """
        max_retry = 5
        for _ in range(max_retry):
            try:
                func = getattr(self.worksheet, action)
                return func(*args)
            except gspread.exceptions.RequestError as details:
                LOGGER.warning("Error when '%s' google sheet '%s': %s",
                               action, self.table, details)
                utils.check_set_gservice_broker()
                self.authorize()
        # pylint: disable=raising-bad-type
        raise details

    def _get_all_values(self):
        """
        Get all values from worksheet
        """
        return self._worksheet_action('get_all_values')

    def _update_cell(self, *args):
        """
        Update a cell in spreadsheet
        """
        return self._worksheet_action('update_cell', *args)

    def _update_cells(self, *args):
        """
        Update a list of cells in spreadsheet
        """
        return self._worksheet_action('update_cells', *args)

    def _row_values(self, *args):
        """
        Get the values of cells in a row
        """
        return self._worksheet_action('row_values', *args)

    def _range(self, *args):
        """
        Get the cells in specified range
        """
        return self._worksheet_action('range', *args)

    def _cell(self, *args):
        """
        Get the cells object
        """
        return self._worksheet_action('cell', *args)

    def fetch(self):
        """
        Fetch data from spreadsheet
        """
        data = self._get_all_values()
        return metadata.DataTable(data)

    def push(self, data):
        """
        Push data to spreadsheet
        """
        cell_list = []
        add, _ = data.diff()
        keys = data.getkeys()
        for info in add.list():
            cells = self._range(info['row'] + 1, 1,
                                info['row'] + 1, len(keys))
            for i_key, key in enumerate(keys):
                if not info.get(key, ''):
                    cells[i_key].value = ''
                else:
                    cells[i_key].value = info.get(key)
            cell_list.extend(cells)
        self._update_cells(cell_list)
