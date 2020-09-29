import itertools

from flask import jsonify
from flask_jwt_extended import jwt_required
from flask_restful import Resource

from dimensigon.domain.entities import Server
from dimensigon.web.decorators import securizer, forward_or_dispatch


class GranuleList(Resource):

    @forward_or_dispatch()
    @jwt_required
    @securizer
    def get(self):
        granules = itertools.chain(*[s.granules for s in Server.query.all()])
        return jsonify(list(set(granules)))
