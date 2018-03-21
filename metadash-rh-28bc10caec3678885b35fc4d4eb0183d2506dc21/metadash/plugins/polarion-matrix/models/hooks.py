"""
"""
import re
import traceback

from .utils.v2v_convert import convert_single_testresult as v2v_convert
from .utils.install_convert import convert_single_testresult as install_convert
from .utils import polarion as Polarion
from metadash.models import db
from metadash.event import on
from metadash.injector import require


testrun = require('testrun')


def gen_polarion_testrun(testrun):
    testrun_description = 'Metadash ID: "{}", Tags: "{}"'.format(
        testrun.uuid, " ".join(testrun.tags))

    testrun_tags = ", ".join(tag.lstrip('polarion:').strip()
                             for tag in testrun.tags if tag.startswith('polarion:'))

    testrun_properties = {}
    for prop_name, prop_value in testrun.properties.items():
        if '-' in prop_name:
            group_name, prop_name = prop_name.split('-', 1)
            prop_group = testrun_properties.setdefault(group_name, {})
            prop_group[prop_name] = prop_value
            if group_name == 'packages':
                testrun_description += "%s: (%s: %s)" % ((
                    group_name.title(), prop_name, prop_value))
        else:
            testrun_properties[prop_name] = prop_value

    testrun_id = '{name} {framework} {build} {date} {extra}'.format(
        name=testrun.name,
        framework=testrun.properties['framework'],
        build=testrun.properties['build'],
        date=testrun.timestamp.isoformat(),
        extra=" ".join(testrun.tags)
    )

    testrun_id = re.sub(r'[.\/:*"<>|~!@#$?%^&\'*()+`,=]', '-', testrun_id)
    testrun_name = testrun_id

    testarch = testrun.properties['arch'].replace('_', '')
    testdate = testrun.timestamp
    testbuild = testrun.properties['build']
    testcomponent = testrun.properties['component']
    testproduct = testrun.properties['product']
    testversion = testrun.properties['version']

    testrun_record = Polarion.TestRunRecord(
        Polarion.POLARION_PROJECT,
        testrun_name,

        # Custom fields
        description=testrun_description,
        assignee="kasong",
        plannedin=Polarion.get_nearest_plan(testproduct, testversion, testdate),
        isautomated=True,
        build=testbuild,
        arch=testarch,
        component=testcomponent,
        jenkinsjobs=testrun.ref_url,
        tags=testrun_tags
    )

    testrun_record.set_polarion_property("group-id", testbuild)
    testrun_record.set_polarion_property("testrun-id", testrun_id)
    # testrun_record.set_polarion_property("testrun-type-id", testrun.type)
    testrun_record.set_polarion_property("testrun-template-id", "libvirt-autotest")
    testrun_record.set_polarion_response("metadash_matrix_submitted", "true")
    testrun_record.set_polarion_response("metadash_testrun_uuid", testrun.uuid)
    testrun_record.set_polarion_response("polarion_testrun_id", testrun_id)

    return testrun_record


def submit_testrun(testrun):
    polarion_testrun = gen_polarion_testrun(testrun)
    try:
        if (
                testrun.properties['component'] == 'installation' and
                testrun.properties['test_type'] == 'matrix' and
                testrun.properties['arch'] == 'x86_64'):
            testtype = 'installation_matrix'
        elif (
                testrun.properties['component'] == 'v2v' and
                testrun.properties['test_type'] in ('matrix', 'acceptance') and
                testrun.properties['test_suffix'] != 'gate' and
                testrun.properties['arch'] == 'x86_64'):
            testtype = 'v2v_matrix'
        else:
            raise Exception('Unacceptable test type')

        for testresult in testrun.testresults:
            if testresult.result in ['ERROR', 'SKIPPED']:
                continue
            if testtype == 'v2v_matrix':
                workitem, parameters = v2v_convert(testrun, testresult)
            elif testtype == 'installation_matrix':
                workitem, parameters = install_convert(testrun, testresult)
            if not workitem:
                raise RuntimeError('Unrecognized test case {}'.format(testresult.testcase_name))
            comment = testresult.details.get('error') or testresult.details.get('failure') or testresult.details.get('skipped')
            polarion_testrun.add_testcase(
                workitem, testresult.result.lower(), testresult.duration, comment=comment, parameters=parameters)

        res = polarion_testrun.submit()
        if res:
            raise Exception(str(res))

    except Exception as error:
        testrun.properties['polarion-matrix-submit-status'] = (
            "Failed: %s: %s" % (type(error), error.message if hasattr(error, 'message') else str(error))
        )  # TODO
        if hasattr(error, "__traceback__"):
            traceback.print_tb(error.__traceback__)
        else:
            traceback.print_exc()
        # TODO: Error Detail

    else:
        # No exception, means everything went well
        testrun.properties['polarion_id'] = polarion_testrun.get_polarion_property('testrun-id')
        testrun.properties['polarion-matrix-submit-status'] = "Waiting For Feedback"


def setup():
    @on(testrun, 'after_save')
    def fetch_testrun_console_text(mapper, connection, testrun):
        if testrun.status == 'FINISHED':
            if 'matrix' in testrun.name:
                if not testrun.properties.get('polarion-matrix-submit-status'):
                    submit_testrun(testrun)
            if 'acceptance-libvirt' in testrun.name:
                if not testrun.properties.get('polarion-matrix-submit-status'):
                    submit_testrun(testrun)
            if 'acceptance-ovirt' in testrun.name:
                if not testrun.properties.get('polarion-matrix-submit-status'):
                    submit_testrun(testrun)
