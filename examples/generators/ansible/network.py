"""Network configuration Ansible action generators - 6 seeds for firewall, DNS, sysctl."""

from examples.generators.base_generator import AnsibleActionGenerator


class NetworkGenerator(AnsibleActionGenerator):
    category = "ansible.network"
    subcategory = "network"

    def seeds(self):
        return [
            {
                'name': 'firewalld-rule',
                'template': {
                    'name': 'Add firewalld {protocol} rule',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Ensure firewalld is running\n'
                        '  systemd:\n'
                        '    name: firewalld\n'
                        '    state: started\n'
                        '    enabled: yes\n'
                        '\n'
                        '- name: Allow port {{input.port}}/{{input.protocol}} in firewalld\n'
                        '  firewalld:\n'
                        '    port: "{{input.port}}/{{input.protocol}}"\n'
                        '    zone: "{{input.zone}}"\n'
                        '    permanent: yes\n'
                        '    immediate: yes\n'
                        '    state: enabled\n'
                    ),
                    'schema': {
                        'input': {
                            'port': {'type': 'string', 'description': 'Port number to allow'},
                            'protocol': {'type': 'string', 'description': 'Protocol: tcp or udp'},
                            'zone': {'type': 'string', 'description': 'Firewalld zone (default public)'},
                        },
                        'required': ['port', 'protocol'],
                    },
                },
                'params': {'protocol': ['tcp', 'udp']},
                'prompts': [
                    'Create an Ansible action to add a firewalld {protocol} port rule',
                    'Ansible playbook that opens a {protocol} port in firewalld permanently',
                ],
                'explanation': 'Ansible action that opens a {protocol} port in firewalld with both immediate and permanent effect.',
            },
            {
                'name': 'iptables-rule',
                'template': {
                    'name': 'Add iptables {action} rule',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Add iptables rule for port {{input.port}}\n'
                        '  iptables:\n'
                        '    chain: INPUT\n'
                        '    protocol: "{{input.protocol}}"\n'
                        '    destination_port: "{{input.port}}"\n'
                        '    source: "{{input.source}}"\n'
                        '    jump: "{{input.jump}}"\n'
                        '    comment: "{{input.comment}}"\n'
                        '\n'
                        '- name: Save iptables rules\n'
                        '  command: iptables-save > /etc/iptables/rules.v4\n'
                        '  changed_when: true\n'
                    ),
                    'schema': {
                        'input': {
                            'port': {'type': 'string', 'description': 'Destination port'},
                            'protocol': {'type': 'string', 'description': 'Protocol: tcp or udp'},
                            'source': {'type': 'string', 'description': 'Source IP/CIDR (default 0.0.0.0/0)'},
                            'jump': {'type': 'string', 'description': 'Target action: ACCEPT, DROP, REJECT'},
                            'comment': {'type': 'string', 'description': 'Rule comment'},
                        },
                        'required': ['port', 'protocol', 'jump'],
                    },
                },
                'params': {'action': ['ACCEPT', 'DROP', 'REJECT']},
                'prompts': [
                    'Create an Ansible action to add an iptables {action} rule',
                    'Ansible playbook that configures an iptables {action} rule and persists it',
                ],
                'explanation': 'Ansible action that adds an iptables {action} rule for a specific port and persists the rules to disk.',
            },
            {
                'name': 'nmcli-connection',
                'template': {
                    'name': 'Configure network connection',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Configure {{input.conn_name}} connection\n'
                        '  community.general.nmcli:\n'
                        '    conn_name: "{{input.conn_name}}"\n'
                        '    ifname: "{{input.interface}}"\n'
                        '    type: ethernet\n'
                        '    ip4: "{{input.ip_address}}"\n'
                        '    gw4: "{{input.gateway}}"\n'
                        '    dns4:\n'
                        '      - "{{input.dns_server}}"\n'
                        '    state: present\n'
                        '    autoconnect: yes\n'
                        '\n'
                        '- name: Bring up connection\n'
                        '  command: "nmcli connection up {{input.conn_name}}"\n'
                        '  changed_when: true\n'
                    ),
                    'schema': {
                        'input': {
                            'conn_name': {'type': 'string', 'description': 'Connection profile name'},
                            'interface': {'type': 'string', 'description': 'Network interface name'},
                            'ip_address': {'type': 'string', 'description': 'IP address with prefix (e.g. 192.168.1.10/24)'},
                            'gateway': {'type': 'string', 'description': 'Default gateway'},
                            'dns_server': {'type': 'string', 'description': 'DNS server IP'},
                        },
                        'required': ['conn_name', 'interface', 'ip_address'],
                    },
                },
                'params': {'interface': ['eth0', 'eth1', 'ens192', 'ens33', 'bond0']},
                'prompts': [
                    'Create an Ansible action to configure network on {interface}',
                    'Ansible playbook that sets up a static IP on {interface} via NetworkManager',
                ],
                'explanation': 'Ansible action that configures a static IP network connection on {interface} using NetworkManager nmcli.',
            },
            {
                'name': 'sysctl-setting',
                'template': {
                    'name': 'Set sysctl parameter',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Set sysctl {{input.sysctl_key}}\n'
                        '  sysctl:\n'
                        '    name: "{{input.sysctl_key}}"\n'
                        '    value: "{{input.sysctl_value}}"\n'
                        '    sysctl_set: yes\n'
                        '    state: present\n'
                        '    reload: yes\n'
                        '    sysctl_file: /etc/sysctl.d/99-custom.conf\n'
                    ),
                    'schema': {
                        'input': {
                            'sysctl_key': {'type': 'string', 'description': 'Sysctl parameter name'},
                            'sysctl_value': {'type': 'string', 'description': 'Sysctl parameter value'},
                        },
                        'required': ['sysctl_key', 'sysctl_value'],
                    },
                },
                'params': {'tuning': ['network', 'memory', 'security', 'performance']},
                'prompts': [
                    'Create an Ansible action to set a {tuning} sysctl parameter',
                    'Ansible playbook that configures a {tuning}-related kernel parameter via sysctl',
                ],
                'explanation': 'Ansible action that sets a {tuning} kernel parameter via sysctl with persistence and immediate reload.',
            },
            {
                'name': 'hosts-file',
                'template': {
                    'name': 'Manage /etc/hosts entry',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Add hosts entry for {{input.hostname}}\n'
                        '  lineinfile:\n'
                        '    path: /etc/hosts\n'
                        '    regexp: ".*{{input.hostname}}$"\n'
                        '    line: "{{input.ip_address}}    {{input.hostname}} {{input.alias}}"\n'
                        '    state: present\n'
                        '    backup: yes\n'
                        '\n'
                        '- name: Verify DNS resolution\n'
                        '  command: "getent hosts {{input.hostname}}"\n'
                        '  register: dns_check\n'
                        '  changed_when: false\n'
                    ),
                    'schema': {
                        'input': {
                            'hostname': {'type': 'string', 'description': 'Hostname to add'},
                            'ip_address': {'type': 'string', 'description': 'IP address for the hostname'},
                            'alias': {'type': 'string', 'description': 'Short alias (optional)'},
                        },
                        'required': ['hostname', 'ip_address'],
                    },
                },
                'params': {'entry_type': ['service', 'database', 'cache', 'api', 'internal']},
                'prompts': [
                    'Create an Ansible action to add a {entry_type} host entry to /etc/hosts',
                    'Ansible playbook that manages a {entry_type} /etc/hosts entry with verification',
                ],
                'explanation': 'Ansible action that adds a {entry_type} hostname entry to /etc/hosts with backup and DNS resolution verification.',
            },
            {
                'name': 'dns-resolver',
                'template': {
                    'name': 'Configure DNS resolver',
                    'action_type': 'ANSIBLE',
                    'code': (
                        '- name: Configure /etc/resolv.conf\n'
                        '  copy:\n'
                        '    dest: /etc/resolv.conf\n'
                        '    content: |\n'
                        '      # Managed by Ansible\n'
                        '      search {{input.search_domain}}\n'
                        '      nameserver {{input.primary_dns}}\n'
                        '      nameserver {{input.secondary_dns}}\n'
                        '      options timeout:2 attempts:3\n'
                        '    owner: root\n'
                        '    group: root\n'
                        '    mode: "0644"\n'
                        '    backup: yes\n'
                        '\n'
                        '- name: Test DNS resolution\n'
                        '  command: "nslookup {{input.test_domain}} {{input.primary_dns}}"\n'
                        '  register: dns_test\n'
                        '  changed_when: false\n'
                        '  failed_when: dns_test.rc != 0\n'
                    ),
                    'schema': {
                        'input': {
                            'search_domain': {'type': 'string', 'description': 'DNS search domain'},
                            'primary_dns': {'type': 'string', 'description': 'Primary DNS server IP'},
                            'secondary_dns': {'type': 'string', 'description': 'Secondary DNS server IP'},
                            'test_domain': {'type': 'string', 'description': 'Domain to test resolution against'},
                        },
                        'required': ['primary_dns', 'secondary_dns'],
                    },
                },
                'params': {'dns_provider': ['internal', 'cloudflare', 'google', 'quad9', 'opendns']},
                'prompts': [
                    'Create an Ansible action to configure {dns_provider} DNS resolver',
                    'Ansible playbook that sets up {dns_provider} DNS resolution with testing',
                ],
                'explanation': 'Ansible action that configures {dns_provider} DNS resolver in /etc/resolv.conf with resolution testing.',
            },
        ]


def get_generators():
    return [NetworkGenerator()]
