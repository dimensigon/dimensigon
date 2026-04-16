"""Shell action generators for disk and storage management."""

from examples.generators.base_generator import ShellActionGenerator


class DiskStorageGenerator(ShellActionGenerator):
    category = "shell.disk_storage"
    subcategory = "disk_storage"

    def seeds(self):
        return [
            {
                'name': 'df-threshold',
                'template': {
                    'name': 'disk-usage-check-{scope}',
                    'action_type': 'SHELL',
                    'code': 'USAGE=$(df "{{input.mount_point}}" --output=pcent | tail -1 | tr -d " %%") && echo "Disk usage on {{input.mount_point}}: ${{USAGE}}%%" && if [ "$USAGE" -ge "{{input.threshold}}" ]; then echo "CRITICAL: Usage ${{USAGE}}%% exceeds threshold {{input.threshold}}%%" >&2; exit 1; else echo "OK: Usage is within acceptable range"; exit 0; fi',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'mount_point': {'type': 'string', 'description': 'Mount point to check (e.g. /, /var, /home)'},
                            'threshold': {'type': 'integer', 'description': 'Usage percentage threshold to alert on'},
                        },
                        'required': ['mount_point', 'threshold'],
                    },
                },
                'params': {'scope': ['root', 'var', 'data', 'home']},
                'prompts': [
                    'Check disk usage on {scope} filesystem against a threshold',
                    'Create a DM action to alert when {scope} disk usage is high',
                    'Write a shell action to monitor {scope} filesystem capacity',
                ],
                'explanation': 'Checks disk usage on the {scope} filesystem and alerts if it exceeds the configured threshold.',
                'features': ['schema_variables'],
            },
            {
                'name': 'mount-filesystem',
                'template': {
                    'name': 'mount-{fs_type}',
                    'action_type': 'SHELL',
                    'code': 'if mountpoint -q "{{input.mount_point}}"; then echo "Already mounted: {{input.mount_point}}"; exit 0; fi && mkdir -p "{{input.mount_point}}" && mount -t {{input.fs_type}} {{input.mount_options}} "{{input.device}}" "{{input.mount_point}}" && echo "Mounted {{input.device}} on {{input.mount_point}}" && grep -q "{{input.device}}" /etc/fstab || echo "{{input.device}} {{input.mount_point}} {{input.fs_type}} defaults 0 2" >> /etc/fstab && echo "Added to fstab for persistent mount"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'device': {'type': 'string', 'description': 'Block device path (e.g. /dev/sdb1)'},
                            'mount_point': {'type': 'string', 'description': 'Mount point directory'},
                            'fs_type': {'type': 'string', 'description': 'Filesystem type (ext4, xfs, nfs)'},
                            'mount_options': {'type': 'string', 'description': 'Mount options (e.g. -o defaults,noatime)'},
                        },
                        'required': ['device', 'mount_point', 'fs_type'],
                    },
                },
                'params': {'fs_type': ['ext4', 'xfs', 'nfs', 'btrfs']},
                'prompts': [
                    'Mount a {fs_type} filesystem and add to fstab',
                    'Create a DM action to mount a {fs_type} partition',
                    'Write a shell action to persistently mount a {fs_type} filesystem',
                ],
                'explanation': 'Mounts a {fs_type} filesystem at the specified mount point and adds it to /etc/fstab for persistence.',
                'features': ['schema_variables'],
                'difficulty': 'intermediate',
            },
            {
                'name': 'lvm-create-extend',
                'template': {
                    'name': 'lvm-{action}',
                    'action_type': 'SHELL',
                    'code': 'if [ "{{input.action}}" = "create" ]; then lvcreate -L {{input.size}} -n {{input.lv_name}} {{input.vg_name}} && mkfs.{{input.fs_type}} /dev/{{input.vg_name}}/{{input.lv_name}} && echo "LV created: /dev/{{input.vg_name}}/{{input.lv_name}} ({{input.size}})"; elif [ "{{input.action}}" = "extend" ]; then lvextend -L+{{input.size}} /dev/{{input.vg_name}}/{{input.lv_name}} && resize2fs /dev/{{input.vg_name}}/{{input.lv_name}} && echo "LV extended by {{input.size}}"; fi',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'action': {'type': 'string', 'description': 'Action: create or extend'},
                            'vg_name': {'type': 'string', 'description': 'Volume group name'},
                            'lv_name': {'type': 'string', 'description': 'Logical volume name'},
                            'size': {'type': 'string', 'description': 'Size (e.g. 10G, 500M)'},
                            'fs_type': {'type': 'string', 'description': 'Filesystem type for new LVs (e.g. ext4, xfs)'},
                        },
                        'required': ['action', 'vg_name', 'lv_name', 'size'],
                    },
                },
                'params': {'action': ['create', 'extend']},
                'prompts': [
                    '{action} an LVM logical volume',
                    'Create a DM action to {action} an LVM volume',
                    'Write a shell action to {action} an LV with LVM',
                ],
                'explanation': 'Performs LVM logical volume {action} operation with filesystem creation or extension.',
                'features': ['schema_variables'],
                'difficulty': 'advanced',
            },
            {
                'name': 'raid-status',
                'template': {
                    'name': 'raid-status-{array}',
                    'action_type': 'SHELL',
                    'code': 'echo "=== RAID Status ===" && cat /proc/mdstat 2>/dev/null && echo "" && echo "=== Detail for {{input.md_device}} ===" && mdadm --detail {{input.md_device}} 2>&1 && echo "" && echo "=== Component Health ===" && mdadm --examine {{input.md_device}} 2>&1 | grep -E "(State|Events|UUID)" || echo "No RAID arrays found or mdadm not available"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'md_device': {'type': 'string', 'description': 'MD RAID device (e.g. /dev/md0)'},
                        },
                        'required': ['md_device'],
                    },
                },
                'params': {'array': ['md0', 'md1', 'primary', 'data']},
                'prompts': [
                    'Check RAID array {array} status',
                    'Create a DM action to monitor RAID {array} health',
                    'Write a shell action to check {array} RAID status',
                ],
                'explanation': 'Checks the health and status of RAID array {array} using mdadm.',
                'features': ['schema_variables'],
                'difficulty': 'intermediate',
            },
            {
                'name': 'fstrim',
                'template': {
                    'name': 'fstrim-{scope}',
                    'action_type': 'SHELL',
                    'code': 'echo "=== Running TRIM on {{input.mount_point}} ===" && fstrim -v "{{input.mount_point}}" 2>&1 && echo "TRIM completed on {{input.mount_point}}"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'mount_point': {'type': 'string', 'description': 'Mount point to TRIM (e.g. /, /data)'},
                        },
                        'required': ['mount_point'],
                    },
                },
                'params': {'scope': ['root', 'all', 'data', 'var']},
                'prompts': [
                    'Run fstrim on {scope} filesystem for SSD optimization',
                    'Create a DM action to TRIM {scope} filesystems',
                    'Write a shell action to run fstrim on {scope} mount points',
                ],
                'explanation': 'Runs fstrim on the {scope} filesystem to reclaim unused blocks on SSD storage.',
                'features': ['schema_variables'],
            },
            {
                'name': 'disk-usage-report',
                'template': {
                    'name': 'disk-report-{scope}',
                    'action_type': 'SHELL',
                    'code': 'echo "=== Filesystem Usage ===" && df -hT | head -20 && echo "" && echo "=== Top 15 Largest Directories under {{input.path}} ===" && du -h --max-depth={{input.depth}} "{{input.path}}" 2>/dev/null | sort -rh | head -15 && echo "" && echo "=== Inode Usage ===" && df -i "{{input.path}}" 2>/dev/null',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'path': {'type': 'string', 'description': 'Path to generate the disk usage report for'},
                            'depth': {'type': 'integer', 'description': 'Maximum directory depth for du report'},
                        },
                        'required': ['path', 'depth'],
                    },
                },
                'params': {'scope': ['full', 'summary', 'detailed']},
                'prompts': [
                    'Generate a {scope} disk usage report',
                    'Create a DM action for a {scope} storage utilization report',
                    'Write a shell action to produce a {scope} disk space report',
                ],
                'explanation': 'Generates a {scope} disk usage report including filesystem usage, largest directories, and inode utilization.',
                'features': ['schema_variables'],
            },
            {
                'name': 'swap-manage',
                'template': {
                    'name': 'swap-{action}',
                    'action_type': 'SHELL',
                    'code': 'if [ "{{input.action}}" = "create" ]; then fallocate -l {{input.size}} {{input.swap_file}} && chmod 600 {{input.swap_file}} && mkswap {{input.swap_file}} && swapon {{input.swap_file}} && echo "{{input.swap_file}} none swap sw 0 0" >> /etc/fstab && echo "Swap file created and activated: {{input.size}}"; elif [ "{{input.action}}" = "remove" ]; then swapoff {{input.swap_file}} && rm -f {{input.swap_file}} && sed -i "\\|{{input.swap_file}}|d" /etc/fstab && echo "Swap file removed"; fi && free -h | grep -i swap',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'action': {'type': 'string', 'description': 'Action: create or remove'},
                            'swap_file': {'type': 'string', 'description': 'Path to the swap file'},
                            'size': {'type': 'string', 'description': 'Swap file size (e.g. 2G, 4G)'},
                        },
                        'required': ['action', 'swap_file'],
                    },
                },
                'params': {'action': ['create', 'remove']},
                'prompts': [
                    '{action} a swap file',
                    'Create a DM action to {action} swap space',
                    'Write a shell action to {action} a swap file with fstab entry',
                ],
                'explanation': 'Manages swap space by performing {action} operation on a swap file.',
                'features': ['schema_variables'],
                'difficulty': 'intermediate',
            },
            {
                'name': 'quota-setup',
                'template': {
                    'name': 'quota-setup-{scope}',
                    'action_type': 'SHELL',
                    'code': 'setquota -u {{input.username}} {{input.soft_blocks}} {{input.hard_blocks}} {{input.soft_inodes}} {{input.hard_inodes}} {{input.filesystem}} && echo "Quota set for {{input.username}} on {{input.filesystem}}" && repquota {{input.filesystem}} | grep {{input.username}}',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'username': {'type': 'string', 'description': 'Username to set quota for'},
                            'filesystem': {'type': 'string', 'description': 'Filesystem to apply quota on'},
                            'soft_blocks': {'type': 'string', 'description': 'Soft block limit (e.g. 1048576 for 1G)'},
                            'hard_blocks': {'type': 'string', 'description': 'Hard block limit'},
                            'soft_inodes': {'type': 'integer', 'description': 'Soft inode limit'},
                            'hard_inodes': {'type': 'integer', 'description': 'Hard inode limit'},
                        },
                        'required': ['username', 'filesystem', 'soft_blocks', 'hard_blocks', 'soft_inodes', 'hard_inodes'],
                    },
                },
                'params': {'scope': ['user', 'team', 'department']},
                'prompts': [
                    'Set up disk quota for a {scope}',
                    'Create a DM action to configure {scope} disk quotas',
                    'Write a shell action to enforce {scope} storage quotas',
                ],
                'explanation': 'Sets up disk quotas for a {scope} with soft and hard limits for blocks and inodes.',
                'features': ['schema_variables'],
                'difficulty': 'advanced',
            },
            {
                'name': 'filesystem-repair',
                'template': {
                    'name': 'fsck-{fs_type}',
                    'action_type': 'SHELL',
                    'code': 'echo "WARNING: Running filesystem check on {{input.device}}" && echo "Checking if filesystem is mounted..." && if mountpoint -q "$(findmnt -n -o TARGET {{input.device}} 2>/dev/null)"; then echo "ERROR: Filesystem is mounted, cannot fsck" >&2; exit 1; fi && fsck -y {{input.device}} 2>&1 && echo "Filesystem check complete on {{input.device}}"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'device': {'type': 'string', 'description': 'Block device to check (e.g. /dev/sda1)'},
                        },
                        'required': ['device'],
                    },
                },
                'params': {'fs_type': ['ext4', 'xfs', 'btrfs']},
                'prompts': [
                    'Run filesystem repair on a {fs_type} partition',
                    'Create a DM action to fsck a {fs_type} filesystem',
                    'Write a shell action to check and repair a {fs_type} filesystem',
                ],
                'explanation': 'Runs filesystem check and repair on a {fs_type} partition, verifying it is unmounted first.',
                'features': ['schema_variables'],
                'difficulty': 'advanced',
            },
            {
                'name': 'inode-monitor',
                'template': {
                    'name': 'inode-monitor-{scope}',
                    'action_type': 'SHELL',
                    'code': 'echo "=== Inode Usage ===" && df -i "{{input.mount_point}}" && INODE_PCT=$(df -i "{{input.mount_point}}" --output=ipcent | tail -1 | tr -d " %%") && if [ "$INODE_PCT" -ge "{{input.threshold}}" ]; then echo "CRITICAL: Inode usage ${{INODE_PCT}}%% exceeds threshold {{input.threshold}}%%" >&2; echo "=== Top directories by file count ===" && find "{{input.mount_point}}" -xdev -type d -exec sh -c \'echo "$(find "$1" -maxdepth 1 -type f | wc -l) $1"\' _ {{}} \\; 2>/dev/null | sort -rn | head -10; exit 1; else echo "OK: Inode usage ${{INODE_PCT}}%%"; fi',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'mount_point': {'type': 'string', 'description': 'Mount point to check inode usage'},
                            'threshold': {'type': 'integer', 'description': 'Inode usage percentage threshold'},
                        },
                        'required': ['mount_point', 'threshold'],
                    },
                },
                'params': {'scope': ['root', 'var', 'tmp', 'data']},
                'prompts': [
                    'Monitor inode usage on {scope} filesystem',
                    'Create a DM action to check {scope} inode utilization',
                    'Write a shell action to alert on {scope} inode exhaustion',
                ],
                'explanation': 'Monitors inode usage on the {scope} filesystem and reports top directories by file count when threshold is exceeded.',
                'features': ['schema_variables'],
            },
        ]


def get_generators():
    return [DiskStorageGenerator()]
