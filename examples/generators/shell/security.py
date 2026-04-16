"""Shell action generators for security hardening operations."""

from examples.generators.base_generator import ShellActionGenerator


class SecurityGenerator(ShellActionGenerator):
    category = "shell.security"
    subcategory = "security"

    def seeds(self):
        return [
            {
                'name': 'ssh-disable-root-login',
                'template': {
                    'name': '{target}-ssh-no-root',
                    'action_type': 'SHELL',
                    'code': 'SSHD_CONFIG="{{input.sshd_config}}" && cp "$SSHD_CONFIG" "${SSHD_CONFIG}.bak.$(date +%s)" && if grep -q "^PermitRootLogin" "$SSHD_CONFIG"; then sed -i "s/^PermitRootLogin.*/PermitRootLogin no/" "$SSHD_CONFIG"; else echo "PermitRootLogin no" >> "$SSHD_CONFIG"; fi && sshd -t -f "$SSHD_CONFIG" 2>&1 && systemctl reload sshd && echo "PermitRootLogin disabled in $SSHD_CONFIG" || (echo "FAILED: sshd config test failed, restoring backup" >&2; cp "${SSHD_CONFIG}.bak."* "$SSHD_CONFIG" 2>/dev/null; exit 1)',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'sshd_config': {'type': 'string', 'description': 'Path to sshd_config file (default: /etc/ssh/sshd_config)'},
                        },
                        'required': ['sshd_config'],
                    },
                },
                'params': {'target': ['server', 'host', 'node', 'bastion']},
                'prompts': [
                    'Disable SSH root login on the {target}',
                    'Create a DM action to set PermitRootLogin no on {target}',
                    'Write a shell action that hardens SSH by disabling root login on {target}',
                ],
                'explanation': 'Disables SSH root login on the {target} by setting PermitRootLogin no, with config validation and backup.',
                'features': ['schema_variables'],
            },
            {
                'name': 'ssh-disable-password-auth',
                'template': {
                    'name': '{target}-ssh-no-password',
                    'action_type': 'SHELL',
                    'code': 'SSHD_CONFIG="{{input.sshd_config}}" && cp "$SSHD_CONFIG" "${SSHD_CONFIG}.bak.$(date +%s)" && if grep -q "^PasswordAuthentication" "$SSHD_CONFIG"; then sed -i "s/^PasswordAuthentication.*/PasswordAuthentication no/" "$SSHD_CONFIG"; else echo "PasswordAuthentication no" >> "$SSHD_CONFIG"; fi && if grep -q "^ChallengeResponseAuthentication" "$SSHD_CONFIG"; then sed -i "s/^ChallengeResponseAuthentication.*/ChallengeResponseAuthentication no/" "$SSHD_CONFIG"; fi && sshd -t -f "$SSHD_CONFIG" 2>&1 && systemctl reload sshd && echo "Password authentication disabled" || (echo "FAILED: sshd config test failed" >&2; exit 1)',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'sshd_config': {'type': 'string', 'description': 'Path to sshd_config file'},
                        },
                        'required': ['sshd_config'],
                    },
                },
                'params': {'target': ['server', 'host', 'node', 'bastion']},
                'prompts': [
                    'Disable SSH password authentication on the {target}',
                    'Create a DM action to enforce key-only SSH on {target}',
                    'Write a shell action to disable PasswordAuthentication on {target}',
                ],
                'explanation': 'Disables SSH password authentication on the {target}, enforcing key-based login only.',
                'features': ['schema_variables'],
            },
            {
                'name': 'fail2ban-jail-setup',
                'template': {
                    'name': '{service}-fail2ban-jail',
                    'action_type': 'SHELL',
                    'code': 'cat > /etc/fail2ban/jail.d/{{input.jail_name}}.conf <<JAIL\n[{{input.jail_name}}]\nenabled = true\nport = {{input.port}}\nfilter = {{input.filter_name}}\nlogpath = {{input.log_path}}\nmaxretry = {{input.max_retry}}\nbantime = {{input.ban_time}}\nfindtime = {{input.find_time}}\naction = %(action_mwl)s\nJAIL\nsystemctl restart fail2ban && fail2ban-client status {{input.jail_name}} 2>&1 && echo "fail2ban jail {{input.jail_name}} configured and active" || (echo "FAILED: fail2ban jail setup error" >&2; exit 1)',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'jail_name': {'type': 'string', 'description': 'Name of the fail2ban jail'},
                            'port': {'type': 'string', 'description': 'Port(s) to protect (e.g. ssh, http,https)'},
                            'filter_name': {'type': 'string', 'description': 'fail2ban filter to use (e.g. sshd, nginx-http-auth)'},
                            'log_path': {'type': 'string', 'description': 'Path to the log file to monitor'},
                            'max_retry': {'type': 'integer', 'description': 'Number of failures before ban'},
                            'ban_time': {'type': 'string', 'description': 'Ban duration (e.g. 3600, 1h, 1d)'},
                            'find_time': {'type': 'string', 'description': 'Time window for counting failures (e.g. 600, 10m)'},
                        },
                        'required': ['jail_name', 'port', 'filter_name', 'log_path', 'max_retry', 'ban_time', 'find_time'],
                    },
                },
                'params': {'service': ['sshd', 'nginx', 'apache', 'postfix', 'dovecot']},
                'prompts': [
                    'Set up a fail2ban jail for {service}',
                    'Create a DM action to configure fail2ban protection for {service}',
                    'Write a shell action that creates a fail2ban jail for {service}',
                ],
                'explanation': 'Creates and activates a fail2ban jail to protect the {service} service from brute force attacks.',
                'features': ['schema_variables'],
                'difficulty': 'intermediate',
            },
            {
                'name': 'firewall-default-deny',
                'template': {
                    'name': '{target}-fw-default-deny',
                    'action_type': 'SHELL',
                    'code': 'iptables -P INPUT DROP && iptables -P FORWARD DROP && iptables -P OUTPUT ACCEPT && iptables -A INPUT -i lo -j ACCEPT && iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT && iptables -A INPUT -p tcp --dport {{input.ssh_port}} -j ACCEPT && iptables -A INPUT -p icmp --icmp-type echo-request -j ACCEPT && iptables-save > /etc/iptables/rules.v4 2>/dev/null || iptables-save > /etc/sysconfig/iptables 2>/dev/null && echo "Default deny policy applied, SSH port {{input.ssh_port}} and established connections allowed"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'ssh_port': {'type': 'integer', 'description': 'SSH port to allow through the firewall'},
                        },
                        'required': ['ssh_port'],
                    },
                },
                'params': {'target': ['server', 'host', 'node', 'gateway']},
                'prompts': [
                    'Set up a default deny firewall policy on the {target}',
                    'Create a DM action for default-deny iptables rules on {target}',
                    'Write a shell action that configures a restrictive firewall on {target}',
                ],
                'explanation': 'Applies a default deny iptables policy on the {target}, allowing only SSH, ICMP, and established connections.',
                'features': ['schema_variables'],
                'difficulty': 'intermediate',
            },
            {
                'name': 'openssl-dhparam',
                'template': {
                    'name': '{target}-dhparam-gen',
                    'action_type': 'SHELL',
                    'code': 'echo "Generating {{input.bits}}-bit DH parameters (this may take several minutes)..." && openssl dhparam -out {{input.output_path}} {{input.bits}} 2>&1 && chmod 644 {{input.output_path}} && openssl dhparam -in {{input.output_path}} -check -noout 2>&1 && echo "DH parameters generated: {{input.output_path}} ({{input.bits}} bits)" || (echo "FAILED: dhparam generation error" >&2; exit 1)',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'output_path': {'type': 'string', 'description': 'Output path for the DH parameters file'},
                            'bits': {'type': 'integer', 'description': 'Key size in bits (2048 or 4096)'},
                        },
                        'required': ['output_path', 'bits'],
                    },
                },
                'params': {'target': ['nginx', 'apache', 'haproxy', 'postfix']},
                'prompts': [
                    'Generate OpenSSL DH parameters for {target}',
                    'Create a DM action to generate dhparam for {target} TLS hardening',
                    'Write a shell action that creates DH parameters for {target}',
                ],
                'explanation': 'Generates strong Diffie-Hellman parameters for {target} TLS configuration.',
                'features': ['schema_variables'],
            },
            {
                'name': 'pam-password-policy',
                'template': {
                    'name': '{target}-pam-password',
                    'action_type': 'SHELL',
                    'code': 'PAM_FILE="/etc/security/pwquality.conf" && cp "$PAM_FILE" "${PAM_FILE}.bak.$(date +%s)" 2>/dev/null; cat > "$PAM_FILE" <<PWQUAL\nminlen = {{input.min_length}}\nminclass = {{input.min_classes}}\nmaxrepeat = {{input.max_repeat}}\nreject_username\nenforcing = 1\nPWQUAL\necho "Password policy set: minlen={{input.min_length}}, minclass={{input.min_classes}}, maxrepeat={{input.max_repeat}}" && if command -v pam-auth-update > /dev/null 2>&1; then echo "Run pam-auth-update to apply changes"; fi',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'min_length': {'type': 'integer', 'description': 'Minimum password length'},
                            'min_classes': {'type': 'integer', 'description': 'Minimum number of character classes (1-4)'},
                            'max_repeat': {'type': 'integer', 'description': 'Maximum consecutive repeated characters'},
                        },
                        'required': ['min_length', 'min_classes', 'max_repeat'],
                    },
                },
                'params': {'target': ['server', 'host', 'workstation', 'node']},
                'prompts': [
                    'Configure PAM password quality policy on the {target}',
                    'Create a DM action to enforce password complexity on {target}',
                    'Write a shell action that sets password strength requirements on {target}',
                ],
                'explanation': 'Configures PAM password quality policy on the {target} with minimum length and complexity requirements.',
                'features': ['schema_variables'],
            },
            {
                'name': 'aide-init-check',
                'template': {
                    'name': '{target}-aide-check',
                    'action_type': 'SHELL',
                    'code': 'if [ "{{input.mode}}" = "init" ]; then echo "Initializing AIDE database..." && aide --init 2>&1 && mv /var/lib/aide/aide.db.new /var/lib/aide/aide.db 2>/dev/null; mv /var/lib/aide/aide.db.new.gz /var/lib/aide/aide.db.gz 2>/dev/null; echo "AIDE database initialized"; elif [ "{{input.mode}}" = "check" ]; then echo "Running AIDE integrity check..." && aide --check 2>&1; RC=$?; if [ $RC -eq 0 ]; then echo "AIDE check passed: no changes detected"; elif [ $RC -le 7 ]; then echo "WARNING: AIDE detected changes (exit code: $RC)"; exit 1; else echo "FAILED: AIDE error (exit code: $RC)" >&2; exit 1; fi; else echo "FAILED: mode must be init or check" >&2; exit 1; fi',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'mode': {'type': 'string', 'description': 'AIDE mode: "init" to initialize database, "check" to verify integrity'},
                        },
                        'required': ['mode'],
                    },
                },
                'params': {'target': ['server', 'host', 'production', 'node']},
                'prompts': [
                    'Run AIDE filesystem integrity check on the {target}',
                    'Create a DM action to initialize or check AIDE on {target}',
                    'Write a shell action for AIDE intrusion detection on {target}',
                ],
                'explanation': 'Initializes or runs an AIDE filesystem integrity check on the {target} for intrusion detection.',
                'features': ['schema_variables'],
            },
            {
                'name': 'audit-rule-addition',
                'template': {
                    'name': '{target}-audit-rule',
                    'action_type': 'SHELL',
                    'code': 'RULE_FILE="/etc/audit/rules.d/{{input.rule_name}}.rules" && echo "{{input.audit_rule}}" > "$RULE_FILE" && chmod 640 "$RULE_FILE" && augenrules --load 2>&1 && auditctl -l 2>&1 | grep -F "{{input.rule_key}}" && echo "Audit rule added: {{input.rule_name}}" || (echo "FAILED: Could not load audit rule" >&2; exit 1)',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'rule_name': {'type': 'string', 'description': 'Name for the audit rules file'},
                            'audit_rule': {'type': 'string', 'description': 'Audit rule definition (e.g. -w /etc/passwd -p wa -k identity)'},
                            'rule_key': {'type': 'string', 'description': 'Audit key to verify the rule was loaded'},
                        },
                        'required': ['rule_name', 'audit_rule', 'rule_key'],
                    },
                },
                'params': {'target': ['server', 'host', 'production', 'compliance']},
                'prompts': [
                    'Add an audit rule to the {target} system',
                    'Create a DM action to configure Linux auditing on {target}',
                    'Write a shell action that adds a persistent audit rule on {target}',
                ],
                'explanation': 'Adds a persistent Linux audit rule on the {target} system and verifies it is loaded.',
                'features': ['schema_variables'],
                'difficulty': 'intermediate',
            },
            {
                'name': 'apparmor-enforce',
                'template': {
                    'name': '{service}-apparmor-enforce',
                    'action_type': 'SHELL',
                    'code': 'if ! command -v aa-enforce > /dev/null 2>&1; then echo "FAILED: apparmor-utils not installed" >&2; exit 1; fi && if [ ! -f "{{input.profile_path}}" ]; then echo "FAILED: Profile not found: {{input.profile_path}}" >&2; exit 1; fi && aa-enforce "{{input.profile_path}}" 2>&1 && aa-status 2>&1 | grep -A1 "enforce" && echo "AppArmor profile enforced: {{input.profile_path}}" || (echo "FAILED: Could not enforce AppArmor profile" >&2; exit 1)',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'profile_path': {'type': 'string', 'description': 'Path to the AppArmor profile to enforce'},
                        },
                        'required': ['profile_path'],
                    },
                },
                'params': {'service': ['nginx', 'mysql', 'apache', 'docker', 'sshd']},
                'prompts': [
                    'Enforce an AppArmor profile for {service}',
                    'Create a DM action to set AppArmor to enforce mode for {service}',
                    'Write a shell action that activates AppArmor enforcement for {service}',
                ],
                'explanation': 'Puts the AppArmor profile for {service} into enforce mode for mandatory access control.',
                'features': ['schema_variables'],
            },
            {
                'name': 'auto-security-updates',
                'template': {
                    'name': '{target}-unattended-upgrades',
                    'action_type': 'SHELL',
                    'code': 'if command -v apt-get > /dev/null 2>&1; then apt-get install -y unattended-upgrades apt-listchanges 2>&1 && cat > /etc/apt/apt.conf.d/50unattended-upgrades <<UUCFG\nUnattended-Upgrade::Allowed-Origins {\n    "${distro_id}:${distro_codename}-security";\n};\nUnattended-Upgrade::AutoFixInterruptedDpkg "true";\nUnattended-Upgrade::MinimalSteps "true";\nUnattended-Upgrade::Mail "{{input.notify_email}}";\nUnattended-Upgrade::Remove-Unused-Dependencies "true";\nUnattended-Upgrade::Automatic-Reboot "{{input.auto_reboot}}";\nUUCFG\ncat > /etc/apt/apt.conf.d/20auto-upgrades <<AUTOCFG\nAPT::Periodic::Update-Package-Lists "1";\nAPT::Periodic::Unattended-Upgrade "1";\nAUTOCFG\necho "Unattended security upgrades configured (notify: {{input.notify_email}})"; elif command -v yum > /dev/null 2>&1; then yum install -y yum-cron 2>&1 && sed -i "s/^update_cmd.*/update_cmd = security/" /etc/yum/yum-cron.conf && sed -i "s/^apply_updates.*/apply_updates = yes/" /etc/yum/yum-cron.conf && systemctl enable --now yum-cron && echo "yum-cron security updates enabled"; else echo "FAILED: Unsupported package manager" >&2; exit 1; fi',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'notify_email': {'type': 'string', 'description': 'Email address for update notifications'},
                            'auto_reboot': {'type': 'string', 'description': 'Whether to auto-reboot if needed (true or false)'},
                        },
                        'required': ['notify_email', 'auto_reboot'],
                    },
                },
                'params': {'target': ['server', 'host', 'production', 'node']},
                'prompts': [
                    'Enable automatic security updates on the {target}',
                    'Create a DM action to configure unattended-upgrades on {target}',
                    'Write a shell action that sets up automatic security patching on {target}',
                ],
                'explanation': 'Configures automatic security updates on the {target} using unattended-upgrades (Debian/Ubuntu) or yum-cron (RHEL/CentOS).',
                'features': ['schema_variables'],
                'difficulty': 'intermediate',
            },
            {
                'name': 'root-login-email-alert',
                'template': {
                    'name': '{target}-root-login-alert',
                    'action_type': 'SHELL',
                    'code': 'ALERT_SCRIPT="/usr/local/bin/root-login-alert.sh" && cat > "$ALERT_SCRIPT" <<\'SCRIPT\'\n#!/bin/bash\nif [ "$PAM_USER" = "root" ] && [ "$PAM_TYPE" = "open_session" ]; then\n  SUBJECT="Root login alert on $(hostname)"\n  BODY="Root login detected\\nUser: $PAM_USER\\nRemote Host: $PAM_RHOST\\nService: $PAM_SERVICE\\nTime: $(date)\\nTTY: $PAM_TTY"\n  echo -e "$BODY" | mail -s "$SUBJECT" "ALERT_EMAIL"\nfi\nSCRIPT\nsed -i "s/ALERT_EMAIL/{{input.alert_email}}/g" "$ALERT_SCRIPT" && chmod 755 "$ALERT_SCRIPT" && if ! grep -q "root-login-alert" /etc/pam.d/sshd; then echo "session optional pam_exec.so /usr/local/bin/root-login-alert.sh" >> /etc/pam.d/sshd; fi && echo "Root login email alert configured ({{input.alert_email}})"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'alert_email': {'type': 'string', 'description': 'Email address to receive root login alerts'},
                        },
                        'required': ['alert_email'],
                    },
                },
                'params': {'target': ['server', 'host', 'production', 'bastion']},
                'prompts': [
                    'Set up root login email alerts on the {target}',
                    'Create a DM action for root login notification on {target}',
                    'Write a shell action that emails an alert when root logs into {target}',
                ],
                'explanation': 'Configures a PAM-based email alert on the {target} that sends a notification whenever root logs in via SSH.',
                'features': ['schema_variables'],
                'difficulty': 'intermediate',
            },
            {
                'name': 'cis-disk-check',
                'template': {
                    'name': '{target}-cis-disk-check',
                    'action_type': 'SHELL',
                    'code': 'echo "=== CIS Benchmark: Filesystem Checks ===" && PASS=0 && FAIL=0 && echo "--- Checking /tmp mount options ---" && if findmnt -n /tmp | grep -q "noexec"; then echo "PASS: /tmp has noexec"; PASS=$((PASS+1)); else echo "FAIL: /tmp missing noexec"; FAIL=$((FAIL+1)); fi && if findmnt -n /tmp | grep -q "nosuid"; then echo "PASS: /tmp has nosuid"; PASS=$((PASS+1)); else echo "FAIL: /tmp missing nosuid"; FAIL=$((FAIL+1)); fi && echo "--- Checking /var mount ---" && if findmnt -n /var > /dev/null 2>&1; then echo "PASS: /var is a separate partition"; PASS=$((PASS+1)); else echo "FAIL: /var is not a separate partition"; FAIL=$((FAIL+1)); fi && echo "--- Checking /var/log mount ---" && if findmnt -n /var/log > /dev/null 2>&1; then echo "PASS: /var/log is a separate partition"; PASS=$((PASS+1)); else echo "FAIL: /var/log is not a separate partition"; FAIL=$((FAIL+1)); fi && echo "--- Checking world-writable dirs ---" && WORLD_WRITABLE=$(find / -xdev -type d -perm -0002 ! -perm -1000 2>/dev/null | head -20) && if [ -z "$WORLD_WRITABLE" ]; then echo "PASS: No world-writable dirs without sticky bit"; PASS=$((PASS+1)); else echo "FAIL: World-writable dirs found:"; echo "$WORLD_WRITABLE"; FAIL=$((FAIL+1)); fi && echo "=== Results: $PASS passed, $FAIL failed ===" && if [ $FAIL -gt 0 ]; then exit 1; fi',
                    'expected_rc': 0,
                    'schema': {
                        'input': {},
                        'required': [],
                    },
                },
                'params': {'target': ['server', 'host', 'production', 'compliance']},
                'prompts': [
                    'Run CIS benchmark disk partition checks on the {target}',
                    'Create a DM action for CIS filesystem compliance audit on {target}',
                    'Write a shell action that checks CIS disk hardening on {target}',
                ],
                'explanation': 'Runs CIS benchmark filesystem checks on the {target} including mount options, partitioning, and world-writable directories.',
                'features': ['schema_variables'],
                'difficulty': 'advanced',
            },
            {
                'name': 'two-factor-auth-setup',
                'template': {
                    'name': '{target}-2fa-setup',
                    'action_type': 'SHELL',
                    'code': 'if ! command -v google-authenticator > /dev/null 2>&1; then if command -v apt-get > /dev/null 2>&1; then apt-get install -y libpam-google-authenticator 2>&1; elif command -v yum > /dev/null 2>&1; then yum install -y google-authenticator 2>&1; fi; fi && if ! grep -q "pam_google_authenticator" /etc/pam.d/sshd; then echo "auth required pam_google_authenticator.so nullok" >> /etc/pam.d/sshd; fi && SSHD_CONFIG="{{input.sshd_config}}" && if grep -q "^ChallengeResponseAuthentication" "$SSHD_CONFIG"; then sed -i "s/^ChallengeResponseAuthentication.*/ChallengeResponseAuthentication yes/" "$SSHD_CONFIG"; else echo "ChallengeResponseAuthentication yes" >> "$SSHD_CONFIG"; fi && if grep -q "^KbdInteractiveAuthentication" "$SSHD_CONFIG"; then sed -i "s/^KbdInteractiveAuthentication.*/KbdInteractiveAuthentication yes/" "$SSHD_CONFIG"; else echo "KbdInteractiveAuthentication yes" >> "$SSHD_CONFIG"; fi && sshd -t -f "$SSHD_CONFIG" 2>&1 && systemctl reload sshd && echo "2FA PAM module installed and SSH configured. Users must run google-authenticator to enroll."',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'sshd_config': {'type': 'string', 'description': 'Path to sshd_config file (default: /etc/ssh/sshd_config)'},
                        },
                        'required': ['sshd_config'],
                    },
                },
                'params': {'target': ['server', 'host', 'bastion', 'node']},
                'prompts': [
                    'Set up two-factor authentication on the {target} using Google Authenticator',
                    'Create a DM action to enable 2FA for SSH on {target}',
                    'Write a shell action that installs and configures TOTP-based 2FA on {target}',
                ],
                'explanation': 'Installs and configures Google Authenticator PAM module for SSH two-factor authentication on the {target}.',
                'features': ['schema_variables'],
                'difficulty': 'intermediate',
            },
            {
                'name': 'ip-allowlist-config',
                'template': {
                    'name': '{target}-ip-allowlist',
                    'action_type': 'SHELL',
                    'code': 'CHAIN_NAME="ALLOWLIST_{{input.service_port}}" && iptables -N "$CHAIN_NAME" 2>/dev/null; iptables -F "$CHAIN_NAME" && IPS="{{input.allowed_ips}}" && for IP in $IPS; do iptables -A "$CHAIN_NAME" -s "$IP" -j ACCEPT && echo "Allowed: $IP"; done && iptables -A "$CHAIN_NAME" -j DROP && iptables -C INPUT -p tcp --dport {{input.service_port}} -j "$CHAIN_NAME" 2>/dev/null || iptables -I INPUT -p tcp --dport {{input.service_port}} -j "$CHAIN_NAME" && echo "IP allowlist applied for port {{input.service_port}} ($(echo $IPS | wc -w) IPs allowed)" && iptables-save > /etc/iptables/rules.v4 2>/dev/null || iptables-save > /etc/sysconfig/iptables 2>/dev/null; echo "Rules persisted"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'service_port': {'type': 'integer', 'description': 'Port number to restrict access to'},
                            'allowed_ips': {'type': 'string', 'description': 'Space-separated list of allowed IP addresses or CIDRs'},
                        },
                        'required': ['service_port', 'allowed_ips'],
                    },
                },
                'params': {'target': ['server', 'database', 'admin-panel', 'api']},
                'prompts': [
                    'Configure an IP allowlist for the {target} service port',
                    'Create a DM action to restrict {target} access to specific IPs',
                    'Write a shell action that sets up an IP whitelist for {target} using iptables',
                ],
                'explanation': 'Configures an iptables IP allowlist for the {target}, permitting only specified IP addresses and blocking all others.',
                'features': ['schema_variables'],
                'difficulty': 'intermediate',
            },
            {
                'name': 'file-permission-audit',
                'template': {
                    'name': '{target}-permission-audit',
                    'action_type': 'SHELL',
                    'code': 'echo "=== File Permission Audit ===" && PASS=0 && FAIL=0 && echo "--- SUID files ---" && SUID_FILES=$(find / -xdev -perm -4000 -type f 2>/dev/null) && SUID_COUNT=$(echo "$SUID_FILES" | grep -c . 2>/dev/null || echo 0) && echo "SUID files found: $SUID_COUNT" && echo "$SUID_FILES" | head -20 && echo "--- SGID files ---" && SGID_FILES=$(find / -xdev -perm -2000 -type f 2>/dev/null) && SGID_COUNT=$(echo "$SGID_FILES" | grep -c . 2>/dev/null || echo 0) && echo "SGID files found: $SGID_COUNT" && echo "$SGID_FILES" | head -20 && echo "--- World-writable files ---" && WW_FILES=$(find / -xdev -perm -0002 -type f 2>/dev/null) && WW_COUNT=$(echo "$WW_FILES" | grep -c . 2>/dev/null || echo 0) && echo "World-writable files: $WW_COUNT" && echo "$WW_FILES" | head -20 && echo "--- Unowned files ---" && NOOWNER=$(find / -xdev \\( -nouser -o -nogroup \\) 2>/dev/null) && NO_COUNT=$(echo "$NOOWNER" | grep -c . 2>/dev/null || echo 0) && echo "Unowned files: $NO_COUNT" && echo "=== Audit complete: SUID=$SUID_COUNT SGID=$SGID_COUNT WW=$WW_COUNT Unowned=$NO_COUNT ==="',
                    'expected_rc': 0,
                    'schema': {
                        'input': {},
                        'required': [],
                    },
                },
                'params': {'target': ['server', 'host', 'production', 'compliance']},
                'prompts': [
                    'Run a file permission audit on the {target}',
                    'Create a DM action to scan for dangerous file permissions on {target}',
                    'Write a shell action that audits SUID, SGID, and world-writable files on {target}',
                ],
                'explanation': 'Audits file permissions on the {target} scanning for SUID, SGID, world-writable, and unowned files.',
                'features': ['schema_variables'],
                'difficulty': 'intermediate',
            },
            {
                'name': 'kernel-hardening',
                'template': {
                    'name': '{target}-kernel-harden',
                    'action_type': 'SHELL',
                    'code': 'SYSCTL_FILE="/etc/sysctl.d/99-hardening.conf" && cat > "$SYSCTL_FILE" <<SYSCTL\n# Network hardening\nnet.ipv4.ip_forward = 0\nnet.ipv4.conf.all.send_redirects = 0\nnet.ipv4.conf.default.send_redirects = 0\nnet.ipv4.conf.all.accept_redirects = 0\nnet.ipv4.conf.default.accept_redirects = 0\nnet.ipv4.conf.all.accept_source_route = 0\nnet.ipv4.conf.all.log_martians = 1\nnet.ipv4.conf.default.log_martians = 1\nnet.ipv4.icmp_echo_ignore_broadcasts = 1\nnet.ipv4.tcp_syncookies = 1\n# Kernel hardening\nkernel.randomize_va_space = 2\nkernel.sysrq = 0\nkernel.core_uses_pid = 1\nfs.suid_dumpable = 0\nSYSTL\nsysctl -p "$SYSCTL_FILE" 2>&1 && echo "Kernel parameters hardened via $SYSCTL_FILE"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {},
                        'required': [],
                    },
                },
                'params': {'target': ['server', 'host', 'production', 'node']},
                'prompts': [
                    'Apply kernel parameter hardening on the {target}',
                    'Create a DM action to configure sysctl security parameters on {target}',
                    'Write a shell action that hardens kernel network and security settings on {target}',
                ],
                'explanation': 'Applies kernel parameter hardening on the {target} including network, ASLR, and core dump protections via sysctl.',
                'features': ['schema_variables'],
                'difficulty': 'advanced',
            },
            {
                'name': 'login-banner-setup',
                'template': {
                    'name': '{target}-login-banner',
                    'action_type': 'SHELL',
                    'code': 'cat > /etc/issue.net <<BANNER\n{{input.banner_text}}\nBANNER\ncat > /etc/issue <<BANNER\n{{input.banner_text}}\nBANNER\nSCONF="{{input.sshd_config}}" && if grep -q "^Banner" "$SCONF"; then sed -i "s|^Banner.*|Banner /etc/issue.net|" "$SCONF"; else echo "Banner /etc/issue.net" >> "$SCONF"; fi && sshd -t -f "$SCONF" 2>&1 && systemctl reload sshd && echo "Login banner configured on {{input.sshd_config}}" && echo "--- Banner content ---" && cat /etc/issue.net',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'sshd_config': {'type': 'string', 'description': 'Path to sshd_config file'},
                            'banner_text': {'type': 'string', 'description': 'Banner text to display before login'},
                        },
                        'required': ['sshd_config', 'banner_text'],
                    },
                },
                'params': {'target': ['server', 'host', 'bastion', 'production']},
                'prompts': [
                    'Set up a login banner on the {target}',
                    'Create a DM action to configure a pre-login warning banner on {target}',
                    'Write a shell action that deploys a legal/security banner for SSH on {target}',
                ],
                'explanation': 'Configures a pre-login warning banner on the {target} displayed to users before SSH authentication.',
                'features': ['schema_variables'],
            },
        ]


def get_generators():
    return [SecurityGenerator()]
