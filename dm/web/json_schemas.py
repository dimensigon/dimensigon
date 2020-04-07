from dm.domain.entities import Scope, ActionType

UUID_pattern = "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"

schema_healthcheck = {
    "type": "object",
    "properties": {
        "action": {"type": "string",
                   "pattern": "^(reboot|stop)"},
    },
    "required": ["action"]
}

schema_lock = {
    "type": "object",
    "properties": {
        "scope": {"type": "string",
                  "pattern": f"^({'|'.join([s.name for s in Scope])})$"},
        "applicant": {"type": ["object", "array", "string"]},
        "action": {"type": "string",
                   "pattern": f"^(PREVENT|LOCK|UNLOCK)$"}
    },
    "required": ["scope", "applicant", "action"]
}

schema_software_send = {
    "type": "object",
    "properties": {
        "software_id": {"type": "string",
                        "pattern": UUID_pattern},
        "dest_server_id": {"type": "string",
                           "pattern": UUID_pattern},
        "dest_path": {"type": "string"},
        "chunk_size": {"type": "integer",
                       # "minimum": 1024 * 1024 * 2,
                       "maximum": 1024 * 1024 * 500,
                       # "multipleOf": 1024
                       },
        "max_senders": {"type": "integer",
                        "minimum": 0}
    },
    "required": ["software_id", "dest_server_id", "dest_path"]
}

post_software_schema = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "version": {"type": "string"},
        "family": {"type": "string"},
        "server_id": {"type": "string",
                      "pattern": UUID_pattern},
        "file": {"type": "string"}
    },
    "required": ["name", "version", "server_id", "file"],
    "dependencies": {
        "server_id": ["file"],
        "file": ["server_id"],
    }
}

patch_software_schema = {
    "type": "object",
    "properties": {
        "server_id": {"type": "string",
                      "pattern": UUID_pattern},
        "path": {"type": "string"},
    },
    "required": ["server_id", "path"]
}

put_software_servers_schema = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "server_id": {"type": "string",
                          "pattern": UUID_pattern},
            "file": {"type": "string"}
        },
        "required": ["server_id", "path"]
    }
}

post_action_template_schema = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "version": {"type": "integer",
                    "minimum": 1},
        "action_type": {"type": "string",
                        "pattern": f"^({'|'.join([at.name for at in ActionType])})$"},
        "code": {"type": "string"},
        "parameters": {"type": "object"},
        "expected_output": {"type": "string"},
        "expected_rc": {"type": "string"},
        "system_kwargs": {"type": "object"},
    },
    "required": ["name", "version", "action_type", "code"]
}

patch_schema_routes = {
    "type": "object",
    "properties": {
        "discover_new_neighbours": {"type": "boolean"},
        "check_current_neighbours": {"type": "boolean"},
        "server_id": {"type": "string",
                      "pattern": UUID_pattern},
        "server_list": {"type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string", "pattern": UUID_pattern},
                                "gateway": {"anyOf": [
                                    {"type": "string",
                                     "pattern": UUID_pattern},
                                    {"type": "null"}
                                ]},
                                "cost": {"anyOf": [
                                    {"type": "integer",
                                     "minimum": 0},
                                    {"type": "null"}
                                ]}
                            },
                            "required": ["id", "gateway", "cost"]
                        }
                        }
    }
}

post_schema_routes = {
    "type": "object",
    "properties": {
        "discover_new_neighbours": {"type": "boolean"},
        "check_current_neighbours": {"type": "boolean"}
    },
    "additionalProperties": False
}

schema_transfers = {
    "type": "object",
    "properties": {
        "software_id": {"type": "string",
                        "pattern": UUID_pattern},
        "dest_path": {"type": "string"},
        "filename": {"type": "string"},
        "num_chunks": {"type": "integer",
                       "minimum": 0},
        "force": {"type": "boolean"}
    },
    "required": ["software_id"]
}

schema_transfer = {
    "type": "object",
    "properties": {
        "transfer_id": {"type": "string",
                        "pattern": UUID_pattern},
        "chunk": {"type": "integer",
                  "minimum": 0},
        "content": {"type": "bytes"},
    },
    "required": ["transfer_id", "chunk", "content"]
}

schema_post_log = {
    "type": "object",
    "properties": {
        "file": {"type": "string"},
        "data": {"type": "string"},
    },
    "required": ["data"]
}

schema_create_log = {
    "type": "object",
    "properties": {
        "src_server_id": {"type": "string",
                          "pattern": UUID_pattern},
        "target": {"type": "string"},
        "include": {"type": "string"},
        "exclude": {"type": "string"},
        "dst_server_id": {"type": "string",
                          "pattern": UUID_pattern},
        "dest_folder": {"type": "string"},
        "recursive": {"type": "boolean"},
    },
    "required": ["src_server_id", "target", "dst_server_id"],
    "additionalProperties": False
}

schema_patch_log = {
    "type": "object",
    "properties": {
        "include": {"type": "string",
                    "format": "regex"},
        "exclude": {"type": "string",
                    "format": "regex"},
        "dest_folder": {"type": "string"},
        "recursive": {"type": "boolean"},
    },
    "additionalProperties": False
}

schema_create_user = {
    "type": "object",
    "properties": {
        "user": {"type": "string"},
        "password": {"type": "string"},
        "email": {"type": "string",
                  "format": "email"}
    },
    "required": ["user", "password", "email"],
    "additionalProperties": False
}

schema_patch_user = {
    "type": "object",
    "properties": {
        "email": {"type": "string",
                  "format": "email"},
        "active": {"type": "boolean"}
    },
    "additionalProperties": False
}
