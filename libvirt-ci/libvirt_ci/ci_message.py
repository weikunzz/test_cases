import logging
import json
import os

from libvirt_ci import utils
from libvirt_ci import package

LOGGER = logging.getLogger(__name__)


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
            LOGGER.error("Failed parsing CI Message.")
            LOGGER.exception(error)
            self._data = {}

        if 'package_name' in self._data.get('build', {}):
            LOGGER.info("It's a build CI Message.")
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
            LOGGER.info("It's a brew CI Message.")
            self.owner = self._data['info']['owner']

            # Retrive accurate NVR from rpm names, form a long list with no duplication
            self.nvrs = list(set(sum([
                [package.Package.from_str(rpm).nvr for rpm in rpms]
                for _, rpms in self._data['rpms'].items()
            ], [])))

            # The shrotest NVR of all package which may stand for them
            self.nvr = min(self.nvrs, key=len)

            if not all(nvr.startswith(self.nvr) for nvr in self.nvrs):
                LOGGER.info("CI Messsage constains nvr for different pacakges, "
                            "parsing might be inaccurate.")
            self.brew_taskid = str(self._data['info']['id'])

            _package = package.Package.from_nvr(self.nvr)
            self.rpms = self._data['rpms']
            self.pkgname = _package.name
            self.version = _package.version
            self.release = _package.release

            self.brew_buildid = self._data['info'].get('id', 'null')
            self.request = self._data['info'].get('request', [{}])
            self.scratch = self.request[-1].get("scratch", False)

        elif "bkr_info" in self._data.keys():
            LOGGER.info("It's a tree CI Message, ignored")

        else:
            LOGGER.error("Unknown CI Message format.")

    def get_target_packages(self, only=None):
        """
        Return a list of target packages, in NVR format
        """
        if self.scratch:
            # Accelerate lookup for scratch build
            # Return directly without detectin if pacakge exists
            # So caller should not fail for non exist pacakge
            arch = utils.get_arch()
            if self.rpms and arch in self.rpms.keys():
                return [p.rstrip("%s.rpm" % arch) for p in self.rpms[arch]
                        if not only or p.startswith(only)]
            else:
                LOGGER.error("Malformed scratch build message.")
        else:
            # Try to find if there is a virtcov build
            ret = []
            for nvr in self.nvrs:
                try:
                    pkg = package.Package.find_one_by_nvr(nvr, virtcov=True)
                    if not only or pkg.nvr.startswith(only):
                        ret.append(pkg.nvr)
                except package.PackageNotExistsError:
                    pass
            return ret

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
