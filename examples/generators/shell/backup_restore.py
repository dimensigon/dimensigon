"""Shell action generators for backup and restore operations."""

from examples.generators.base_generator import ShellActionGenerator


class BackupRestoreGenerator(ShellActionGenerator):
    category = "shell.backup_restore"
    subcategory = "backup_restore"

    def seeds(self):
        return [
            {
                'name': 'pg-dump-full',
                'template': {
                    'name': '{db}-pg-dump-full',
                    'action_type': 'SHELL',
                    'code': 'TIMESTAMP=$(date +%Y%m%d_%H%M%S) && DUMP_FILE="{{input.backup_dir}}/{{input.database}}_${TIMESTAMP}.sql.gz" && mkdir -p {{input.backup_dir}} && pg_dump -h {{input.host}} -U {{input.username}} -d {{input.database}} --no-password -Fc | gzip > "$DUMP_FILE" && FILESIZE=$(du -sh "$DUMP_FILE" | cut -f1) && echo "Backup completed: $DUMP_FILE ($FILESIZE)" || (echo "FAILED: pg_dump error" >&2; exit 1)',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'host': {'type': 'string', 'description': 'PostgreSQL host address'},
                            'username': {'type': 'string', 'description': 'Database user for authentication'},
                            'database': {'type': 'string', 'description': 'Name of the database to dump'},
                            'backup_dir': {'type': 'string', 'description': 'Directory to store the backup file'},
                        },
                        'required': ['host', 'username', 'database', 'backup_dir'],
                    },
                },
                'params': {'db': ['production', 'staging', 'analytics', 'warehouse']},
                'prompts': [
                    'Create a full pg_dump backup of the {db} PostgreSQL database',
                    'Write a DM action to dump the {db} database with compression',
                    'Generate a shell action for a compressed pg_dump of {db}',
                ],
                'explanation': 'Creates a full compressed pg_dump backup of the {db} PostgreSQL database with a timestamp.',
                'features': ['schema_variables'],
            },
            {
                'name': 'mysqldump-compressed',
                'template': {
                    'name': '{db}-mysqldump',
                    'action_type': 'SHELL',
                    'code': 'TIMESTAMP=$(date +%Y%m%d_%H%M%S) && DUMP_FILE="{{input.backup_dir}}/{{input.database}}_${TIMESTAMP}.sql.gz" && mkdir -p {{input.backup_dir}} && mysqldump -h {{input.host}} -u {{input.username}} --single-transaction --routines --triggers --events {{input.database}} 2>/dev/null | gzip > "$DUMP_FILE" && FILESIZE=$(du -sh "$DUMP_FILE" | cut -f1) && echo "MySQL dump completed: $DUMP_FILE ($FILESIZE)" || (echo "FAILED: mysqldump error" >&2; exit 1)',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'host': {'type': 'string', 'description': 'MySQL host address'},
                            'username': {'type': 'string', 'description': 'MySQL user for authentication'},
                            'database': {'type': 'string', 'description': 'Name of the database to dump'},
                            'backup_dir': {'type': 'string', 'description': 'Directory to store the backup file'},
                        },
                        'required': ['host', 'username', 'database', 'backup_dir'],
                    },
                },
                'params': {'db': ['production', 'staging', 'wordpress', 'app']},
                'prompts': [
                    'Create a compressed mysqldump of the {db} database',
                    'Write a DM action for a full MySQL backup of {db} with compression',
                    'Generate a shell action to dump {db} MySQL database',
                ],
                'explanation': 'Creates a compressed mysqldump of the {db} MySQL database with transactions, routines, and triggers preserved.',
                'features': ['schema_variables'],
            },
            {
                'name': 'mongodump-directory',
                'template': {
                    'name': '{db}-mongodump',
                    'action_type': 'SHELL',
                    'code': 'TIMESTAMP=$(date +%Y%m%d_%H%M%S) && DUMP_DIR="{{input.backup_dir}}/{{input.database}}_${TIMESTAMP}" && mkdir -p "$DUMP_DIR" && mongodump --host {{input.host}} --port {{input.port}} --db {{input.database}} --out "$DUMP_DIR" --gzip 2>&1 && FILECOUNT=$(find "$DUMP_DIR" -type f | wc -l) && echo "Mongodump completed: $DUMP_DIR ($FILECOUNT files)" || (echo "FAILED: mongodump error" >&2; exit 1)',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'host': {'type': 'string', 'description': 'MongoDB host address'},
                            'port': {'type': 'integer', 'description': 'MongoDB port number'},
                            'database': {'type': 'string', 'description': 'Name of the database to dump'},
                            'backup_dir': {'type': 'string', 'description': 'Parent directory for the dump output'},
                        },
                        'required': ['host', 'port', 'database', 'backup_dir'],
                    },
                },
                'params': {'db': ['production', 'staging', 'logs', 'analytics']},
                'prompts': [
                    'Create a mongodump backup of the {db} database to a directory',
                    'Write a DM action for a compressed MongoDB dump of {db}',
                    'Generate a shell action to dump {db} MongoDB database with gzip',
                ],
                'explanation': 'Creates a compressed mongodump of the {db} MongoDB database to a timestamped directory.',
                'features': ['schema_variables'],
            },
            {
                'name': 'redis-bgsave',
                'template': {
                    'name': '{env}-redis-bgsave',
                    'action_type': 'SHELL',
                    'code': 'LAST_SAVE=$(redis-cli -h {{input.host}} -p {{input.port}} LASTSAVE | awk \'{print $1}\') && redis-cli -h {{input.host}} -p {{input.port}} BGSAVE && sleep 2 && RETRIES=0 && while [ $RETRIES -lt 30 ]; do NEW_SAVE=$(redis-cli -h {{input.host}} -p {{input.port}} LASTSAVE | awk \'{print $1}\'); if [ "$NEW_SAVE" != "$LAST_SAVE" ]; then echo "BGSAVE completed at $(date -d @$NEW_SAVE 2>/dev/null || echo $NEW_SAVE)"; exit 0; fi; sleep 1; RETRIES=$((RETRIES+1)); done; echo "FAILED: BGSAVE did not complete within 30 seconds" >&2; exit 1',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'host': {'type': 'string', 'description': 'Redis host address'},
                            'port': {'type': 'integer', 'description': 'Redis port number'},
                        },
                        'required': ['host', 'port'],
                    },
                },
                'params': {'env': ['production', 'staging', 'cache', 'session']},
                'prompts': [
                    'Trigger a Redis BGSAVE on the {env} instance',
                    'Create a DM action to initiate a background save on {env} Redis',
                    'Write a shell action to run BGSAVE on {env} Redis and verify completion',
                ],
                'explanation': 'Triggers a Redis BGSAVE on the {env} instance and waits for it to complete.',
                'features': ['schema_variables'],
            },
            {
                'name': 'tar-full-system-backup',
                'template': {
                    'name': '{target}-tar-backup',
                    'action_type': 'SHELL',
                    'code': 'TIMESTAMP=$(date +%Y%m%d_%H%M%S) && ARCHIVE="{{input.backup_dir}}/{{input.backup_name}}_${TIMESTAMP}.tar.gz" && mkdir -p {{input.backup_dir}} && tar czf "$ARCHIVE" --exclude={{input.backup_dir}} --exclude=/proc --exclude=/sys --exclude=/dev --exclude=/run --exclude=/tmp --exclude=/mnt --exclude=/media --exclude=/lost+found {{input.source_dir}} 2>&1 && FILESIZE=$(du -sh "$ARCHIVE" | cut -f1) && echo "Full backup completed: $ARCHIVE ($FILESIZE)" || (echo "FAILED: tar backup error" >&2; exit 1)',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'source_dir': {'type': 'string', 'description': 'Root directory to back up (e.g. /)'},
                            'backup_dir': {'type': 'string', 'description': 'Directory to store the archive'},
                            'backup_name': {'type': 'string', 'description': 'Base name for the backup archive'},
                        },
                        'required': ['source_dir', 'backup_dir', 'backup_name'],
                    },
                },
                'params': {'target': ['system', 'server', 'host', 'node']},
                'prompts': [
                    'Create a full tar backup of the {target}',
                    'Write a DM action for a compressed system-level tar backup of {target}',
                    'Generate a shell action to archive the entire {target} filesystem',
                ],
                'explanation': 'Creates a compressed tar archive of the full {target} filesystem, excluding virtual filesystems.',
                'features': ['schema_variables'],
            },
            {
                'name': 'rsync-incremental',
                'template': {
                    'name': '{target}-rsync-incremental',
                    'action_type': 'SHELL',
                    'code': 'mkdir -p {{input.dest_dir}} && rsync -avz --delete --stats --link-dest={{input.link_dest}} {{input.source_dir}}/ {{input.dest_dir}}/ 2>&1 && echo "Incremental rsync backup completed to {{input.dest_dir}}" || (echo "FAILED: rsync error" >&2; exit 1)',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'source_dir': {'type': 'string', 'description': 'Source directory to back up'},
                            'dest_dir': {'type': 'string', 'description': 'Destination directory for this backup'},
                            'link_dest': {'type': 'string', 'description': 'Previous backup directory for hard-link based incrementals'},
                        },
                        'required': ['source_dir', 'dest_dir', 'link_dest'],
                    },
                },
                'params': {'target': ['daily', 'hourly', 'webapp', 'data']},
                'prompts': [
                    'Run an incremental rsync backup for {target} data',
                    'Create a DM action for an rsync incremental {target} backup with hard links',
                    'Write a shell action for {target} rsync backup using link-dest',
                ],
                'explanation': 'Performs an incremental rsync backup for {target} data using hard links to save space.',
                'features': ['schema_variables'],
            },
            {
                'name': 'etcd-snapshot-save',
                'template': {
                    'name': '{env}-etcd-snapshot',
                    'action_type': 'SHELL',
                    'code': 'TIMESTAMP=$(date +%Y%m%d_%H%M%S) && SNAP_FILE="{{input.backup_dir}}/etcd_snapshot_${TIMESTAMP}.db" && mkdir -p {{input.backup_dir}} && ETCDCTL_API=3 etcdctl snapshot save "$SNAP_FILE" --endpoints={{input.endpoints}} --cacert={{input.ca_cert}} --cert={{input.client_cert}} --key={{input.client_key}} 2>&1 && ETCDCTL_API=3 etcdctl snapshot status "$SNAP_FILE" --write-out=table 2>&1 && echo "etcd snapshot saved: $SNAP_FILE" || (echo "FAILED: etcd snapshot error" >&2; exit 1)',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'backup_dir': {'type': 'string', 'description': 'Directory to store the snapshot'},
                            'endpoints': {'type': 'string', 'description': 'etcd endpoint URL (e.g. https://127.0.0.1:2379)'},
                            'ca_cert': {'type': 'string', 'description': 'Path to CA certificate file'},
                            'client_cert': {'type': 'string', 'description': 'Path to client certificate file'},
                            'client_key': {'type': 'string', 'description': 'Path to client key file'},
                        },
                        'required': ['backup_dir', 'endpoints', 'ca_cert', 'client_cert', 'client_key'],
                    },
                },
                'params': {'env': ['production', 'staging', 'k8s-cluster', 'dr']},
                'prompts': [
                    'Create an etcd snapshot backup for the {env} cluster',
                    'Write a DM action to save an etcd snapshot for {env}',
                    'Generate a shell action for etcd backup on {env} with TLS',
                ],
                'explanation': 'Creates an etcd v3 snapshot backup for the {env} cluster with TLS authentication.',
                'features': ['schema_variables'],
                'difficulty': 'intermediate',
            },
            {
                'name': 'lvm-snapshot-create',
                'template': {
                    'name': '{target}-lvm-snapshot',
                    'action_type': 'SHELL',
                    'code': 'SNAP_NAME="{{input.lv_name}}_snap_$(date +%Y%m%d_%H%M%S)" && lvcreate --size {{input.snap_size}} --snapshot --name "$SNAP_NAME" {{input.vg_name}}/{{input.lv_name}} 2>&1 && lvs {{input.vg_name}}/"$SNAP_NAME" 2>&1 && echo "LVM snapshot created: $SNAP_NAME (size: {{input.snap_size}})" || (echo "FAILED: LVM snapshot creation error" >&2; exit 1)',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'vg_name': {'type': 'string', 'description': 'Volume group name'},
                            'lv_name': {'type': 'string', 'description': 'Logical volume name to snapshot'},
                            'snap_size': {'type': 'string', 'description': 'Size for the snapshot (e.g. 5G, 10G)'},
                        },
                        'required': ['vg_name', 'lv_name', 'snap_size'],
                    },
                },
                'params': {'target': ['data', 'root', 'database', 'app']},
                'prompts': [
                    'Create an LVM snapshot of the {target} logical volume',
                    'Write a DM action to take an LVM snapshot for {target} before maintenance',
                    'Generate a shell action for LVM snapshot creation on {target}',
                ],
                'explanation': 'Creates an LVM snapshot of the {target} logical volume for point-in-time recovery.',
                'features': ['schema_variables'],
                'difficulty': 'intermediate',
            },
            {
                'name': 'file-restore-from-backup',
                'template': {
                    'name': '{target}-file-restore',
                    'action_type': 'SHELL',
                    'code': 'if [ ! -f "{{input.backup_archive}}" ]; then echo "FAILED: Backup archive not found: {{input.backup_archive}}" >&2; exit 1; fi && echo "Restoring {{input.file_path}} from {{input.backup_archive}}" && mkdir -p "{{input.restore_dir}}" && tar xzf "{{input.backup_archive}}" -C "{{input.restore_dir}}" "{{input.file_path}}" 2>&1 && if [ -f "{{input.restore_dir}}/{{input.file_path}}" ]; then echo "File restored to {{input.restore_dir}}/{{input.file_path}}"; else echo "FAILED: File not found in archive" >&2; exit 1; fi',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'backup_archive': {'type': 'string', 'description': 'Path to the tar.gz backup archive'},
                            'file_path': {'type': 'string', 'description': 'Relative path of the file inside the archive to restore'},
                            'restore_dir': {'type': 'string', 'description': 'Directory to restore the file into'},
                        },
                        'required': ['backup_archive', 'file_path', 'restore_dir'],
                    },
                },
                'params': {'target': ['config', 'data', 'application', 'database']},
                'prompts': [
                    'Restore a {target} file from a tar backup archive',
                    'Create a DM action to extract a specific {target} file from backup',
                    'Write a shell action that restores a {target} file from a tar.gz archive',
                ],
                'explanation': 'Restores a specific {target} file from a tar.gz backup archive to a given directory.',
                'features': ['schema_variables'],
            },
            {
                'name': 'backup-rotation',
                'template': {
                    'name': '{target}-backup-rotation',
                    'action_type': 'SHELL',
                    'code': 'BACKUP_DIR="{{input.backup_dir}}" && KEEP={{input.keep_count}} && if [ ! -d "$BACKUP_DIR" ]; then echo "FAILED: Backup directory not found: $BACKUP_DIR" >&2; exit 1; fi && TOTAL=$(ls -1t "$BACKUP_DIR"/{{input.file_pattern}} 2>/dev/null | wc -l) && if [ "$TOTAL" -le "$KEEP" ]; then echo "No rotation needed: $TOTAL backups found, keeping $KEEP"; exit 0; fi && DELETE_COUNT=$((TOTAL - KEEP)) && ls -1t "$BACKUP_DIR"/{{input.file_pattern}} | tail -n "$DELETE_COUNT" | xargs rm -f && echo "Rotation complete: deleted $DELETE_COUNT old backups, kept $KEEP newest"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'backup_dir': {'type': 'string', 'description': 'Directory containing backup files'},
                            'file_pattern': {'type': 'string', 'description': 'Glob pattern to match backup files (e.g. *.sql.gz, *.tar.gz)'},
                            'keep_count': {'type': 'integer', 'description': 'Number of most recent backups to keep'},
                        },
                        'required': ['backup_dir', 'file_pattern', 'keep_count'],
                    },
                },
                'params': {'target': ['daily', 'weekly', 'database', 'system']},
                'prompts': [
                    'Rotate {target} backups keeping only the last N files',
                    'Create a DM action for {target} backup rotation by count',
                    'Write a shell action that cleans up old {target} backups',
                ],
                'explanation': 'Rotates {target} backups by deleting the oldest files and keeping only the specified number.',
                'features': ['schema_variables'],
            },
            {
                'name': 'backup-integrity-verify',
                'template': {
                    'name': '{target}-backup-verify',
                    'action_type': 'SHELL',
                    'code': 'if [ ! -f "{{input.backup_file}}" ]; then echo "FAILED: Backup file not found: {{input.backup_file}}" >&2; exit 1; fi && echo "Computing SHA-256 checksum..." && COMPUTED=$(sha256sum "{{input.backup_file}}" | awk \'{print $1}\') && if [ -n "{{input.expected_checksum}}" ]; then if [ "$COMPUTED" = "{{input.expected_checksum}}" ]; then echo "VERIFIED: Checksum matches ($COMPUTED)"; else echo "FAILED: Checksum mismatch (expected: {{input.expected_checksum}}, got: $COMPUTED)" >&2; exit 1; fi; else echo "SHA-256: $COMPUTED"; echo "$COMPUTED  {{input.backup_file}}" >> "{{input.backup_file}}.sha256"; echo "Checksum saved to {{input.backup_file}}.sha256"; fi',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'backup_file': {'type': 'string', 'description': 'Path to the backup file to verify'},
                            'expected_checksum': {'type': 'string', 'description': 'Expected SHA-256 checksum (leave empty to generate)'},
                        },
                        'required': ['backup_file'],
                    },
                },
                'params': {'target': ['database', 'system', 'archive', 'snapshot']},
                'prompts': [
                    'Verify the integrity of a {target} backup using SHA-256',
                    'Create a DM action to check a {target} backup file checksum',
                    'Write a shell action that validates {target} backup integrity',
                ],
                'explanation': 'Verifies {target} backup integrity by computing or comparing SHA-256 checksums.',
                'features': ['schema_variables'],
            },
            {
                'name': 'offsite-copy-scp',
                'template': {
                    'name': '{target}-offsite-scp',
                    'action_type': 'SHELL',
                    'code': 'if [ ! -f "{{input.local_file}}" ]; then echo "FAILED: Source file not found: {{input.local_file}}" >&2; exit 1; fi && echo "Copying {{input.local_file}} to {{input.remote_user}}@{{input.remote_host}}:{{input.remote_dir}}/" && scp -o StrictHostKeyChecking=accept-new -o ConnectTimeout=30 -i {{input.ssh_key}} "{{input.local_file}}" "{{input.remote_user}}@{{input.remote_host}}:{{input.remote_dir}}/" 2>&1 && echo "Offsite copy completed successfully" || (echo "FAILED: scp transfer error" >&2; exit 1)',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'local_file': {'type': 'string', 'description': 'Path to the local backup file to transfer'},
                            'remote_host': {'type': 'string', 'description': 'Remote server hostname or IP'},
                            'remote_user': {'type': 'string', 'description': 'SSH user on the remote server'},
                            'remote_dir': {'type': 'string', 'description': 'Destination directory on the remote server'},
                            'ssh_key': {'type': 'string', 'description': 'Path to the SSH private key file'},
                        },
                        'required': ['local_file', 'remote_host', 'remote_user', 'remote_dir', 'ssh_key'],
                    },
                },
                'params': {'target': ['database', 'system', 'archive', 'dr']},
                'prompts': [
                    'Copy a {target} backup offsite via scp',
                    'Create a DM action to transfer a {target} backup to a remote server',
                    'Write a shell action for offsite {target} backup copy using scp',
                ],
                'explanation': 'Copies a {target} backup file to an offsite remote server via scp with key-based authentication.',
                'features': ['schema_variables'],
            },
            {
                'name': 'rsync-checksum-incremental',
                'template': {
                    'name': '{target}-rsync-checksum',
                    'action_type': 'SHELL',
                    'code': 'mkdir -p {{input.dest_dir}} && rsync -avz --checksum --delete --stats --partial --progress {{input.source_dir}}/ {{input.dest_dir}}/ 2>&1 && echo "Checksum-based incremental backup completed to {{input.dest_dir}}" || (echo "FAILED: rsync checksum backup error" >&2; exit 1)',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'source_dir': {'type': 'string', 'description': 'Source directory to back up'},
                            'dest_dir': {'type': 'string', 'description': 'Destination directory for backup'},
                        },
                        'required': ['source_dir', 'dest_dir'],
                    },
                },
                'params': {'target': ['data', 'config', 'webapp', 'media']},
                'prompts': [
                    'Run an incremental rsync backup for {target} using checksum comparison',
                    'Create a DM action for a checksum-verified rsync backup of {target}',
                    'Write a shell action that does an rsync --checksum backup of {target} data',
                ],
                'explanation': 'Performs a checksum-based incremental rsync backup of {target} data, ensuring only truly changed files are transferred.',
                'features': ['schema_variables'],
            },
            {
                'name': 'backup-encrypt-gpg',
                'template': {
                    'name': '{target}-backup-encrypt',
                    'action_type': 'SHELL',
                    'code': 'if [ ! -f "{{input.backup_file}}" ]; then echo "FAILED: Source file not found: {{input.backup_file}}" >&2; exit 1; fi && echo "Encrypting {{input.backup_file}} with GPG..." && gpg --batch --yes --symmetric --cipher-algo AES256 --passphrase "{{input.passphrase}}" --output "{{input.backup_file}}.gpg" "{{input.backup_file}}" 2>&1 && ORIG_SIZE=$(du -sh "{{input.backup_file}}" | cut -f1) && ENC_SIZE=$(du -sh "{{input.backup_file}}.gpg" | cut -f1) && echo "Encryption complete: {{input.backup_file}}.gpg ($ENC_SIZE, original: $ORIG_SIZE)" || (echo "FAILED: GPG encryption error" >&2; exit 1)',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'backup_file': {'type': 'string', 'description': 'Path to the backup file to encrypt'},
                            'passphrase': {'type': 'string', 'description': 'Symmetric encryption passphrase'},
                        },
                        'required': ['backup_file', 'passphrase'],
                    },
                },
                'params': {'target': ['database', 'system', 'archive', 'config']},
                'prompts': [
                    'Encrypt a {target} backup file with GPG AES256',
                    'Create a DM action to encrypt a {target} backup using GPG symmetric encryption',
                    'Write a shell action that GPG-encrypts a {target} backup file',
                ],
                'explanation': 'Encrypts a {target} backup file using GPG symmetric AES256 encryption with a passphrase.',
                'features': ['schema_variables'],
                'difficulty': 'intermediate',
            },
            {
                'name': 'backup-s3-upload',
                'template': {
                    'name': '{target}-s3-upload',
                    'action_type': 'SHELL',
                    'code': 'if [ ! -f "{{input.local_file}}" ]; then echo "FAILED: File not found: {{input.local_file}}" >&2; exit 1; fi && echo "Uploading {{input.local_file}} to s3://{{input.bucket}}/{{input.s3_prefix}}/" && aws s3 cp "{{input.local_file}}" "s3://{{input.bucket}}/{{input.s3_prefix}}/$(basename {{input.local_file}})" --storage-class {{input.storage_class}} --sse AES256 2>&1 && echo "Upload to S3 complete" && aws s3 ls "s3://{{input.bucket}}/{{input.s3_prefix}}/$(basename {{input.local_file}})" 2>&1 || (echo "FAILED: S3 upload error" >&2; exit 1)',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'local_file': {'type': 'string', 'description': 'Path to the local backup file'},
                            'bucket': {'type': 'string', 'description': 'S3 bucket name'},
                            's3_prefix': {'type': 'string', 'description': 'S3 key prefix/folder path'},
                            'storage_class': {'type': 'string', 'description': 'S3 storage class (STANDARD, STANDARD_IA, GLACIER, DEEP_ARCHIVE)'},
                        },
                        'required': ['local_file', 'bucket', 's3_prefix', 'storage_class'],
                    },
                },
                'params': {'target': ['database', 'system', 'archive', 'logs']},
                'prompts': [
                    'Upload a {target} backup to Amazon S3',
                    'Create a DM action to copy a {target} backup file to S3 with server-side encryption',
                    'Write a shell action that pushes a {target} backup to an S3 bucket',
                ],
                'explanation': 'Uploads a {target} backup file to Amazon S3 with server-side AES256 encryption and configurable storage class.',
                'features': ['schema_variables'],
                'difficulty': 'intermediate',
            },
            {
                'name': 'backup-verify-tar',
                'template': {
                    'name': '{target}-backup-verify-tar',
                    'action_type': 'SHELL',
                    'code': 'if [ ! -f "{{input.backup_file}}" ]; then echo "FAILED: Backup file not found: {{input.backup_file}}" >&2; exit 1; fi && echo "Verifying archive integrity: {{input.backup_file}}" && gzip -t "{{input.backup_file}}" 2>&1 && echo "GZIP integrity: OK" && echo "Listing archive contents..." && FILE_COUNT=$(tar tzf "{{input.backup_file}}" 2>&1 | wc -l) && FILESIZE=$(du -sh "{{input.backup_file}}" | cut -f1) && echo "Archive: {{input.backup_file}} ($FILESIZE, $FILE_COUNT entries)" && echo "VERIFIED: Archive is intact and readable" || (echo "FAILED: Archive is corrupt or unreadable" >&2; exit 1)',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'backup_file': {'type': 'string', 'description': 'Path to the tar.gz backup file to verify'},
                        },
                        'required': ['backup_file'],
                    },
                },
                'params': {'target': ['database', 'system', 'config', 'application']},
                'prompts': [
                    'Verify the integrity of a {target} tar.gz backup',
                    'Create a DM action to validate a {target} backup archive is not corrupt',
                    'Write a shell action that checks a {target} tar.gz backup can be read',
                ],
                'explanation': 'Verifies the integrity of a {target} tar.gz backup by testing gzip compression and listing archive contents.',
                'features': ['schema_variables'],
            },
            {
                'name': 'db-pitr-restore',
                'template': {
                    'name': '{db}-pitr-restore',
                    'action_type': 'SHELL',
                    'code': 'echo "=== Point-in-Time Restore for {{input.database}} ===" && echo "Stopping PostgreSQL..." && systemctl stop postgresql 2>&1 && echo "Cleaning data directory..." && rm -rf {{input.data_dir}}/* && echo "Restoring base backup..." && tar xzf "{{input.base_backup}}" -C {{input.data_dir}}/ 2>&1 && echo "Configuring recovery target..." && cat > {{input.data_dir}}/recovery.signal <<SIGNAL\nSIGNAL\ncat >> {{input.data_dir}}/postgresql.auto.conf <<RECOVERY\nrestore_command = \'cp {{input.wal_archive_dir}}/%f %p\'\nrecovery_target_time = \'{{input.target_time}}\'\nrecovery_target_action = \'promote\'\nRECOVERY\nchown -R postgres:postgres {{input.data_dir}} && echo "Starting PostgreSQL for recovery..." && systemctl start postgresql 2>&1 && echo "PITR restore initiated to target time: {{input.target_time}}"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'database': {'type': 'string', 'description': 'Database identifier'},
                            'data_dir': {'type': 'string', 'description': 'PostgreSQL data directory path'},
                            'base_backup': {'type': 'string', 'description': 'Path to the base backup tar.gz file'},
                            'wal_archive_dir': {'type': 'string', 'description': 'Directory containing WAL archive files'},
                            'target_time': {'type': 'string', 'description': 'Recovery target timestamp (e.g. 2024-01-15 14:30:00)'},
                        },
                        'required': ['database', 'data_dir', 'base_backup', 'wal_archive_dir', 'target_time'],
                    },
                },
                'params': {'db': ['production', 'staging', 'analytics', 'warehouse']},
                'prompts': [
                    'Perform a point-in-time restore of the {db} PostgreSQL database',
                    'Create a DM action for PostgreSQL PITR on the {db} database',
                    'Write a shell action that restores {db} database to a specific point in time',
                ],
                'explanation': 'Performs a PostgreSQL point-in-time recovery for the {db} database using a base backup and WAL archive.',
                'features': ['schema_variables'],
                'difficulty': 'advanced',
            },
        ]


def get_generators():
    return [BackupRestoreGenerator()]
