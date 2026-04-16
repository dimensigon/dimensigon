"""Shared parameter pools for example generators.

These pools are used by the Parameterizer to create diverse variations
of seed templates across services, packages, paths, and infrastructure.
"""

# ── Service Names ─────────────────────────────────────────────────────
SERVICES = [
    "nginx", "apache2", "httpd", "caddy", "haproxy", "traefik",
    "postgresql", "mysql", "mariadb", "mongod", "redis-server", "memcached",
    "docker", "containerd", "kubelet",
    "prometheus", "grafana-server", "node_exporter", "alertmanager",
    "elasticsearch", "kibana", "logstash", "filebeat",
    "rabbitmq-server", "kafka", "zookeeper",
    "postfix", "dovecot", "opendkim",
    "sshd", "fail2ban", "ufw", "firewalld",
    "cron", "atd", "rsyslog", "systemd-journald",
    "php-fpm", "gunicorn", "uwsgi", "pm2", "supervisord",
    "consul", "vault", "nomad", "etcd",
    "gitea", "gitlab-runner", "jenkins",
    "wireguard", "openvpn", "strongswan",
]

# ── Package Managers & Install Commands ───────────────────────────────
PKG_MANAGERS = {
    "apt": {"install": "apt-get install -y", "update": "apt-get update", "remove": "apt-get remove -y"},
    "yum": {"install": "yum install -y", "update": "yum update -y", "remove": "yum remove -y"},
    "dnf": {"install": "dnf install -y", "update": "dnf update -y", "remove": "dnf remove -y"},
    "apk": {"install": "apk add --no-cache", "update": "apk update", "remove": "apk del"},
}

# ── Common Packages by Category ──────────────────────────────────────
PACKAGES = {
    "web": ["nginx", "apache2", "httpd", "caddy", "haproxy"],
    "database": ["postgresql", "mysql-server", "mariadb-server", "mongodb-org", "redis"],
    "monitoring": ["prometheus", "grafana", "prometheus-node-exporter", "nagios"],
    "security": ["fail2ban", "ufw", "iptables-persistent", "clamav", "aide"],
    "runtime": ["nodejs", "python3", "openjdk-17-jdk", "golang", "ruby"],
    "container": ["docker-ce", "docker-compose-plugin", "podman", "buildah"],
    "tools": ["curl", "wget", "jq", "htop", "tmux", "git", "vim", "rsync"],
    "mail": ["postfix", "dovecot-imapd", "opendkim", "spamassassin"],
}

# ── File Paths ────────────────────────────────────────────────────────
CONFIG_PATHS = {
    "nginx": "/etc/nginx/nginx.conf",
    "apache2": "/etc/apache2/apache2.conf",
    "httpd": "/etc/httpd/conf/httpd.conf",
    "postgresql": "/etc/postgresql/15/main/postgresql.conf",
    "mysql": "/etc/mysql/mysql.conf.d/mysqld.cnf",
    "redis": "/etc/redis/redis.conf",
    "mongod": "/etc/mongod.conf",
    "haproxy": "/etc/haproxy/haproxy.cfg",
    "sshd": "/etc/ssh/sshd_config",
    "fail2ban": "/etc/fail2ban/jail.local",
    "prometheus": "/etc/prometheus/prometheus.yml",
    "docker": "/etc/docker/daemon.json",
    "postfix": "/etc/postfix/main.cf",
}

LOG_PATHS = {
    "nginx": "/var/log/nginx",
    "apache2": "/var/log/apache2",
    "httpd": "/var/log/httpd",
    "postgresql": "/var/log/postgresql",
    "mysql": "/var/log/mysql",
    "syslog": "/var/log/syslog",
    "auth": "/var/log/auth.log",
    "docker": "/var/log/docker",
    "app": "/var/log/app",
}

DATA_PATHS = {
    "postgresql": "/var/lib/postgresql/15/main",
    "mysql": "/var/lib/mysql",
    "mongodb": "/var/lib/mongodb",
    "redis": "/var/lib/redis",
    "docker": "/var/lib/docker",
    "grafana": "/var/lib/grafana",
    "prometheus": "/var/lib/prometheus",
}

BACKUP_PATHS = ["/backup", "/mnt/backup", "/opt/backup", "/var/backup"]
APP_DIRS = ["/opt/app", "/srv/app", "/home/deploy/app", "/var/www/app"]

# ── Server Granules (for multi-server orchestrations) ─────────────────
GRANULES = {
    "web_tier": ["web", "frontend", "app-server", "www"],
    "db_tier": ["db", "database", "postgres", "mysql", "mongo"],
    "lb_tier": ["lb", "loadbalancer", "proxy", "haproxy", "nginx-lb"],
    "cache_tier": ["cache", "redis", "memcached", "varnish"],
    "monitor_tier": ["monitor", "prometheus", "grafana", "elk"],
    "queue_tier": ["queue", "rabbitmq", "kafka", "worker"],
    "storage_tier": ["storage", "nfs", "gluster", "ceph"],
    "ci_tier": ["ci", "jenkins", "gitlab-runner", "build"],
}

# ── Database Credentials (template variables) ─────────────────────────
DB_USERS = ["admin", "app_user", "readonly", "replicator", "backup_user"]
DB_NAMES = ["app_db", "production", "staging", "analytics", "logs_db"]

# ── Network ───────────────────────────────────────────────────────────
PORTS = {
    "nginx": 80, "nginx_ssl": 443, "haproxy": 80, "haproxy_stats": 8404,
    "postgresql": 5432, "mysql": 3306, "mongodb": 27017, "redis": 6379,
    "prometheus": 9090, "grafana": 3000, "node_exporter": 9100,
    "elasticsearch": 9200, "kibana": 5601, "rabbitmq": 5672,
    "ssh": 22, "smtp": 25, "imap": 993, "docker_api": 2375,
}

# ── User Prompt Variations ────────────────────────────────────────────
PROMPT_STYLES = {
    "imperative": [
        "Create a {action_type} action that {task}",
        "Write a DM action template to {task}",
        "Make an action that {task}",
    ],
    "question": [
        "How do I {task} using Dimensigon?",
        "I need to {task}, can you create an action for that?",
        "What's the best way to {task} in DM?",
    ],
    "scenario": [
        "I'm setting up {context} and need to {task}",
        "For our {context}, create an action that {task}",
        "As part of {context}, I need an action to {task}",
    ],
}

ORCH_PROMPT_STYLES = {
    "imperative": [
        "Create an orchestration that {task}",
        "Build a DM workflow to {task}",
        "Design an orchestration for {task}",
    ],
    "scenario": [
        "I need to {task} across {topology}",
        "Set up an automated workflow that {task} on {topology}",
        "Create a deployment pipeline that {task} targeting {topology}",
    ],
    "migration": [
        "Convert this Ansible playbook to a DM orchestration: {task}",
        "I currently use {source} to {task}, migrate this to Dimensigon",
        "Replace our {source} setup for {task} with a DM orchestration",
    ],
}
