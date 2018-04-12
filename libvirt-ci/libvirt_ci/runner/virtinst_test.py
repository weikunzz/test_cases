"""
Runner module for python-virtinst test framework
"""
import logging
import os
import re

from .. import runner
from .. import utils
from .. import coverage

LOGGER = logging.getLogger(__name__)


class VirtinstTestRunner(runner.RunnerBase):
    """
    Runner for python-virtinst test framework
    """
    repos = {
        "python-virtinst":
            'http://git.host.prod.eng.bos.redhat.com/git/python-virtinst.git rhel7',
    }
    error_pattern = r'(ERROR)(\s+)(.*)$'
    result_line_pattern = r'(ERROR)(\s+)(.*)$'

    def init(self):
        """
        Initialize test framework specific parameters. These parameters are
        retrieved only after framework is prepared.
        Steps before framework preparation like `init, replace, bootstrap`
        **CANNOT** access these parameters
        """
        self.working_dir = os.path.join(self.test_path,
                                        'python-virtinst')

    def init_coverage(self):
        """
        Test framework specific coverage initialization
        """
        cobertura_xml = None
        html_report_dir = None

        if os.environ.get('WORKSPACE'):
            if self.params.cobertura_xml:
                cobertura_xml = os.path.join(os.environ.get('WORKSPACE'),
                                             self.params.cobertura_xml)
            html_report_dir = os.path.join(os.environ.get('WORKSPACE'),
                                           'html_report')

        helper = os.path.join(self.working_dir, 'virtmanager-codecoverage')
        self.coverage = coverage.VirtinstCoverageHelper(
            'virt-install', '/.virtmanager_codecoverage/.virtmanager-coverage*',
            helper, cobertura_xml, output_dir=html_report_dir)

    # pylint: disable=no-self-use
    def list_tests(self):
        """
        Get all specific type tests in python-virtinst.
        """
        old_path = os.getcwd()
        try:
            os.chdir(self.working_dir)
            tests = []
            for path, _, files in os.walk('test_cases'):
                for file_name in files:
                    test = '.'.join(path.split('/')[1:] +
                                    [re.sub(r'\.tc$', '', file_name)])
                    tests.append(test)
            return tests
        finally:
            os.chdir(old_path)

    def run_test(self, test_name):
        """
        Run a single test
        """
        old_path = os.getcwd()
        try:
            os.chdir(self.working_dir)
            path = test_name.replace('.', '/') + '.tc'
            cmd = ('bash ./pyinst-test -t test_cases/%s' % path)
            return utils.run(cmd, timeout=int(self.params.timeout))
        finally:
            os.chdir(old_path)

    def parse_result(self, result):
        """
        Parse result into variables loggable.
        """
        lines = result.stderr.splitlines()
        status = 'ERROR'
        for line in lines:
            if line.startswith('PASS'):
                status = 'PASS'
            if line.startswith('FAIL'):
                status = 'FAIL'

        if status == 'ERROR':
            LOGGER.error("Can't find test results in:\n%s", result)

        for line in lines:
            if 'Log file:' in line:
                log_file = os.path.join(self.working_dir,
                                        line.split()[-1])

        LOGGER.debug('Log file found in "%s"', log_file)
        log_txt = ''
        try:
            with open(log_file) as log_fp:
                log_txt = log_fp.read()
        except (IOError, OSError) as detail:
            LOGGER.error("Unable to read log file %s:\n%s",
                         log_file, detail)
        return status, log_txt.splitlines()

    def update_report(self, test, status, result_line, duration, logs, _):
        class_name, test_name = test.split('.', 1)
        status, result_line = self._ignore_failures(
            test_name, status, result_line)
        self.report.update(test_name, class_name, status, '\n'.join(logs),
                           result_line, duration,
                           prefix=self.params.qemu_pkg)
