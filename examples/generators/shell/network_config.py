"""Shell action generators for network configuration."""

from examples.generators.base_generator import ShellActionGenerator


class NetworkConfigGenerator(ShellActionGenerator):
    category = "shell.network_config"
    subcategory = "network_config"

    def seeds(self):
        return [
            {
                'name': 'iptables-rule',
                'template': {
                    'name': 'iptables-{action}',
                    'action_type': 'SHELL',
                    'code': 'iptables -C {{input.chain}} -p {{input.protocol}} --dport {{input.port}} -j {{input.target}} 2>/dev/null && echo "Rule already exists" || (iptables -A {{input.chain}} -p {{input.protocol}} --dport {{input.port}} -j {{input.target}} && echo "Rule added: {{input.chain}} {{input.protocol}} port {{input.port}} -> {{input.target}}") && iptables-save > /etc/iptables/rules.v4 2>/dev/null || iptables-save > /etc/sysconfig/iptables 2>/dev/null && echo "Rules persisted"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'chain': {'type': 'string', 'description': 'iptables chain (INPUT, OUTPUT, FORWARD)'},
                            'protocol': {'type': 'string', 'description': 'Protocol (tcp, udp)'},
                            'port': {'type': 'integer', 'description': 'Port number'},
                            'target': {'type': 'string', 'description': 'Target action (ACCEPT, DROP, REJECT)'},
                        },
                        'required': ['chain', 'protocol', 'port', 'target'],
                    },
                },
                'params': {'action': ['allow', 'deny', 'add', 'block']},
                'prompts': [
                    '{action} traffic with an iptables rule',
                    'Create a DM action to {action} a port using iptables',
                    'Write a shell action to {action} network traffic via iptables',
                ],
                'explanation': 'Adds an iptables rule to {action} traffic and persists the configuration.',
                'features': ['schema_variables'],
                'difficulty': 'intermediate',
            },
            {
                'name': 'firewalld-zone',
                'template': {
                    'name': 'firewalld-{action}',
                    'action_type': 'SHELL',
                    'code': 'firewall-cmd --zone={{input.zone}} --add-service={{input.service_name}} --permanent && firewall-cmd --reload && echo "Service {{input.service_name}} added to zone {{input.zone}}" && firewall-cmd --zone={{input.zone}} --list-services',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'zone': {'type': 'string', 'description': 'Firewalld zone (public, internal, trusted)'},
                            'service_name': {'type': 'string', 'description': 'Service name to allow (http, https, ssh)'},
                        },
                        'required': ['zone', 'service_name'],
                    },
                },
                'params': {'action': ['allow-svc', 'add-svc', 'open-svc']},
                'prompts': [
                    '{action} in a firewalld zone',
                    'Create a DM action to {action} using firewalld',
                    'Write a shell action to {action} in firewalld',
                ],
                'explanation': 'Adds a service to a firewalld zone to {action} the firewall and reloads the configuration.',
                'features': ['schema_variables'],
            },
            {
                'name': 'ufw-rule',
                'template': {
                    'name': 'ufw-{action}',
                    'action_type': 'SHELL',
                    'code': 'ufw {{input.action}} {{input.direction}} {{input.port}}/{{input.protocol}} comment "{{input.comment}}" && ufw status verbose | grep {{input.port}} && echo "UFW rule applied: {{input.action}} {{input.port}}/{{input.protocol}}"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'action': {'type': 'string', 'description': 'UFW action (allow, deny, reject)'},
                            'direction': {'type': 'string', 'description': 'Direction (in, out, empty for both)'},
                            'port': {'type': 'integer', 'description': 'Port number'},
                            'protocol': {'type': 'string', 'description': 'Protocol (tcp, udp)'},
                            'comment': {'type': 'string', 'description': 'Rule comment/description'},
                        },
                        'required': ['action', 'port', 'protocol', 'comment'],
                    },
                },
                'params': {'action': ['allow', 'deny']},
                'prompts': [
                    '{action} a port with UFW firewall',
                    'Create a DM action to {action} traffic using UFW',
                    'Write a shell action to {action} a port in UFW',
                ],
                'explanation': 'Configures a UFW firewall rule to {action} traffic on a specific port.',
                'features': ['schema_variables'],
            },
            {
                'name': 'ip-route-add',
                'template': {
                    'name': 'route-{action}',
                    'action_type': 'SHELL',
                    'code': 'ip route add {{input.network}} via {{input.gateway}} dev {{input.interface}} 2>/dev/null && echo "Route added: {{input.network}} via {{input.gateway}} dev {{input.interface}}" || echo "Route may already exist" && echo "{{input.network}} via {{input.gateway}} dev {{input.interface}}" >> /etc/sysconfig/network-scripts/route-{{input.interface}} 2>/dev/null || echo "{{input.network}} via {{input.gateway}}" >> /etc/network/routes 2>/dev/null && ip route show | grep "{{input.network}}"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'network': {'type': 'string', 'description': 'Destination network (e.g. 10.0.0.0/24)'},
                            'gateway': {'type': 'string', 'description': 'Gateway IP address'},
                            'interface': {'type': 'string', 'description': 'Network interface (e.g. eth0, ens33)'},
                        },
                        'required': ['network', 'gateway', 'interface'],
                    },
                },
                'params': {'action': ['add', 'configure', 'setup']},
                'prompts': [
                    '{action} a static IP route',
                    'Create a DM action to {action} a network route',
                    'Write a shell action to {action} a static routing entry',
                ],
                'explanation': 'Adds a static IP route to {action} traffic routing through a specified gateway.',
                'features': ['schema_variables'],
                'difficulty': 'intermediate',
            },
            {
                'name': 'dns-resolver',
                'template': {
                    'name': 'dns-config-{action}',
                    'action_type': 'SHELL',
                    'code': 'cp /etc/resolv.conf /etc/resolv.conf.bak.$(date +%%Y%%m%%d%%H%%M%%S) && cat > /etc/resolv.conf <<DNS\nsearch {{input.search_domain}}\nnameserver {{input.dns_primary}}\nnameserver {{input.dns_secondary}}\noptions timeout:2 attempts:3\nDNS\necho "DNS resolvers configured" && cat /etc/resolv.conf && echo "Testing resolution..." && nslookup {{input.test_domain}} {{input.dns_primary}} 2>&1 | head -5',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'dns_primary': {'type': 'string', 'description': 'Primary DNS server IP'},
                            'dns_secondary': {'type': 'string', 'description': 'Secondary DNS server IP'},
                            'search_domain': {'type': 'string', 'description': 'DNS search domain'},
                            'test_domain': {'type': 'string', 'description': 'Domain to test resolution against'},
                        },
                        'required': ['dns_primary', 'dns_secondary', 'search_domain', 'test_domain'],
                    },
                },
                'params': {'action': ['configure', 'update', 'set']},
                'prompts': [
                    '{action} DNS resolver settings',
                    'Create a DM action to {action} resolv.conf',
                    'Write a shell action to {action} DNS nameservers',
                ],
                'explanation': 'Configures DNS resolver settings to {action} nameserver entries in /etc/resolv.conf.',
                'features': ['schema_variables'],
                'difficulty': 'intermediate',
            },
            {
                'name': 'ntp-sync',
                'template': {
                    'name': 'ntp-{action}',
                    'action_type': 'SHELL',
                    'code': 'if command -v timedatectl &>/dev/null; then timedatectl set-ntp true && timedatectl set-timezone "{{input.timezone}}" && echo "NTP enabled, timezone set to {{input.timezone}}" && timedatectl status; elif command -v ntpdate &>/dev/null; then ntpdate {{input.ntp_server}} && echo "Time synchronized with {{input.ntp_server}}"; else chronyc makestep 2>/dev/null && echo "Time stepped with chrony"; fi',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'timezone': {'type': 'string', 'description': 'Timezone (e.g. UTC, America/New_York)'},
                            'ntp_server': {'type': 'string', 'description': 'NTP server hostname'},
                        },
                        'required': ['timezone', 'ntp_server'],
                    },
                },
                'params': {'action': ['sync', 'configure', 'enable']},
                'prompts': [
                    '{action} NTP time synchronization',
                    'Create a DM action to {action} NTP and set timezone',
                    'Write a shell action to {action} NTP time sync',
                ],
                'explanation': 'Enables NTP time synchronization and sets the system timezone ({action} operation).',
                'features': ['schema_variables'],
            },
            {
                'name': 'hostname-set',
                'template': {
                    'name': 'hostname-{action}',
                    'action_type': 'SHELL',
                    'code': 'OLD_HOSTNAME=$(hostname) && hostnamectl set-hostname "{{input.new_hostname}}" && echo "Hostname changed: $OLD_HOSTNAME -> {{input.new_hostname}}" && sed -i "s/$OLD_HOSTNAME/{{input.new_hostname}}/g" /etc/hosts 2>/dev/null && echo "Updated /etc/hosts" && hostname',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'new_hostname': {'type': 'string', 'description': 'New hostname to set'},
                        },
                        'required': ['new_hostname'],
                    },
                },
                'params': {'action': ['set', 'change', 'update']},
                'prompts': [
                    '{action} the system hostname',
                    'Create a DM action to {action} the server hostname',
                    'Write a shell action to {action} hostname persistently',
                ],
                'explanation': 'Changes the system hostname to {action} it and updates /etc/hosts accordingly.',
                'features': ['schema_variables'],
            },
            {
                'name': 'hosts-entry',
                'template': {
                    'name': 'hosts-{action}',
                    'action_type': 'SHELL',
                    'code': 'if grep -q "{{input.hostname}}" /etc/hosts; then sed -i "/{{input.hostname}}/d" /etc/hosts; echo "Removed old entry for {{input.hostname}}"; fi && echo "{{input.ip_address}}    {{input.hostname}} {{input.aliases}}" >> /etc/hosts && echo "Added: {{input.ip_address}} -> {{input.hostname}}" && grep "{{input.hostname}}" /etc/hosts',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'ip_address': {'type': 'string', 'description': 'IP address to map'},
                            'hostname': {'type': 'string', 'description': 'Hostname to map the IP to'},
                            'aliases': {'type': 'string', 'description': 'Optional hostname aliases'},
                        },
                        'required': ['ip_address', 'hostname'],
                    },
                },
                'params': {'action': ['add', 'update', 'set']},
                'prompts': [
                    '{action} an entry in /etc/hosts',
                    'Create a DM action to {action} a hosts file mapping',
                    'Write a shell action to {action} a hostname in /etc/hosts',
                ],
                'explanation': 'Manages /etc/hosts entries to {action} hostname-to-IP mappings.',
                'features': ['schema_variables'],
            },
            {
                'name': 'port-check',
                'template': {
                    'name': 'port-check-{tool}',
                    'action_type': 'SHELL',
                    'code': 'echo "=== Listening ports ===" && (ss -tlnp 2>/dev/null || netstat -tlnp 2>/dev/null) | grep ":{{input.port}}" && if ss -tlnp 2>/dev/null | grep -q ":{{input.port}}"; then echo "Port {{input.port}} is LISTENING"; PID=$(ss -tlnp | grep ":{{input.port}}" | grep -oP "pid=\\K[0-9]+"); echo "Process: $(ps -p $PID -o comm= 2>/dev/null)"; exit 0; else echo "Port {{input.port}} is NOT listening" >&2; exit 1; fi',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'port': {'type': 'integer', 'description': 'Port number to check'},
                        },
                        'required': ['port'],
                    },
                },
                'params': {'tool': ['ss', 'netstat']},
                'prompts': [
                    'Check if a port is listening using {tool}',
                    'Create a DM action to verify port status with {tool}',
                    'Write a shell action to check port availability via {tool}',
                ],
                'explanation': 'Checks whether a specified port is listening and identifies the owning process using {tool}.',
                'features': ['schema_variables'],
            },
            {
                'name': 'bandwidth-limit',
                'template': {
                    'name': 'tc-bw-limit-{action}',
                    'action_type': 'SHELL',
                    'code': 'tc qdisc del dev {{input.interface}} root 2>/dev/null; tc qdisc add dev {{input.interface}} root tbf rate {{input.rate}} burst {{input.burst}} latency {{input.latency}} && echo "Bandwidth limited on {{input.interface}}: rate={{input.rate}}, burst={{input.burst}}" && tc qdisc show dev {{input.interface}}',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'interface': {'type': 'string', 'description': 'Network interface (e.g. eth0)'},
                            'rate': {'type': 'string', 'description': 'Rate limit (e.g. 100mbit, 1gbit)'},
                            'burst': {'type': 'string', 'description': 'Burst size (e.g. 32kbit)'},
                            'latency': {'type': 'string', 'description': 'Maximum latency (e.g. 400ms)'},
                        },
                        'required': ['interface', 'rate', 'burst', 'latency'],
                    },
                },
                'params': {'action': ['limit', 'throttle', 'shape']},
                'prompts': [
                    '{action} bandwidth on a network interface with tc',
                    'Create a DM action to {action} network bandwidth',
                    'Write a shell action to {action} interface throughput with tc',
                ],
                'explanation': 'Configures traffic control to {action} bandwidth on a network interface using tc.',
                'features': ['schema_variables'],
                'difficulty': 'advanced',
            },
            {
                'name': 'vlan-config',
                'template': {
                    'name': 'vlan-{action}',
                    'action_type': 'SHELL',
                    'code': 'modprobe 8021q 2>/dev/null && ip link add link {{input.parent_iface}} name {{input.parent_iface}}.{{input.vlan_id}} type vlan id {{input.vlan_id}} && ip addr add {{input.ip_address}}/{{input.netmask}} dev {{input.parent_iface}}.{{input.vlan_id}} && ip link set up dev {{input.parent_iface}}.{{input.vlan_id}} && echo "VLAN {{input.vlan_id}} configured on {{input.parent_iface}}" && ip -d link show {{input.parent_iface}}.{{input.vlan_id}}',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'parent_iface': {'type': 'string', 'description': 'Parent network interface (e.g. eth0)'},
                            'vlan_id': {'type': 'integer', 'description': 'VLAN ID (1-4094)'},
                            'ip_address': {'type': 'string', 'description': 'IP address for the VLAN interface'},
                            'netmask': {'type': 'integer', 'description': 'Netmask in CIDR notation (e.g. 24)'},
                        },
                        'required': ['parent_iface', 'vlan_id', 'ip_address', 'netmask'],
                    },
                },
                'params': {'action': ['create', 'configure', 'setup']},
                'prompts': [
                    '{action} a VLAN interface',
                    'Create a DM action to {action} VLAN tagging',
                    'Write a shell action to {action} a VLAN on a network interface',
                ],
                'explanation': 'Creates and configures a VLAN interface to {action} VLAN tagging on a parent interface.',
                'features': ['schema_variables'],
                'difficulty': 'advanced',
            },
            {
                'name': 'bridge-setup',
                'template': {
                    'name': 'bridge-{action}',
                    'action_type': 'SHELL',
                    'code': 'ip link add name {{input.bridge_name}} type bridge && ip link set {{input.slave_iface}} master {{input.bridge_name}} && ip addr add {{input.ip_address}}/{{input.netmask}} dev {{input.bridge_name}} && ip link set up dev {{input.bridge_name}} && echo "Bridge {{input.bridge_name}} created with slave {{input.slave_iface}}" && bridge link show',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'bridge_name': {'type': 'string', 'description': 'Bridge interface name (e.g. br0)'},
                            'slave_iface': {'type': 'string', 'description': 'Slave interface to add to bridge'},
                            'ip_address': {'type': 'string', 'description': 'IP address for the bridge'},
                            'netmask': {'type': 'integer', 'description': 'Netmask in CIDR notation'},
                        },
                        'required': ['bridge_name', 'slave_iface', 'ip_address', 'netmask'],
                    },
                },
                'params': {'action': ['create', 'setup', 'configure']},
                'prompts': [
                    '{action} a network bridge',
                    'Create a DM action to {action} a bridge interface',
                    'Write a shell action to {action} a Linux network bridge',
                ],
                'explanation': 'Creates a Linux network bridge to {action} bridged networking with a slave interface.',
                'features': ['schema_variables'],
                'difficulty': 'advanced',
            },
        ]


def get_generators():
    return [NetworkConfigGenerator()]
