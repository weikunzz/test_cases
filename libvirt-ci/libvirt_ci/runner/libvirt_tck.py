"""
Runner module for libvirt-tck test framework
"""
import os
import re

from .. import runner
from .. import utils


class LibvirtTckRunner(runner.RunnerBase):
    """
    Runner class for libvirt-tck test framework
    """
    repos = {
        "libvirt-tck":
            'https://gitlab.cee.redhat.com/weizhan/libvirt-tck.git rhel7',
    }
    error_pattern = r'(not ok )(\d+ - )(.*)$'
    result_line_pattern = r'(not ok )(\d+ - )(.*)$'

    def init(self):
        """
        Test framework specific initialization.
        """
        self.working_dir = os.path.join(self.test_path,
                                        'libvirt-tck')
        self.required_packages += ['gmp-devel']

    def bootstrap(self):
        """
        Bootstrap this test framework.
        """
        utils.run_playbook('bootstrap_libvirt_tck', debug=True,
                           libvirt_tck_path=self.working_dir)

    def list_tests(self):
        """
        Get all specific type tests in libvirt-tck.
        """
        old_path = os.getcwd()
        try:
            os.chdir(self.working_dir)
            tests = []
            for path, _, files in os.walk('scripts'):
                for file_name in files:
                    if not file_name.endswith('.t'):
                        continue
                    test = '.'.join(path.split('/')[1:] +
                                    [re.sub(r'\.t$', '', file_name)])
                    tests.append(test)
            return tests
        finally:
            os.chdir(old_path)

    def run_test(self, test_name):
        """
        Run a single test
        """
        path = os.path.join(self.working_dir, 'scripts',
                            test_name.replace('.', '/') + '.t')
        cmd = ('libvirt-tck -v --testdir %s' % path)
        return utils.run(cmd, timeout=int(self.params.timeout))

    def parse_result(self, result):
        """
        Parse result into variables loggable.
        """
        lines = result.stdout.splitlines()
        status = 'ERROR'
        for line in lines:
            if line.startswith('Result: '):
                status = line.split()[-1]
        return status, lines
