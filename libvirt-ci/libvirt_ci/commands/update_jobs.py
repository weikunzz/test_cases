"""
Generate JJB job YAML file and update the new job to Jenkins server
"""

import logging
import fnmatch
import os
import tempfile

import yaml

from libvirt_ci import utils

from libvirt_ci.jenkins_job import JobGenerator
from libvirt_ci.data import RESOURCE_PATH
from libvirt_ci.config import CONFIG_PATH

LOGGER = logging.getLogger(__name__)

REQUIREMENTS = {
    "jenkins-job-builder": {},
    "jenkins-ci-sidekick": {
        "index-url":
            "http://ci-ops-jenkins-update-site.rhev-ci-vms.eng.rdu2."
            "redhat.com/packages/simple",
        "trusted-host":
            "ci-ops-jenkins-update-site.rhev-ci-vms.eng.rdu2.redhat.com",
    }
}


def run(params):
    """
    Main function to generate Jenkins jobs
    """
    jobs_config_file = os.path.join(CONFIG_PATH, 'jobs.yaml')

    jenkins_config_file = os.path.join(RESOURCE_PATH, 'jobs', 'config')

    jobs_path = os.path.join(RESOURCE_PATH, 'jobs')

    jobs = list(JobGenerator(jobs_config_file).jobs())

    if params.jobs:
        jobs = [job for job in jobs if fnmatch.fnmatch(job.name, params.jobs)]
    yaml_obj = [job.get_object() for job in jobs]
    if params.config:
        yaml_file = open(params.config, 'w')
        yaml_path = params.config
    else:
        yaml_file = tempfile.NamedTemporaryFile(
            prefix='libvirt_ci-jobs-', suffix='.yaml',
            dir=jobs_path, delete=False)
        yaml_path = yaml_file.name
    try:
        yaml.dump(yaml_obj, stream=yaml_file, indent=4,
                  default_flow_style=False)
        yaml_file.close()

        if params.only_config:
            return

        cmd = "jenkins-jobs"
        cmd += " --conf %s" % jenkins_config_file
        if params.test:
            cmd += " test"
        else:
            cmd += " update"

        cmd += " -r %s" % jobs_path
        if params.jobs:
            cmd += " %s" % params.jobs
        # Ignore standard output of jenkins-job-builder
        cmd += " > /dev/null"

        utils.run(cmd, debug=True, ignore_fail=False, timeout=3600)
    finally:
        if params.only_config:
            LOGGER.info('Keep job file %s', yaml_path)
        else:
            try:
                LOGGER.info('Removing job file %s', yaml_path)
                os.remove(yaml_path)
            except (OSError, IOError) as details:
                LOGGER.warning('Failed to remove job file %s: %s',
                               yaml_file.name, details)


def parse(parser):
    """
    Parse arguments for generate Jenkins jobs
    """
    parser.add_argument(
        '--only-config', dest='only_config', action='store_true',
        help='If set, Just generate job config file. Do not run '
        'jenkins-jobs-builder')
    parser.add_argument(
        '--config', dest='config', action='store',
        help='Specify a custom config file instead using random generated '
        'config file name')
    parser.add_argument(
        '--jobs', dest='jobs', action='store',
        help='Update/Test only on specific jobs. Wildcard acceptable')
    parser.add_argument(
        '--test', dest='test', action='store_true',
        help='If set, Just dry run jenkins-jobs to make sure config works')
