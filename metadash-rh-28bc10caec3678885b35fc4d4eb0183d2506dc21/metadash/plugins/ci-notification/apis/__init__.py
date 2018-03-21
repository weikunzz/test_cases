from flask import Blueprint, abort
from flask_restful import Resource, Api
from metadash.injector import require
from ..models.hooks import publish_notification

TestRun = require('testrun')

app = Blueprint = Blueprint('ci-notification', __name__)

Api = Api(Blueprint)


class Nitification(Resource):
    def get(self, uuid_, op):
        if op == 'publish':
            testrun = TestRun.query.filter_by(uuid=uuid_).first() or abort(
                404, message="TestRun {} doesn't exist".format(uuid_))
            publish_notification(testrun)
            return {'message': 'Nofification published'}
        else:
            return abort(401, message="Invalid request")


Api.add_resource(Nitification, '/ci-notification/<uuid_>/<op>', endpoint='ci-notification')
