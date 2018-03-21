from flask import Blueprint, abort
from flask_restful import Resource, Api
from sqlalchemy import or_
from metadash import db
from metadash.injector import require
from metadash.apis import pager, envolop
from ..models.hooks import submit_testrun

TestRun = require('testrun')

app = Blueprint = Blueprint('matrix', __name__)

Api = Api(Blueprint)


class TestRunList(Resource):
    def get(self):
        testruns = []
        for testrun in pager(TestRun.query.filter(or_(
                TestRun.name.like('%matrix%'),
                TestRun.name.like('%acceptance-libvirt%'),
                TestRun.name.like('%acceptance-ovirt%'),
        )).order_by(TestRun.timestamp.desc())):
            dict_ = testrun.as_dict(exclude=['details', 'properties'])
            dict_['polarion-matrix-submit-status'] = testrun.properties.get('polarion-matrix-submit-status') or 'not submitted'
            dict_['polarion-matrix-submit-url'] = testrun.properties.get('polarion-matrix-submit-url')
            dict_['polarion-matrix-submit-log'] = testrun.properties.get('polarion-matrix-submit-log')
            testruns.append(dict_)

        return envolop(testruns)


class TestRunDetail(Resource):
    def get(self, uuid_, op):
        if op == 'submit':
            testrun = TestRun.query.filter_by(uuid=uuid_).first() or abort(
                404, message="TestRun {} doesn't exist".format(uuid_))
            submit_testrun(testrun)
            db.session.commit()
            return {'message': 'Request submitted'}
        else:
            return abort(401, message="Invalid request")


Api.add_resource(TestRunList, '/polarion-matrix-testruns/', endpoint='matrix-testrun')
Api.add_resource(TestRunDetail, '/polarion-matrix-testruns/<uuid_>/<op>', endpoint='matrix-testrun-op')
