from dimensigon.domain.entities import Scope, ActionType, LogMode
from dimensigon.domain.entities.transfer import Status

UUID_pattern = "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
Id = {"type": "string", "pattern": UUID_pattern}
Id_or_null = {"type": ["string", "null"],
              "pattern": UUID_pattern}
Multiline = {"type": ["string", "array", "null"],
             "items": {"type": "string"}}
Any = ["string", "integer", "number", "object", "array", "boolean", "null"]

login_post = {
    "type": "object",
    "properties": {
        "username": {"type": "string"},
        "password": {"type": "string"}

    },
    "required": ["username", "password"],
    "additionalProperties": False
}

healthcheck_post = {
    "type": "object",
    "properties": {
        "me": Id,
        "heartbeat": {"type": "string"},
    },
    "required": ["me", "heartbeat"],
    "additionalProperties": False
}

cluster_post = {
    "type": "array",
    "items": {"type": "object",
              "properties": {
                  "id": Id,
                  "keepalive": {"type": "string"},
                  "death": {"type": ["boolean", "null"]}
              },
              "required": ["id", "keepalive", "death"]
              }
}

locker_prevent_post = {
    "type": "object",
    "properties": {
        "scope": {"type": "string",
                  "pattern": f"^({'|'.join([s.name for s in Scope])})$"},
        "applicant": {"type": ["object", "array", "string"]},
        "datemark": {"type": "string"},
    },
    "required": ["scope", "applicant", "datemark"],
    "additionalProperties": False
}

locker_unlock_lock_post = {
    "type": "object",
    "properties": {
        "scope": {"type": "string",
                  "pattern": f"^({'|'.join([s.name for s in Scope])})$"},
        "applicant": {"type": ["object", "array", "string"]},
        "force": {"type": "boolean"},
    },
    "required": ["scope", "applicant"],
    "additionalProperties": False
}

manager_server_ignore_lock_post = {
    "type": "object",
    "properties": {
        "server_ids": {"type": "array",
                       "items": Id,
                       },
        "ignore_on_lock": {"type": "boolean"}
    },
    "required": ["ignore_on_lock", "server_ids"],
    "additionalProperties": False
}

send_post = {
    "type": "object",
    "properties": {
        "software_id": Id,
        "software": {"type": "string"},
        "version": {"type": "string"},
        "file": {"type": "string"},
        "dest_server_id": Id,
        "dest_path": {"type": "string"},
        "chunk_size": {"type": "integer",  # size in MB
                       "minimum": 1,
                       "maximum": 4 * 1024,
                       },
        "max_senders": {"type": "integer",
                        "minimum": 1},
        "background": {"type": "boolean"},
        "force": {"type": "boolean"},
        "include_transfer_data": {"type": "boolean"},
    },
    "oneOf": [{"required": ["software_id", "dest_server_id"]},
              {"required": ["software", "version", "dest_server_id"]},
              {"required": ["file", "dest_server_id", "dest_path"]}],
    "additionalProperties": False
}

software_post = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "version": {"type": "string"},
        "family": {"type": "string"},
        "file": {"type": "string"}
    },
    "required": ["name", "version", "file"],
    "additionalProperties": False
}

software_servers_put = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "server_id": Id,
            "file": {"type": "string"}
        },
        "required": ["server_id", "path"]
    },
    "additionalProperties": False
}

software_servers_patch = software_servers_put

software_servers_delete = {
    "type": "array",
    "items": Id,
    "additionalProperties": False
}

schema = {"type": "object",
          "properties": {
              "input": {"type": "object"},
              "required": {"type": "array",
                           "items": {"type": "string"}
                           },
              "output": {"type": "array",
                         "items": {"type": "string"}},
              "mapping": {"type": "object",
                          # "patternProperties": {
                          #     ".*": {"type": ["object",
                          #            "properties": {
                          #                "from": {"type": "string"},
                          #                "replace": {"type": "string"}
                          #            }}},
                          }
          }}

action_type_pattern = f"^({'|'.join([at.name for at in ActionType if at.name != 'NATIVE'])})$"
action_template_post = {
    "type": "object",
    "properties": {
        "name": {"type": "string",
                 "maxLength": 40},
        "description": Multiline,
        "action_type": {"type": "string",
                        "pattern": action_type_pattern},
        "code": Multiline,
        "schema": schema,
        "expected_stdout": Multiline,
        "expected_stderr": Multiline,
        "expected_rc": {"type": "integer"},
        "system_kwargs": {"type": "object"},
        "pre_process": Multiline,
        "post_process": Multiline,
    },
    "if": {
        "properties": {"action_type": {"const": "SEND"}}
    },
    "then": {
        "required": ["name", "action_type"],
    },
    "else": {
        "properties": {"code": Multiline},
        "required": ["name", "action_type", "code"],
    },
    "required": ["name", "action_type", "code"],
    "additionalProperties": False
}

action_template_patch = {
    "type": "object",
    "properties": {
        "description": Multiline,
        "action_type": {"type": "string",
                        "pattern": f"^({'|'.join([at.name for at in ActionType])})$"},
        "code": Multiline,
        "schema": schema,
        "expected_stdout": Multiline,
        "expected_stderr": Multiline,
        "expected_rc": {"type": "integer"},
        "system_kwargs": {"type": "object"},
        "pre_process": Multiline,
        "post_process": Multiline,
    },
    "additionalProperties": False
}

_step_post = {
    "type": "object",
    "properties": {
        "id": {"anyOf": [{"type": "string"},
                         {"type": "integer", "minimum": 1}]},
        "orchestration_id": Id,
        "undo": {"type": "boolean"},
        "name": {"type": "string",
                 "maxLength": 40},
        "description": Multiline,
        "stop_on_error": {"type": "boolean"},
        "stop_undo_on_error": {"type": "boolean"},
        "action_template_id": Id,
        "action_type": {"type": "string",
                        "pattern": action_type_pattern},
        "undo_on_error": {"type": "boolean"},
        "code": Multiline,
        "schema": schema,
        "expected_stdout": Multiline,
        "expected_stderr": Multiline,
        "expected_rc": {"type": "integer"},
        "system_kwargs": {"type": "object"},
        "pre_process": Multiline,
        "post_process": Multiline,
        "parent_step_ids": {"type": "array",
                            "items": {"anyOf": [Id,
                                                {"type": "integer", "minimum": 1}]
                                      }
                            },
        "target": {"anyOf": [{"type": "string"},
                             {"type": "array", "items": {"type": "string"}}]}
    },
    "oneOf": [{"required": ["orchestration_id", "undo", "action_template_id"]},
              {"required": ["orchestration_id", "undo", "action_type"]}],
    "additionalProperties": False
}

step_post = {
    "anyOf": [
        {"type": "array",
         "items": _step_post},
        _step_post
    ]
}

step_put = {
    "type": "object",
    "properties": {
        "undo": {"type": "boolean"},
        "stop_on_error": {"type": "boolean"},
        "stop_undo_on_error": {"type": "boolean"},
        "undo_on_error": {"type": "boolean"},
        "action_template_id": Id,
        "action_type": {"type": "string",
                        "pattern": action_type_pattern},

        "code": Multiline,
        "schema": schema,
        "expected_stdout": Multiline,
        "expected_stderr": Multiline,
        "expected_rc": {"type": "integer"},
        "system_kwargs": {"type": "object"},
        "pre_process": Multiline,
        "post_process": Multiline,
        "name": {"type": "string",
                 "maxLength": 40},
        "description": Multiline,
        "parent_step_ids": {"type": "array",
                            "items": {"anyOf": [Id,
                                                {"type": "integer", "minimum": 1}]
                                      }
                            },
        "child_step_ids": {"type": "array",
                           "items": {"anyOf": [Id,
                                               {"type": "integer", "minimum": 1}]
                                     }
                           },
        "target": {"anyOf": [{"type": "string"},
                             {"type": "array", "items": {"type": "string"}}]}
    },
    "oneOf": [{"required": ["undo", "action_template_id"]},
              {"required": ["undo", "action_type"]}],
    "additionalProperties": False
}

step_patch = {
    "type": "object",
    "properties": {
        "undo": {"type": "boolean"},
        "stop_on_error": {"type": "boolean"},
        "stop_undo_on_error": {"type": "boolean"},
        "action_template_id": Id,
        "action_type": {"type": "string",
                        "pattern": action_type_pattern},
        "undo_on_error": {"type": "boolean"},
        "code": {"anyOf": [{"type": "string"},
                           {"type": "array",
                            "items": {"type": "string"}}]},
        "parameters": {"type": "object"},
        "schema": schema,
        "expected_stdout": Multiline,
        "expected_stderr": Multiline,
        "expected_rc": {"type": "integer"},
        "system_kwargs": {"type": "object"},
        "pre_process": Multiline,
        "post_process": Multiline,
        "name": {"type": "string",
                 "maxLength": 40},
        "description": {"type": "string"},
        "parent_step_ids": {"type": "array",
                            "items": {"anyOf": [Id,
                                                {"type": "integer", "minimum": 1}]
                                      }
                            },
        "child_step_ids": {"type": "array",
                           "items": {"anyOf": [Id,
                                               {"type": "integer", "minimum": 1}]
                                     }
                           },
        "target": {"anyOf": [{"type": "string"},
                             {"type": "array", "items": {"type": "string"}}]}
    },
    "additionalProperties": False
}

step_parents = {
    "type": "object",
    "properties": {
        "parent_step_ids": {"type": "array", "items": Id},
        "additionalProperties": False
    }
}

step_children = {
    "type": "object",
    "properties": {
        "children_step_ids": {"type": "array", "items": Id},
        "additionalProperties": False
    }
}

routes_patch = {
    "type": "object",
    "properties": {
        "server_id": Id,
        "route_list": {"type": "array",
                       "items": {
                           "type": "object",
                           "properties": {
                               "destination_id": Id,
                               "proxy_server_id": Id_or_null,
                               "gate_id": Id_or_null,
                               "cost": {"anyOf": [
                                   {"type": "integer",
                                    "minimum": 0},
                                   {"type": "null"}
                               ]}
                           },
                           "required": ["destination_id", "gate_id", "cost"]
                       }
                       },
        "exclude": {"type": "array",
                    "items": Id}
    },
    "additionalProperties": False,
    "required": ["server_id", "route_list"]
}

routes_post = {
    "type": "object",
    "properties": {
        "discover_new_neighbours": {"type": "boolean"},
        "check_current_neighbours": {"type": "boolean"},
        "max_num_discovery": {"type": ["integer", "null"],
                              "minimum": 1}
    },
    "additionalProperties": False
}

orchestration_post = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "description": {"type": "string"},
        "stop_on_error": {"type": "boolean"},
        "stop_undo_on_error": {"type": "boolean"},
        "undo_on_error": {"type": "boolean"}
    },
    "required": ["name"],
    "additionalProperties": False
}

orchestration_step = {
    "type": "object",
    "properties": {
        "id": {"type": ["string", "integer"]},
        "undo": {"type": "boolean"},
        "name": {"type": "string"},
        "stop_on_error": {"type": "boolean"},
        "stop_undo_on_error": {"type": "boolean"},
        "action_template_id": Id,
        "action_type": {"type": "string",
                        "pattern": action_type_pattern},
        "undo_on_error": {"type": "boolean"},
        "code": Multiline,
        "schema": schema,
        "expected_stdout": Multiline,
        "expected_stderr": Multiline,
        "expected_rc": {"type": ["integer", "null"]},
        "system_kwargs": {"type": "object"},
        "pre_process": Multiline,
        "post_process": Multiline,
        "parent_step_ids": {"type": "array",
                            "items": {"type": ["string", "integer"]}
                            },
        "target": {"type": ["string", "array", "null"],
                   "items": {"type": "string"}}
    },
    "oneOf": [{"required": ["undo", "action_template_id"]},
              {"required": ["undo", "action_type"]}],
    "additionalProperties": False
}

orchestration_full = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "description": Multiline,
        "stop_on_error": {"type": "boolean"},
        "stop_undo_on_error": {"type": "boolean"},
        "undo_on_error": {"type": "boolean"},
        "steps": {"type": "array",
                  "items": orchestration_step}
    },
    "required": ["name", "steps"],
    "additionalProperties": False
}

orchestration_patch = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "version": {"type": "integer", "minimum": 1},
        "description": Multiline,
        "stop_on_error": {"type": "boolean"},
        "stop_undo_on_error": {"type": "boolean"},
        "undo_on_error": {"type": "boolean"}
    },
    "additionalProperties": False
}

launch_orchestration_post = {
    "type": "object",
    "properties": {
        'hosts': {"type": ["string", "array", "object"],
                  "items": {"type": "string"},
                  "minItems": 1,
                  "patternProperties": {
                      ".*": {"anyOf": [{"type": "string"},
                                       {"type": "array",
                                        "items": {"type": "string"},
                                        "minItems": 1
                                        },
                                       ]
                             },
                  },
                  },
        "params": {"type": ["object", "null"]},
        "background": {"type": "boolean"},
        "skip_validation": {"type": "boolean"},
        "scope": {"type": "string"},
        "timeout": {"type": "integer"}
    },
    "required": ["hosts"],
    "additionalProperties": False,
}

transfers_post = {
    "type": "object",
    "properties": {
        "software_id": Id,
        "filename": {"type": "string"},  # specify filename if you want to send a file instead of a software
        "size": {"type": "integer"},
        "checksum": {"type": "string"},
        "dest_path": {"type": "string"},  # if not specified DM_SOFTWARE_REPO is used
        "num_chunks": {"type": "integer",
                       "minimum": 0},
        "cancel_pending": {"type": "boolean"},  # cancels pending transfers from the same file in the same folder
        "force": {"type": "boolean"},  # forces to transfer file even if it exists in the destination

    },
    "oneOf": [{"required": ["num_chunks", "software_id"]},
              {"required": ["num_chunks", "filename", "dest_path", "size", "checksum"]}],
    "additionalProperties": False
}

transfer_post = {
    "type": "object",
    "properties": {
        "chunk": {"type": "integer",
                  "minimum": 0},
        "content": {"type": "string"},
    },
    "required": ["chunk", "content"],
    "additionalProperties": False
}

transfer_patch = {
    "type": "object",
    "properties": {
        "status": {"type": "string",
                   "pattern": f"^({'|'.join([s.name for s in Status])})$"},
    },
    "required": ["status"],
    "additionalProperties": False
}

logs_post = {
    "type": "object",
    "properties": {
        "src_server_id": Id,
        "target": {"type": "string"},
        "include": {"type": "string"},
        "exclude": {"type": "string"},
        "dst_server_id": Id,
        "dest_folder": {"type": "string"},
        "recursive": {"type": "boolean"},
        "mode": {"type": "string",
                 "pattern": f"^({'|'.join([m.name for m in LogMode])})$"}
    },
    "additionalProperties": False,
    "required": ["src_server_id", "target", "dst_server_id"],
}

log_patch = {
    "type": "object",
    "properties": {
        "include": {"type": "string",
                    "format": "regex"},
        "exclude": {"type": "string",
                    "format": "regex"},
        "dest_folder": {"type": "string"},
        "recursive": {"type": "boolean"},
        "mode": {"type": "string",
                 "pattern": f"^({'|'.join([m.name for m in LogMode])})$"}
    },
    "additionalProperties": False
}

log_post = {
    "type": "object",
    "properties": {
        "file": {"type": "string"},
        "data": {"type": "string"},
        "compress": {"type": "boolean"}
    },
    "required": ["data"],
    "additionalProperties": False
}

users_post = {
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

user_patch = {
    "type": "object",
    "properties": {
        "email": {"type": "string",
                  "format": "email"},
        "active": {"type": "boolean"}
    },
    "additionalProperties": False
}

launch_command_post = {
    "type": "object",
    "properties": {
        "command": {"type": "string"},
        "target": {"anyOf": [{"type": "string"},
                             {"type": "array",
                              "items": {"type": "string"}},
                             ]
                   },
        "timeout": {"type": "integer",
                    "minimum": 1},
        "input": {"type": "string"},
    },
    "required": ["command"],
    "additionalProperties": False,
}

servers_delete = {
    "type": "object",
    "properties": {"server_ids": {"type": "array",
                                  "items": Id}
                   },
    "additionalProperties": False,
    "required": ["server_ids"]
}

server_post = {
    "type": "object",
    "properties": {
        # "gates": {"type": "object",
        #           "properties": {
        #               "dns_or_ip": {"type": "string"},
        #               "port": {"type": "integer",
        #                        "minimum": 1,
        #                        "maximum": 65535},
        #               "hidden": {"type": "boolean"},
        #               "required": ["dns_or_ip", "port"],
        #               "additionalProperties": False,
        #           }},
        "granules": {"type": "array",
                     "items": {"type": "string"}}
    },
    "additionalProperties": False,
    "required": ["granules"]
}

server_patch = {
    "type": "object",
    "properties": {
        "gates": {"type": "array",
                  "items": {"type": "object",
                            "properties": {
                                "dns_or_ip": {"type": "string"},
                                "port": {"type": "integer",
                                         "minimum": 1,
                                         "maximum": 65535},
                                "hidden": {"type": "boolean"},

                            },
                            "required": ["dns_or_ip", "port"],
                            "additionalProperties": False,
                            }
                  },
        "granules": {"type": "array",
                     "items": {"type": "string"}},
        "ignore_on_lock": {"type": "boolean"},
    },
    "additionalProperties": False,
}

files_post = {
    "properties": {
        "src_server_id": Id,
        "target": {"type": "string"},
        "dest_folder": {"type": "string"},
        "destinations": {"type": "array",
                         "items": {"type": "object",
                                   "properties": {
                                       "dst_server_id": Id,
                                       "dest_folder": {"type": "string"}
                                   },
                                   "required": ["dst_server_id"],
                                   "additionalProperties": False
                                   }
                         }
    },
    "required": ["src_server_id", "target", 'destinations'],
    "additionalProperties": False
}

file_post = files_post

file_patch = {
    "properties": {
        "src_server_id": Id,
        "target": {"type": "string"},
        "dest_folder": {"type": "string"},
        "destinations": {"type": "array",
                         "items": {"type": "object",
                                   "properties": {
                                       "dst_server_id": Id,
                                       "dest_folder": {"type": "string"}

                                   },
                                   "required": ["dst_server_id"],
                                   "additionalProperties": False
                                   }
                         }
    },
    "additionalProperties": False
}

file_sync = {
    "type": "object",
    "properties": {
        "file": {"type": "string"},
        "data": {"type": "string"},
        "force": {"type": "boolean"}

    },
    "required": ["data", "file"],
    "additionalProperties": False
}

destination = {"type": "object",
               "properties": {
                   "dst_server_id": Id,
                   "dest_folder": {"type": ["string", "null"]}

               },
               "required": ["dst_server_id"],
               "additionalProperties": False
               }

file_server_associations_post = {
    "anyOf": [destination,
              {"type": "array",
               "items": destination}
              ]
}

file_server_associations_patch = file_server_associations_post

file_server_associations_delete = file_server_associations_post

vaults_post = {
    "type": "object",
    "properties": {
        "scope": {"type": "string"},
        "name": {"type": "string"},
        "value": {"type": Any},

    },
    "required": ["name", "value"]
}

vault_post = {
    "type": "object",
    "properties": {
        "value": {"type": Any},

    },
    "required": ["value"]
}

vault_put = vault_post
