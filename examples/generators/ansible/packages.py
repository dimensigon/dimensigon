"""Package management Ansible action generators - 8 seeds for apt, yum, pip, npm, etc."""

from examples.generators.base_generator import AnsibleActionGenerator


class PackagesGenerator(AnsibleActionGenerator):
    category = "ansible.packages"
    subcategory = "packages"

    def seeds(self):
        return [
            {
                'name': 'apt-install',
                'template': {
                    'name': 'Install {package} via apt',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Update apt cache\n'
                        '  apt:\n'
                        '    update_cache: yes\n'
                        '    cache_valid_time: 3600\n'
                        '\n'
                        '- name: Install {{input.package}}\n'
                        '  apt:\n'
                        '    name: "{{input.package}}"\n'
                        '    state: present\n'
                        '  register: install_result\n'
                        '\n'
                        '- name: Verify installation\n'
                        '  command: "dpkg -l {{input.package}}"\n'
                        '  register: verify\n'
                        '  changed_when: false\n'
                    ),
                    'schema': {
                        'input': {
                            'package': {'type': 'string', 'description': 'Package name to install via apt'},
                        },
                        'required': ['package'],
                    },
                },
                'params': {'package': ['nginx', 'curl', 'htop', 'vim', 'git', 'jq', 'tmux', 'wget']},
                'prompts': [
                    'Create an Ansible action to install {package} via apt',
                    'Ansible playbook that installs the {package} package using apt',
                ],
                'explanation': 'Ansible action that installs {package} via apt with cache update and installation verification.',
            },
            {
                'name': 'yum-install',
                'template': {
                    'name': 'Install {package} via yum',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Install {{input.package}}\n'
                        '  yum:\n'
                        '    name: "{{input.package}}"\n'
                        '    state: present\n'
                        '  register: install_result\n'
                        '\n'
                        '- name: Verify installation\n'
                        '  command: "rpm -q {{input.package}}"\n'
                        '  register: verify\n'
                        '  changed_when: false\n'
                    ),
                    'schema': {
                        'input': {
                            'package': {'type': 'string', 'description': 'Package name to install via yum'},
                        },
                        'required': ['package'],
                    },
                },
                'params': {'package': ['httpd', 'nginx', 'git', 'vim-enhanced', 'curl', 'jq', 'wget', 'tar']},
                'prompts': [
                    'Create an Ansible action to install {package} via yum',
                    'Ansible playbook that installs {package} on RHEL/CentOS using yum',
                ],
                'explanation': 'Ansible action that installs {package} via yum with RPM verification on RHEL/CentOS systems.',
            },
            {
                'name': 'pip-install',
                'template': {
                    'name': 'Install {package} via pip',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Ensure pip is installed\n'
                        '  package:\n'
                        '    name: python3-pip\n'
                        '    state: present\n'
                        '\n'
                        '- name: Install {{input.package}} via pip\n'
                        '  pip:\n'
                        '    name: "{{input.package}}"\n'
                        '    version: "{{input.version}}"\n'
                        '    state: present\n'
                        '    executable: pip3\n'
                        '  when: input.version is defined and input.version != ""\n'
                        '\n'
                        '- name: Install {{input.package}} latest via pip\n'
                        '  pip:\n'
                        '    name: "{{input.package}}"\n'
                        '    state: latest\n'
                        '    executable: pip3\n'
                        '  when: input.version is not defined or input.version == ""\n'
                    ),
                    'schema': {
                        'input': {
                            'package': {'type': 'string', 'description': 'Python package name'},
                            'version': {'type': 'string', 'description': 'Package version (optional)'},
                        },
                        'required': ['package'],
                    },
                },
                'params': {'package': ['flask', 'django', 'requests', 'boto3', 'ansible', 'paramiko', 'celery', 'gunicorn']},
                'prompts': [
                    'Create an Ansible action to install {package} via pip',
                    'Ansible playbook that installs the {package} Python package with pip',
                ],
                'explanation': 'Ansible action that installs the {package} Python package via pip3 with optional version pinning.',
            },
            {
                'name': 'npm-install',
                'template': {
                    'name': 'Install {package} via npm',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Install {{input.package}} globally via npm\n'
                        '  npm:\n'
                        '    name: "{{input.package}}"\n'
                        '    global: yes\n'
                        '    state: present\n'
                        '\n'
                        '- name: Verify {{input.package}} is installed\n'
                        '  command: "npm list -g {{input.package}}"\n'
                        '  register: npm_check\n'
                        '  changed_when: false\n'
                    ),
                    'schema': {
                        'input': {
                            'package': {'type': 'string', 'description': 'NPM package name'},
                        },
                        'required': ['package'],
                    },
                },
                'params': {'package': ['pm2', 'yarn', 'typescript', 'eslint', 'webpack', 'nodemon', 'express', 'next']},
                'prompts': [
                    'Create an Ansible action to install {package} globally via npm',
                    'Ansible playbook that installs the {package} npm package globally',
                ],
                'explanation': 'Ansible action that installs {package} globally via npm and verifies the installation.',
            },
            {
                'name': 'apt-upgrade-all',
                'template': {
                    'name': 'Upgrade all apt packages',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Update apt cache\n'
                        '  apt:\n'
                        '    update_cache: yes\n'
                        '\n'
                        '- name: Upgrade all packages\n'
                        '  apt:\n'
                        '    upgrade: "{{input.upgrade_type}}"\n'
                        '  register: upgrade_result\n'
                        '\n'
                        '- name: Check if reboot is needed\n'
                        '  stat:\n'
                        '    path: /var/run/reboot-required\n'
                        '  register: reboot_required\n'
                        '\n'
                        '- name: Display reboot status\n'
                        '  debug:\n'
                        '    msg: "Reboot required: {{ reboot_required.stat.exists }}"\n'
                    ),
                    'schema': {
                        'input': {
                            'upgrade_type': {'type': 'string', 'description': 'Upgrade type: safe, full, dist (default safe)'},
                        },
                        'required': [],
                    },
                },
                'params': {'upgrade_type': ['safe', 'full', 'dist']},
                'prompts': [
                    'Create an Ansible action to perform a {upgrade_type} apt upgrade',
                    'Ansible playbook that runs a {upgrade_type} upgrade of all system packages',
                ],
                'explanation': 'Ansible action that performs a {upgrade_type} upgrade of all apt packages and checks if a reboot is required.',
            },
            {
                'name': 'package-version-pin',
                'template': {
                    'name': 'Pin {package} version',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Install {{input.package}} at specific version\n'
                        '  apt:\n'
                        '    name: "{{input.package}}={{input.version}}"\n'
                        '    state: present\n'
                        '    force: yes\n'
                        '\n'
                        '- name: Hold {{input.package}} at current version\n'
                        '  dpkg_selections:\n'
                        '    name: "{{input.package}}"\n'
                        '    selection: hold\n'
                    ),
                    'schema': {
                        'input': {
                            'package': {'type': 'string', 'description': 'Package name to pin'},
                            'version': {'type': 'string', 'description': 'Exact version string to pin to'},
                        },
                        'required': ['package', 'version'],
                    },
                },
                'params': {'package': ['docker-ce', 'kubelet', 'kubeadm', 'kubectl', 'nginx', 'postgresql']},
                'prompts': [
                    'Create an Ansible action to pin {package} to a specific version',
                    'Ansible playbook that installs and holds {package} at a pinned version',
                ],
                'explanation': 'Ansible action that installs {package} at a specific version and marks it as held to prevent automatic upgrades.',
            },
            {
                'name': 'repo-management',
                'template': {
                    'name': 'Add {repo} apt repository',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Install prerequisite packages\n'
                        '  apt:\n'
                        '    name:\n'
                        '      - apt-transport-https\n'
                        '      - ca-certificates\n'
                        '      - gnupg\n'
                        '    state: present\n'
                        '\n'
                        '- name: Add GPG key for {{input.repo_name}}\n'
                        '  apt_key:\n'
                        '    url: "{{input.gpg_key_url}}"\n'
                        '    state: present\n'
                        '  when: input.gpg_key_url is defined and input.gpg_key_url != ""\n'
                        '\n'
                        '- name: Add {{input.repo_name}} repository\n'
                        '  apt_repository:\n'
                        '    repo: "{{input.repo_line}}"\n'
                        '    state: present\n'
                        '    filename: "{{input.repo_name}}"\n'
                        '    update_cache: yes\n'
                    ),
                    'schema': {
                        'input': {
                            'repo_name': {'type': 'string', 'description': 'Repository name identifier'},
                            'repo_line': {'type': 'string', 'description': 'Full apt repository line'},
                            'gpg_key_url': {'type': 'string', 'description': 'URL to GPG key (optional)'},
                        },
                        'required': ['repo_name', 'repo_line'],
                    },
                },
                'params': {'repo': ['docker', 'kubernetes', 'nodejs', 'postgresql', 'grafana', 'elasticsearch']},
                'prompts': [
                    'Create an Ansible action to add the {repo} apt repository',
                    'Ansible playbook that configures the {repo} package repository with GPG key',
                ],
                'explanation': 'Ansible action that adds the {repo} apt repository with GPG key verification and cache update.',
            },
            {
                'name': 'package-removal',
                'template': {
                    'name': 'Remove {package} with cleanup',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Remove {{input.package}}\n'
                        '  apt:\n'
                        '    name: "{{input.package}}"\n'
                        '    state: absent\n'
                        '    purge: yes\n'
                        '\n'
                        '- name: Autoremove unused dependencies\n'
                        '  apt:\n'
                        '    autoremove: yes\n'
                        '\n'
                        '- name: Clean apt cache\n'
                        '  apt:\n'
                        '    autoclean: yes\n'
                    ),
                    'schema': {
                        'input': {
                            'package': {'type': 'string', 'description': 'Package name to remove'},
                        },
                        'required': ['package'],
                    },
                },
                'params': {'package': ['apache2', 'mysql-server', 'sendmail', 'telnet', 'rsh-server', 'ftp']},
                'prompts': [
                    'Create an Ansible action to remove {package} and clean up',
                    'Ansible playbook that purges {package} and removes unused dependencies',
                ],
                'explanation': 'Ansible action that removes {package} with purge, autoremoving unused dependencies and cleaning apt cache.',
            },
            {
                'name': 'flatpak-install',
                'template': {
                    'name': 'Install {package} via flatpak',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Ensure flatpak is installed\n'
                        '  package:\n'
                        '    name: flatpak\n'
                        '    state: present\n'
                        '\n'
                        '- name: Add Flathub repository\n'
                        '  command: "flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo"\n'
                        '  changed_when: false\n'
                        '\n'
                        '- name: Install {{input.package}} via flatpak\n'
                        '  flatpak:\n'
                        '    name: "{{input.package}}"\n'
                        '    state: present\n'
                        '    remote: flathub\n'
                        '\n'
                        '- name: Verify flatpak installation\n'
                        '  command: "flatpak info {{input.package}}"\n'
                        '  register: flatpak_check\n'
                        '  changed_when: false\n'
                    ),
                    'schema': {
                        'input': {
                            'package': {'type': 'string', 'description': 'Flatpak application ID (e.g. org.gimp.GIMP)'},
                        },
                        'required': ['package'],
                    },
                },
                'params': {'package': ['org.gimp.GIMP', 'org.mozilla.firefox', 'org.videolan.VLC', 'com.visualstudio.code', 'org.libreoffice.LibreOffice']},
                'prompts': [
                    'Create an Ansible action to install {package} via flatpak',
                    'Ansible playbook that installs the {package} flatpak application from Flathub',
                ],
                'explanation': 'Ansible action that installs {package} via flatpak from the Flathub repository with verification.',
            },
            {
                'name': 'snap-install',
                'template': {
                    'name': 'Install {package} via snap',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Ensure snapd is installed\n'
                        '  package:\n'
                        '    name: snapd\n'
                        '    state: present\n'
                        '\n'
                        '- name: Start and enable snapd\n'
                        '  systemd:\n'
                        '    name: snapd\n'
                        '    state: started\n'
                        '    enabled: yes\n'
                        '\n'
                        '- name: Install {{input.package}} via snap\n'
                        '  snap:\n'
                        '    name: "{{input.package}}"\n'
                        '    channel: "{{input.channel}}"\n'
                        '    classic: "{{input.classic}}"\n'
                        '    state: present\n'
                        '\n'
                        '- name: Verify snap installation\n'
                        '  command: "snap info {{input.package}}"\n'
                        '  register: snap_check\n'
                        '  changed_when: false\n'
                    ),
                    'schema': {
                        'input': {
                            'package': {'type': 'string', 'description': 'Snap package name'},
                            'channel': {'type': 'string', 'description': 'Snap channel (stable, edge, beta, candidate)'},
                            'classic': {'type': 'string', 'description': 'Use classic confinement: yes/no'},
                        },
                        'required': ['package'],
                    },
                },
                'params': {'package': ['lxd', 'microk8s', 'go', 'node', 'kubectl', 'docker', 'helm']},
                'prompts': [
                    'Create an Ansible action to install {package} via snap',
                    'Ansible playbook that installs {package} as a snap package',
                ],
                'explanation': 'Ansible action that installs {package} via snap with configurable channel and confinement mode.',
            },
            {
                'name': 'gem-install',
                'template': {
                    'name': 'Install {package} via gem',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Ensure Ruby is installed\n'
                        '  package:\n'
                        '    name:\n'
                        '      - ruby\n'
                        '      - ruby-dev\n'
                        '    state: present\n'
                        '\n'
                        '- name: Install {{input.package}} gem\n'
                        '  gem:\n'
                        '    name: "{{input.package}}"\n'
                        '    version: "{{input.version}}"\n'
                        '    state: present\n'
                        '    user_install: no\n'
                        '  when: input.version is defined and input.version != ""\n'
                        '\n'
                        '- name: Install {{input.package}} gem (latest)\n'
                        '  gem:\n'
                        '    name: "{{input.package}}"\n'
                        '    state: latest\n'
                        '    user_install: no\n'
                        '  when: input.version is not defined or input.version == ""\n'
                        '\n'
                        '- name: Verify gem installation\n'
                        '  command: "gem list {{input.package}}"\n'
                        '  register: gem_check\n'
                        '  changed_when: false\n'
                    ),
                    'schema': {
                        'input': {
                            'package': {'type': 'string', 'description': 'Ruby gem name'},
                            'version': {'type': 'string', 'description': 'Gem version (optional)'},
                        },
                        'required': ['package'],
                    },
                },
                'params': {'package': ['bundler', 'rake', 'rails', 'puma', 'sinatra', 'fpm', 'chef']},
                'prompts': [
                    'Create an Ansible action to install the {package} Ruby gem',
                    'Ansible playbook that installs {package} via gem with optional version pinning',
                ],
                'explanation': 'Ansible action that installs the {package} Ruby gem system-wide with optional version pinning.',
            },
            {
                'name': 'cargo-install',
                'template': {
                    'name': 'Install {package} via cargo',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Check if Rust/Cargo is installed\n'
                        '  command: cargo --version\n'
                        '  register: cargo_check\n'
                        '  changed_when: false\n'
                        '  failed_when: false\n'
                        '\n'
                        '- name: Install Rust via rustup\n'
                        '  shell: "curl --proto \'=https\' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y"\n'
                        '  args:\n'
                        '    creates: "/root/.cargo/bin/cargo"\n'
                        '  when: cargo_check.rc != 0\n'
                        '\n'
                        '- name: Install {{input.package}} via cargo\n'
                        '  command: "/root/.cargo/bin/cargo install {{input.package}}"\n'
                        '  register: install_result\n'
                        '  environment:\n'
                        '    PATH: "/root/.cargo/bin:{{ ansible_env.PATH }}"\n'
                        '\n'
                        '- name: Verify installation\n'
                        '  command: "which {{input.binary_name}}"\n'
                        '  register: binary_check\n'
                        '  changed_when: false\n'
                        '  environment:\n'
                        '    PATH: "/root/.cargo/bin:{{ ansible_env.PATH }}"\n'
                    ),
                    'schema': {
                        'input': {
                            'package': {'type': 'string', 'description': 'Cargo crate name'},
                            'binary_name': {'type': 'string', 'description': 'Expected binary name after install'},
                        },
                        'required': ['package', 'binary_name'],
                    },
                },
                'params': {'package': ['ripgrep', 'fd-find', 'bat', 'exa', 'tokei', 'hyperfine', 'starship']},
                'prompts': [
                    'Create an Ansible action to install {package} via Cargo',
                    'Ansible playbook that installs the {package} Rust tool using cargo install',
                ],
                'explanation': 'Ansible action that installs {package} via Cargo (Rust package manager), installing Rust first if needed.',
            },
        ]


def get_generators():
    return [PackagesGenerator()]
