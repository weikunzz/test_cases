"""
Publish metrics data to the message bus
"""
import logging
import sys
import json
import stomp

from libvirt_ci import report
from libvirt_ci import metadata
from libvirt_ci import ci_message

LOGGER = logging.getLogger(__name__)


def parse(parser):
    """
    Parse arguments for send message to message bus.
    """
    parser.add_argument(
        '--bus-user',
        dest='bus_user',
        default='ci-ops-central-jenkins',
        help='Username to use to connect to the message bus.'
    )
    parser.add_argument(
        '--bus-password',
        dest='bus_password',
        default='tQrYdOHhBqOMJi/k',
        help='Password to use to connect to the message bus.'
    )
    parser.add_argument(
        '--bus-host',
        dest='bus_host',
        default='ci-bus.lab.eng.rdu2.redhat.com',
        help='Message bus host.'
    )
    parser.add_argument(
        '--bus-port',
        dest='bus_port',
        type=int,
        default=61613,
        help='Message bus port.'
    )
    parser.add_argument(
        '--bus-destination',
        dest='bus_destination',
        default='/topic/CI',
        help='Message bus topic/subscription.'
    )

    parser.add_argument(
        '--xunit',
        dest='xunit',
        required=True, action='append',
        help='xunit(s) contains the test results.'
    )

    # Data that can only be parsed from command line
    parser.add_argument(
        '--owner-id', dest='owner_id', default='libvirt-ci',
    )
    parser.add_argument(
        '--trigger', dest='trigger', default="brew build",
    )
    parser.add_argument(
        '--team', dest='team', default="libvirt-ci",
    )
    parser.add_argument(
        '--executor', dest='executor', default='beaker',
    )
    parser.add_argument(
        '--recipients', dest='recipients', default='kasong, gsun',
    )

    # Data that could be retrived from param or report
    parser.add_argument(
        '--subtest', dest='variant', default='',
    )
    parser.add_argument(
        '--arch', dest='arch',
    )
    parser.add_argument(
        '--product', dest='product',
    )
    parser.add_argument(
        '--version', dest='version',
    )
    parser.add_argument(
        '--jenkins-job-url', dest='job_url',
    )
    parser.add_argument(
        '--jenkins-build-url', dest='build_url',
    )
    parser.add_argument(
        '--job-name', dest='name',
    )

    # Data that could be parsed or judged from CI message
    parser.add_argument(
        '--ci-message', dest='message',
    )
    parser.add_argument(
        '--base-distro', dest='base_distro',
    )
    parser.add_argument(
        '--nvr', dest='nvr',
    )
    parser.add_argument(
        '--build-type', dest='build_type',
    )
    parser.add_argument(
        '--brew-taskid', dest='brew_taskid',
    )
    parser.add_argument(
        '--ci-tier', dest='ci_tier', type=int,
    )

    # Not used yet
    parser.add_argument(
        '--logstash-url', dest='logstash_url', default='',
    )
    parser.add_argument(
        '--CI-infra-failure', dest='CI_infra_failure', default='',
    )
    parser.add_argument(
        '--CI-infra-failure-desc', dest='CI_infra_failure_desc', default='',
    )
    parser.add_argument(
        '--note', dest='note', default='',
    )


def run(params):
    """
    Publish a message on the message bus.
    """
    for xunit in params.xunit:
        headers = {
            "CI_TYPE": "ci-metricsdata",
            "owner_id": params.owner_id,
        }

        result = report.Report()
        result.load(junit_path=xunit)
        result_keys = result.get_report_keys()

        # pylint: disable=cell-var-from-loop
        def require_param(name):
            ret = params.__dict__.get(name) or result_keys.get(name)
            if not ret:
                raise Exception("Missing paramater %s" % name)
            return ret

        job_name = require_param("job_name")
        job_url = require_param("job_url")
        build_url = require_param("build_url")
        arch = require_param("arch")
        product = require_param("product")
        version = require_param("version")
        subtest = require_param("variant")

        base_distro = params.base_distro or metadata.Metadata('Products').get(
            "%s%s" % (product, version))['Beaker Distro']

        try:
            message = ci_message.CIMessage(params.ci_message or require_param("message"))
        except ci_message.CIMessageParseError:
            sys.exit(1)

        brew_taskid = message.brew_taskid
        nvr = message.nvr
        scratch = message.scratch

        if not all([brew_taskid, nvr]):
            LOGGER.error("This command is only suppoesed to be used with a testrun "
                         "which is triggered by a CI message, if this testrun is triggered "
                         "by a CI message, then the message is lost, something is wrong.")
            sys.exit(0)

        brew_taskid = params.brew_taskid or brew_taskid
        nvr = params.nvr or nvr
        ci_tier = params.ci_tier or 1 if scratch else 2
        build_type = params.build_type or "scratch" if scratch else "official"

        body = {
            "trigger": params.trigger,
            "team": params.team,
            "recipients": params.recipients,

            "component": nvr,
            "jenkins_job_url": job_url,
            "jenkins_build_url": build_url,
            "job_name": job_name,
            "CI_tier": ci_tier,
            "base_distro": base_distro,
            "brew_task_id": brew_taskid,
            "build_type": build_type,

            # Not used
            "logstash_url": params.logstash_url,
            "CI_infra_failure": params.CI_infra_failure,
            "CI_infra_failure_desc": params.CI_infra_failure_desc,
            "note": params.note,
        }

        body.update({
            "tests": [
                {
                    "executor": params.executor,
                    "subtest": subtest,
                    "arch": arch,
                    "executed": result.result_counter["ALL"],
                    "passed": result.result_counter["PASS"],
                    "failed": result.result_counter["ALL"] - result.result_counter["PASS"],
                },
            ],
            "create_time": result.start_time.isoformat(),
            "complete_time": result.end_time.isoformat(),
        })

        json_msg = json.dumps(body, indent=4)
        LOGGER.info("Sending message header:\n%s\n, body:\n%s\n",
                    json.dumps(headers, indent=4), json_msg)

        conn = stomp.Connection([(params.bus_host, params.bus_port)], timeout=60)
        conn.start()
        conn.connect(login=params.bus_user, passcode=params.bus_password)
        if stomp.__version__[0] < 4:
            # pylint: disable=no-value-for-parameter
            conn.send(message=json_msg, headers=headers,
                      destination=params.bus_destination)
        else:
            conn.send(body=json_msg, headers=headers,
                      destination=params.bus_destination)
        conn.disconnect()
        LOGGER.info('Metrics message sent.')
