import logging
import json
import os


from . import package


class CIMessageParseError(Exception):
    pass


class CIMessage(object):
    def __init__(self, string):
        """
        Init a empty CI message skeleton

        Currently we only extract infomation we needed
        """
        # Raw message string
        self._raw = string

        self.brew_taskid = None
        self.brew_buildid = None
        self.tag = None
        self.arches = []
        self.rpms = {}
        self.rpm_string = None
        self.nvr = None
        self.nvrs = None

        self.owner = None
        self.version = None
        self.release = None
        self.pkgname = None
        self.request = None
        self.scratch = False

        try:
            # Parsed ci message data
            self._data = json.loads(self._raw)
        # pylint: disable=broad-except
        except Exception as error:
            logging.error("Failed parsing CI Message.")
            logging.exception(error)
            self._data = {}

        if 'package_name' in self._data.get('build', {}):
            logging.info("It's a build CI Message.")
            self.owner = self._data['build']['owner_name']
            self.nvr = self._data['build']['nvr']
            self.nvrs = [self.nvr]
            self.tag = self._data['tag']['name']
            self.brew_taskid = str(self._data['build']['task_id'])
            self.brew_buildid = str(self._data['build']['id'])
            self.pkgname = self._data['build']['package_name']
            self.version = self._data['build']['version']
            self.release = self._data['build']['release']

        elif "info" in self._data.keys():
            logging.info("It's a brew CI Message.")
            self.owner = self._data['info']['owner']

            # Retrive accurate NVR from rpm names, form a long list with no duplication
            self.nvrs = list(set(sum([
                [package.Package.from_str(rpm).nvr for rpm in rpms]
                for _, rpms in self._data['rpms'].items()
            ], [])))

            # The shrotest NVR of all package which may stand for them
            self.nvr = min(self.nvrs, key=len)

            if not all(nvr.startswith(self.nvr) for nvr in self.nvrs):
                logging.info("CI Messsage constains nvr for different pacakges, "
                             "parsing might be inaccurate.")
            self.brew_taskid = str(self._data['info']['id'])

            _package = package.Package.from_nvr(self.nvr)
            self.rpms = self._data['rpms']
            self.pkgname = _package.name
            self.version = _package.version
            self.release = _package.release

            self.request = self._data['info'].get('request', [{}])
            self.scratch = self.request[-1].get("scratch", False)

        elif "bkr_info" in self._data.keys():
            logging.info("It's a tree CI Message, ignored")

        else:
            logging.error("Unknown CI Message format.")

    @classmethod
    def current(cls, params=None):
        """
        Get CI Message for current test run
        Return None if no message can be founded

        pass params then this class can retrive ci message from ci params
        """

        ci_message_string = params.message or os.environ.get('CI_MESSAGE')

        if not ci_message_string:
            return None

        try:
            return cls(ci_message_string)
        except CIMessageParseError:
            return None
