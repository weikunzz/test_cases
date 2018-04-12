"""
Runner module for libvirt-test-API test framework
"""
import logging
import os
import re
import string
import yaml
import commands
from datetime import datetime

from .. import config
from .. import runner
from .. import utils

LOGGER = logging.getLogger(__name__)


class TestApiRunner(runner.RunnerBase):
    """
    Runner for libvirt-test-API test framework
    """
    repos = {
        "test-api":
            'http://git.host.prod.eng.bos.redhat.com/git/libvirt-test-API.git rhel7',
    }

    def init(self):
        """
        Test framework specific initialization.
        """
        self.working_dir = os.path.join(self.test_path, 'test-api')
        self.params.img_path = '/var/lib/libvirt/images/libvirt-ci.qcow2'

    # pylint: disable=no-self-use
    def list_tests(self):
        """
        Get all specific type tests in libvirt-test-API.
        """
        old_path = os.getcwd()
        try:
            os.chdir(self.working_dir)
            return [file_name for file_name in os.listdir('templates')
                    if file_name.endswith('conf')]
        finally:
            os.chdir(old_path)

    def run_test(self, _):
        """
        Run a single test
        """
        cmd = 'python -u ./libvirt-test-api'
        old_path = os.getcwd()
        try:
            os.chdir(self.working_dir)
            return utils.run(cmd, timeout=int(self.params.timeout))
        finally:
            os.chdir(old_path)

    def parse_result(self, result):
        """
        Parse result into variables loggable.
        """
        status = 'INVALID'
        lines = result.stdout.splitlines()
        for line in lines:
            if 'Result:' in line:
                if 'OK' in line.split()[-1]:
                    status = 'PASS'
                else:
                    status = 'FAIL'
        if status == 'INVALID':
            LOGGER.error("Can't find result in result output:")
            for line in lines:
                LOGGER.info(line)
        lines = result.stderr.splitlines()
        log_file = None
        for line in lines:
            if 'Log File:' in line:
                log_file = os.path.join(self.working_dir, line.split()[-1])

        if log_file:
            LOGGER.debug('Log file found in "%s"', log_file)
        else:
            LOGGER.error('Log file not found in output:\n%s', line)
        log_txt = ''
        try:
            with open(log_file) as log_fp:
                log_txt = log_fp.read()
        except (IOError, OSError) as detail:
            LOGGER.error("Unable to read log file %s:\n%s",
                         log_file, detail)
        return status, log_txt.splitlines()

    def prepare_test(self, test_name):
        """
        Action to perform before a test case
        """
        # pylint: disable=unused-variable
        test = test_name
        params_path = os.path.join(config.PATH, 'test_api_params.yaml')
        with open(params_path) as param_fp:
            all_params = yaml.load(param_fp)

        params = all_params['defaults']
        for override in all_params['overrides']:
            # pylint: disable=unused-variable,eval-used
            # Prepare variables for eval
            info = self  # noqa
            if eval(override['when']):
                for key, value in override.items():
                    if key != 'when':
                        params[key] = value

                    caselist = ['acceptance_storage_logical', 'acceptance_snapshot_rhev_specific_iscsi']
                    if any(i for i in caselist if i in value):
                        cmd = "iscsiadm -m session -P 3 |grep 'Attached scsi disk '|awk '{{print $4}}'"
                        (status, output) = commands.getstatusoutput(cmd)
                        value = '/dev/' + output + '1'
                        if not status and output:
                            params['SOURCEPATH'] = value

                    caselist = ['storage_disk', 'storage_disk_build_on_active', 'domain_basic_rhev']
                    if any(i for i in caselist if i in value):
                        cmd = "iscsiadm -m session -P 3 |grep 'Attached scsi disk '|awk '{{print $4}}'"
                        (status, output) = commands.getstatusoutput(cmd)
                        value = '/dev/' + output
                        if not status and output:
                            params['SOURCEPATH'] = value

        # Substitute $ENV_NAME or ${ENV_NAME} to ENV_VALUE
        for key, value in params.items():
            params[key] = string.Template(value).safe_substitute(os.environ)

        case_str = []
        template_path = os.path.join(self.working_dir, 'templates', test_name)
        with open(template_path) as template_fp:
            for line in template_fp.read().splitlines():
                result = re.findall(r'#([_A-Z]+)#', line)
                if result:
                    for placeholder in result:
                        line = re.sub(
                            '#%s#' % placeholder,
                            params[placeholder], line)
                case_str.append(line)

        case_conf_path = os.path.join(self.working_dir, 'case.conf')
        with open(case_conf_path, 'w') as conf_fp:
            conf_fp.write('\n'.join(case_str))

    # pylint:disable=arguments-differ
    def update_report(self, test, status, result_line, duration, logs, idx):
        steps = []
        step = {'log': '', 'error': ''}
        log_lines = []
        current_log = ''
        logged_time = 0
        for line in logs:
            step['log'] += line + '\n'

            head_match = re.findall(
                r'^-+\s+(\S+)\s+-+$', line)
            tail_match = re.findall(
                r'^-+\s+(\S+)\s+(\S+)\s+-+$', line)
            log_match = re.findall(
                r'^\[(\d{1,2}:\d{1,2}:\d{1,2})\] \S+ \S+\s+(.*)$', line)
            if head_match:
                step['log_start'] = None
                step['log_end'] = None
                step['name'] = head_match[0]
            elif tail_match:
                step['status'] = tail_match[0][1].upper()
                step['log_start'] = datetime.strptime(step['log_start'] or '00:00:00', '%H:%M:%S')
                step['log_end'] = datetime.strptime(step['log_end'] or '00:00:00', '%H:%M:%S')
                step['log_duration'] = (step['log_end'] - step['log_start']).seconds
                logged_time += step['log_duration']
                steps.append(step)
                if current_log:
                    log_lines.append(current_log)
                current_log = ''
                errors = [line for line in log_lines if 'ERROR' in line]
                step['error'] = ''.join(errors)
                step = {'log': '', 'error': ''}
                log_lines = []
            elif log_match:
                if not step['log_start']:
                    step['log_start'] = log_match[0][0]
                step['log_end'] = log_match[0][0]
                if current_log:
                    log_lines.append(current_log)
                current_log = line + '\n'
            else:
                current_log += line + '\n'
        for step_idx, step in enumerate(steps):
            class_name = test
            if class_name.endswith('.conf'):
                class_name = class_name[:-5]
            step['status'], step['error'] = self._ignore_failures(
                class_name, step['status'], step['error'])
            self.report.update(step['name'],
                               class_name,
                               step['status'],
                               step['log'],
                               step['error'],
                               (duration - logged_time) / len(steps) + step['log_duration'],
                               test_idx=step_idx,
                               class_idx=idx,
                               prefix=self.params.qemu_pkg)

    def bootstrap(self):
        """
        Bootstrap this test framework.
        """
        if "migration" in os.environ.get('JOB_NAME'):
            resource = os.environ.get('RESOURCE_HOSTNAME')
            worker = os.environ.get('WORKER_HOSTNAME')
            hosts = {"worker": [worker], "resource": [resource]}
            utils.run_playbook('bootstrap_test_api_migration', hosts=hosts,
                               private_key='libvirt-jenkins',
                               debug=True)
