"""
Classes for job generation
"""
from __future__ import absolute_import

import logging
import copy
import yaml

LOGGER = logging.getLogger(__name__)


def _literal_presenter(dumper, data):
    style = '"'
    if '\n' in data:
        style = '|'
    elif len(data) > 70:
        style = '>'
    return dumper.represent_scalar('tag:yaml.org,2002:str', data,
                                   style=style)


def _include_raw_presenter(dumper, data):
    if isinstance(data.value, (str, unicode)):
        return dumper.represent_scalar(u'!include-raw:', data.value)
    if isinstance(data.value, (tuple, list)):
        return dumper.represent_sequence(u'!include-raw:', data.value)


def _include_raw_constructor(loader, node):
    if isinstance(node, yaml.nodes.ScalarNode):
        value = loader.construct_scalar(node)
    elif isinstance(node, yaml.nodes.SequenceNode):
        value = loader.construct_sequence(node)
    return _IncludeRaw(value)


def _extend_constructor(loader, node):
    if isinstance(node, yaml.nodes.ScalarNode):
        value = [loader.construct_scalar(node)]
    elif isinstance(node, yaml.nodes.SequenceNode):
        value = loader.construct_sequence(node)
    return _Extend(value)


class _Literal(unicode):
    pass


# pylint: disable=too-few-public-methods
class _IncludeRaw(object):
    def __init__(self, value):
        self.value = value


class _Extend(object):
    def __init__(self, value):
        self.value = value


yaml.add_representer(_Literal, _literal_presenter)
yaml.add_representer(_IncludeRaw, _include_raw_presenter)
yaml.add_constructor(u'!include-raw:', _include_raw_constructor)
yaml.add_constructor(u'!extend', _extend_constructor)


class JobError(Exception):
    """
    Exception class for job module.
    """
    pass


class JobExclusionError(JobError):
    """
    Exception class for job module indicate a job should be excluded.
    """
    pass


# pylint: disable=too-many-instance-attributes
class Job(object):
    """
    A jenkins-job-builder job YAML configuration.
    """
    def __init__(self, arch, product, version, *identifiers):
        """
        Initialize a Test Job object.

        :param arch: CPU arch of the job. Example: x86_64, ppc64le
        :param product: product name of the job. Example: fedora, rhel
        :param version: product version of the job. Example: 6.8, 23
        :param identifiers: A list of strings identifies this test job.
               The first entry should be test component name like 'libvirt' or 'v2v'.
               The second entry should be test type like 'acceptance' or 'function'.
               The entries from third will be optional and contains
               custom identifier of the test job.
        """
        if len(identifiers) == 1:
            identifiers = identifiers + ('all', )
        self.arch = arch
        self.version = version
        self.product = product

        # Identifiers for what is being tested, eg. libvirt.acceptance.general
        self.test = '.'.join(identifiers)
        self.component = identifiers[0]
        self.test_type = identifiers[1]
        self.test_suffixes = identifiers[2:]
        self.test_suffix = '-'.join(self.test_suffixes)
        # Helper for JJB job naming cause JJB can't perform logic operation
        self.test_type_n_suffix = '-'.join(identifiers[1:])
        self.name = '-'.join((
            self.component,  # Put component on the beginning
            self.product, self.version, self.arch,
            self.test_type) + self.test_suffixes)
        self.project = {}
        try:
            self.major, self.minor = [
                int(n) for n in self.version.split('.')]
        except ValueError:
            self.major, self.minor = int(self.version), 0

        # Expose variables for JJB
        # JJB use 'name' as job's name, Jenkis will set a env variable JOB_NAME with its value
        self.set('name', self.name)
        self.set('component', self.component)
        self.set('product', self.product)
        self.set('version', self.version)
        self.set('arch', arch)
        self.set('test-name', self.test)
        self.set('test-type', self.test_type)
        self.set('test-suffix', self.test_suffix)
        self.set('job-suffix', self.test_type_n_suffix)

        self._obj = {'project': self.project}

    def set(self, key, value):
        """
        Set a key value pair for JJB project dictionary.
        """
        if isinstance(value, (str, unicode)):
            value = _Literal(value)
        self.project[key] = value

    def get(self, key):
        """
        Get a key value pair for JJB project dictionary.
        """
        return self.project.get(key)

    def get_object(self):
        """
        Get the dictionary containing the detail information of the job.
        """
        return self._obj

    def evaluate(self, eval_str):
        """
        Evaluate a python expression and return its value.
        """
        # pylint: disable=eval-used,unused-variable
        # Expose variables for yaml eval
        arch = self.arch  # noqa
        component = self.component  # noqa

        test = self.test  # noqa
        test_type = self.test_type  # noqa
        test_suffix = self.test_suffix  # noqa

        major = self.major  # noqa
        minor = self.minor  # noqa
        version = self.version  # noqa
        product = self.product  # noqa

        return eval(eval_str)

    def __str__(self):
        return yaml.dump(
            self._obj, indent=4,
            default_flow_style=False,
        )


class JobGenerator(object):
    """
    Generator class to parse a custom YAML config file and generate
    jenkins-job-builder compatible YAML files.
    """
    def __init__(self, matrix_path, level=None, archs=None, products=None):
        def _expand_test_jobs(tests, cur_test, tests_hierachy, level=None):
            next_level = None if level is None else level - 1
            if level == 0:
                if len(cur_test) != 0:
                    tests.append(tuple(cur_test))
                return
            if isinstance(tests_hierachy, dict):
                for key, value in tests_hierachy.items():
                    cur_test.append(key)
                    _expand_test_jobs(tests, cur_test, value, next_level)
                    cur_test.pop()
            elif isinstance(tests_hierachy, (list, tuple)):
                for item in tests_hierachy:
                    _expand_test_jobs(tests, cur_test, item, level)
            elif isinstance(tests_hierachy, (str, unicode)):
                cur_test.append(tests_hierachy)
                tests.append(tuple(cur_test))
                cur_test.pop()
            else:
                raise Exception("Unknown type: '%s' %s" %
                                (type(tests_hierachy), tests_hierachy))

        with open(matrix_path) as matrix_file:
            matrix = yaml.load(matrix_file)

        self._archs = archs
        self._products = products
        if not self._archs:
            self._archs = matrix['archs']
        if not self._products:
            self._products = []
            for key, value in matrix['products'].items():
                for item in value:
                    self._products.append((key, item))

        self._test_jobs = []
        _expand_test_jobs(self._test_jobs, [], matrix['jobs'], level)
        for test_identifiers in self._test_jobs:
            if len(test_identifiers) < 2 and len(test_identifiers) < level:
                raise JobError("At lease two levels(component:type) are "
                               "needed for a test job. Got %s." % test_identifiers)
        self.rules = matrix['rules']

    # Need to solve this warning
    # pylint: disable=too-many-statements
    def _generate_job(self, arch, product, version, test_identifiers):
        """
        Generate a YAML job config by parameters.
        """
        # Need to solve this warning
        # pylint: disable=too-many-branches
        def _process_key_value(job, rule, key, value):
            """
            Update job configuration according to key, value pair.
            Raise a JobExclusionError if the job should be excluded.
            """

            if key == 'when':
                return

            if key == 'exclude':
                excludes = rule['exclude']
                if isinstance(excludes, (str, unicode)):
                    excludes = [excludes]
                for exclude in excludes:
                    if job.evaluate(exclude):
                        raise JobExclusionError("Job should be excluded.")
                return

            if key in ['assignee', 'watchers']:
                if key == 'assignee':
                    recipients = [value]
                elif key == 'watchers':
                    if not isinstance(value, (tuple, list)):
                        raise JobError(
                            'Value of watchers should be list or tuple.')
                    recipients = value[:]
                    watchers = []
                    for item in value:
                        if '-list' not in item:
                            watchers.append(item)
                    value = ','.join(watchers)
                if job.get('recipients'):
                    recipients.extend(job.get('recipients').split(','))
                # pylint: disable=consider-using-enumerate
                for index in range(len(recipients)):
                    if not recipients[index].endswith('@redhat.com'):
                        recipients[index] += '@redhat.com'
                job.set('recipients', ','.join(set(recipients)))

            if isinstance(value, _Extend):
                old_value = job.get(key)

                # Silent a pylint false positive
                # pylint: disable=no-member
                if old_value:
                    _value = old_value + '\n' + '\n'.join(value.value)
                else:
                    _value = '\n'.join(value.value)
            else:
                if isinstance(value, (list, tuple)):
                    _value = '\n'.join(value)
                else:
                    _value = copy.deepcopy(value)

            if isinstance(key, (str, unicode)):
                key = key.format(job.__dict__)
            if isinstance(_value, (str, unicode)):
                _value = _value.format(**job.__dict__)
            job.set(key, _value)

        # Initialize the job
        job = Job(arch, product, version, *test_identifiers)

        # Fill the job with parameters according to the rules
        for rule in self.rules:
            if 'when' not in rule or job.evaluate(rule['when']):
                for key, value in rule.items():
                    _process_key_value(job, rule, key, value)

        # Change job-template to a list according to jenkins-job-builder
        job_temp = job.get('job-template')
        if ',' in job_temp:
            job.set('jobs', job.get('job-template').split(','))
        else:
            job.set('jobs', [job.get('job-template')])

        job_tags = job.get('tags').replace("\n", ",").strip(",")
        job_feature = job.get('feature')

        if job_feature:
            job_tags = ("polarion: %s,%s" % (job_feature, job_tags)).strip(",")

        job.set('dashboard-tags', job_tags)

        return job

    def jobs(self):
        """
        Generate a list YAML job configurations.
        """
        for product, version in self._products:
            for arch in self._archs:
                for test_identifiers in self._test_jobs:
                    try:
                        job = self._generate_job(
                            arch, product, version, test_identifiers)
                        yield job
                    except JobExclusionError:
                        pass
