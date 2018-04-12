# pylint:disable=missing-docstring

import pytest
import mock

from libvirt_ci.report import Report

legacy_xml = """
<testsuites>
    <testsuite name="rhev.virsh" failure="1" errors="1" skipped="1" tests="4" time="3.0000" timestamp="2017-03-01T20:17:37.872370">
        <properties>
            <property name="p1" value="v1"/>
            <property name="p2" value="v2"/>
            <property name="p3" value="v3"/>
            <property name="p4" value="v4"/>
        </properties>
        <testcase name="case.1" time="1.0000" >
            <failure message="FAILURE" type="failure"/>
        </testcase>
        <testcase name="case.2" time="1.0000" >
            <skipped message="SKIP" type="skipped"/>
        </testcase>
        <testcase name="case.3" >
            <error message="FAILURE" type="error"/>
        </testcase>
        <testcase name="case.4" time="1.0000">
            <system-out> LOG </system-out>
        </testcase>
    </testsuite>

    <testsuite name="rhel.virsh" failure="1" errors="1" skipped="1" tests="4" time="3.0000" timestamp="2017-03-01T20:17:37.872370">
        <properties>
            <property name="p1" value="v1"/>
            <property name="p2" value="v2"/>
            <property name="p3" value="v3"/>
            <property name="p4" value="v4"/>
        </properties>
        <testcase name="case.1" time="1.0000">
            <failure message="FAILURE" type="failure"/>
        </testcase>
        <testcase name="case.2" time="1.0000">
            <skipped message="SKIP" type="skipped"/>
        </testcase>
        <testcase name="case.3">
            <error message="FAILURE" type="error"/>
        </testcase>
        <testcase name="case.4" time="1.0000">
            <system-out> LOG </system-out>
        </testcase>
    </testsuite>
</testsuites>
"""

xml = """
<testsuites>
    <testsuite name="avocado-function" failure="1" errors="1" skipped="1" tests="4" time="3.0000"
     hostname="TEST MACHINE" id="ID" package="DISTRO1" timestamp="2017-03-01T20:17:37.872370">
        <properties>
            <property name="p1" value="v1"/>
            <property name="p2" value="v2"/>
            <property name="p3" value="v3"/>
            <property name="p4" value="v4"/>
        </properties>
        <testcase name="case.1" time="1.0000" classname="rhel.virsh" >
            <failure message="FAILURE" type="failure"/>
            <system-out> LOG </system-out>
        </testcase>
        <testcase name="case.2" time="1.0000" classname="rhel.virsh" >
            <skipped message="SKIP" type="skipped"/>
            <system-out> LOG </system-out>
        </testcase>
        <testcase name="case.3" classname="rhel.virsh" >
            <error message="FAILURE" type="error"/>
            <system-out> LOG </system-out>
        </testcase>
        <testcase name="case.4" time="1.0000" classname="rhel.virsh" >
            <system-out> LOG </system-out>
        </testcase>
    </testsuite>
    <!-- Usually we only have one suite, just in case of future requirement -->
    <testsuite name="avocado-function-variant" failure="1" errors="1" skipped="1" tests="4" time="3.0000"
     hostname="TEST MACHINE" id="ID" package="DISTRO1" timestamp="2017-03-01T20:17:37.872370">
        <properties>
            <property name="p1" value="v1"/>
            <property name="p2" value="v2"/>
            <property name="p3" value="v3"/>
            <property name="p4" value="v4-change"/>
        </properties>
        <testcase name="case.1" time="1.0000" classname="rhev.virsh" >
            <failure message="FAILURE" type="failure"/>
        </testcase>
        <testcase name="case.2" time="1.0000" classname="rhev.virsh" >
            <skipped message="SKIP" type="skipped"/>
        </testcase>
        <testcase name="case.3" classname="rhev.virsh" >
            <error message="FAILURE" type="error"/>
        </testcase>
        <testcase name="case.4" time="1.0000" classname="rhev.virsh" >
            <system-out> LOG </system-out>
        </testcase>
    </testsuite>
</testsuites>
"""

names = [
    'virsh.case.1',
    'virsh.case.2',
    'virsh.case.3',
    'virsh.case.4',
    'virsh.case.1',
    'virsh.case.2',
    'virsh.case.3',
    'virsh.case.4']
full_names = [
    'rhel.virsh.case.1',
    'rhel.virsh.case.2',
    'rhel.virsh.case.3',
    'rhel.virsh.case.4',
    'rhev.virsh.case.1',
    'rhev.virsh.case.2',
    'rhev.virsh.case.3',
    'rhev.virsh.case.4']
results = ['FAIL', 'SKIP', 'FAIL', 'PASS', 'FAIL', 'SKIP', 'FAIL', 'PASS']

def test_legacy_load():
    report = Report()
    report.load(junit_string=legacy_xml)
    assert set([i.name for i in report.get_flatten_testcases_legacy()]) == set(names)
    assert set([i.full_name for i in report.get_flatten_testcases()]) == set(full_names)
    assert set([i.result for i in report.get_flatten_testcases()]) == set(results)

def test_load():
    report = Report()
    report.load(junit_string=xml)
    assert set([i.name for i in report.get_flatten_testcases_legacy()]) == set(names)
    assert set([i.full_name for i in report.get_flatten_testcases()]) == set(full_names)
    assert set([i.result for i in report.get_flatten_testcases()]) == set(results)
