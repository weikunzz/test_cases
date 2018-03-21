from flask import Blueprint, abort
from flask_restful import Resource, Api
from metadash import db
from metadash.injector import require
from ..models import export_testrun, export_all_testrun

TestRun = require('testrun')

app = Blueprint = Blueprint('elastic-search', __name__)

Api = Api(Blueprint)


class TestRunDetail(Resource):
    def get(self, uuid_):
        if uuid_ == 'all':
            export_all_testrun.delay()
        else:
            testrun = TestRun.query.filter_by(uuid=uuid_).first() or abort(
                404, message="TestRun {} doesn't exist".format(uuid_))
            export_testrun.delay(testrun.uuid)
        return {'message': 'Request submitted'}


Api.add_resource(TestRunDetail, '/push-to-elk/<uuid_>', endpoint='matrix-testrun-op')
