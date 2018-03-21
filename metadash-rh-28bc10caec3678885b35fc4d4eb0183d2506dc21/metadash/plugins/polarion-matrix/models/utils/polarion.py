"""
More specified ORM for Polaroin
Wrapper for Pylaroin
"""
import pytz
import logging
import datetime
import tempfile

import os
import sys
import re

import requests

import xml.etree.ElementTree as ET
import xml.dom.minidom

logging.basicConfig(
    format='%(asctime)s %(levelname)-8s|%(message)s',
    level=logging.INFO)

LOGGER = logging.getLogger(__name__)

COMMIT_CHUNK_SIZE = 100

POLARION_PLAN_QUERY = {
    "RHEL-7.5": "7.5",
    "RHEL-ALT-7.5": "7.5",
    "RHEL-7.4": "7.4",
    "RHEL-7.3": "7.3",
    "RHEL-7.2": "7.2",
    "Pegas-7.4": "Pegas",
}

POLARION_URL = 'https://polarion.engineering.redhat.com/polarion'
POLARION_USER = 'rhel7_machine'
POLARION_PROJECT = 'RedHatEnterpriseLinux7'
POLARION_PASSWORD = 'polarion'
POLARION_DEFAULT_PLANNED_IN = None
POLARION_PLANS = {
    "Pegas Early Availability 1": {
        "plan_id": "Early_Availability_2", "due_date": "2017-06-06",
    },
    "Pegas Alpha": {
        "plan_id": "Pegas_Alpha", "due_date": "2017-08-01",
    },
    "Pegas Internal Beta": {
        "plan_id": "Pegas_Internal_Beta", "due_date": "2017-08-18",
    },
    "Pegas Snapshot 1": {
        "plan_id": "Pegas_Snapshot_1", "due_date": "2017-09-06",
    },
    "Pegas Snapshot 2": {
        "plan_id": "Pegas_Snapshot_2", "due_date": "2017-09-13",
    },
    "Pegas Snapshot 3": {
        "plan_id": "Pegas_Snapshot_3", "due_date": "2017-09-20",
    },
    "7.2 Batch Update 9": {
        "plan_id": "7_2_Batch_Update_9", "due_date": "2016-12-20",
    },
    "7.3 Batch Update 4": {
        "plan_id": "7_3_Batch_Update_4", "due_date": "2017-04-11",
    },
    "7.3 Batch Update 5": {
        "plan_id": "7_3_Batch_Update_5", "due_date": "2017-05-23",
    },
    "7.3 Batch Update 6": {
        "plan_id": "7_3_Batch_Update_6", "due_date": "2027-06-27",
    },
    "7.4 Pre-testing": {
        "plan_id": "7_4_Pre-testing", "due_date": "2017-04-27",
    },
    "7.4 Alpha": {
        "plan_id": "7_4_Alpha", "due_date": "2017-04-27",
    },
    "7.4 Beta": {
        "plan_id": "7_4_Beta", "due_date": "2017-05-18",
    },
    "7.4 Snap1": {
        "plan_id": "7_4_Snap1", "due_date": "2017-05-31",
    },
    "7.4 Snap2": {
        "plan_id": "7_4_Snap2", "due_date": "2017-06-07",
    },
    "7.4 Snap3": {
        "plan_id": "7_4_Snap3", "due_date": "2017-06-14",
    },
    "7.4 Snap4": {
        "plan_id": "7_4_Snap4", "due_date": "2017-06-21",
    },
    "7.4 Snap5": {
        "plan_id": "7_4_Snap5", "due_date": "2017-06-28",
    },
    "7.4 RC": {
        "plan_id": "7_4_RC", "due_date": "2017-07-20",
    },
    "7.4 Release": {
        "plan_id": "7_4_Release", "due_date": "2017-08-01",
    },
    "7.4 Batch update 1": {
        "plan_id": "7_4_Batch_update_1", "due_date": "2018-08-01",
    },
    "7.5 Internal Devel Freeze": {
        "plan_id": "7_5_Internal_Devel_Freeze", "due_date": "2017-11-03",
    },
    "7.5 Pre-testing": {
        "plan_id": "7_5_Pre-testing", "due_date": "2017-11-09",
    },
    "7.5 Alpha": {
        "plan_id": "7_5_Alpha", "due_date": "2018-01-05",
    },
    "7.5 Beta": {
        "plan_id": "7_5_Beta", "due_date": "2018-01-11",
    },
    "7.5 Snap1": {
        "plan_id": "7_5_Snap1", "due_date": "2018-01-24",
    },
    "7.5 Snap2": {
        "plan_id": "7_5_Snap2", "due_date": "2018-01-31",
    },
    "7.5 Snap3": {
        "plan_id": "7_5_Snap3", "due_date": "2018-02-07",
    },
    "7.5 Snap4": {
        "plan_id": "7_5_Snap4", "due_date": "2018-02-14",
    },
    "7.5 Snap5": {
        "plan_id": "7_5_Snap4", "due_date": "2018-02-21",
    },
    "7.5 RC": {
        "plan_id": "7_5_RC", "due_date": "2018-03-15",
    },
}


class PolarionException(Exception):
    pass


def get_nearest_plan(product, version, date=None):
    """
    Get next nearest next plan ID
    """
    kw = POLARION_PLAN_QUERY['{}-{}'.format(product, version)]
    utc = pytz.UTC
    plan_id = None
    plan_name = None
    nearest_date = None

    if not date:
        date = datetime.datetime.today()
        LOGGER.info('Using plan date %s', date)

    for key, value in POLARION_PLANS.items():
        if kw not in key:
            continue
        try:
            LOGGER.debug('trying plan %s', key)
            due_date = datetime.datetime.strptime(value.get('due_date'), "%Y-%m-%d")
        except ValueError:
            LOGGER.error("Wrong date time: %s", datetime)
            raise
        except TypeError:
            LOGGER.debug("no date, %s", key)
            raise

        if date < utc.localize(due_date):
            if not plan_id or due_date < nearest_date:
                plan_name, plan_id, nearest_date = key, value['plan_id'], due_date

    if plan_id:
        LOGGER.info('Next nearest plan is %s', plan_name)
        return plan_id
    else:
        raise PolarionException("Unable to find a planned in.")


class TestSuites(object):
    POLARION_PROPERTIES = [
        "polarion-testrun-id",
        "polarion-testrun-template-id",
        "polarion-testrun-status-id",
        "polarion-testrun-template-id",
        "polarion-testrun-title",
        "polarion-testrun-type-id",
        "polarion-dry-run",
        "polarion-include-skipped",
        "polarion-use-testcase-iterations",
        "polarion-lookup-method",
    ]

    def __init__(self, project_id, **kwargs):
        self.properties = {
            "polarion-project-id": project_id,
        }
        self.testsuites = []

    def set_polarion_response(self, response_key, response_value):
        if not response_key.startswith("polarion-response-"):
            response_key = "polarion-response-{}".format(response_key)
        self.properties[response_key] = response_value

    def set_polarion_property(self, key, value):
        if not key.startswith("polarion-"):
            key = "polarion-{}".format(key)
        self.properties[key] = value

    def set_polarion_custom_field(self, key, value):
        if not key.startswith("polarion-custom-"):
            key = "polarion-custom-{}".format(key)
        self.properties[key] = value

    def build_xml_str(self):
        xml_element = ET.Element("testsuites")

        if self.properties:
            props_element = ET.SubElement(xml_element, "properties")
            for k, v in self.properties.items():
                attrs = {'name': str(k), 'value': str(v)}
                ET.SubElement(props_element, "property", attrs)

        for suite in self.testsuites:
            xml_element.append(suite.build_xml_doc())

        xml_string = ET.tostring(xml_element)
        xml_string = TestSuites._clean_illegal_xml_chars(xml_string.decode('utf-8'))
        xml_string = xml.dom.minidom.parseString(xml_string).toprettyxml()

        return xml_string

    @staticmethod
    def _clean_illegal_xml_chars(string_to_clean):
        """
        Removes any illegal unicode characters from the given XML string, Copy & paste code
        """
        # see http://stackoverflow.com/questions/1707890/fast-way-to-filter-illegal-xml-unicode-chars-in-python
        illegal_unichrs = [(0x00, 0x08), (0x0B, 0x1F), (0x7F, 0x84), (0x86, 0x9F),
                           (0xD800, 0xDFFF), (0xFDD0, 0xFDDF), (0xFFFE, 0xFFFF),
                           (0x1FFFE, 0x1FFFF), (0x2FFFE, 0x2FFFF), (0x3FFFE, 0x3FFFF),
                           (0x4FFFE, 0x4FFFF), (0x5FFFE, 0x5FFFF), (0x6FFFE, 0x6FFFF),
                           (0x7FFFE, 0x7FFFF), (0x8FFFE, 0x8FFFF), (0x9FFFE, 0x9FFFF),
                           (0xAFFFE, 0xAFFFF), (0xBFFFE, 0xBFFFF), (0xCFFFE, 0xCFFFF),
                           (0xDFFFE, 0xDFFFF), (0xEFFFE, 0xEFFFF), (0xFFFFE, 0xFFFFF),
                           (0x10FFFE, 0x10FFFF)]

        illegal_ranges = ["%s-%s" % (chr(low), chr(high))
                          for (low, high) in illegal_unichrs
                          if low < sys.maxunicode]

        illegal_xml_re = re.compile(u'[%s]' % u''.join(illegal_ranges))
        return illegal_xml_re.sub('', string_to_clean)


class TestSuite(object):
    """
    Contains a set of TestCase object
    """
    def __init__(self, name):
        self.name = name
        self.testcases = []

    def add_testcase(self, testcase):
        assert isinstance(testcase, TestCase)
        self.testcases.append(testcase)

    def build_xml_doc(self):
        xml_element = ET.Element("testsuite", {
            'failures': str(self.failures),
            'errors': str(self.errors),
            'skipped': str(self.skipped),
            'tests': str(len(self.testcases)),
            'time': str(self.time),
            'name': str(self.name)
        })

        for testcase in self.testcases:
            xml_element.append(testcase.build_xml_doc())

        return xml_element

    @property
    def failures(self):
        return len([c for c in self.testcases if c.failure])

    @property
    def errors(self):
        return len([c for c in self.testcases if c.error])

    @property
    def skipped(self):
        return len([c for c in self.testcases if c.skipped])

    @property
    def time(self):
        return sum([c.elapsed_sec for c in self.testcases])


class TestCase(object):
    """
    Stands for a record of a test run on Polarion
    """
    def __init__(self, name, id,
                 stdout=None, stderr=None,
                 failure=None, skipped=None, error=None,
                 classname=None, comment=None, elapsed_sec=None):
        # Attr
        self.classname = classname
        self.name = name

        # Sub ele
        self.stdout = stdout
        self.stderr = stderr
        self.failure = failure
        self.skipped = skipped
        self.error = error
        self.elapsed_sec = elapsed_sec

        # Polarion Prop
        self.properties = {
            "polarion-testcase-id": id,
            "polarion-testcase-comment": comment,
        }

    def set_polarion_parameter(self, key, value):
        if not key.startswith("polarion-parameter-"):
            key = "polarion-parameter-{}".format(key)
        self.properties[key] = value

    @property
    def passed(self):
        return not self.failure and not self.skipped and not self.error

    def build_xml_doc(self):
        status = iter([self.failure, self.skipped, self.error])
        assert self.passed or any(status) and not any(status)

        attrs = {"name": str(self.name)}
        if self.classname:
            attrs["classname"] = str(self.classname)
        if self.elapsed_sec:
            attrs["time"] = str(self.elapsed_sec)

        xml_element = ET.Element("testcase", attrs)

        if self.failure:
            ET.SubElement(xml_element, "failure", {"type": "failure", "message": str(self.failure)})

        if self.skipped:
            ET.SubElement(xml_element, "skipped", {"type": "skipped", "message": str(self.skipped)})

        if self.error:
            ET.SubElement(xml_element, "error", {"type": "error", "message": str(self.error)})

        ET.SubElement(xml_element, "system-out").text = str(self.stdout or "")
        ET.SubElement(xml_element, "system-err").text = str(self.stderr or "")

        if self.properties:
            props_element = ET.SubElement(xml_element, "properties")
            for k, v in self.properties.items():
                attrs = {'name': str(k), 'value': str(v)}
                ET.SubElement(props_element, "property", attrs)

        return xml_element


# pylint: disable=no-member
class TestRunRecord(object):
    def __init__(self, project_id, testrun_name, **kwargs):
        self.tss = TestSuites(project_id)

        self.set_polarion_property = self.tss.set_polarion_property
        self.set_polarion_response = self.tss.set_polarion_response
        self.set_polarion_custom_field = self.tss.set_polarion_custom_field

        for key, value in kwargs.items():
            self.tss.set_polarion_custom_field(key, value)

        self.ts = TestSuite(testrun_name)
        self.tss.testsuites.append(self.ts)

    def get_polarion_property(self, key):
        if not key.startswith("polarion-"):
            key = "polarion-{}".format(key)
        return self.tss.properties[key]

    def add_testcase(
            self, case, result, elapsed_sec, comment=None, parameters=None):
        """
        Update test run content according to the test cases.
        """

        if result not in ['failed', 'passed', 'blocked']:
            raise PolarionException('Result can only be "failed", "passed" or "blocked", got "%s"' % result)

        # executed/executed_by is set automatically to the submit user and submit time
        record = TestCase(
            case, case, elapsed_sec=elapsed_sec, comment=comment
        )

        for key, value in (parameters or {}).items():
            record.set_polarion_parameter(key, value)

        if result == "failed":
            record.failure = comment
        elif result == "blocked":
            record.error = comment

        self.ts.add_testcase(record)
        return record

    def submit(self):
        """
        Submit / Update a test run on polarion.
        """
        xmldoc = self.tss.build_xml_str()
        fd, temp_path = tempfile.mkstemp()

        with open(temp_path, "w") as fp:
            fp.write(xmldoc)

        with open(temp_path, "r") as fp:
            res = requests.post("{}/import/xunit".format(POLARION_URL),
                                auth=(POLARION_USER, POLARION_PASSWORD),
                                files={"temp_path": fp}, verify=False)  # FIXME
            if res.status_code != requests.status_codes.codes.ok:
                return res.text

        os.close(fd)

        return None
