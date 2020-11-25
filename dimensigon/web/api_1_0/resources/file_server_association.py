import typing as t

from flask import request, current_app
from flask_jwt_extended import jwt_required
from flask_restful import Resource

from dimensigon.domain.entities import FileServerAssociation, File, Server
from dimensigon.web import db, errors
from dimensigon.web.decorators import securizer, forward_or_dispatch, lock_catalog, validate_schema
from dimensigon.web.helpers import filter_query, check_param_in_uri
from dimensigon.web.json_schemas import file_server_associations_post, file_server_associations_patch, \
    file_server_associations_delete


class FileServerAssociationList(Resource):

    @jwt_required
    @securizer
    @forward_or_dispatch()
    def get(self, file_id):
        query = filter_query(FileServerAssociation, request.args).filter_by(file_id=file_id)
        return [fsa.to_json(human=check_param_in_uri('human'), no_delete=True) for fsa in query.all()]

    @jwt_required
    @securizer
    @forward_or_dispatch()
    @validate_schema(file_server_associations_post)
    @lock_catalog
    def post(self, file_id):
        destinations = request.get_json()
        if isinstance(destinations, dict):
            destinations = [destinations]
        new_fsas = change_destinations(File.query.get_or_raise(file_id), destinations, action='add')
        new = [(fsa.file.id, fsa.destination_server.id) for fsa in new_fsas]
        db.session.commit()
        fs = current_app.dm.file_sync
        if fs:
            [fs.add(*k) for k in new]
        return {}, 204

    @jwt_required
    @securizer
    @forward_or_dispatch()
    @validate_schema(file_server_associations_patch)
    @lock_catalog
    def patch(self, file_id):
        destinations = request.get_json()
        if isinstance(destinations, dict):
            destinations = [destinations]
        new_fsas = change_destinations(File.query.get_or_raise(file_id), destinations)
        new = [(fsa.file.id, fsa.destination_server.id) for fsa in new_fsas]
        db.session.commit()
        fs = current_app.extensions.get('file_sync')
        if fs:
            [fs.add(*k) for k in new]
        return {}, 204

    @jwt_required
    @securizer
    @forward_or_dispatch()
    @validate_schema(file_server_associations_delete)
    @lock_catalog
    def delete(self, file_id):
        destinations = request.get_json()
        if isinstance(destinations, dict):
            destinations = [destinations]
        change_destinations(File.query.get_or_raise(file_id), destinations, action='delete')
        db.session.commit()
        return {}, 204


def change_destinations(file: File, destinations: t.List, action: str = None):
    """

    :param file: file to change its destinations
    :param destinations:
    :param action:
    :return:
    """
    current = set([d.dst_server_id for d in file.destinations])
    new = set([d.get('dst_server_id') for d in destinations])
    new_fsas = []
    if action == 'add':
        to_remove = []
        to_modify = []
        already_there = current.intersection(new)
        if already_there:
            raise errors.InvalidValue("destination servers already exist",
                                      destinations=[{'id': ident, 'name': Server.query.get(ident).name} for ident
                                                    in already_there])
        to_add = new
    elif action == 'delete':
        to_remove = new
        not_there = new - current
        if not_there:
            raise errors.InvalidValue("destination servers do not exist",
                                      destinations=[{'id': ident, 'name': Server.query.get(ident).name} for ident
                                                    in not_there])
        to_modify = []
        to_add = []
    else:
        to_remove = current - new
        to_modify = new.intersection(current)
        to_add = new - current

    for dst_server_id in to_add:
        s = Server.query.get_or_raise(dst_server_id)
        if s._me:
            raise errors.InvalidValue("Destination cannot be the same as the source server",
                                      source_server={'id': s.id, 'name': s.name})
        dest = [d for d in destinations if d['dst_server_id'] == dst_server_id][0]
        fsa = FileServerAssociation(file=file, destination_server=s, dest_folder=dest.get('dest_folder', None))

        db.session.add(fsa)
        new_fsas.append(fsa)
    for dst_server_id in to_modify:
        s = Server.query.get_or_raise(dst_server_id)
        curr_dest = [d for d in file.destinations if d.dst_server_id == dst_server_id][0]
        in_dest = [d for d in destinations if d['dst_server_id'] == dst_server_id][0]
        if curr_dest.dest_folder != in_dest.get('dest_folder', None):
            curr_dest.dest_folder = in_dest.get('dest_folder', None)
    for dst_server_id in to_remove:
        s = Server.query.get_or_raise(dst_server_id)
        dest = [d for d in file.destinations if d.dst_server_id == dst_server_id]
        if dest:
            db.session.delete(dest[0])
        else:
            raise errors.GenericError("File does not have this destination", status_code=404, file_id=file.id,
                                      destination={'id': dst_server_id, 'name': s.name})
    return new_fsas
