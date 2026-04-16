"""Cloud infrastructure Ansible action generators - 6 seeds for AWS, GCP, Azure."""

from examples.generators.base_generator import AnsibleActionGenerator


class CloudGenerator(AnsibleActionGenerator):
    category = "ansible.cloud"
    subcategory = "cloud"

    def seeds(self):
        return [
            {
                'name': 'ec2-instance',
                'template': {
                    'name': 'Launch EC2 instance',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Launch EC2 instance\n'
                        '  amazon.aws.ec2_instance:\n'
                        '    name: "{{input.instance_name}}"\n'
                        '    instance_type: "{{input.instance_type}}"\n'
                        '    image_id: "{{input.ami_id}}"\n'
                        '    key_name: "{{input.key_name}}"\n'
                        '    security_groups:\n'
                        '      - "{{input.security_group}}"\n'
                        '    region: "{{input.region}}"\n'
                        '    state: running\n'
                        '    wait: yes\n'
                        '    tags:\n'
                        '      Environment: "{{input.environment}}"\n'
                        '  register: ec2_result\n'
                    ),
                    'schema': {
                        'input': {
                            'instance_name': {'type': 'string', 'description': 'EC2 instance name tag'},
                            'instance_type': {'type': 'string', 'description': 'Instance type (e.g. t3.micro)'},
                            'ami_id': {'type': 'string', 'description': 'AMI image ID'},
                            'key_name': {'type': 'string', 'description': 'SSH key pair name'},
                            'security_group': {'type': 'string', 'description': 'Security group name'},
                            'region': {'type': 'string', 'description': 'AWS region'},
                            'environment': {'type': 'string', 'description': 'Environment tag value'},
                        },
                        'required': ['instance_name', 'instance_type', 'ami_id', 'region'],
                    },
                },
                'params': {'instance_type': ['t3.micro', 't3.small', 't3.medium', 'm5.large', 'c5.xlarge']},
                'prompts': [
                    'Create an Ansible action to launch a {instance_type} EC2 instance',
                    'Ansible playbook that provisions an AWS EC2 {instance_type} instance',
                ],
                'explanation': 'Ansible action that launches an AWS EC2 {instance_type} instance with security group, key pair, and environment tags.',
            },
            {
                'name': 's3-bucket',
                'template': {
                    'name': 'Create S3 bucket',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Create S3 bucket {{input.bucket_name}}\n'
                        '  amazon.aws.s3_bucket:\n'
                        '    name: "{{input.bucket_name}}"\n'
                        '    region: "{{input.region}}"\n'
                        '    versioning: "{{input.versioning}}"\n'
                        '    encryption: AES256\n'
                        '    public_access:\n'
                        '      block_public_acls: true\n'
                        '      block_public_policy: true\n'
                        '      ignore_public_acls: true\n'
                        '      restrict_public_buckets: true\n'
                        '    tags:\n'
                        '      Environment: "{{input.environment}}"\n'
                        '    state: present\n'
                    ),
                    'schema': {
                        'input': {
                            'bucket_name': {'type': 'string', 'description': 'S3 bucket name'},
                            'region': {'type': 'string', 'description': 'AWS region'},
                            'versioning': {'type': 'string', 'description': 'Enable versioning: yes/no'},
                            'environment': {'type': 'string', 'description': 'Environment tag'},
                        },
                        'required': ['bucket_name', 'region'],
                    },
                },
                'params': {'purpose': ['backups', 'artifacts', 'logs', 'static-assets', 'data-lake']},
                'prompts': [
                    'Create an Ansible action to provision an S3 bucket for {purpose}',
                    'Ansible playbook that creates a secure S3 bucket for {purpose} storage',
                ],
                'explanation': 'Ansible action that creates an S3 bucket for {purpose} with encryption, versioning, and public access blocking.',
            },
            {
                'name': 'route53-record',
                'template': {
                    'name': 'Create Route53 DNS record',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Create Route53 {{input.record_type}} record\n'
                        '  amazon.aws.route53:\n'
                        '    zone: "{{input.zone_name}}"\n'
                        '    record: "{{input.record_name}}"\n'
                        '    type: "{{input.record_type}}"\n'
                        '    value: "{{input.record_value}}"\n'
                        '    ttl: "{{input.ttl}}"\n'
                        '    state: present\n'
                        '    overwrite: yes\n'
                    ),
                    'schema': {
                        'input': {
                            'zone_name': {'type': 'string', 'description': 'Route53 hosted zone name'},
                            'record_name': {'type': 'string', 'description': 'DNS record name'},
                            'record_type': {'type': 'string', 'description': 'Record type: A, AAAA, CNAME, TXT'},
                            'record_value': {'type': 'string', 'description': 'Record value'},
                            'ttl': {'type': 'string', 'description': 'TTL in seconds (default 300)'},
                        },
                        'required': ['zone_name', 'record_name', 'record_type', 'record_value'],
                    },
                },
                'params': {'record_type': ['A', 'AAAA', 'CNAME', 'TXT', 'MX']},
                'prompts': [
                    'Create an Ansible action to manage a Route53 {record_type} record',
                    'Ansible playbook that creates or updates a {record_type} DNS record in Route53',
                ],
                'explanation': 'Ansible action that creates or updates a {record_type} DNS record in AWS Route53 with overwrite support.',
            },
            {
                'name': 'security-group',
                'template': {
                    'name': 'Configure security group',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Create security group {{input.group_name}}\n'
                        '  amazon.aws.ec2_security_group:\n'
                        '    name: "{{input.group_name}}"\n'
                        '    description: "{{input.description}}"\n'
                        '    vpc_id: "{{input.vpc_id}}"\n'
                        '    region: "{{input.region}}"\n'
                        '    rules:\n'
                        '      - proto: tcp\n'
                        '        from_port: "{{input.port}}"\n'
                        '        to_port: "{{input.port}}"\n'
                        '        cidr_ip: "{{input.cidr}}"\n'
                        '        rule_desc: "{{input.rule_description}}"\n'
                        '    state: present\n'
                        '  register: sg_result\n'
                    ),
                    'schema': {
                        'input': {
                            'group_name': {'type': 'string', 'description': 'Security group name'},
                            'description': {'type': 'string', 'description': 'Security group description'},
                            'vpc_id': {'type': 'string', 'description': 'VPC ID'},
                            'region': {'type': 'string', 'description': 'AWS region'},
                            'port': {'type': 'string', 'description': 'Port to allow'},
                            'cidr': {'type': 'string', 'description': 'Source CIDR for rule'},
                            'rule_description': {'type': 'string', 'description': 'Rule description'},
                        },
                        'required': ['group_name', 'description', 'vpc_id', 'region'],
                    },
                },
                'params': {'service_type': ['web', 'database', 'cache', 'application', 'management']},
                'prompts': [
                    'Create an Ansible action to configure a {service_type} security group',
                    'Ansible playbook that creates an AWS security group for {service_type} access',
                ],
                'explanation': 'Ansible action that creates an AWS security group for {service_type} with inbound TCP rules.',
            },
            {
                'name': 'gcp-compute-instance',
                'template': {
                    'name': 'Create GCP compute instance',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Create GCP instance {{input.instance_name}}\n'
                        '  google.cloud.gcp_compute_instance:\n'
                        '    name: "{{input.instance_name}}"\n'
                        '    machine_type: "{{input.machine_type}}"\n'
                        '    zone: "{{input.zone}}"\n'
                        '    project: "{{input.project_id}}"\n'
                        '    disks:\n'
                        '      - auto_delete: true\n'
                        '        boot: true\n'
                        '        initialize_params:\n'
                        '          source_image: "{{input.source_image}}"\n'
                        '          disk_size_gb: "{{input.disk_size_gb}}"\n'
                        '    network_interfaces:\n'
                        '      - network:\n'
                        '          selfLink: "global/networks/default"\n'
                        '        access_configs:\n'
                        '          - name: External NAT\n'
                        '            type: ONE_TO_ONE_NAT\n'
                        '    state: present\n'
                    ),
                    'schema': {
                        'input': {
                            'instance_name': {'type': 'string', 'description': 'Instance name'},
                            'machine_type': {'type': 'string', 'description': 'Machine type (e.g. e2-medium)'},
                            'zone': {'type': 'string', 'description': 'GCP zone'},
                            'project_id': {'type': 'string', 'description': 'GCP project ID'},
                            'source_image': {'type': 'string', 'description': 'Source image for boot disk'},
                            'disk_size_gb': {'type': 'string', 'description': 'Boot disk size in GB'},
                        },
                        'required': ['instance_name', 'machine_type', 'zone', 'project_id'],
                    },
                },
                'params': {'machine_type': ['e2-micro', 'e2-small', 'e2-medium', 'n2-standard-2', 'n2-standard-4']},
                'prompts': [
                    'Create an Ansible action to launch a GCP {machine_type} instance',
                    'Ansible playbook that provisions a {machine_type} compute instance on GCP',
                ],
                'explanation': 'Ansible action that creates a GCP {machine_type} compute instance with boot disk and external networking.',
            },
            {
                'name': 'azure-vm',
                'template': {
                    'name': 'Create Azure VM',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Create Azure VM {{input.vm_name}}\n'
                        '  azure.azcollection.azure_rm_virtualmachine:\n'
                        '    resource_group: "{{input.resource_group}}"\n'
                        '    name: "{{input.vm_name}}"\n'
                        '    vm_size: "{{input.vm_size}}"\n'
                        '    admin_username: "{{input.admin_username}}"\n'
                        '    ssh_password_enabled: false\n'
                        '    ssh_public_keys:\n'
                        '      - path: "/home/{{input.admin_username}}/.ssh/authorized_keys"\n'
                        '        key_data: "{{input.ssh_key}}"\n'
                        '    image:\n'
                        '      offer: "{{input.image_offer}}"\n'
                        '      publisher: "{{input.image_publisher}}"\n'
                        '      sku: "{{input.image_sku}}"\n'
                        '      version: latest\n'
                        '    state: present\n'
                    ),
                    'schema': {
                        'input': {
                            'resource_group': {'type': 'string', 'description': 'Azure resource group'},
                            'vm_name': {'type': 'string', 'description': 'Virtual machine name'},
                            'vm_size': {'type': 'string', 'description': 'VM size (e.g. Standard_B2s)'},
                            'admin_username': {'type': 'string', 'description': 'Admin username'},
                            'ssh_key': {'type': 'string', 'description': 'SSH public key data'},
                            'image_offer': {'type': 'string', 'description': 'Image offer (e.g. UbuntuServer)'},
                            'image_publisher': {'type': 'string', 'description': 'Image publisher (e.g. Canonical)'},
                            'image_sku': {'type': 'string', 'description': 'Image SKU (e.g. 22_04-lts)'},
                        },
                        'required': ['resource_group', 'vm_name', 'vm_size', 'admin_username'],
                    },
                },
                'params': {'vm_size': ['Standard_B1s', 'Standard_B2s', 'Standard_D2s_v3', 'Standard_D4s_v3']},
                'prompts': [
                    'Create an Ansible action to provision an Azure {vm_size} VM',
                    'Ansible playbook that creates a {vm_size} virtual machine on Azure',
                ],
                'explanation': 'Ansible action that provisions an Azure {vm_size} virtual machine with SSH key authentication and marketplace image.',
            },
        ]


def get_generators():
    return [CloudGenerator()]
