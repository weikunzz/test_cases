"""
Coverage helper
"""
import logging
import os
import abc

import requests

from . import utils
from . import package
from . import env

LOGGER = logging.getLogger(__name__)

REQUIREMENTS = [
    "coverage",
]


class CoverageHelperInterface(object):
    """
    Basic class of coverage interface
    """
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def prepare(self):
        """
        Helper interface to prepare the coverage env
        """
        raise NotImplementedError('prepare')

    @abc.abstractmethod
    def clean_up(self):
        """
        Helper interface to clean up the coverage env
        """
        raise NotImplementedError('clean_up')

    @abc.abstractmethod
    def gen_report(self):
        """
        Helper interface to generate and upload coverage report
        """
        raise NotImplementedError('gen_report')


class VirtcovCoverageHelper(CoverageHelperInterface):
    """
    Libvirt virtcov coverage helper class
    """
    def __init__(self, coverage_xml=None, lcov_tracefile='/tmp/lcov.tracefile',
                 coverage_pool_url='http://10.66.4.127:8000/upload/coveragefile/',
                 output_dir='/tmp/html_report'):
        self.tracefile = lcov_tracefile
        self.coverage_xml = coverage_xml
        self.coverage_pool_url = coverage_pool_url
        self.output_dir = output_dir

    def prepare(self):
        if not utils.which('virtcov'):
            raise Exception('Cannot find virtcov. Please make sure virtcov '
                            'libvirt package is installed')
        env.Env.install_pkgs('lcov')
        # TODO: use pip env handler
        utils.run('pip install gcovr', debug=True)

        utils.run('virtcov -s', debug=True)

    def clean_up(self):
        utils.run('virtcov -c', debug=True)

    def _gen_test_name(self):
        if os.environ.get('JOB_NAME') and os.environ.get('BUILD_ID'):
            return '%s-%s' % (os.environ.get('JOB_NAME'), os.environ.get('BUILD_ID'))
        else:
            LOGGER.info('No Job name or build id, will use a common name: Auto-test-coverage')
            return 'Auto-test-coverage'

    def _gen_lcov_report(self, work_dir, test_name):
        cmd_fmt = 'lcov --capture --directory "%s" --output-file "%s" --test-name "%s"'
        cmd = cmd_fmt % (work_dir, self.tracefile, test_name)
        utils.run(cmd, debug=True)

    def _gen_gcovr_report(self, work_dir):
        cmd = 'gcovr -r %s --xml -o %s' % (work_dir, self.coverage_xml)
        utils.run(cmd, debug=True)

    def _gen_html_report(self):
        cmd = 'genhtml %s --output-directory %s' % (self.tracefile, self.output_dir)
        utils.run(cmd, debug=True)

    def _get_work_dir(self, version):
        # Devel build coverage package in /builddir/build/ not in /mnt/coverage/
        # This is a work around to find the coverage work dir
        work_dir = '/mnt/coverage/BUILD/libvirt-%s/' % version
        if os.path.isdir(work_dir):
            return work_dir
        work_dir = '/builddir/build/BUILD/libvirt-%s/' % version
        if os.path.isdir(work_dir):
            return work_dir

        raise Exception('Cannot find an available virtcov work dir')

    def gen_report(self):
        libvirt_rpm_info = package.Package.from_name('libvirt')
        # check if there is a virtlogd
        if libvirt_rpm_info.version >= '1.3.0':
            utils.restart_service(['libvirt', 'virtlogd'])
        else:
            utils.restart_service('libvirt')

        work_dir = self._get_work_dir(libvirt_rpm_info.version)
        test_name = self._gen_test_name()

        # Generate xml and lcov tracefile report
        self._gen_lcov_report(work_dir, test_name)

        if self.coverage_xml:
            self._gen_gcovr_report(work_dir)
            LOGGER.info('Put coverage xml on %s', self.coverage_xml)

        # upload tracefile
        self.upload_tracefile(test_name, 'jenkins', str(libvirt_rpm_info))

        if self.output_dir:
            # Generate html report
            self._gen_html_report()
            LOGGER.info('Generate coverage html report on %s', self.output_dir)

    def upload_tracefile(self, test_name, user_name, version):
        datas = {'name': test_name,
                 'user_name': user_name,
                 'version': version}
        files = {'coveragefile': open(self.tracefile, 'rb')}
        ret = requests.post(self.coverage_pool_url, files=files, data=datas)
        ret.raise_for_status()
        LOGGER.info("Upload tracefile to %s: status_code=%d reason=%s",
                    self.coverage_pool_url, ret.status_code, ret.reason)


class PythonCoverageHelper(CoverageHelperInterface):
    """
    Python coverage helper class
    """
    def __init__(self, name, tracefile_path, coverage_xml=None,
                 coverage_pool_url='http://10.66.4.127:8000/upload/coveragefile/',
                 output_dir='/tmp/html_report'):
        self.name = name
        self.tracefile_path = tracefile_path
        self.coverage_xml = coverage_xml
        self.coverage_pool_url = coverage_pool_url
        self.output_dir = output_dir
        self.tracefile = None

    def prepare(self):
        pass

    def clean_up(self):
        pass

    def _gen_html_report(self):
        # TODO: Need update to support run remotely
        cmd = 'coverage html -d %s' % self.output_dir
        utils.run(cmd, debug=True)

    def _gen_xml_report(self):
        cmd = 'coverage xml -o %s' % self.coverage_xml
        utils.run(cmd, debug=True)

    def _gen_test_name(self):
        if os.environ.get('JOB_NAME') and os.environ.get('BUILD_ID'):
            return '%s-%s' % (os.environ.get('JOB_NAME'), os.environ.get('BUILD_ID'))
        else:
            LOGGER.info('No Job name or build id, will use a common name: Auto-test-coverage')
            return 'Auto-test-coverage'

    def gen_report(self):
        rpm_info = package.Package.from_name(self.name)

        test_name = self._gen_test_name()

        cmd = 'coverage combine %s' % self.tracefile_path
        utils.run(cmd, debug=True)
        self.tracefile = '.coverage'

        if self.coverage_xml:
            self._gen_xml_report()
            LOGGER.info('Put coverage xml on %s', self.coverage_xml)

        # upload tracefile
        self.upload_tracefile(test_name, 'jenkins', str(rpm_info))

        if self.output_dir:
            # Generate html report
            self._gen_html_report()
            LOGGER.info('Generate coverage html report on %s', self.output_dir)

    def upload_tracefile(self, test_name, user_name, version):
        datas = {'name': test_name,
                 'user_name': user_name,
                 'version': version}
        files = {'coveragefile': open(self.tracefile, 'rb')}
        ret = requests.post(self.coverage_pool_url, files=files, data=datas)
        ret.raise_for_status()
        LOGGER.info("Upload tracefile to %s: status_code=%d reason=%s",
                    self.coverage_pool_url, ret.status_code, ret.reason)


# NOTE: This is a temporary workaround since env module need to change.
#       We can use general PythonCoverageHelper after env module is done.
class VirtinstCoverageHelper(PythonCoverageHelper):
    """
    Python virtinstall coverage helper class
    """
    def __init__(self, name, tracefile_path, helper_path, coverage_xml=None,
                 coverage_pool_url='http://10.66.4.127:8000/upload/coveragefile/',
                 output_dir='/tmp/html_report'):
        super(VirtinstCoverageHelper, self).__init__(name, tracefile_path, coverage_xml, coverage_pool_url, output_dir)
        self.helper_path = helper_path

    def prepare(self):
        if not os.path.exists(self.helper_path):
            raise Exception('Cannot find virtmanager-codecoverage'
                            ' in the %s' % self.helper_path)

        LOGGER.info('Use virtmanager-codecoverage to prepare coverage env')
        utils.run('sh %s --setup-all' % self.helper_path, debug=True)
        utils.run('source /etc/bashrc', debug=True)
