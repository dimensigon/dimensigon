"""Shell action generators for package management operations."""

from examples.generators.base_generator import ShellActionGenerator


class PackagesGenerator(ShellActionGenerator):
    category = "shell.packages"
    subcategory = "packages"

    def seeds(self):
        return [
            {
                'name': 'apt-install',
                'template': {
                    'name': 'apt-install-{pkg}',
                    'action_type': 'SHELL',
                    'code': 'export DEBIAN_FRONTEND=noninteractive && apt-get update -qq && apt-get install -y -qq {{input.package_name}} && dpkg -l {{input.package_name}} | tail -1 && echo "Package installed successfully"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'package_name': {'type': 'string', 'description': 'Package name to install via apt'},
                        },
                        'required': ['package_name'],
                    },
                },
                'params': {'pkg': ['nginx', 'curl', 'vim', 'htop', 'jq', 'tree', 'unzip']},
                'prompts': [
                    'Install {pkg} using apt-get',
                    'Create a DM action to install {pkg} on Debian/Ubuntu',
                    'Write a shell action to apt-get install {pkg}',
                ],
                'explanation': 'Installs the {pkg} package using apt-get with non-interactive mode.',
                'features': ['schema_variables'],
            },
            {
                'name': 'yum-install',
                'template': {
                    'name': 'yum-install-{pkg}',
                    'action_type': 'SHELL',
                    'code': 'yum install -y {{input.package_name}} && rpm -qi {{input.package_name}} && echo "Package installed successfully"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'package_name': {'type': 'string', 'description': 'Package name to install via yum'},
                        },
                        'required': ['package_name'],
                    },
                },
                'params': {'pkg': ['nginx', 'httpd', 'wget', 'vim-enhanced', 'net-tools', 'bind-utils']},
                'prompts': [
                    'Install {pkg} using yum',
                    'Create a DM action to install {pkg} on RHEL/CentOS',
                    'Write a shell action to yum install {pkg}',
                ],
                'explanation': 'Installs the {pkg} package using yum on RHEL/CentOS systems.',
                'features': ['schema_variables'],
            },
            {
                'name': 'dnf-install',
                'template': {
                    'name': 'dnf-install-{pkg}',
                    'action_type': 'SHELL',
                    'code': 'dnf install -y {{input.package_name}} && rpm -qi {{input.package_name}} && echo "Package installed via dnf"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'package_name': {'type': 'string', 'description': 'Package name to install via dnf'},
                        },
                        'required': ['package_name'],
                    },
                },
                'params': {'pkg': ['nginx', 'podman', 'cockpit', 'firewalld', 'tmux']},
                'prompts': [
                    'Install {pkg} using dnf',
                    'Create a DM action to install {pkg} on Fedora/RHEL 8+',
                    'Write a shell action to dnf install {pkg}',
                ],
                'explanation': 'Installs the {pkg} package using dnf on Fedora/RHEL 8+ systems.',
                'features': ['schema_variables'],
            },
            {
                'name': 'pip-install',
                'template': {
                    'name': 'pip-install-{pkg}',
                    'action_type': 'SHELL',
                    'code': 'pip3 install --no-cache-dir {{input.package_name}}=={{input.version}} && pip3 show {{input.package_name}} && echo "Python package installed"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'package_name': {'type': 'string', 'description': 'Python package name to install'},
                            'version': {'type': 'string', 'description': 'Package version to install'},
                        },
                        'required': ['package_name', 'version'],
                    },
                },
                'params': {'pkg': ['flask', 'django', 'requests', 'celery', 'gunicorn', 'boto3']},
                'prompts': [
                    'Install Python package {pkg} with pip',
                    'Create a DM action to pip install {pkg} at a specific version',
                    'Write a shell action to install {pkg} via pip3',
                ],
                'explanation': 'Installs the {pkg} Python package at a specific version using pip3.',
                'features': ['schema_variables'],
            },
            {
                'name': 'npm-install',
                'template': {
                    'name': 'npm-install-{pkg}',
                    'action_type': 'SHELL',
                    'code': 'npm install -g {{input.package_name}}@{{input.version}} && npm list -g {{input.package_name}} && echo "npm package installed globally"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'package_name': {'type': 'string', 'description': 'npm package name to install'},
                            'version': {'type': 'string', 'description': 'Package version (e.g. latest, 1.2.3)'},
                        },
                        'required': ['package_name', 'version'],
                    },
                },
                'params': {'pkg': ['pm2', 'serve', 'nodemon', 'typescript', 'yarn']},
                'prompts': [
                    'Install {pkg} globally with npm',
                    'Create a DM action to npm install {pkg} globally',
                    'Write a shell action to install {pkg} via npm',
                ],
                'explanation': 'Installs the {pkg} npm package globally at a specified version.',
                'features': ['schema_variables'],
            },
            {
                'name': 'apt-autoremove',
                'template': {
                    'name': 'apt-autoremove-{scope}',
                    'action_type': 'SHELL',
                    'code': 'export DEBIAN_FRONTEND=noninteractive && echo "=== Packages to remove ===" && apt-get autoremove --dry-run 2>&1 | grep "^Remv" && apt-get autoremove -y -qq && apt-get clean && echo "Unused packages removed and cache cleaned"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {},
                        'required': [],
                    },
                },
                'params': {'scope': ['full', 'cleanup', 'maintenance']},
                'prompts': [
                    'Run apt autoremove for {scope} cleanup',
                    'Create a DM action for {scope} package cleanup on Ubuntu',
                    'Write a shell action to remove unused packages ({scope})',
                ],
                'explanation': 'Removes unused packages and cleans the apt cache ({scope} cleanup).',
                'features': ['schema_variables'],
            },
            {
                'name': 'pkg-version-pin',
                'template': {
                    'name': 'pin-pkg-{pkg}',
                    'action_type': 'SHELL',
                    'code': 'cat > /etc/apt/preferences.d/{{input.package_name}}.pref <<PIN\nPackage: {{input.package_name}}\nPin: version {{input.pin_version}}\nPin-Priority: 1001\nPIN\necho "Package {{input.package_name}} pinned to version {{input.pin_version}}" && apt-cache policy {{input.package_name}}',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'package_name': {'type': 'string', 'description': 'Package name to pin'},
                            'pin_version': {'type': 'string', 'description': 'Version to pin the package to'},
                        },
                        'required': ['package_name', 'pin_version'],
                    },
                },
                'params': {'pkg': ['nginx', 'postgresql', 'redis', 'docker-ce', 'nodejs']},
                'prompts': [
                    'Pin {pkg} to a specific version with apt',
                    'Create a DM action to version-pin {pkg}',
                    'Write a shell action to lock {pkg} to a specific version',
                ],
                'explanation': 'Pins the {pkg} package to a specific version using apt preferences.',
                'features': ['schema_variables'],
                'difficulty': 'intermediate',
            },
            {
                'name': 'repo-add',
                'template': {
                    'name': 'add-repo-{repo_type}',
                    'action_type': 'SHELL',
                    'code': 'apt-get install -y -qq software-properties-common && add-apt-repository -y "{{input.repo_url}}" && apt-get update -qq && echo "Repository added and index updated"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'repo_url': {'type': 'string', 'description': 'Repository URL or PPA to add'},
                        },
                        'required': ['repo_url'],
                    },
                },
                'params': {'repo_type': ['ppa', 'third-party', 'vendor', 'custom']},
                'prompts': [
                    'Add a {repo_type} repository to the system',
                    'Create a DM action to add a {repo_type} package repository',
                    'Write a shell action to configure a {repo_type} repo source',
                ],
                'explanation': 'Adds a {repo_type} package repository and updates the package index.',
                'features': ['schema_variables'],
            },
            {
                'name': 'gpg-key-import',
                'template': {
                    'name': 'import-gpg-{source}',
                    'action_type': 'SHELL',
                    'code': 'curl -fsSL "{{input.key_url}}" | gpg --dearmor -o /etc/apt/keyrings/{{input.keyring_name}}.gpg && chmod 644 /etc/apt/keyrings/{{input.keyring_name}}.gpg && echo "GPG key imported to /etc/apt/keyrings/{{input.keyring_name}}.gpg"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'key_url': {'type': 'string', 'description': 'URL of the GPG key to import'},
                            'keyring_name': {'type': 'string', 'description': 'Name for the keyring file'},
                        },
                        'required': ['key_url', 'keyring_name'],
                    },
                },
                'params': {'source': ['docker', 'hashicorp', 'kubernetes', 'grafana', 'elastic']},
                'prompts': [
                    'Import the {source} GPG key for package verification',
                    'Create a DM action to import {source} repository GPG key',
                    'Write a shell action to add {source} GPG signing key',
                ],
                'explanation': 'Imports the {source} GPG key into the apt keyring for package signature verification.',
                'features': ['schema_variables'],
                'difficulty': 'intermediate',
            },
            {
                'name': 'pkg-hold',
                'template': {
                    'name': 'hold-pkg-{pkg}',
                    'action_type': 'SHELL',
                    'code': 'apt-mark hold {{input.package_name}} && echo "Package {{input.package_name}} held from upgrades" && apt-mark showhold | grep -q {{input.package_name}} && echo "Confirmed: package is on hold"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'package_name': {'type': 'string', 'description': 'Package name to hold from upgrades'},
                        },
                        'required': ['package_name'],
                    },
                },
                'params': {'pkg': ['linux-image', 'docker-ce', 'postgresql', 'mysql-server', 'kubelet']},
                'prompts': [
                    'Hold {pkg} from automatic upgrades',
                    'Create a DM action to prevent {pkg} from being upgraded',
                    'Write a shell action to apt-mark hold {pkg}',
                ],
                'explanation': 'Holds the {pkg} package to prevent it from being upgraded automatically.',
                'features': ['schema_variables'],
            },
            {
                'name': 'dpkg-reconfigure',
                'template': {
                    'name': 'dpkg-reconf-{pkg}',
                    'action_type': 'SHELL',
                    'code': 'export DEBIAN_FRONTEND={{input.frontend}} && dpkg-reconfigure {{input.package_name}} && echo "Package {{input.package_name}} reconfigured"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'package_name': {'type': 'string', 'description': 'Package name to reconfigure'},
                            'frontend': {'type': 'string', 'description': 'Debconf frontend (noninteractive, dialog, readline)'},
                        },
                        'required': ['package_name', 'frontend'],
                    },
                },
                'params': {'pkg': ['locales', 'tzdata', 'console-setup', 'keyboard-configuration']},
                'prompts': [
                    'Reconfigure {pkg} with dpkg',
                    'Create a DM action to dpkg-reconfigure {pkg}',
                    'Write a shell action to reconfigure the {pkg} package',
                ],
                'explanation': 'Reconfigures the {pkg} package using dpkg-reconfigure.',
                'features': ['schema_variables'],
            },
            {
                'name': 'snap-install',
                'template': {
                    'name': 'snap-install-{pkg}',
                    'action_type': 'SHELL',
                    'code': 'snap install {{input.package_name}} {{input.flags}} && snap list {{input.package_name}} && echo "Snap package installed"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'package_name': {'type': 'string', 'description': 'Snap package name to install'},
                            'flags': {'type': 'string', 'description': 'Install flags (e.g. --classic, --edge)'},
                        },
                        'required': ['package_name'],
                    },
                },
                'params': {'pkg': ['lxd', 'microk8s', 'go', 'node', 'code', 'kubectl']},
                'prompts': [
                    'Install {pkg} as a snap package',
                    'Create a DM action to snap install {pkg}',
                    'Write a shell action to install {pkg} via snap',
                ],
                'explanation': 'Installs the {pkg} snap package with optional flags.',
                'features': ['schema_variables'],
            },
        ]


def get_generators():
    return [PackagesGenerator()]
