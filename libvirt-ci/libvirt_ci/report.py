"""
Jenkins split result into three level (For java):

Package Level - Class Level - Case Level

Package and Class are extracted from "classname" with format: (Package.Class)
and fallback to use testsuite's name when "classname" is not presenting.

We use Package Level to distinct RHEL/RHEV/Fed/(Other Distro)
We use Class Level to distinct Test Framework.

Case's should be the exact test case name, which can be used to present
a valid test case.

Make use of Package/Class to make test report on Jenkins prettier, we
should be able to remove them at anytime without break anything, since
using these attributes doesn't change the Junit strucutre.

Structure of a report:

* <testsuites> <!--Report root--!>
*     <testsuite name=""
*      failure="0" errors="0" skipped="0" tests="0" time="0.0000"
*      hostname='TEST MACHINE' id='TBD' package='DISTRO' timestamp='TIME'>
*         <properties>
*             <property name="" value=""/>
*         </properties>
*         <testcase name='test.case.name' time="0.0000" classname='Package.Class' >
*             <failure> Only show up when test failed </failure>
*             <error> Only show up when error occured during test run </error>
*             <skipped> Only show up when test skipped </skipped>
*             <system-out> Log here </system-out>
*             <system-error> TBD </system-error>
*         </testcase>
*     </testsuite>
* </testsuites>

"""
import logging
import os
import copy
import string
import xml.etree.ElementTree as ET
import junit_xml

from datetime import datetime
from datetime import timedelta
from dateutil import parser as dateparser

from libvirt_ci import package
from libvirt_ci import utils
from libvirt_ci import ci_message

LOGGER = logging.getLogger(__name__)


class TestCase(junit_xml.TestCase):
    """
    Presents a result of a single test run.
    classname=None, elapsed_sec=None, stdout=None,
    stderr=None
    """
    ALL_RESULTS = ['PASS', 'FAIL', 'SKIP', 'ERROR', 'DIFF', 'TIMEOUT',
                   'CANCEL', 'INVALID', 'NOTESTS', 'WARN', 'INTERRUPTED']
    XML_RESULTS = ['PASS', 'FAIL', 'SKIP', 'ERROR']

    def __init__(self, suite, *args, **kwargs):
        super(TestCase, self).__init__(*args, **kwargs)
        self.suite = suite
        self._name = self.name
        assert isinstance(self.suite, TestSuite)

    def is_ignored(self):
        return self.is_skipped() and 'Test failure ignored.' in self.skipped_message

    def is_blacklisted(self):
        return self.is_skipped() and 'BLACKLISTED' in self.skipped_message

    @property
    def result(self):
        if self.is_skipped():
            return 'SKIP'
        if self.is_failure():
            return 'FAIL'
        if self.is_error():
            return 'FAIL'
        return 'PASS'

    @property
    def message(self):
        return self.error_message or self.failure_message or self.skipped_message

    @property
    def full_name(self):
        """
        Prepend package name and class name
        """
        name = self._name
        if self.classname:
            try:
                package_name, classname = self.classname.split('.', 2)
                name = "%s.%s.%s" % (package_name, classname, name)
            except (TypeError, ValueError):
                name = "%s.%s" % (self.classname, self.name)
        return name

    def get_url(self, base_url=None):
        base_url = base_url or self.suite.properties.get('env-BUILD_URL')
        if base_url is None:
            return None
        split_name = self.classname.rsplit('.', 1)
        if len(split_name) == 1:
            package_name, classname = '(root)', self.classname
        else:
            package_name, classname = split_name
        test_name = self._name
        for char in '.-':
            test_name = test_name.replace(char, '_')
        return "%s/testReport/%s/%s/%s" % (
            base_url.rstrip('/'), package_name, classname, test_name)


class TestSuite(junit_xml.TestSuite):
    def __init__(self, report, name, **kwargs):
        self.report = report
        self.result_cluster = {
            "PASS": [],
            "FAIL": [],
            "SKIP": [],
        }
        super(TestSuite, self).__init__(name, **kwargs)

    @property
    def time(self):
        return sum(c.elapsed_sec for c in self.test_cases if c.elapsed_sec)

    def get_properties(self, hierarchical=None):
        """
        Get all properties, if hierarchical is True, return a two level dict
        with first level is the prefix.
        Else return one level dict.
        """
        if not hierarchical:
            return self.properties
        elif hierarchical is True:
            ret = {}
            for key, value in self.properties.items():
                prefix, key = key.split('-', 2)
                ret.setdefault(prefix, {})[key] = value
            return ret

    def create_testcase(self, name, result, log, message, duration, classname, **kwargs):
        """
        Insert a new item into report.
        :param name: The name of the test case
        :param result: The result of the test case, one of "FAIL", "PASS", "SKIP", etc
        :param log: Usually the stdout content of the test run
        :param message: Usually failure message, saying what went wrong
        :param duratoin: How long the test run take
        :param classname: Class name, two layer, Package.Class
        """
        if result not in TestCase.ALL_RESULTS:
            raise Exception("Unexpected result %s" % result)

        def _filter_characters(text):
            if type(text) is unicode:
                _text = text
            else:
                _text = unicode(text, errors='ignore')
            # Filter non-printable characters
            return ''.join(s for s in _text
                           if s in string.printable)

        if not self.timestamp:
            self.timestamp = (datetime.now() - timedelta(seconds=duration)).isoformat()

        log = _filter_characters(log)
        message = _filter_characters(message)

        # Enable showing newline in error messages
        message = message.replace('\n', '&#10;')

        test_case = TestCase(self, name, elapsed_sec=duration,
                             stdout=log, classname=classname, **kwargs)
        self.test_cases.append(test_case)

        # Make sure the message is not empty when test fails.
        # Or Jenkins will mark test case as PASS
        fail_list = ['FAIL', 'TIMEOUT', 'ERROR', 'SKIP', 'CANCEL', 'DIFF']
        if not message and result in fail_list:
            message = 'Result message not found. Please check log instead.'

        if result == 'FAIL':
            test_case.add_failure_info(message)
        elif result in ['TIMEOUT', 'ERROR', 'INVALID']:
            test_case.add_error_info(message)
        elif result in ['SKIP', 'CANCEL']:
            test_case.add_skipped_info(message)
        elif 'DIFF' in result and self.report.fail_diff:
            test_case.add_error_info(message)

        self.result_cluster.setdefault(result, []).append(test_case)


class Report(object):
    def __init__(self, fail_diff=False, host=None):
        self.default_properties = {}
        self.testsuites = {}
        self.fail_diff = fail_diff
        self.host = host

    @property
    def start_time(self):
        start_time = datetime.now()
        for ts in self.testsuites.values():
            try:
                start_time = min(dateparser.parse(ts.timestamp), start_time)
            # pylint: disable=broad-except
            except Exception:
                pass
        return start_time.isoformat()

    @property
    def end_time(self):
        end_time = self.start_time
        for ts in self.testsuites.values():
            try:
                end_time = dateparser.parse(ts.timestamp) + timedelta(seconds=int(ts.time or 0))
                end_time = end_time.isoformat()
            # pylint: disable=broad-except
            except Exception:
                pass
        return end_time

    @property
    def result_cluster(self):
        """
        Assorted test cases results by their outcome, return a dict
        An empty report will return:
        {
            "PASS": [],
            "FAIL": [],
            "SKIP": [],
        }
        """
        _cluster = {}
        for testsuite in self.testsuites.values():
            for key, value in testsuite.result_cluster.items():
                _cluster.setdefault(key, []).extend(value)
        return _cluster

    @property
    def result_counter(self):
        """
        Counter of cases in different results, return a dict
        An empty report will return:
        {
            "ALL": 0,
            "PASS": 0,
            "FAIL": 0,
            "SKIP": 0,
        }
        """
        _counter = {
            "ALL": 0,
            "PASS": 0,
            "FAIL": 0,
            "SKIP": 0,
        }
        for testsuite in self.testsuites.values():
            for key, value in testsuite.result_cluster.items():
                _counter[key] = _counter.get(key, 0) + len(value)
                _counter["ALL"] += len(value)
        return _counter

    def get_flatten_testcases(self, flatten_filter=None):
        """
        Get all test cases of all test suites belongs to this report, add
        apply a per case filter
        """
        test_cases = []
        flatten_filter = flatten_filter or (lambda *_: _[0])
        for suite in self.testsuites.values():
            test_cases.extend(map(flatten_filter, copy.deepcopy(suite.test_cases)))

        return test_cases

    def get_flatten_testcases_legacy(self):
        """
        Same as get_flatten_testcases but concat testcase's name, class name
        and suite name as the test case name
        """
        def _format(case):
            """
            Treat classname as part of case name.
            """
            if any([case.classname.startswith(prefix)
                    for prefix in ['rhev', 'rhel']]):
                case.name = case.full_name[5:]
            return case

        return self.get_flatten_testcases(flatten_filter=_format)

    def load(self, junit_path=None, junit_string=None):
        """
        Load from a xunit file or string
        """
        assert junit_path or junit_string
        root = (ET.parse(junit_path).getroot() if junit_path else
                ET.fromstring(junit_string))

        for testsuite_elem in root.findall('testsuite'):
            suite_name = testsuite_elem.get('name')
            suite_attr = {}
            for key in ["hostname", "package", "id", ]:
                suite_attr[key] = testsuite_elem.get(key)
            try:
                suite_attr['timestamp'] = dateparser.parse(testsuite_elem.get('timestamp')).isoformat()
            except (TypeError, ValueError):
                suite_attr['timestamp'] = datetime.now().isoformat()

            test_suite = self.create_testsuite(suite_name, **suite_attr)

            property_elems = testsuite_elem.find('properties')
            if len(property_elems):
                for elem in property_elems:
                    name, value = elem.get('name'), elem.get('value')
                    test_suite.properties[name] = value.decode('string_escape')
                    # Restore python native types
                    # FIXME: Won't work if what is stored is a string with value 'None'
                    if test_suite.properties[name] == 'None':
                        test_suite.properties[name] = None
                    if test_suite.properties[name] == 'False':
                        test_suite.properties[name] = True
                    if test_suite.properties[name] == 'False':
                        test_suite.properties[name] = False

            for test_case in testsuite_elem.findall('testcase'):
                case_duration = float(test_case.get('time') or 0)
                classname = test_case.get('classname')
                name = test_case.get('name')
                output = test_case.find('system-out')
                output = output.text if output is not None else ''
                failure = test_case.find('failure')
                failure = failure.get('message') if failure is not None else ''
                error = test_case.find('error')
                error = error.get('message') if error is not None else ''
                skip = test_case.find('skipped')
                skip = skip.get('message') if skip is not None else ''

                if failure:
                    result = "FAIL"
                elif error:
                    result = "ERROR"
                elif skip:
                    result = "SKIP"
                elif output:
                    result = "PASS"
                else:
                    raise RuntimeError("This XML seems invalid, test case %s" % test_case.text)

                if suite_name.startswith('rhel') or suite_name.startswith('rhev'):
                    # In case we need to process some old report
                    if classname is None:
                        classname = suite_name

                self.update(name, classname, result, output,
                            failure or error or skip, case_duration,
                            suite_name=suite_name)

    def save(self, junit_path):
        """
        Save current state of report to files.
        """
        testsuites = self.testsuites.values()
        with open(junit_path, 'w') as _file:
            xml_string = junit_xml.TestSuite.to_xml_string(testsuites)
            xml = ET.fromstring(xml_string)
            # Remove testsuites attributes which is not recognized in
            # Jenkins XUnit Plugin
            xml.attrib = {}
            _file.write(ET.tostring(xml))

    def create_testsuite(self, name, **kwargs):
        """
        Params:
        test_cases=None, hostname=None, id=None,
        package=None, timestamp=None, properties=None
        """
        try:
            properties = kwargs.pop("properties")
            for key, value in self.default_properties.items():
                properties.setdefault(key, value)
        except KeyError:
            properties = copy.copy(self.default_properties)

        testsuite = TestSuite(self, name, properties=properties, **kwargs)
        self.testsuites[name] = testsuite
        return testsuite

    def update(self, test_name, classname, result, log, message, duration,
               suite_name=None, test_idx=None, class_idx=None, prefix=None,
               **kwargs):
        """
        A shortcut for updating test result for a test suite with name suite_name
        If suite_name is not given, will use the test framework as the suite_name.

        kwargs could be (hostname, id, package, timestamp) for creating new test case
        Test suite creation only happend on first "update" call with a new suite_name.

        Some param are for backward compatibility
        """
        if class_idx is not None:
            classname = "%02d-%s" % (class_idx, classname)
        if test_idx is not None:
            test_name = "%02d-%s" % (test_idx, test_name)
        if prefix:
            classname = '%s.%s' % (prefix, classname)

        if suite_name is None:
            suite_name = self.default_properties.get('param-test_framework', 'libvirt-ci')

        if not self.testsuites or not self.testsuites.get(suite_name):
            self.create_testsuite(suite_name, **kwargs)

        testsuite = self.testsuites[suite_name]
        testsuite.create_testcase(test_name, result, log, message, duration, classname=classname)

    def set_default_property(self, key, value, prefix=None):
        """
        Set defualt property, if new created testsuite doesn't have a property which is in
        default properties, it will be given the default value.

        If value is None, set to empty string "", as xml only accept string
        """
        key = prefix + "-" + key if prefix else key
        value = value or ""
        self.default_properties[key] = ''.join(
            [_c if ord(_c) < 128 else _c.encode('string_escape') for _c in str(value)])

    def gen_common_properties(self):
        """
        Generate default property among test suites.

        If all testsuite have a property with same value, then it's considerd default.
        """
        if len(self.testsuites) == 0:
            return self.default_properties
        return reduce(lambda d, nd: dict(list(set(d.items()) & set(nd.items()))),
                      [_.properties for _ in self.testsuites.values()])

    add_property = set_default_property
    set_property = set_default_property

    def get_properties(self, hierarchical=None):
        """
        """
        if len(self.testsuites) == 0:
            return self.default_properties
        elif len(self.testsuites) == 1:
            testsuite = self.testsuites.values()[0]
            return testsuite.get_properties(hierarchical)
        else:
            prop = self.gen_common_properties()
            if not hierarchical:
                return prop
            ret = {}
            for key, value in prop.items():
                prefix, key = key.split('-', 2)
                ret.setdefault(prefix, {})[key] = value
            return ret

    def record_params(self, param):
        """
        Shortcut for recording parameters,
        """
        for key, value in param.items():
            self.add_property(key, str(value), prefix="param")

    def record_env(self):
        """
        Shortcut for recording enviroment variables, and some extra info
        """
        for key, value in os.environ.items():
            self.add_property(key, str(value), prefix="env")
        if "BUILD_URL" not in os.environ.keys():
            LOGGER.info("BUILD_URL is set to None")
            self.default_properties["env-BUILD_URL"] = None
        if "JOB_URL" not in os.environ.keys():
            LOGGER.info("JOB_URL is set to None")
            self.default_properties["env-JOB_URL"] = None
        self.default_properties['arch'] = utils.get_arch()

    def record_packages(self, pkgs):
        """
        Shortcut for recording installed packages
        """
        if not isinstance(pkgs, list):
            pkgs = utils.split(pkgs)
        for pkg in pkgs:
            try:
                pkg_name = str(package.Package.from_name(pkg, host=self.host))
                self.add_property(pkg, str(pkg_name), prefix="package")
            except package.PackageNotExistsError:
                self.add_property(pkg, "not installed", prefix="package")
            except package.PackageParseError:
                self.add_property(pkg, "invalid", prefix="package")

    def record_ci_message(self, message):
        """
        Shortcut for recording installed packages
        """
        message = ci_message.CIMessage(message)
        self.add_property('brewid', message.brew_buildid)
        self.add_property('brewner', message.owner)

    def record_report_keys(self):
        for key, value in self.get_report_keys().items():
            self.add_property(key, value)

    def get_report_keys(self):
        """
        A Unified entry point to generate all needed parameter
        for and report_to_* command, to decouple the useage of jjb config
        and commandline, so hopefully we don't need to include {{param}}
        in the script file for reporting anymore.
        """
        ret = {}
        prop = self.get_properties()
        ret['brewid'] = prop.get('brewid') or None
        ret['brewner'] = prop.get('brewner') or None
        ret['product'] = prop.get('param-product') or 'linux'
        ret['version'] = prop.get('param-product_version') or 'generic'
        ret['variant'] = self.get_rhel_rhev() or 'unknown'
        ret['component'] = prop.get('param-component') or 'libvirt'
        ret['test_name'] = prop.get('param-test_name') or 'standalone'
        ret['test_type'] = prop.get('param-test_type') or 'standalone'
        ret['test_suffix'] = prop.get('param-test_suffix') or 'test'
        ret['job_name'] = prop.get('param-job_name') or 'standalone-test'
        ret['job_url'] = prop.get('env-JOB_URL') or None
        ret['build_url'] = prop.get('env-BUILD_URL') or None
        ret['test_framework'] = prop.get('param-test_framework') or 'libvirt-ci'
        ret['arch'] = prop.get('arch') or utils.get_arch()
        ret['message'] = prop.get('param-message') or '{}'
        ret['build'] = prop.get('package-%s' % prop.get('param-label_package')) or 'unkown-build'
        ret['date'] = (self.end_time or datetime.now().isoformat())
        try:
            ret['nvr'] = str(package.Package.from_str(ret['build']))
        except package.PackageError as error:
            LOGGER.error("Failed to retrive package info with: %s", error)
            ret['nvr'] = None
        return ret

    def get_rhel_rhev(self):
        """
        Helper to get rhel/rhev, it's not very intuitive to access prop manually.
        """
        return self.get_properties().get("param-qemu_pkg", 'rhel')

    def get_env(self, name):
        return self.get_properties().get("env-%s" % name, None)

    def get_package(self, name):
        return self.get_properties().get("package-%s" % name, None)

    def get_param(self, name):
        return self.get_properties().get("param-%s" % name, None)
