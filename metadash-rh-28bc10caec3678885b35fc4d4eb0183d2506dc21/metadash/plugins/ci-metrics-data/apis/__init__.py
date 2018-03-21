from flask import Blueprint, abort
from flask_restful import Resource, Api
from metadash import db
from metadash.injector import require
from ..models.hooks import submit_metrics

TestRun = require('testrun')

app = Blueprint = Blueprint('metrics-data', __name__)

Api = Api(Blueprint)


class TestRunDetail(Resource):
    def get(self, uuid_, op):
        if op == 'submit':
            testrun = TestRun.query.filter_by(uuid=uuid_).first() or abort(
                404, message="TestRun {} doesn't exist".format(uuid_))
            submit_metrics(testrun)
            db.session.commit()
            return {'message': 'Request submitted'}
        else:
            return abort(401, message="Invalid request")


Api.add_resource(TestRunDetail, '/ci-metrics-data/<uuid_>/<op>', endpoint='ci-metrics-data')
