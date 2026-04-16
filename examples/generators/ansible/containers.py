"""Container management Ansible action generators - 8 seeds for Docker operations."""

from examples.generators.base_generator import AnsibleActionGenerator


class ContainersGenerator(AnsibleActionGenerator):
    category = "ansible.containers"
    subcategory = "containers"

    def seeds(self):
        return [
            {
                'name': 'docker-image-pull',
                'template': {
                    'name': 'Pull Docker image {image}',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Pull Docker image {{input.image_name}}:{{input.tag}}\n'
                        '  docker_image:\n'
                        '    name: "{{input.image_name}}"\n'
                        '    tag: "{{input.tag}}"\n'
                        '    source: pull\n'
                        '    force_source: yes\n'
                    ),
                    'schema': {
                        'input': {
                            'image_name': {'type': 'string', 'description': 'Docker image name'},
                            'tag': {'type': 'string', 'description': 'Image tag (default latest)'},
                        },
                        'required': ['image_name'],
                    },
                },
                'params': {'image': ['nginx', 'redis', 'postgres', 'node', 'python', 'ubuntu', 'alpine', 'grafana/grafana']},
                'prompts': [
                    'Create an Ansible action to pull the {image} Docker image',
                    'Ansible playbook that pulls the latest {image} Docker image',
                ],
                'explanation': 'Ansible action that pulls the {image} Docker image with force refresh to ensure the latest version.',
            },
            {
                'name': 'docker-container-run',
                'template': {
                    'name': 'Run {container} container',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Run {{input.container_name}} container\n'
                        '  docker_container:\n'
                        '    name: "{{input.container_name}}"\n'
                        '    image: "{{input.image}}"\n'
                        '    state: started\n'
                        '    restart_policy: unless-stopped\n'
                        '    ports:\n'
                        '      - "{{input.host_port}}:{{input.container_port}}"\n'
                        '    env: "{{input.environment}}"\n'
                        '    volumes:\n'
                        '      - "{{input.volume_mount}}"\n'
                    ),
                    'schema': {
                        'input': {
                            'container_name': {'type': 'string', 'description': 'Container name'},
                            'image': {'type': 'string', 'description': 'Docker image to use'},
                            'host_port': {'type': 'string', 'description': 'Host port to map'},
                            'container_port': {'type': 'string', 'description': 'Container port to expose'},
                            'environment': {'type': 'string', 'description': 'Environment variables as JSON'},
                            'volume_mount': {'type': 'string', 'description': 'Volume mount (host:container)'},
                        },
                        'required': ['container_name', 'image'],
                    },
                },
                'params': {'container': ['web', 'api', 'db', 'cache', 'worker', 'proxy']},
                'prompts': [
                    'Create an Ansible action to run a {container} Docker container',
                    'Ansible playbook that starts a {container} container with port mapping and volumes',
                ],
                'explanation': 'Ansible action that runs a {container} Docker container with port mapping, environment variables, and volume mounts.',
            },
            {
                'name': 'docker-network',
                'template': {
                    'name': 'Create Docker network',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Create Docker network {{input.network_name}}\n'
                        '  docker_network:\n'
                        '    name: "{{input.network_name}}"\n'
                        '    driver: "{{input.driver}}"\n'
                        '    ipam_config:\n'
                        '      - subnet: "{{input.subnet}}"\n'
                        '    state: present\n'
                    ),
                    'schema': {
                        'input': {
                            'network_name': {'type': 'string', 'description': 'Docker network name'},
                            'driver': {'type': 'string', 'description': 'Network driver (default bridge)'},
                            'subnet': {'type': 'string', 'description': 'Network subnet CIDR'},
                        },
                        'required': ['network_name'],
                    },
                },
                'params': {'driver': ['bridge', 'overlay', 'macvlan']},
                'prompts': [
                    'Create an Ansible action to create a Docker {driver} network',
                    'Ansible playbook that sets up a {driver} Docker network with IPAM',
                ],
                'explanation': 'Ansible action that creates a Docker {driver} network with custom IPAM subnet configuration.',
            },
            {
                'name': 'docker-volume',
                'template': {
                    'name': 'Create Docker volume',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Create Docker volume {{input.volume_name}}\n'
                        '  docker_volume:\n'
                        '    name: "{{input.volume_name}}"\n'
                        '    driver: "{{input.driver}}"\n'
                        '    state: present\n'
                        '\n'
                        '- name: Verify volume exists\n'
                        '  command: "docker volume inspect {{input.volume_name}}"\n'
                        '  register: vol_info\n'
                        '  changed_when: false\n'
                    ),
                    'schema': {
                        'input': {
                            'volume_name': {'type': 'string', 'description': 'Docker volume name'},
                            'driver': {'type': 'string', 'description': 'Volume driver (default local)'},
                        },
                        'required': ['volume_name'],
                    },
                },
                'params': {'purpose': ['database', 'application', 'logs', 'backups', 'shared']},
                'prompts': [
                    'Create an Ansible action to create a {purpose} Docker volume',
                    'Ansible playbook that provisions a {purpose} Docker volume for persistent storage',
                ],
                'explanation': 'Ansible action that creates a {purpose} Docker volume for persistent container data storage.',
            },
            {
                'name': 'docker-compose-deploy',
                'template': {
                    'name': 'Deploy with docker-compose',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Copy docker-compose file\n'
                        '  copy:\n'
                        '    src: "{{input.compose_src}}"\n'
                        '    dest: "{{input.compose_dest}}"\n'
                        '    mode: "0644"\n'
                        '\n'
                        '- name: Pull images for compose project\n'
                        '  command: "docker compose -f {{input.compose_dest}} pull"\n'
                        '  register: pull_result\n'
                        '\n'
                        '- name: Deploy compose stack\n'
                        '  command: "docker compose -f {{input.compose_dest}} up -d --remove-orphans"\n'
                        '  register: deploy_result\n'
                    ),
                    'schema': {
                        'input': {
                            'compose_src': {'type': 'string', 'description': 'Source docker-compose.yml path'},
                            'compose_dest': {'type': 'string', 'description': 'Destination path on target'},
                        },
                        'required': ['compose_src', 'compose_dest'],
                    },
                },
                'params': {'stack': ['web', 'monitoring', 'database', 'application', 'infrastructure']},
                'prompts': [
                    'Create an Ansible action to deploy a {stack} docker-compose stack',
                    'Ansible playbook that deploys {stack} services using docker-compose',
                ],
                'explanation': 'Ansible action that deploys a {stack} docker-compose stack by copying the file, pulling images, and starting services.',
            },
            {
                'name': 'container-health-check',
                'template': {
                    'name': 'Check container health',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Get {{input.container_name}} status\n'
                        '  command: "docker inspect --format=\'{{.State.Status}}\'  {{input.container_name}}"\n'
                        '  register: container_status\n'
                        '  changed_when: false\n'
                        '  failed_when: false\n'
                        '\n'
                        '- name: Assert container is running\n'
                        '  assert:\n'
                        '    that:\n'
                        '      - container_status.stdout == "running"\n'
                        '    fail_msg: "Container {{input.container_name}} is {{ container_status.stdout }}"\n'
                        '\n'
                        '- name: Check container health\n'
                        '  command: "docker inspect --format=\'{{.State.Health.Status}}\'  {{input.container_name}}"\n'
                        '  register: health_status\n'
                        '  changed_when: false\n'
                        '  failed_when: false\n'
                        '  when: container_status.stdout == "running"\n'
                    ),
                    'schema': {
                        'input': {
                            'container_name': {'type': 'string', 'description': 'Container name to check'},
                        },
                        'required': ['container_name'],
                    },
                },
                'params': {'service': ['web', 'api', 'database', 'cache', 'proxy', 'worker']},
                'prompts': [
                    'Create an Ansible action to check the health of a {service} container',
                    'Ansible playbook that validates {service} Docker container health status',
                ],
                'explanation': 'Ansible action that checks the running status and health of a {service} Docker container using docker inspect.',
            },
            {
                'name': 'registry-auth',
                'template': {
                    'name': 'Docker registry login',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Login to Docker registry\n'
                        '  docker_login:\n'
                        '    registry_url: "{{input.registry_url}}"\n'
                        '    username: "{{input.username}}"\n'
                        '    password: "{{input.password}}"\n'
                        '    reauthorize: yes\n'
                    ),
                    'schema': {
                        'input': {
                            'registry_url': {'type': 'string', 'description': 'Registry URL'},
                            'username': {'type': 'string', 'description': 'Registry username'},
                            'password': {'type': 'string', 'description': 'Registry password or token'},
                        },
                        'required': ['registry_url', 'username', 'password'],
                    },
                },
                'params': {'registry': ['dockerhub', 'ecr', 'gcr', 'acr', 'ghcr', 'harbor']},
                'prompts': [
                    'Create an Ansible action to authenticate with {registry} Docker registry',
                    'Ansible playbook that logs in to {registry} container registry',
                ],
                'explanation': 'Ansible action that authenticates with the {registry} Docker registry for pulling private images.',
            },
            {
                'name': 'multi-container-stack',
                'template': {
                    'name': 'Deploy multi-container stack',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Create application network\n'
                        '  docker_network:\n'
                        '    name: "{{input.network_name}}"\n'
                        '    state: present\n'
                        '\n'
                        '- name: Create data volume\n'
                        '  docker_volume:\n'
                        '    name: "{{input.volume_name}}"\n'
                        '    state: present\n'
                        '\n'
                        '- name: Start database container\n'
                        '  docker_container:\n'
                        '    name: "{{input.db_container}}"\n'
                        '    image: "{{input.db_image}}"\n'
                        '    state: started\n'
                        '    restart_policy: unless-stopped\n'
                        '    networks:\n'
                        '      - name: "{{input.network_name}}"\n'
                        '    volumes:\n'
                        '      - "{{input.volume_name}}:/var/lib/data"\n'
                        '\n'
                        '- name: Start application container\n'
                        '  docker_container:\n'
                        '    name: "{{input.app_container}}"\n'
                        '    image: "{{input.app_image}}"\n'
                        '    state: started\n'
                        '    restart_policy: unless-stopped\n'
                        '    networks:\n'
                        '      - name: "{{input.network_name}}"\n'
                        '    ports:\n'
                        '      - "{{input.app_port}}:{{input.app_port}}"\n'
                    ),
                    'schema': {
                        'input': {
                            'network_name': {'type': 'string', 'description': 'Docker network name'},
                            'volume_name': {'type': 'string', 'description': 'Data volume name'},
                            'db_container': {'type': 'string', 'description': 'Database container name'},
                            'db_image': {'type': 'string', 'description': 'Database Docker image'},
                            'app_container': {'type': 'string', 'description': 'Application container name'},
                            'app_image': {'type': 'string', 'description': 'Application Docker image'},
                            'app_port': {'type': 'string', 'description': 'Application port'},
                        },
                        'required': ['network_name', 'db_image', 'app_image'],
                    },
                },
                'params': {'stack_type': ['web-app', 'microservice', 'api-backend', 'data-pipeline']},
                'prompts': [
                    'Create an Ansible action to deploy a {stack_type} multi-container stack',
                    'Ansible playbook that sets up a {stack_type} with database and app containers',
                ],
                'explanation': 'Ansible action that deploys a {stack_type} multi-container stack with networking, volumes, database, and application.',
            },
            {
                'name': 'docker-prune',
                'template': {
                    'name': 'Docker system prune',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Prune stopped containers\n'
                        '  docker_prune:\n'
                        '    containers: yes\n'
                        '    containers_filters:\n'
                        '      until: "{{input.older_than}}"\n'
                        '  register: container_prune\n'
                        '\n'
                        '- name: Prune unused images\n'
                        '  docker_prune:\n'
                        '    images: yes\n'
                        '    images_filters:\n'
                        '      dangling: "{{input.dangling_only}}"\n'
                        '  register: image_prune\n'
                        '\n'
                        '- name: Prune unused volumes\n'
                        '  docker_prune:\n'
                        '    volumes: yes\n'
                        '  register: volume_prune\n'
                        '  when: input.prune_volumes is defined and input.prune_volumes == "yes"\n'
                        '\n'
                        '- name: Prune unused networks\n'
                        '  docker_prune:\n'
                        '    networks: yes\n'
                        '  register: network_prune\n'
                        '\n'
                        '- name: Report prune results\n'
                        '  debug:\n'
                        '    msg: "Containers: {{ container_prune.containers_pruned | default(0) }}, Images: {{ image_prune.images_pruned | default(0) }}, Space reclaimed: {{ image_prune.space_reclaimed | default(0) }} bytes"\n'
                    ),
                    'schema': {
                        'input': {
                            'older_than': {'type': 'string', 'description': 'Remove resources older than (e.g. 24h, 168h)'},
                            'dangling_only': {'type': 'string', 'description': 'Only prune dangling images: true/false'},
                            'prune_volumes': {'type': 'string', 'description': 'Also prune volumes: yes/no'},
                        },
                        'required': ['older_than'],
                    },
                },
                'params': {'target': ['server', 'ci-runner', 'staging', 'production']},
                'prompts': [
                    'Create an Ansible action to prune Docker resources on a {target}',
                    'Ansible playbook that cleans up unused Docker containers, images, and networks on {target}',
                ],
                'explanation': 'Ansible action that prunes unused Docker containers, images, networks, and optionally volumes on {target} to reclaim disk space.',
            },
            {
                'name': 'docker-swarm',
                'template': {
                    'name': 'Initialize Docker Swarm',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Check if swarm is already initialized\n'
                        '  command: docker info --format "{{.Swarm.LocalNodeState}}"\n'
                        '  register: swarm_state\n'
                        '  changed_when: false\n'
                        '  failed_when: false\n'
                        '\n'
                        '- name: Initialize Docker Swarm\n'
                        '  docker_swarm:\n'
                        '    state: present\n'
                        '    advertise_addr: "{{input.advertise_addr}}"\n'
                        '  register: swarm_init\n'
                        '  when: swarm_state.stdout != "active"\n'
                        '\n'
                        '- name: Get swarm join tokens\n'
                        '  command: docker swarm join-token {{ item }} -q\n'
                        '  loop:\n'
                        '    - worker\n'
                        '    - manager\n'
                        '  register: join_tokens\n'
                        '  changed_when: false\n'
                        '\n'
                        '- name: Display swarm info\n'
                        '  debug:\n'
                        '    msg: "Swarm initialized. Worker token: {{ join_tokens.results[0].stdout }}, Manager token: {{ join_tokens.results[1].stdout }}"\n'
                    ),
                    'schema': {
                        'input': {
                            'advertise_addr': {'type': 'string', 'description': 'IP address or interface to advertise to other nodes'},
                        },
                        'required': ['advertise_addr'],
                    },
                },
                'params': {'env': ['production', 'staging', 'development', 'lab']},
                'prompts': [
                    'Create an Ansible action to initialize a Docker Swarm in {env}',
                    'Ansible playbook that sets up Docker Swarm mode for {env} cluster',
                ],
                'explanation': 'Ansible action that initializes Docker Swarm mode in {env} and retrieves worker and manager join tokens.',
            },
            {
                'name': 'container-exec',
                'template': {
                    'name': 'Execute command in container',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Check {{input.container_name}} is running\n'
                        '  command: "docker inspect --format=\'{{.State.Running}}\' {{input.container_name}}"\n'
                        '  register: container_running\n'
                        '  changed_when: false\n'
                        '  failed_when: container_running.stdout != "true"\n'
                        '\n'
                        '- name: Execute command in {{input.container_name}}\n'
                        '  command: "docker exec {{input.container_name}} {{input.command}}"\n'
                        '  register: exec_result\n'
                        '\n'
                        '- name: Display exec output\n'
                        '  debug:\n'
                        '    msg: "{{ exec_result.stdout_lines }}"\n'
                    ),
                    'schema': {
                        'input': {
                            'container_name': {'type': 'string', 'description': 'Name of the running container'},
                            'command': {'type': 'string', 'description': 'Command to execute inside the container'},
                        },
                        'required': ['container_name', 'command'],
                    },
                },
                'params': {'task': ['health-check', 'migration', 'cache-clear', 'config-reload', 'diagnostics']},
                'prompts': [
                    'Create an Ansible action to exec a {task} command in a Docker container',
                    'Ansible playbook that runs a {task} command inside a running container',
                ],
                'explanation': 'Ansible action that executes a {task} command inside a running Docker container and displays the output.',
            },
            {
                'name': 'docker-buildx',
                'template': {
                    'name': 'Build multi-platform image with buildx',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Check if buildx is available\n'
                        '  command: docker buildx version\n'
                        '  register: buildx_check\n'
                        '  changed_when: false\n'
                        '  failed_when: false\n'
                        '\n'
                        '- name: Create buildx builder\n'
                        '  command: "docker buildx create --name {{input.builder_name}} --use"\n'
                        '  when: buildx_check.rc == 0\n'
                        '  register: builder_create\n'
                        '  failed_when: false\n'
                        '\n'
                        '- name: Build multi-platform image\n'
                        '  command: >-\n'
                        '    docker buildx build\n'
                        '    --platform {{input.platforms}}\n'
                        '    -t {{input.image_name}}:{{input.tag}}\n'
                        '    -f {{input.dockerfile}}\n'
                        '    --push={{ input.push | default("false") }}\n'
                        '    {{input.build_context}}\n'
                        '  register: build_result\n'
                        '\n'
                        '- name: Display build result\n'
                        '  debug:\n'
                        '    msg: "Multi-platform build complete for {{ input.image_name }}:{{ input.tag }} ({{ input.platforms }})"\n'
                    ),
                    'schema': {
                        'input': {
                            'builder_name': {'type': 'string', 'description': 'Name for the buildx builder instance'},
                            'image_name': {'type': 'string', 'description': 'Image name to build'},
                            'tag': {'type': 'string', 'description': 'Image tag'},
                            'platforms': {'type': 'string', 'description': 'Comma-separated platforms (e.g. linux/amd64,linux/arm64)'},
                            'dockerfile': {'type': 'string', 'description': 'Path to the Dockerfile'},
                            'build_context': {'type': 'string', 'description': 'Build context directory'},
                            'push': {'type': 'string', 'description': 'Push to registry after build: true/false'},
                        },
                        'required': ['image_name', 'tag', 'platforms', 'build_context'],
                    },
                },
                'params': {'arch': ['amd64-arm64', 'amd64-arm-arm64', 'amd64-only', 'arm64-only']},
                'prompts': [
                    'Create an Ansible action to build a multi-platform Docker image for {arch}',
                    'Ansible playbook that uses docker buildx for a {arch} cross-platform build',
                ],
                'explanation': 'Ansible action that uses docker buildx to build a multi-platform image for {arch} targets with optional registry push.',
            },
        ]


def get_generators():
    return [ContainersGenerator()]
