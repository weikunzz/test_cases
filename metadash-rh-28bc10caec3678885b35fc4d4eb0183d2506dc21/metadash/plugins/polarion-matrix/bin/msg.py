"""
Listen on UMB
TODO: Restruct with celery
"""
import json
import logging

from metadash import app
from metadash.injector import require
from metadash.utils.umb import quick_subscribe


logger = logging.getLogger(__name__)

TestRun = require('testrun')


def on_message(self, headers, message):
    """
    Handler on message
    """
    logging.info("=" * 72)
    logging.info('Message headers:\n%s', headers)
    logging.info('Message body:\n%s', message)
    metadash_testrun_uuid = headers.get('metadash_testrun_uuid')
    polarion_testrun = headers.get('polarion_testrun_id')
    if not metadash_testrun_uuid or not polarion_testrun:
        return

    message = json.loads(message)
    status = message.get('status')
    log_url = message.get('log-url')
    testrun_url = message.get('testrun-url')
    with app.app_context():
        testrun = TestRun.query.filter(TestRun.uuid == metadash_testrun_uuid).first()
        if not testrun:
            return

        if status == 'passed':
            testrun.properties['polarion-matrix-submit-status'] = 'success'
            testrun.properties['polarion-matrix-submit-id'] = polarion_testrun
            testrun.properties['polarion-matrix-submit-url'] = testrun_url
        else:
            testrun.properties['polarion-matrix-submit-status'] = 'failed'
        testrun.properties['polarion-matrix-submit-log'] = log_url
        TestRun.query.session.commit()


if __name__ == "__main__":
    quick_subscribe('metadash-polarion', 'qe.ci.polarion', on_message=on_message)
