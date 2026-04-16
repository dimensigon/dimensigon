"""Shell action generators for container management operations."""

from examples.generators.base_generator import ShellActionGenerator


class ContainersGenerator(ShellActionGenerator):
    category = "shell.containers"
    subcategory = "containers"

    def seeds(self):
        return [
            {
                'name': 'docker-run',
                'template': {
                    'name': '{app}-docker-run',
                    'action_type': 'SHELL',
                    'code': 'docker run -d --name {{input.container_name}} --restart={{input.restart_policy}} -p {{input.host_port}}:{{input.container_port}} -e {{input.env_var}} {{input.image}}:{{input.tag}} && sleep 2 && if docker inspect --format="{{.State.Running}}" {{input.container_name}} 2>/dev/null | grep -q "true"; then echo "Container {{input.container_name}} is running"; docker port {{input.container_name}}; else echo "FAILED: Container not running" >&2; docker logs {{input.container_name}} 2>&1; exit 1; fi',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'container_name': {'type': 'string', 'description': 'Name for the container'},
                            'image': {'type': 'string', 'description': 'Docker image name'},
                            'tag': {'type': 'string', 'description': 'Image tag (e.g. latest, 3.9, alpine)'},
                            'host_port': {'type': 'integer', 'description': 'Host port to bind'},
                            'container_port': {'type': 'integer', 'description': 'Container port to expose'},
                            'env_var': {'type': 'string', 'description': 'Environment variable in KEY=VALUE format'},
                            'restart_policy': {'type': 'string', 'description': 'Restart policy (no, always, unless-stopped, on-failure)'},
                        },
                        'required': ['container_name', 'image', 'tag', 'host_port', 'container_port', 'env_var', 'restart_policy'],
                    },
                },
                'params': {'app': ['webapp', 'api', 'worker', 'redis', 'nginx', 'postgres']},
                'prompts': [
                    'Run a {app} Docker container with port mapping and environment variables',
                    'Create a DM action to start a {app} container with docker run',
                    'Write a shell action that launches a {app} Docker container',
                ],
                'explanation': 'Starts a {app} Docker container with port mapping, environment variables, and restart policy.',
                'features': ['schema_variables'],
            },
            {
                'name': 'docker-stop-rm',
                'template': {
                    'name': '{app}-docker-stop-rm',
                    'action_type': 'SHELL',
                    'code': 'if docker inspect {{input.container_name}} > /dev/null 2>&1; then echo "Stopping container {{input.container_name}}..." && docker stop -t {{input.timeout}} {{input.container_name}} 2>&1 && docker rm {{input.container_name}} 2>&1 && echo "Container {{input.container_name}} stopped and removed"; else echo "Container {{input.container_name}} does not exist"; fi',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'container_name': {'type': 'string', 'description': 'Name of the container to stop and remove'},
                            'timeout': {'type': 'integer', 'description': 'Seconds to wait before killing the container'},
                        },
                        'required': ['container_name', 'timeout'],
                    },
                },
                'params': {'app': ['webapp', 'api', 'worker', 'redis', 'nginx', 'postgres']},
                'prompts': [
                    'Stop and remove the {app} Docker container',
                    'Create a DM action to tear down the {app} container',
                    'Write a shell action that stops and removes a {app} container',
                ],
                'explanation': 'Gracefully stops and removes the {app} Docker container with a configurable timeout.',
                'features': ['schema_variables'],
            },
            {
                'name': 'docker-build',
                'template': {
                    'name': '{app}-docker-build',
                    'action_type': 'SHELL',
                    'code': 'cd {{input.build_context}} && docker build -t {{input.image_name}}:{{input.tag}} -f {{input.dockerfile}} --no-cache={{input.no_cache}} . 2>&1 && docker images {{input.image_name}}:{{input.tag}} && echo "Image built: {{input.image_name}}:{{input.tag}}" || (echo "FAILED: Docker build error" >&2; exit 1)',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'build_context': {'type': 'string', 'description': 'Path to the build context directory'},
                            'dockerfile': {'type': 'string', 'description': 'Path to the Dockerfile (relative to build context)'},
                            'image_name': {'type': 'string', 'description': 'Name for the built image'},
                            'tag': {'type': 'string', 'description': 'Tag for the built image'},
                            'no_cache': {'type': 'string', 'description': 'Whether to disable build cache (true or false)'},
                        },
                        'required': ['build_context', 'dockerfile', 'image_name', 'tag', 'no_cache'],
                    },
                },
                'params': {'app': ['webapp', 'api', 'worker', 'frontend', 'microservice']},
                'prompts': [
                    'Build a Docker image for the {app} application',
                    'Create a DM action to build a {app} Docker image from Dockerfile',
                    'Write a shell action that builds a {app} container image',
                ],
                'explanation': 'Builds a Docker image for the {app} application from a specified Dockerfile and build context.',
                'features': ['schema_variables'],
            },
            {
                'name': 'docker-compose-up',
                'template': {
                    'name': '{app}-compose-up',
                    'action_type': 'SHELL',
                    'code': 'cd {{input.project_dir}} && docker-compose -f {{input.compose_file}} up -d --remove-orphans 2>&1 && echo "=== Running containers ===" && docker-compose -f {{input.compose_file}} ps 2>&1 && echo "docker-compose stack started from {{input.compose_file}}" || (echo "FAILED: docker-compose up error" >&2; exit 1)',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'project_dir': {'type': 'string', 'description': 'Path to the project directory'},
                            'compose_file': {'type': 'string', 'description': 'docker-compose file name (e.g. docker-compose.yml)'},
                        },
                        'required': ['project_dir', 'compose_file'],
                    },
                },
                'params': {'app': ['webapp', 'stack', 'platform', 'infra', 'monitoring']},
                'prompts': [
                    'Start the {app} docker-compose stack in detached mode',
                    'Create a DM action to deploy {app} with docker-compose up -d',
                    'Write a shell action that launches the {app} compose stack',
                ],
                'explanation': 'Starts the {app} docker-compose stack in detached mode, removing orphan containers.',
                'features': ['schema_variables'],
            },
            {
                'name': 'docker-system-prune',
                'template': {
                    'name': '{target}-docker-prune',
                    'action_type': 'SHELL',
                    'code': 'echo "=== Disk usage before prune ===" && docker system df 2>&1 && echo "=== Pruning unused resources ===" && docker system prune -af --volumes --filter "until={{input.older_than}}" 2>&1 && echo "=== Disk usage after prune ===" && docker system df 2>&1 && echo "Docker system prune completed"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'older_than': {'type': 'string', 'description': 'Remove resources older than this duration (e.g. 24h, 168h, 720h)'},
                        },
                        'required': ['older_than'],
                    },
                },
                'params': {'target': ['server', 'host', 'node', 'ci-runner']},
                'prompts': [
                    'Run docker system prune on the {target} to free disk space',
                    'Create a DM action to clean up unused Docker resources on {target}',
                    'Write a shell action that prunes Docker images, containers, and volumes on {target}',
                ],
                'explanation': 'Prunes unused Docker images, containers, networks, and volumes on the {target} to reclaim disk space.',
                'features': ['schema_variables'],
            },
            {
                'name': 'docker-network-create',
                'template': {
                    'name': '{app}-docker-network',
                    'action_type': 'SHELL',
                    'code': 'if docker network inspect {{input.network_name}} > /dev/null 2>&1; then echo "Network {{input.network_name}} already exists"; docker network inspect {{input.network_name}} --format="Driver: {{.Driver}}, Subnet: {{range .IPAM.Config}}{{.Subnet}}{{end}}" 2>&1; else docker network create --driver {{input.driver}} --subnet {{input.subnet}} --gateway {{input.gateway}} {{input.network_name}} 2>&1 && echo "Network created: {{input.network_name}} ({{input.driver}}, {{input.subnet}})"; fi',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'network_name': {'type': 'string', 'description': 'Name for the Docker network'},
                            'driver': {'type': 'string', 'description': 'Network driver (bridge, overlay, macvlan)'},
                            'subnet': {'type': 'string', 'description': 'Subnet CIDR (e.g. 172.20.0.0/16)'},
                            'gateway': {'type': 'string', 'description': 'Gateway IP address'},
                        },
                        'required': ['network_name', 'driver', 'subnet', 'gateway'],
                    },
                },
                'params': {'app': ['backend', 'frontend', 'monitoring', 'database', 'infra']},
                'prompts': [
                    'Create a Docker network for the {app} stack',
                    'Create a DM action to set up a Docker network for {app}',
                    'Write a shell action that creates a custom Docker network for {app}',
                ],
                'explanation': 'Creates a custom Docker network for the {app} stack with configurable driver and subnet.',
                'features': ['schema_variables'],
            },
            {
                'name': 'docker-volume-create',
                'template': {
                    'name': '{app}-docker-volume',
                    'action_type': 'SHELL',
                    'code': 'if docker volume inspect {{input.volume_name}} > /dev/null 2>&1; then echo "Volume {{input.volume_name}} already exists"; else docker volume create --driver {{input.driver}} --opt type={{input.fs_type}} --opt device={{input.device_path}} {{input.volume_name}} 2>&1 && echo "Volume created: {{input.volume_name}}"; fi && docker volume inspect {{input.volume_name}} 2>&1',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'volume_name': {'type': 'string', 'description': 'Name for the Docker volume'},
                            'driver': {'type': 'string', 'description': 'Volume driver (local, nfs, etc.)'},
                            'fs_type': {'type': 'string', 'description': 'Filesystem type (none, tmpfs, nfs, ext4)'},
                            'device_path': {'type': 'string', 'description': 'Device or host path to bind'},
                        },
                        'required': ['volume_name', 'driver', 'fs_type', 'device_path'],
                    },
                },
                'params': {'app': ['postgres', 'mysql', 'redis', 'elasticsearch', 'minio']},
                'prompts': [
                    'Create a Docker volume for {app} persistent data',
                    'Create a DM action to set up a Docker volume for {app} storage',
                    'Write a shell action that creates a Docker volume for {app}',
                ],
                'explanation': 'Creates a Docker volume for {app} persistent data storage with a configurable driver and mount options.',
                'features': ['schema_variables'],
            },
            {
                'name': 'container-health-check',
                'template': {
                    'name': '{app}-health-check',
                    'action_type': 'SHELL',
                    'code': 'HEALTH=$(docker inspect --format="{{.State.Health.Status}}" {{input.container_name}} 2>/dev/null) && if [ -z "$HEALTH" ]; then echo "No healthcheck configured for {{input.container_name}}"; RUNNING=$(docker inspect --format="{{.State.Running}}" {{input.container_name}} 2>/dev/null); echo "Running: $RUNNING"; elif [ "$HEALTH" = "healthy" ]; then echo "HEALTHY: {{input.container_name}}"; docker inspect --format="{{range .State.Health.Log}}{{.Output}}{{end}}" {{input.container_name}} 2>/dev/null | tail -5; else echo "UNHEALTHY: {{input.container_name}} (status: $HEALTH)" >&2; docker inspect --format="{{range .State.Health.Log}}{{.Output}}{{end}}" {{input.container_name}} 2>/dev/null | tail -5; exit 1; fi',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'container_name': {'type': 'string', 'description': 'Name of the container to health check'},
                        },
                        'required': ['container_name'],
                    },
                },
                'params': {'app': ['webapp', 'api', 'postgres', 'redis', 'nginx', 'worker']},
                'prompts': [
                    'Check the health status of the {app} container',
                    'Create a DM action to verify {app} container health',
                    'Write a shell action that inspects {app} container healthcheck status',
                ],
                'explanation': 'Checks the Docker health status of the {app} container and displays recent health log output.',
                'features': ['schema_variables'],
            },
            {
                'name': 'docker-pull',
                'template': {
                    'name': '{app}-docker-pull',
                    'action_type': 'SHELL',
                    'code': 'echo "Pulling {{input.image}}:{{input.tag}}..." && docker pull {{input.image}}:{{input.tag}} 2>&1 && docker image inspect {{input.image}}:{{input.tag}} --format="Size: {{.Size}}, Created: {{.Created}}" 2>&1 && echo "Image pulled: {{input.image}}:{{input.tag}}" || (echo "FAILED: Could not pull image" >&2; exit 1)',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'image': {'type': 'string', 'description': 'Docker image name (e.g. nginx, postgres, myregistry/myapp)'},
                            'tag': {'type': 'string', 'description': 'Image tag to pull'},
                        },
                        'required': ['image', 'tag'],
                    },
                },
                'params': {'app': ['nginx', 'postgres', 'redis', 'node', 'python', 'alpine']},
                'prompts': [
                    'Pull the {app} Docker image from registry',
                    'Create a DM action to pull a specific {app} image tag',
                    'Write a shell action that downloads the {app} Docker image',
                ],
                'explanation': 'Pulls the {app} Docker image from a registry and displays its size and creation date.',
                'features': ['schema_variables'],
            },
            {
                'name': 'docker-login',
                'template': {
                    'name': '{registry}-docker-login',
                    'action_type': 'SHELL',
                    'code': 'echo "{{input.password}}" | docker login {{input.registry_url}} -u {{input.username}} --password-stdin 2>&1 && echo "Logged in to registry: {{input.registry_url}}" || (echo "FAILED: Docker login error" >&2; exit 1)',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'registry_url': {'type': 'string', 'description': 'Docker registry URL (e.g. docker.io, ghcr.io, ecr.aws)'},
                            'username': {'type': 'string', 'description': 'Registry username'},
                            'password': {'type': 'string', 'description': 'Registry password or access token'},
                        },
                        'required': ['registry_url', 'username', 'password'],
                    },
                },
                'params': {'registry': ['dockerhub', 'ghcr', 'ecr', 'gcr', 'harbor']},
                'prompts': [
                    'Log in to the {registry} Docker registry',
                    'Create a DM action to authenticate with {registry}',
                    'Write a shell action for Docker login to {registry}',
                ],
                'explanation': 'Authenticates to the {registry} Docker registry using stdin for secure password passing.',
                'features': ['schema_variables'],
            },
            {
                'name': 'docker-logs-tail',
                'template': {
                    'name': '{app}-docker-logs',
                    'action_type': 'SHELL',
                    'code': 'if ! docker inspect {{input.container_name}} > /dev/null 2>&1; then echo "FAILED: Container {{input.container_name}} not found" >&2; exit 1; fi && echo "=== Last {{input.tail_lines}} log lines from {{input.container_name}} ===" && docker logs --tail {{input.tail_lines}} --timestamps {{input.container_name}} 2>&1',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'container_name': {'type': 'string', 'description': 'Name of the container to get logs from'},
                            'tail_lines': {'type': 'integer', 'description': 'Number of recent log lines to display'},
                        },
                        'required': ['container_name', 'tail_lines'],
                    },
                },
                'params': {'app': ['webapp', 'api', 'worker', 'nginx', 'postgres', 'redis']},
                'prompts': [
                    'Tail Docker logs for the {app} container',
                    'Create a DM action to view recent {app} container logs',
                    'Write a shell action that shows the last N log lines for {app}',
                ],
                'explanation': 'Displays the most recent log lines with timestamps from the {app} Docker container.',
                'features': ['schema_variables'],
            },
            {
                'name': 'docker-stats-check',
                'template': {
                    'name': '{app}-docker-stats',
                    'action_type': 'SHELL',
                    'code': 'if ! docker inspect {{input.container_name}} > /dev/null 2>&1; then echo "FAILED: Container {{input.container_name}} not found" >&2; exit 1; fi && echo "=== Resource usage for {{input.container_name}} ===" && docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}\t{{.PIDs}}" {{input.container_name}} 2>&1 && echo "=== Container inspect ===" && docker inspect --format="Status: {{.State.Status}}, Restarts: {{.RestartCount}}, StartedAt: {{.State.StartedAt}}" {{input.container_name}} 2>&1',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'container_name': {'type': 'string', 'description': 'Name of the container to check stats for'},
                        },
                        'required': ['container_name'],
                    },
                },
                'params': {'app': ['webapp', 'api', 'worker', 'postgres', 'redis', 'nginx']},
                'prompts': [
                    'Check Docker resource usage stats for the {app} container',
                    'Create a DM action to monitor {app} container resource consumption',
                    'Write a shell action that displays CPU, memory, and network stats for {app}',
                ],
                'explanation': 'Displays CPU, memory, network I/O, block I/O, and process stats for the {app} Docker container.',
                'features': ['schema_variables'],
            },
            {
                'name': 'docker-exec',
                'template': {
                    'name': '{app}-docker-exec',
                    'action_type': 'SHELL',
                    'code': 'if ! docker inspect {{input.container_name}} > /dev/null 2>&1; then echo "FAILED: Container {{input.container_name}} not found" >&2; exit 1; fi && if [ "$(docker inspect --format="{{.State.Running}}" {{input.container_name}} 2>/dev/null)" != "true" ]; then echo "FAILED: Container {{input.container_name}} is not running" >&2; exit 1; fi && echo "Executing command in {{input.container_name}}..." && docker exec {{input.container_name}} {{input.command}} 2>&1 && echo "Command executed successfully in {{input.container_name}}"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'container_name': {'type': 'string', 'description': 'Name of the running container'},
                            'command': {'type': 'string', 'description': 'Command to execute inside the container'},
                        },
                        'required': ['container_name', 'command'],
                    },
                },
                'params': {'app': ['webapp', 'api', 'postgres', 'redis', 'nginx', 'worker']},
                'prompts': [
                    'Execute a command inside the {app} Docker container',
                    'Create a DM action to run a command in the {app} container via docker exec',
                    'Write a shell action that exec into {app} container to run a command',
                ],
                'explanation': 'Executes a command inside the running {app} Docker container using docker exec.',
                'features': ['schema_variables'],
            },
            {
                'name': 'docker-cp',
                'template': {
                    'name': '{app}-docker-cp',
                    'action_type': 'SHELL',
                    'code': 'if ! docker inspect {{input.container_name}} > /dev/null 2>&1; then echo "FAILED: Container {{input.container_name}} not found" >&2; exit 1; fi && if [ "{{input.direction}}" = "to" ]; then docker cp "{{input.local_path}}" "{{input.container_name}}:{{input.container_path}}" 2>&1 && echo "Copied {{input.local_path}} -> {{input.container_name}}:{{input.container_path}}"; elif [ "{{input.direction}}" = "from" ]; then docker cp "{{input.container_name}}:{{input.container_path}}" "{{input.local_path}}" 2>&1 && echo "Copied {{input.container_name}}:{{input.container_path}} -> {{input.local_path}}"; else echo "FAILED: direction must be to or from" >&2; exit 1; fi',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'container_name': {'type': 'string', 'description': 'Container name'},
                            'local_path': {'type': 'string', 'description': 'Local file or directory path'},
                            'container_path': {'type': 'string', 'description': 'Path inside the container'},
                            'direction': {'type': 'string', 'description': 'Copy direction: "to" (local->container) or "from" (container->local)'},
                        },
                        'required': ['container_name', 'local_path', 'container_path', 'direction'],
                    },
                },
                'params': {'app': ['webapp', 'api', 'nginx', 'postgres', 'worker']},
                'prompts': [
                    'Copy a file to or from the {app} Docker container',
                    'Create a DM action to transfer files between host and {app} container',
                    'Write a shell action that uses docker cp with the {app} container',
                ],
                'explanation': 'Copies files between the host and the {app} Docker container in either direction using docker cp.',
                'features': ['schema_variables'],
            },
            {
                'name': 'docker-multi-stage-build',
                'template': {
                    'name': '{app}-multistage-build',
                    'action_type': 'SHELL',
                    'code': 'DOCKERFILE="{{input.build_dir}}/Dockerfile" && if [ ! -f "$DOCKERFILE" ]; then echo "FAILED: Dockerfile not found at $DOCKERFILE" >&2; exit 1; fi && echo "Building multi-stage image {{input.image_name}}:{{input.tag}}..." && docker build --target {{input.target_stage}} -t {{input.image_name}}:{{input.tag}} -f "$DOCKERFILE" {{input.build_dir}} 2>&1 && echo "=== Image details ===" && docker images {{input.image_name}}:{{input.tag}} --format "Size: {{.Size}}, Created: {{.CreatedAt}}" && echo "Multi-stage build complete: {{input.image_name}}:{{input.tag}} (stage: {{input.target_stage}})" || (echo "FAILED: Multi-stage build error" >&2; exit 1)',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'build_dir': {'type': 'string', 'description': 'Build context directory containing Dockerfile'},
                            'image_name': {'type': 'string', 'description': 'Name for the built image'},
                            'tag': {'type': 'string', 'description': 'Tag for the built image'},
                            'target_stage': {'type': 'string', 'description': 'Target build stage name (e.g. production, runtime)'},
                        },
                        'required': ['build_dir', 'image_name', 'tag', 'target_stage'],
                    },
                },
                'params': {'app': ['webapp', 'api', 'frontend', 'microservice', 'worker']},
                'prompts': [
                    'Build a multi-stage Docker image for {app}',
                    'Create a DM action to build {app} using a specific Dockerfile stage',
                    'Write a shell action for a multi-stage Docker build targeting a specific stage for {app}',
                ],
                'explanation': 'Builds a multi-stage Docker image for the {app} application targeting a specific build stage for optimized image size.',
                'features': ['schema_variables'],
                'difficulty': 'intermediate',
            },
            {
                'name': 'container-resource-limits',
                'template': {
                    'name': '{app}-resource-limits',
                    'action_type': 'SHELL',
                    'code': 'docker update --memory={{input.memory_limit}} --memory-swap={{input.memory_swap}} --cpus={{input.cpu_limit}} --restart={{input.restart_policy}} {{input.container_name}} 2>&1 && echo "=== Updated limits for {{input.container_name}} ===" && docker inspect --format="Memory: {{.HostConfig.Memory}}, CPUs: {{.HostConfig.NanoCpus}}, Restart: {{.HostConfig.RestartPolicy.Name}}" {{input.container_name}} 2>&1 && echo "Resource limits applied to {{input.container_name}}" || (echo "FAILED: Could not update container resource limits" >&2; exit 1)',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'container_name': {'type': 'string', 'description': 'Name of the running container to update'},
                            'memory_limit': {'type': 'string', 'description': 'Memory limit (e.g. 512m, 1g)'},
                            'memory_swap': {'type': 'string', 'description': 'Memory+swap limit (e.g. 1g, -1 for unlimited)'},
                            'cpu_limit': {'type': 'string', 'description': 'CPU limit (e.g. 0.5, 2.0)'},
                            'restart_policy': {'type': 'string', 'description': 'Restart policy (no, always, unless-stopped, on-failure)'},
                        },
                        'required': ['container_name', 'memory_limit', 'cpu_limit', 'restart_policy'],
                    },
                },
                'params': {'app': ['webapp', 'api', 'worker', 'postgres', 'redis', 'elasticsearch']},
                'prompts': [
                    'Set resource limits on the {app} Docker container',
                    'Create a DM action to cap memory and CPU for {app} container',
                    'Write a shell action that updates resource constraints for the running {app} container',
                ],
                'explanation': 'Updates memory, CPU, and restart policy limits on the running {app} Docker container.',
                'features': ['schema_variables'],
            },
            {
                'name': 'docker-swarm-init',
                'template': {
                    'name': '{target}-swarm-init',
                    'action_type': 'SHELL',
                    'code': 'if docker info --format "{{.Swarm.LocalNodeState}}" 2>/dev/null | grep -q "active"; then echo "Swarm already active on this node" && docker node ls 2>&1; else echo "Initializing Docker Swarm..." && docker swarm init --advertise-addr {{input.advertise_addr}} 2>&1 && echo "=== Swarm initialized ===" && docker node ls 2>&1 && echo "=== Worker join token ===" && docker swarm join-token worker -q 2>&1 && echo "=== Manager join token ===" && docker swarm join-token manager -q 2>&1; fi',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'advertise_addr': {'type': 'string', 'description': 'Advertise address for the swarm manager (IP or IP:port)'},
                        },
                        'required': ['advertise_addr'],
                    },
                },
                'params': {'target': ['production', 'staging', 'cluster', 'lab']},
                'prompts': [
                    'Initialize a Docker Swarm cluster on the {target} host',
                    'Create a DM action to set up Docker Swarm on {target}',
                    'Write a shell action that initializes Docker Swarm mode for {target}',
                ],
                'explanation': 'Initializes a Docker Swarm cluster on the {target} host and displays join tokens for workers and managers.',
                'features': ['schema_variables'],
                'difficulty': 'intermediate',
            },
            {
                'name': 'container-backup',
                'template': {
                    'name': '{app}-container-backup',
                    'action_type': 'SHELL',
                    'code': 'TIMESTAMP=$(date +%Y%m%d_%H%M%S) && BACKUP_FILE="{{input.backup_dir}}/{{input.container_name}}_${TIMESTAMP}.tar" && mkdir -p {{input.backup_dir}} && echo "Committing container state..." && docker commit {{input.container_name}} {{input.container_name}}-backup:${TIMESTAMP} 2>&1 && echo "Saving image to archive..." && docker save {{input.container_name}}-backup:${TIMESTAMP} -o "$BACKUP_FILE" 2>&1 && gzip "$BACKUP_FILE" && FILESIZE=$(du -sh "${BACKUP_FILE}.gz" | cut -f1) && echo "Container backup complete: ${BACKUP_FILE}.gz ($FILESIZE)" && docker rmi {{input.container_name}}-backup:${TIMESTAMP} 2>&1 > /dev/null || (echo "FAILED: Container backup error" >&2; exit 1)',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'container_name': {'type': 'string', 'description': 'Name of the container to backup'},
                            'backup_dir': {'type': 'string', 'description': 'Directory to store the backup archive'},
                        },
                        'required': ['container_name', 'backup_dir'],
                    },
                },
                'params': {'app': ['webapp', 'api', 'postgres', 'redis', 'worker', 'nginx']},
                'prompts': [
                    'Back up the {app} Docker container to a tar archive',
                    'Create a DM action to snapshot and export the {app} container',
                    'Write a shell action that commits and saves the {app} container as a backup',
                ],
                'explanation': 'Backs up the {app} Docker container by committing its state and saving the image as a compressed tar archive.',
                'features': ['schema_variables'],
            },
        ]


def get_generators():
    return [ContainersGenerator()]
