import uuid

from flask_jwt_extended import jwt_required
from flask_restful import Resource

from dm.web import ajl
from dm.web.decorators import securizer, forward_or_dispatch


class JobList(Resource):

    @securizer
    @jwt_required
    @forward_or_dispatch
    def get(self):
        return ajl.queue.get_info(json=True)


class JobResource(Resource):
    @securizer
    @jwt_required
    @forward_or_dispatch
    def get(self, job_id):
        job_id = uuid.UUID(job_id)
        return ajl.queue.get_info(job_id)
