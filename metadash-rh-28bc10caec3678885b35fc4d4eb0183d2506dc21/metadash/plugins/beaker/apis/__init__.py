from __future__ import print_function
from metadash.auth import requires_roles, get_identity, get_all_users
import time
import subprocess
import datetime
import logging

from flask import Blueprint, jsonify

from ..models import Beaker
from metadash.exceptions import RemoteAuthError


def BeakerSession():
    return Beaker()


logger = logging.getLogger('beaker')

BEAKER_JOB_STATUS = ["QUEUED", "INSTALLING", "UPDATING", "RUNNING", "CANCELLED", "ABORTED"]
BEAKER_JOB_RESULTS = ["NEW", "PASS", "WARN", "PANIC"]

BEAKER_JOB_STATUS_CRIT = ["CANCELLED", "ABORTED"]
BEAKER_JOB_RESULTS_CRIT = ["WARN", "PANIC"]


app = Blueprint = Blueprint('beaker', __name__)


@app.route("/beaker-cancel-job/<job_id>")
@requires_roles("admin")
def beaker_cancel_job(job_id):
    try:
        job_id = int(job_id)
    except Exception as error:
        return jsonify({"message": "Illegal job id"}), 400
    proc = subprocess.Popen("bkr job-cancel J:{}".format(job_id),
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            shell=True)
    (out, err) = proc.communicate()
    rc = proc.returncode
    if 'No Kerberos credential cache found' in str(out) + str(err):
        raise RemoteAuthError('global-kerberos', 'Beaker authentication failure')
    return jsonify({"message": str(out) + '\n' + str(err)}), 503 if err or rc else 200


@app.route("/beaker-all-users-running-jobs/")
def beaker_all_users_jobs():
    all_jobs = []
    for user in get_all_users():
        all_jobs.extend(BeakerSession().get_user_jobs(user['username']))
    return jsonify(all_jobs)


@app.route("/beaker-my-group-running-jobs/")
def beaker_my_group_running_jobs():
    user = get_identity()["username"]
    return jsonify(BeakerSession().get_user_group_running_jobs(user))


@app.route("/beaker-all-users-loaned-machines/")
def beaker_all_users_loaned_machines():
    systems = []
    for user in get_all_users():
        data = BeakerSession().get_loaned_systems(user['username'])
        systems.extend(data)
    return jsonify({
        "data": systems
    })


@app.route("/beaker-baremetal-free-systems/")
def beaker_baremetal_free_systems():
    return jsonify({
        "data": BeakerSession().get_baremetal_free_systems()
    })


@app.route("/beaker-queue-length/")
def beaker_queue_length():
    data = {}
    for hour in reversed(range(4)):
        queue_info = BeakerSession().get_queue_length(datetime.datetime.utcnow() - datetime.timedelta(hours=hour))
        for arch, length in queue_info.items():
            data.setdefault(arch, []).append(length)
    return jsonify({
        "data": [[key] + value for key, value in data.items()]
    })


@app.route("/beaker-queue-wait-time/")
def beaker_queue_wait_time():
    return jsonify(BeakerSession().get_average_queue_wait_time())
