import jsonschema
from flask import request, url_for
from flask_jwt_extended import jwt_required

from dm.domain.entities import Software, Server, SoftwareServerAssociation
from dm.use_cases.interactor import send_software
from dm.web import ajl
from dm.web.api_1_0 import api_bp
from dm.web.api_1_0.routes import UUID_pattern
from dm.web.decorators import securizer, forward_or_dispatch
from dm.web.extensions.job_background import TaskStatus

schema_software_send = {
    "type": "object",
    "properties": {
        "software_id": {"type": "string",
                        "pattern": UUID_pattern},
        "dest_server_id": {"type": "string",
                           "pattern": UUID_pattern},
        "dest_path": {"type": "string"},
        "chunk_size": {"type": "integer",
                       "minimum": 1024 * 1024 * 2,
                       "maximum": 1024 * 1024 * 500,
                       "multipleOf": 1024},
        "max_senders": {"type": "integer",
                        "minimum": 0}
    },
    "required": ["software_id", "dest_server_id", "dest_path"]
}


@api_bp.route('/software/send', methods=['POST'])
@securizer
@jwt_required
@forward_or_dispatch
def software_send():
    # Validate Data
    json = request.get_json()
    jsonschema.validate(json, schema_software_send)

    software = Software.query.get(json['software_id'])
    if not software:
        return {"error": f"Software id '{json['software_id']}' not found"}, 404
    dest_server = Server.query.get(json['dest_server_id'])
    if not dest_server:
        return {"error": f"Server id '{json['dest_server_id']}' not found"}, 404

    kwargs = {}

    if 'chunk_size' in json:
        kwargs.update(chunk_size=json.get('chunk_size'))
    if 'max_senders' in json:
        kwargs.update(max_senders=json.get('max_senders'))

    ssa = SoftwareServerAssociation.query.filter_by(server=dest_server, software=software)
    kwargs.update(ssa=ssa, dest_server=dest_server, dest_path=json.get('dest_path'))
    job_id = ajl.register(send_software, (), kwargs, priority=1)

    trans_id = ajl.queue.wait_data(job_id, 'transfer_id', timeout=20)
    if trans_id is None:
        status = ajl.queue.status(job_id)
        if status == TaskStatus.ERROR:
            return {'error': f"error on job_id: {job_id}", 'exception': str(ajl.queue.exception(job_id))}, 500
        elif status == TaskStatus.FINISHED:
            return {'error': f"Job id {job_id} ended but no data published"}, 500
        elif status in (TaskStatus.RUNNING, TaskStatus.PENDING):
            return {'message': f"Job is still running but no data published. "
                               f"Check job url for more information",
                    'job_id': job_id,
                    'url': url_for('api_1_0', job_id=job_id)}, 102

    return {'transfer_id': str(trans_id)}, 202
