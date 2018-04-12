"""
Runner module for libvirt unit test framework
"""
import logging
import os
import re

from .. import runner
from .. import utils

LOGGER = logging.getLogger(__name__)


class LibvirtUnitTestRunner(runner.RunnerBase):
    """
    Runner for libvirt unit test framework
    """
    repos = {
    }

    def init_framework_params(self):
        """
        Initialize test framework specific parameters. These parameters are
        retrieved only after framework is prepared.
        Steps before framework preparation like `init, replace, bootstrap`
        **CANNOT** access these parameters
        """
        self.working_dir = os.path.join(self.test_path, 'libvirt')

    def list_tests(self):
        """
        Get all specific type tests
        """
        return ['check', 'syntax-check']

    def bootstrap(self):
        """
        Bootstrap this test framework.
        """
        libvirt_path = os.path.join(self.test_path, 'libvirt')
        utils.run_playbook('bootstrap_libvirt_unit_test',
                           debug=True,
                           libvirt_path=libvirt_path)

    def run_test(self, test_name):
        """
        Run a single test
        """
        old_path = os.getcwd()
        os.environ['VIR_TEST_EXPENSIVE'] = '1'
        os.environ['VIR_TEST_DEBUG'] = '1'
        try:
            os.chdir(self.working_dir)

            cmd = 'make ' + test_name
            return utils.run(cmd, timeout=int(self.params.timeout))

        finally:
            os.chdir(old_path)

    def parse_result(self, result):
        """
        Parse result of libvirt unit test
        """
        if result.exit_code == 0:
            status = "PASS"
        else:
            status = "FAIL"

        return status, result.stdout.splitlines()

    def _get_single_test_log(self, test_name):
        """
        Get the test log with specific test name
        """
        test_log_path = os.path.join(self.working_dir, 'tests', '%s.log' % test_name)

        with open(test_log_path) as f:
            return f.read()

    def _get_single_test_result(self, test_name):
        """
        Get the test result with specific test name
        """
        test_result_path = os.path.join(self.working_dir, 'tests', '%s.trs' % test_name)
        with open(test_result_path) as f:
            result_txt = f.read()
        result_line = result_txt.splitlines()[0]
        match = re.match(r'^:test-result: (.+)$', result_line)
        if not match:
            raise ValueError('Cannot parse log result %s' % result_line)
        sub_status = match.group(1)
        return sub_status, result_line

    def _get_test_name(self, log_name):
        """
        Get the test name from the test log
        """
        match = re.match(r'^(.+)\.log$', log_name)
        if not match:
            raise ValueError('Cannot parse log file name %s' % log_name)
        return match.group(1)

    def update_report(self, test, status, result_line, duration, logs, _idx):
        if test == "check":
            old_path = os.getcwd()
            try:
                os.chdir(self.working_dir)

                logfiles = [file_name for file_name in os.listdir('tests') if file_name.endswith('log')]
                LOGGER.info("Find %d test log in tests", len(logfiles))
                if len(logfiles) == 0 and status == 'FAIL':
                    # this means make check failed in compile phase
                    self.report.update("tests_compile", "libvirt_unit_test", status, "\n".join(logs), "", duration)
                    return

                fake_duration = duration / (len(logfiles) - 1)
                for log_name in logfiles:
                    if log_name == "test-suite.log":
                        # Ignore test-suite since it is not a test
                        continue

                    test_name = self._get_test_name(log_name)
                    log_txt = self._get_single_test_log(test_name)
                    sub_status, result_line = self._get_single_test_result(test_name)

                    self.report.update(test_name, "libvirt_unit_test", sub_status, log_txt,
                                       result_line, fake_duration)

            finally:
                os.chdir(old_path)

        else:
            self.report.update(test, "basic-check", status, "\n".join(logs), "", duration)
