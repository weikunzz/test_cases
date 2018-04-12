"""
Runner module for cimtest test framework
"""
import logging
import os
import re

from .. import runner
from .. import utils

LOGGER = logging.getLogger(__name__)


class CimtestRunner(runner.RunnerBase):
    """
    Runner class for cimtest test framework
    """
    repos = {
        "cimtest":
            'git://libvirt.org/cimtest.git master',
    }
    error_pattern = r'(ERROR)()(.*)$'
    result_line_pattern = r'(ERROR)()(.*)$'

    def init(self):
        """
        Test framework specific initialization.
        """
        self.working_dir = os.path.join(self.test_path,
                                        'cimtest')
        self.params.img_path = '/var/lib/libvirt/images/default-kvm-dimage'

    def bootstrap(self):
        """
        Bootstrap this test framework.
        """
        utils.run_playbook('bootstrap_cimtest', debug=True)

    def list_tests(self):
        """
        Get all specific type tests in cimtest.
        """
        old_path = os.getcwd()
        try:
            os.chdir(self.working_dir)
            tests = []
            for path, _, files in os.walk('suites/libvirt-cim/cimtest'):
                for file_name in files:
                    # file name should be started with digits
                    if re.match(r'\d+_.*', file_name):
                        test = '.'.join(path.split('/')[3:] +
                                        [re.sub(r'\.py$', '', file_name)])
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
            group, test = test_name.split('.')
            cmd = 'CIM_NS=root/virt CIM_USER=pegasus CIM_PASS=redhat'
            cmd += ' ./runtests libvirt-cim -v KVM localhost'
            cmd += ' -g %s -t %s.py' % (group, test)
            return utils.run(cmd, timeout=int(self.params.timeout))
        finally:
            os.chdir(old_path)

    def parse_result(self, result):
        """
        Parse result into variables loggable.
        """
        lines = result.stdout.splitlines()
        status = 'INVALID'
        for line in lines:
            match = re.findall(r'^\S+ - \S+.py: (.*)', line)
            if match:
                status_str = match[0]
                if 'PASS' in status_str:
                    status = 'PASS'
                elif 'FAIL' in status_str:
                    status = 'FAIL'
                elif 'SKIP' in status_str:
                    status = 'SKIP'
                break

        log_file = os.path.join(self.working_dir,
                                'suites/libvirt-cim/run_report.txt')
        try:
            with open(log_file) as log_fp:
                log_txt = log_fp.read()
        except (IOError, OSError) as detail:
            LOGGER.error("Unable to read log file %s:\n%s",
                         log_file, detail)
        return status, log_txt.splitlines()
