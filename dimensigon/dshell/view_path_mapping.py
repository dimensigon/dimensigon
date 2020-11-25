view_path_map = {'api_1_0.actiontemplatelist': '/api/v1.0/action_templates',
                 'api_1_0.actiontemplateresource': '/api/v1.0/action_templates/<action_template_id>',
                 'api_1_0.catalog': '/api/v1.0/catalog/<string:data_mark>',
                 'api_1_0.catalog_update': '/api/v1.0/catalog',
                 'api_1_0.cluster': '/api/v1.0/cluster',
                 'api_1_0.cluster_in': '/api/v1.0/cluster/in/<server_id>',
                 'api_1_0.cluster_out': '/api/v1.0/cluster/out/<server_id>',
                 'api_1_0.events': '/api/v1.0/events/<event_id>',
                 'api_1_0.file_sync': '/api/v1.0/file/<file_id>/sync',
                 'api_1_0.filelist': '/api/v1.0/file',
                 'api_1_0.fileresource': '/api/v1.0/file/<file_id>',
                 'api_1_0.fileserverassociationlist': '/api/v1.0/file/<file_id>/destinations',
                 'api_1_0.granulelist': '/api/v1.0/granules',
                 'api_1_0.home': '/api/v1.0/',
                 'api_1_0.internal_server': '/api/v1.0/manager/server_ignore_lock',
                 'api_1_0.join': '/api/v1.0/join',
                 'api_1_0.join_acknowledge': '/api/v1.0/join/acknowledge/<server_id>',
                 'api_1_0.join_public': '/api/v1.0/join/public',
                 'api_1_0.join_token': '/api/v1.0/join/token',
                 'api_1_0.launch_command': '/api/v1.0/launch/command',
                 'api_1_0.launch_operation': '/api/v1.0/launch/operation',
                 'api_1_0.launch_orchestration': '/api/v1.0/launch/orchestration/<orchestration_id>',
                 'api_1_0.locker': '/api/v1.0/locker',
                 'api_1_0.locker_lock': '/api/v1.0/locker/lock',
                 'api_1_0.locker_prevent': '/api/v1.0/locker/prevent',
                 'api_1_0.locker_unlock': '/api/v1.0/locker/unlock',
                 'api_1_0.loglist': '/api/v1.0/log',
                 'api_1_0.logresource': '/api/v1.0/log/<log_id>',
                 'api_1_0.orchestrationexecutionrelationship': '/api/v1.0/orchestrations/<orchestration_id>/executions',
                 'api_1_0.orchestrationlist': '/api/v1.0/orchestrations',
                 'api_1_0.orchestrationresource': '/api/v1.0/orchestrations/<orchestration_id>',
                 'api_1_0.orchestrations_full': '/api/v1.0/orchestrations/full',
                 'api_1_0.orchexecstepexecrelationship': '/api/v1.0/orchestration_executions/<execution_id>/step_executions',
                 'api_1_0.orchexecutionlist': '/api/v1.0/orchestration_executions',
                 'api_1_0.orchexecutionresource': '/api/v1.0/orchestration_executions/<execution_id>',
                 'api_1_0.routes': '/api/v1.0/routes',
                 'api_1_0.send': '/api/v1.0/send',
                 'api_1_0.serverlist': '/api/v1.0/servers',
                 'api_1_0.serverresource': '/api/v1.0/servers/<server_id>',
                 'api_1_0.software_dimensigon': '/api/v1.0/software/dimensigon',
                 'api_1_0.softwarelist': '/api/v1.0/software',
                 'api_1_0.softwareresource': '/api/v1.0/software/<software_id>',
                 'api_1_0.softwareserversresource': '/api/v1.0/software/<software_id>/servers',
                 'api_1_0.stepexecutionlist': '/api/v1.0/step_executions',
                 'api_1_0.stepexecutionresource': '/api/v1.0/step_executions/<execution_id>',
                 'api_1_0.steplist': '/api/v1.0/steps',
                 'api_1_0.steprelationshipchildren': '/api/v1.0/steps/<step_id>/relationship/children',
                 'api_1_0.steprelationshipparents': '/api/v1.0/steps/<step_id>/relationship/parents',
                 'api_1_0.stepresource': '/api/v1.0/steps/<step_id>',
                 'api_1_0.transferlist': '/api/v1.0/transfers',
                 'api_1_0.transferresource': '/api/v1.0/transfers/<transfer_id>',
                 'api_1_0.userlist': '/api/v1.0/users',
                 'api_1_0.userresource': '/api/v1.0/users/<user_id>',
                 'api_1_0.vaultlist': '/api/v1.0/vault',
                 'api_1_0.vaultresource': '/api/v1.0/vault/<scope>/<name>',
                 'root.fresh_login': '/fresh-login',
                 'root.healthcheck': '/healthcheck',
                 'root.home': '/',
                 'root.login': '/login',
                 'root.ping': '/ping',
                 'root.refresh': '/refresh',
                 'static': '/static/<path:filename>'}
