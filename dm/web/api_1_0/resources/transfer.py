import base64
import os
import re

from flask import request, current_app
from flask_jwt_extended import jwt_required
from flask_restful import Resource
from sqlalchemy import or_

import dm.defaults as d
from dm.domain.entities import Transfer, TransferStatus, Software
from dm.utils.helpers import md5, get_now
from dm.web import db, errors
from dm.web.decorators import securizer, forward_or_dispatch, validate_schema
from dm.web.json_schemas import transfers_post, transfer_post


class TransferList(Resource):

    @forward_or_dispatch
    @jwt_required
    @securizer
    def get(self):
        return [t.to_json() for t in Transfer.query.all()]

    @forward_or_dispatch
    @jwt_required
    @securizer
    @validate_schema(transfers_post)
    def post(self):
        # validation
        json_data = request.get_json()
        soft = None
        if 'software_id' in json_data:
            soft = Software.query.get_or_404(json_data['software_id'])
            pending = Transfer.query.filter_by(software=soft, dest_path=json_data['dest_path']).filter(
                or_(Transfer.status == TransferStatus.WAITING_CHUNKS,
                    Transfer.status == TransferStatus.IN_PROGRESS)).all()

            if pending and not json_data.get('cancel_pending', False):
                return {"error": f"There is already a transfer sending software {soft.id}"}, 409
            elif pending and json_data['cancel_pending']:
                for trans in pending:
                    trans.status = TransferStatus.CANCELED
        elif 'filename' not in json_data:
            return {'error': 'Neither filename nor software specified for the transfer'}, 404
        elif 'filename' in json_data and ('size' not in json_data or 'checksum' not in json_data):
            return {'error': 'size and checksum must be specified when a filename set'}, 404
        else:
            pending = Transfer.query.filter_by(_filename=json_data['filename'],
                                               dest_path=json_data['dest_path']).filter(
                or_(Transfer.status == TransferStatus.WAITING_CHUNKS,
                    Transfer.status == TransferStatus.IN_PROGRESS)).all()

            if pending and not json_data.get('cancel_pending', False):
                return {"error": f"There is already a transfer sending file "
                                 f"{os.path.join(json_data['dest_path'], json_data['filename'])}"}, 409
            elif pending and json_data.get('cancel_pending', False):
                for trans in pending:
                    trans.status = TransferStatus.CANCELED

        dest_path = json_data.get('dest_path', current_app.config['SOFTWARE_REPO'])
        file = os.path.join(dest_path, soft.filename if soft else json_data['filename'])

        if os.path.exists(file):
            if not json_data.get('force', False):
                return {"error": "File already exists. Use force=True if needed"}, 409
            else:
                try:
                    os.remove(file)
                except FileNotFoundError:
                    pass
                except Exception as e:
                    msg = f"Unable to remove {file}"
                    current_app.logger.exception(msg)
                    return {'error': msg + f": {e}"}, 500

        # remove chunk files if exist
        for dirpath, dirnames, filenames in os.walk(dest_path):
            for f in filenames:
                if re.search(rf"^{os.path.basename(file)}_chunk\.(\d+)$", f):
                    current_app.logger.debug(f'removing chunk file {os.path.join(dest_path, f)}')
                    try:
                        os.remove(os.path.join(dirpath, f))
                    except:
                        pass
            break

        if soft:
            t = Transfer(software=soft, dest_path=dest_path,
                         num_chunks=json_data['num_chunks'])
        else:
            t = Transfer(software=json_data['filename'], dest_path=dest_path, num_chunks=json_data['num_chunks'],
                         size=json_data['size'], checksum=json_data['checksum'])

        try:
            os.makedirs(t.dest_path, exist_ok=True)
        except Exception as e:
            msg = f"Unable to create dest path {t.dest_path}"
            current_app.logger.exception(msg)
            return {'error': msg + f": {e}"}, 500

        db.session.add(t)
        db.session.commit()
        return {'transfer_id': str(t.id)}, 202


CHUNK_READ_BUFFER = d.CHUNK_SIZE


class TransferResource(Resource):

    @forward_or_dispatch
    @jwt_required
    @securizer
    def get(self, transfer_id):
        return Transfer.query.get_or_404(transfer_id).to_json()

    @forward_or_dispatch
    @jwt_required
    @securizer
    @validate_schema(transfer_post)
    def post(self, transfer_id):
        """Generates the chunk into disk"""
        data = request.get_json()
        trans: Transfer = Transfer.query.get_or_404(transfer_id)
        if trans.status == TransferStatus.WAITING_CHUNKS:
            trans.started_on = get_now()
            trans.status = TransferStatus.IN_PROGRESS
            db.session.commit()
        elif trans.status != TransferStatus.IN_PROGRESS:
            raise errors.TransferNotInValidState(transfer_id, trans.status.name)

        chunk = data.get('content')
        chunk_id = data.get('chunk')
        if trans.num_chunks == 1:
            file = os.path.join(trans.dest_path, f'{trans.filename}')
        else:
            file = os.path.join(trans.dest_path, f'{trans.filename}_chunk.{chunk_id}')
        with open(file, 'wb') as fd:
            raw = base64.b64decode(chunk.encode('ascii'))
            fd.write(raw)
        if trans.num_chunks == 1:
            msg = f"File {trans.filename} from transfer {transfer_id} generated successfully"
            trans.status = TransferStatus.COMPLETED
            db.session.commit()
        else:
            msg = f"Chunk {chunk_id} from transfer {transfer_id} generated successfully"

        current_app.logger.debug(msg)
        return {'message': msg}, 201

    @forward_or_dispatch
    @jwt_required
    @securizer
    def patch(self, transfer_id):
        """ends the transfer creating the file"""
        trans: Transfer = Transfer.query.get_or_404(transfer_id)
        if trans.status == TransferStatus.COMPLETED:
            return {'error': 'Transfer has already completed'}, 410
        elif trans.status == TransferStatus.WAITING_CHUNKS:
            return {'error': 'Transfer still waiting for chunks'}, 406
        current_app.logger.debug(
            f"Generating file {os.path.join(trans.dest_path, trans.filename)} from transfer {trans.id}")
        chunk_pattern = re.compile(rf"^{trans.filename}_chunk\.(\d+)$")
        file = os.path.join(trans.dest_path, trans.filename)

        try:
            files, chunks_ids = zip(*sorted(
                [(f, int(chunk_pattern.match(f).groups()[0])) for f in os.listdir(trans.dest_path) if
                 os.path.isfile(os.path.join(trans.dest_path, f)) and chunk_pattern.match(f)],
                key=lambda x: x[1]))
        except:
            files, chunks_ids = [], []

        if len(files) != trans.num_chunks or sum(chunks_ids) != (trans.num_chunks - 1) * trans.num_chunks / 2:
            if len(files) == 0:
                msg = f"Any chunk found on {trans.dest_path}"
            else:
                msg = f"Not enough chunks to generate the file"
            current_app.logger.error(msg)
            return {"error": msg}, 404
        with open(file, 'wb') as outfile:
            for fname in files:
                f = os.path.join(trans.dest_path, fname)
                with open(f, 'rb') as infile:
                    while True:
                        c = infile.read(CHUNK_READ_BUFFER)
                        if not c:
                            break
                        outfile.write(c)
                try:
                    os.remove(f)
                except Exception as e:
                    current_app.logger.warning(f"Unable to remove chunk file {f}. Exception: {e}")
        # check final file length and checksum
        if os.path.getsize(file) != trans.size:
            trans.status = TransferStatus.SIZE_ERROR
            db.session.commit()
            # os.remove(file)
            msg = f"Error on transfer '{transfer_id}': Final file size does not match expected size"
            current_app.logger.error(msg)
            return {"error": msg}, 404

        if md5(file) != trans.checksum:
            trans.status = TransferStatus.CHECKSUM_ERROR
            db.session.commit()
            # os.remove(file)
            msg = f"Error on transfer '{transfer_id}': Checksum error"
            current_app.logger.error(msg)
            return {"error": msg}, 404

        trans.status = TransferStatus.COMPLETED
        db.session.commit()
        msg = f"File {os.path.join(trans.dest_path, trans.filename)} from transfer {trans.id} recived successfully"
        current_app.logger.debug(msg)
        return {"message": msg}, 201
