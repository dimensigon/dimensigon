# Dimensigon 2.0 Production Deployment Guide

## Table of Contents
- [Overview](#overview)
- [System Requirements](#system-requirements)
- [Pre-Deployment Checklist](#pre-deployment-checklist)
- [Deployment Methods](#deployment-methods)
  - [Docker Deployment (Recommended)](#docker-deployment-recommended)
  - [Traditional Linux Deployment](#traditional-linux-deployment)
  - [Kubernetes Deployment](#kubernetes-deployment)
- [Configuration](#configuration)
- [Database Setup](#database-setup)
- [SSL/TLS Configuration](#ssltls-configuration)
- [Service Management](#service-management)
- [Monitoring and Logging](#monitoring-and-logging)
- [Backup and Recovery](#backup-and-recovery)
- [Troubleshooting](#troubleshooting)
- [Performance Tuning](#performance-tuning)
- [Security Hardening](#security-hardening)

## Overview

Dimensigon 2.0 is a distributed orchestration platform featuring:
- Mesh networking and decentralized management
- RESTful API with Flask backend
- DM-WebManager GUI for administration
- Distributed vault for secrets management
- Double encryption (SSL + encrypted messaging)
- Log federation and high-complex orchestrations

This guide covers production deployment with high availability, security, and scalability considerations.

## System Requirements

### Minimum Requirements
- **OS**: Linux (Ubuntu 20.04+, RHEL 8+, Debian 11+, CentOS 8+)
- **Python**: 3.8+ (3.9-3.12 recommended)
- **CPU**: 2 cores
- **RAM**: 4 GB
- **Disk**: 20 GB available space
- **Network**: Static IP or reliable DNS resolution

### Recommended Production Requirements
- **OS**: Ubuntu 22.04 LTS or RHEL 9
- **Python**: 3.11
- **CPU**: 4+ cores
- **RAM**: 8+ GB
- **Disk**: 50+ GB SSD storage
- **Network**: 1 Gbps network interface
- **Load Balancer**: Nginx or HAProxy for high availability

### Software Dependencies
- **Database**: PostgreSQL 12+ (recommended) or SQLite (development only)
- **Web Server**: Gunicorn (included) with Nginx reverse proxy
- **Container Runtime**: Docker 20.10+ and Docker Compose 2.0+ (for containerized deployment)
- **Python Packages**: See requirements.txt

## Pre-Deployment Checklist

### 1. Infrastructure Preparation
- [ ] Provision servers with required specifications
- [ ] Configure network connectivity between nodes
- [ ] Set up DNS records for all nodes
- [ ] Configure firewall rules (allow port 20194 or custom port)
- [ ] Prepare SSL/TLS certificates (self-signed or CA-signed)
- [ ] Set up backup storage location
- [ ] Configure monitoring infrastructure

### 2. Security Preparation
- [ ] Generate strong passwords for database and admin accounts
- [ ] Create SSL certificates and keys
- [ ] Set up secret management (environment variables or vault)
- [ ] Review and apply security policies
- [ ] Configure SELinux/AppArmor policies (if applicable)
- [ ] Plan network segmentation and access controls

### 3. Database Preparation
- [ ] Install and configure PostgreSQL server
- [ ] Create database and dedicated user
- [ ] Configure database backups
- [ ] Test database connectivity
- [ ] Plan database migration strategy

### 4. Application Preparation
- [ ] Download/clone Dimensigon 2.0 source code
- [ ] Review and customize configuration files
- [ ] Prepare environment variable files
- [ ] Plan initial dimension creation or join strategy
- [ ] Document deployment architecture

## Deployment Methods

### Docker Deployment (Recommended)

Docker deployment is the recommended method for production as it provides:
- Consistent environment across deployments
- Easy scaling and orchestration
- Isolated application runtime
- Simplified dependency management

#### Prerequisites
```bash
# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

#### Step 1: Clone Repository
```bash
cd /opt
sudo git clone https://github.com/dimensigon/dimensigon.git
cd dimensigon
```

#### Step 2: Configure Environment
```bash
# Copy environment template
cp .env.example .env

# Edit environment variables
sudo nano .env

# Required variables:
# - DM_SECRET_KEY: Strong random secret key
# - SQLALCHEMY_DATABASE_URI: PostgreSQL connection string
# - FLASK_CONFIG: Set to "production"
# - DM_PORT: Default 20194
```

#### Step 3: Configure SSL Certificates
```bash
# Create SSL directory
sudo mkdir -p /opt/dimensigon/ssl

# Copy or generate certificates
# Option A: Copy existing certificates
sudo cp /path/to/cert.pem /opt/dimensigon/ssl/
sudo cp /path/to/key.pem /opt/dimensigon/ssl/

# Option B: Generate self-signed certificate
sudo openssl req -x509 -nodes -days 365 -newkey rsa:4096 \
  -keyout /opt/dimensigon/ssl/key.pem \
  -out /opt/dimensigon/ssl/cert.pem \
  -subj "/C=US/ST=State/L=City/O=Organization/CN=dimensigon.local"

# Set proper permissions
sudo chmod 600 /opt/dimensigon/ssl/key.pem
sudo chmod 644 /opt/dimensigon/ssl/cert.pem
```

#### Step 4: Deploy with Docker Compose
```bash
# Start services
sudo docker-compose up -d

# View logs
sudo docker-compose logs -f

# Check service status
sudo docker-compose ps
```

#### Step 5: Initialize Dimension
```bash
# Create new dimension (first node)
sudo docker-compose exec dimensigon dimensigon new production-cluster

# Or join existing dimension
sudo docker-compose exec dimensigon dimensigon join <server-ip> <token> --port 20194
```

#### Step 6: Verify Deployment
```bash
# Check health
curl -k https://localhost:20194/health

# Access Web GUI
# Navigate to: https://<server-ip>:20194/
# Default credentials: root / <password-set-during-init>
```

### Traditional Linux Deployment

For environments without Docker or requiring direct OS installation:

#### Step 1: Install System Dependencies
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y python3.11 python3.11-venv python3.11-dev \
  gcc libpq-dev libssl-dev git postgresql postgresql-contrib \
  nginx supervisor

# RHEL/CentOS
sudo dnf install -y python3.11 python3.11-devel gcc postgresql-server \
  postgresql-devel openssl-devel git nginx supervisor
```

#### Step 2: Create Application User
```bash
sudo useradd -r -m -s /bin/bash -d /opt/dimensigon dimensigon
```

#### Step 3: Install Dimensigon
```bash
# Switch to dimensigon user
sudo su - dimensigon

# Clone repository
git clone https://github.com/dimensigon/dimensigon.git
cd dimensigon

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install Dimensigon
pip install -r requirements.txt
pip install -e .
```

#### Step 4: Configure Database
```bash
# Initialize PostgreSQL (RHEL/CentOS only)
sudo postgresql-setup --initdb
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Create database and user
sudo -u postgres psql << EOF
CREATE DATABASE dimensigon;
CREATE USER dimensigon WITH ENCRYPTED PASSWORD 'your-secure-password';
GRANT ALL PRIVILEGES ON DATABASE dimensigon TO dimensigon;
\q
EOF
```

#### Step 5: Configure Application
```bash
# Create configuration directory
mkdir -p ~/.dimensigon/.ssl

# Copy SSL certificates
cp /path/to/cert.pem ~/.dimensigon/.ssl/
cp /path/to/key.pem ~/.dimensigon/.ssl/
chmod 600 ~/.dimensigon/.ssl/key.pem

# Set environment variables
cat > ~/.dimensigon/env << EOF
export FLASK_CONFIG=production
export DM_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export SQLALCHEMY_DATABASE_URI="postgresql://dimensigon:your-secure-password@localhost/dimensigon"
export DM_PORT=20194
EOF

# Load environment
source ~/.dimensigon/env
```

#### Step 6: Initialize Dimension
```bash
source venv/bin/activate
source ~/.dimensigon/env

# Create new dimension
dimensigon new production-cluster

# The command will prompt for root password and generate join token
```

#### Step 7: Install Systemd Service
```bash
# Exit dimensigon user
exit

# Copy systemd service file
sudo cp /opt/dimensigon/dimensigon.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable and start service
sudo systemctl enable dimensigon
sudo systemctl start dimensigon

# Check status
sudo systemctl status dimensigon
```

#### Step 8: Configure Nginx Reverse Proxy
```bash
# Create nginx configuration
sudo tee /etc/nginx/sites-available/dimensigon << 'EOF'
upstream dimensigon_backend {
    server 127.0.0.1:20194;
}

server {
    listen 443 ssl http2;
    server_name dimensigon.example.com;

    ssl_certificate /opt/dimensigon/ssl/cert.pem;
    ssl_certificate_key /opt/dimensigon/ssl/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    client_max_body_size 100M;

    location / {
        proxy_pass https://dimensigon_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_ssl_verify off;
    }
}

server {
    listen 80;
    server_name dimensigon.example.com;
    return 301 https://$server_name$request_uri;
}
EOF

# Enable site
sudo ln -s /etc/nginx/sites-available/dimensigon /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx
```

### Kubernetes Deployment

For orchestrated container deployments (see k8s/ directory for manifests):

```bash
# Apply Kubernetes manifests
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/dimensigon.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml
```

## Configuration

### Environment Variables

Core configuration via environment variables:

```bash
# Application
FLASK_CONFIG=production              # production, development, test
DM_SECRET_KEY=<secret-key>          # JWT and session encryption key
PYTHONDONTWRITEBYTECODE=1           # Prevent .pyc files

# Database
SQLALCHEMY_DATABASE_URI=postgresql://user:pass@host:5432/db
SQLALCHEMY_TRACK_MODIFICATIONS=False

# Server
DM_PORT=20194                       # Listen port (default 20194)
HTTP_HOST=0.0.0.0                   # Bind address
WORKERS=4                           # Gunicorn workers (2-4 x CPU cores)

# Security
SSL_VERIFY=True                     # Verify SSL certificates
PREFERRED_URL_SCHEME=https          # Communication scheme

# Logging
LOG_LEVEL=INFO                      # DEBUG, INFO, WARNING, ERROR, CRITICAL
ACCESS_LOGFILE=/var/log/dimensigon/access.log
ERROR_LOGFILE=/var/log/dimensigon/error.log

# Performance
EXECUTOR_MAX_WORKERS=32             # Thread pool size
GUNICORN_TIMEOUT=120                # Request timeout in seconds
```

### Configuration Files

#### Logging Configuration (logconfig.yaml)

```yaml
version: 1
disable_existing_loggers: false

formatters:
  default:
    format: '%(asctime)s [%(process)d] [%(module)s] [%(funcName)s] [%(name)s] [%(levelname)s] %(message)s'
    datefmt: '%Y-%m-%d %H:%M:%S %z'
  access:
    format: '%(message)s'

handlers:
  console:
    class: logging.StreamHandler
    formatter: default
    stream: ext://sys.stdout

  file:
    class: logging.handlers.RotatingFileHandler
    formatter: default
    filename: /var/log/dimensigon/dimensigon.log
    maxBytes: 10485760  # 10MB
    backupCount: 10

  access_file:
    class: logging.handlers.RotatingFileHandler
    formatter: access
    filename: /var/log/dimensigon/access.log
    maxBytes: 10485760
    backupCount: 10

loggers:
  gunicorn.error:
    level: INFO
    handlers: [console, file]
    propagate: false

  gunicorn.access:
    level: INFO
    handlers: [access_file]
    propagate: false

  dimensigon:
    level: INFO
    handlers: [console, file]
    propagate: false

  sqlalchemy:
    level: WARNING
    handlers: [file]
    propagate: false

root:
  level: INFO
  handlers: [console, file]
```

## Database Setup

### PostgreSQL Setup

#### Installation
```bash
# Ubuntu/Debian
sudo apt-get install -y postgresql postgresql-contrib

# RHEL/CentOS
sudo dnf install -y postgresql-server postgresql-contrib
sudo postgresql-setup --initdb
```

#### Configuration
```bash
# Edit PostgreSQL configuration
sudo nano /etc/postgresql/*/main/postgresql.conf

# Recommended settings:
max_connections = 100
shared_buffers = 256MB
effective_cache_size = 1GB
maintenance_work_mem = 64MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
work_mem = 2621kB
min_wal_size = 1GB
max_wal_size = 4GB

# Configure authentication
sudo nano /etc/postgresql/*/main/pg_hba.conf

# Add:
local   dimensigon      dimensigon                              md5
host    dimensigon      dimensigon      127.0.0.1/32            md5
host    dimensigon      dimensigon      ::1/128                 md5

# Restart PostgreSQL
sudo systemctl restart postgresql
```

#### Database Creation
```bash
sudo -u postgres psql << EOF
CREATE DATABASE dimensigon
    WITH ENCODING='UTF8'
    LC_COLLATE='en_US.UTF-8'
    LC_CTYPE='en_US.UTF-8'
    TEMPLATE=template0;

CREATE USER dimensigon WITH ENCRYPTED PASSWORD 'secure-password-here';
GRANT ALL PRIVILEGES ON DATABASE dimensigon TO dimensigon;

\c dimensigon
GRANT ALL ON SCHEMA public TO dimensigon;
\q
EOF
```

### Database Migration

Dimensigon uses SQLAlchemy with automatic migrations:

```bash
# Database tables are created automatically on first run
# Check database initialization in logs

# Manual schema inspection
sudo -u postgres psql -d dimensigon -c "\dt"
```

## SSL/TLS Configuration

### Generate Self-Signed Certificates

For development or internal use:

```bash
# Create directory
mkdir -p ~/.dimensigon/.ssl
cd ~/.dimensigon/.ssl

# Generate private key
openssl genrsa -out key.pem 4096

# Generate certificate signing request
openssl req -new -key key.pem -out cert.csr \
  -subj "/C=US/ST=State/L=City/O=Organization/OU=IT/CN=dimensigon.local"

# Generate self-signed certificate (valid 10 years)
openssl x509 -req -days 3650 -in cert.csr -signkey key.pem -out cert.pem

# Set permissions
chmod 600 key.pem
chmod 644 cert.pem

# Clean up CSR
rm cert.csr
```

### Use CA-Signed Certificates

For production with external access:

```bash
# Copy certificates to application directory
cp /path/to/your/domain.crt ~/.dimensigon/.ssl/cert.pem
cp /path/to/your/domain.key ~/.dimensigon/.ssl/key.pem
cp /path/to/ca-bundle.crt ~/.dimensigon/.ssl/ca-bundle.pem

# Set permissions
chmod 600 ~/.dimensigon/.ssl/key.pem
chmod 644 ~/.dimensigon/.ssl/cert.pem
```

### Certificate Rotation

```bash
# Stop service
sudo systemctl stop dimensigon

# Backup old certificates
mv ~/.dimensigon/.ssl/cert.pem ~/.dimensigon/.ssl/cert.pem.old
mv ~/.dimensigon/.ssl/key.pem ~/.dimensigon/.ssl/key.pem.old

# Copy new certificates
cp /path/to/new/cert.pem ~/.dimensigon/.ssl/
cp /path/to/new/key.pem ~/.dimensigon/.ssl/

# Start service
sudo systemctl start dimensigon
```

## Service Management

### Systemd Service Control

```bash
# Start service
sudo systemctl start dimensigon

# Stop service
sudo systemctl stop dimensigon

# Restart service
sudo systemctl restart dimensigon

# Reload configuration (graceful)
sudo systemctl reload dimensigon

# Check status
sudo systemctl status dimensigon

# Enable auto-start
sudo systemctl enable dimensigon

# View logs
sudo journalctl -u dimensigon -f
```

### Docker Service Control

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# Restart services
docker-compose restart

# View logs
docker-compose logs -f dimensigon

# Scale services
docker-compose up -d --scale dimensigon=3
```

### Health Checks

```bash
# HTTP health check
curl -k https://localhost:20194/health

# Check process
ps aux | grep dimensigon

# Check listening ports
sudo netstat -tlnp | grep 20194
sudo ss -tlnp | grep 20194

# Check database connection
sudo -u postgres psql -d dimensigon -c "SELECT COUNT(*) FROM D_server;"
```

## Monitoring and Logging

### Log Locations

```bash
# Traditional deployment
/var/log/dimensigon/dimensigon.log      # Application logs
/var/log/dimensigon/access.log          # HTTP access logs
/var/log/dimensigon/error.log           # Error logs

# Docker deployment
docker-compose logs dimensigon          # Container logs

# Systemd journal
sudo journalctl -u dimensigon           # Service logs
```

### Log Rotation

```bash
# Create logrotate configuration
sudo tee /etc/logrotate.d/dimensigon << 'EOF'
/var/log/dimensigon/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    missingok
    create 0640 dimensigon dimensigon
    sharedscripts
    postrotate
        systemctl reload dimensigon > /dev/null 2>&1 || true
    endscript
}
EOF
```

### Monitoring Metrics

Key metrics to monitor:

1. **Application Health**
   - HTTP endpoint availability
   - Response time
   - Error rate

2. **System Resources**
   - CPU usage
   - Memory usage
   - Disk I/O
   - Network throughput

3. **Database Performance**
   - Connection pool usage
   - Query performance
   - Database size

4. **Mesh Network**
   - Node connectivity
   - Catalog synchronization
   - Route table health

### Prometheus Integration

```yaml
# Add to docker-compose.yml
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana_data:/var/lib/grafana
```

## Backup and Recovery

### Database Backup

#### Automated Backup Script

```bash
#!/bin/bash
# /opt/dimensigon/backup.sh

BACKUP_DIR="/backup/dimensigon"
DATE=$(date +%Y%m%d_%H%M%S)
DB_NAME="dimensigon"
RETENTION_DAYS=30

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup database
sudo -u postgres pg_dump $DB_NAME | gzip > $BACKUP_DIR/dimensigon_$DATE.sql.gz

# Backup configuration
tar -czf $BACKUP_DIR/config_$DATE.tar.gz /opt/dimensigon/.dimensigon/

# Remove old backups
find $BACKUP_DIR -name "*.sql.gz" -mtime +$RETENTION_DAYS -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +$RETENTION_DAYS -delete

echo "Backup completed: $DATE"
```

#### Schedule Backup

```bash
# Add to crontab
crontab -e

# Daily backup at 2 AM
0 2 * * * /opt/dimensigon/backup.sh >> /var/log/dimensigon/backup.log 2>&1
```

### Database Recovery

```bash
# Stop service
sudo systemctl stop dimensigon

# Drop and recreate database
sudo -u postgres psql << EOF
DROP DATABASE IF EXISTS dimensigon;
CREATE DATABASE dimensigon;
GRANT ALL PRIVILEGES ON DATABASE dimensigon TO dimensigon;
\q
EOF

# Restore from backup
gunzip -c /backup/dimensigon/dimensigon_20240101_020000.sql.gz | \
  sudo -u postgres psql dimensigon

# Restore configuration
tar -xzf /backup/dimensigon/config_20240101_020000.tar.gz -C /

# Start service
sudo systemctl start dimensigon
```

### Disaster Recovery

1. **Full System Recovery**
   ```bash
   # Install Dimensigon on new server
   # Restore database backup
   # Restore configuration files
   # Update IP addresses and certificates if needed
   # Restart service
   ```

2. **Node Replacement**
   ```bash
   # Remove failed node from cluster
   # Deploy new node
   # Join new node to dimension using token
   # Update routes and gates
   ```

## Troubleshooting

### Common Issues

#### 1. Service Won't Start

```bash
# Check logs
sudo journalctl -u dimensigon -n 50

# Common causes:
# - Port already in use
sudo netstat -tlnp | grep 20194

# - Database connection failure
sudo -u postgres psql -d dimensigon -c "SELECT 1;"

# - Permission issues
ls -la /opt/dimensigon/.dimensigon/
```

#### 2. Database Connection Errors

```bash
# Test database connectivity
sudo -u dimensigon psql -h localhost -U dimensigon -d dimensigon

# Check PostgreSQL is running
sudo systemctl status postgresql

# Review PostgreSQL logs
sudo tail -f /var/log/postgresql/postgresql-*.log

# Verify pg_hba.conf allows connections
sudo grep dimensigon /etc/postgresql/*/main/pg_hba.conf
```

#### 3. Certificate Errors

```bash
# Verify certificate validity
openssl x509 -in ~/.dimensigon/.ssl/cert.pem -text -noout

# Check expiration
openssl x509 -in ~/.dimensigon/.ssl/cert.pem -enddate -noout

# Verify key and certificate match
openssl x509 -in ~/.dimensigon/.ssl/cert.pem -noout -modulus | md5sum
openssl rsa -in ~/.dimensigon/.ssl/key.pem -noout -modulus | md5sum
```

#### 4. Unable to Join Dimension

```bash
# Verify network connectivity
curl -k https://<server-ip>:20194/api/v1.0/join/public

# Check token validity
# Tokens expire after 15 minutes by default

# Generate new token on master node
dimensigon token <dimension-name>

# Verify firewall rules
sudo firewall-cmd --list-all
sudo iptables -L -n
```

#### 5. High Memory Usage

```bash
# Check process memory
ps aux | grep dimensigon | awk '{print $6}'

# Adjust worker count in systemd service
# Reduce EXECUTOR_MAX_WORKERS environment variable

# Check for memory leaks
# Review application logs for unusual patterns
```

#### 6. Slow Performance

```bash
# Check database performance
sudo -u postgres psql -d dimensigon << EOF
SELECT schemaname, tablename, n_live_tup, n_dead_tup
FROM pg_stat_user_tables
ORDER BY n_dead_tup DESC;
EOF

# Run vacuum analyze
sudo -u postgres psql -d dimensigon -c "VACUUM ANALYZE;"

# Check system resources
top
htop
iotop
```

### Debug Mode

Enable debug logging for troubleshooting:

```bash
# Set environment variable
export LOG_LEVEL=DEBUG

# Restart service
sudo systemctl restart dimensigon

# Or run in foreground
dimensigon --debug
```

## Performance Tuning

### Application Tuning

```bash
# Optimize Gunicorn workers
# Formula: (2 x CPU cores) + 1
WORKERS=$(($(nproc) * 2 + 1))

# Adjust thread pool
EXECUTOR_MAX_WORKERS=32  # Default, increase for more concurrency

# Configure timeouts
GUNICORN_TIMEOUT=120     # Request timeout
TIMEOUT_REQUEST=60       # Network request timeout
```

### Database Tuning

```sql
-- PostgreSQL optimization

-- Analyze query performance
EXPLAIN ANALYZE SELECT * FROM D_server;

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_server_name ON D_server(name);
CREATE INDEX IF NOT EXISTS idx_gate_server ON D_gate(server_id);

-- Update statistics
ANALYZE;

-- Vacuum regularly
VACUUM ANALYZE;
```

### Network Tuning

```bash
# Increase system limits
sudo tee -a /etc/sysctl.conf << EOF
# Network tuning for Dimensigon
net.core.somaxconn = 1024
net.ipv4.tcp_max_syn_backlog = 2048
net.ipv4.ip_local_port_range = 1024 65535
net.ipv4.tcp_tw_reuse = 1
net.ipv4.tcp_fin_timeout = 15
EOF

# Apply changes
sudo sysctl -p
```

### System Resource Limits

```bash
# Increase file descriptors
sudo tee /etc/security/limits.d/dimensigon.conf << EOF
dimensigon soft nofile 65536
dimensigon hard nofile 65536
dimensigon soft nproc 4096
dimensigon hard nproc 4096
EOF

# Update systemd service
sudo mkdir -p /etc/systemd/system/dimensigon.service.d/
sudo tee /etc/systemd/system/dimensigon.service.d/limits.conf << EOF
[Service]
LimitNOFILE=65536
LimitNPROC=4096
EOF

sudo systemctl daemon-reload
sudo systemctl restart dimensigon
```

## Security Hardening

### 1. Firewall Configuration

```bash
# UFW (Ubuntu/Debian)
sudo ufw allow 20194/tcp
sudo ufw allow from <trusted-ip> to any port 20194
sudo ufw enable

# firewalld (RHEL/CentOS)
sudo firewall-cmd --permanent --add-port=20194/tcp
sudo firewall-cmd --permanent --add-rich-rule='rule family="ipv4" source address="<trusted-ip>" port protocol="tcp" port="20194" accept'
sudo firewall-cmd --reload
```

### 2. SELinux Configuration

```bash
# RHEL/CentOS with SELinux
sudo semanage port -a -t http_port_t -p tcp 20194
sudo setsebool -P httpd_can_network_connect 1
```

### 3. Application Security

```bash
# Strong secret key generation
python3 -c 'import secrets; print(secrets.token_hex(32))'

# Secure environment file permissions
chmod 600 /opt/dimensigon/.env
chown dimensigon:dimensigon /opt/dimensigon/.env

# Disable debug mode in production
FLASK_CONFIG=production
FLASK_DEBUG=0
```

### 4. Database Security

```bash
# Use strong passwords
# Enable SSL for database connections
# Restrict database access by IP
# Regular security updates
sudo apt-get update && sudo apt-get upgrade postgresql
```

### 5. Regular Security Updates

```bash
# System updates
sudo apt-get update && sudo apt-get upgrade -y  # Ubuntu/Debian
sudo dnf update -y                               # RHEL/CentOS

# Python package updates
pip list --outdated
pip install --upgrade <package>
```

### 6. Audit Logging

```bash
# Enable comprehensive logging
export LOG_LEVEL=INFO

# Monitor access logs regularly
tail -f /var/log/dimensigon/access.log

# Set up intrusion detection
sudo apt-get install fail2ban
```

## Multi-Node Cluster Deployment

### Creating First Node (Master)

```bash
# Deploy first node
dimensigon new production-cluster

# Note the join token generated (valid 15 minutes)
```

### Adding Additional Nodes

```bash
# On each additional node
dimensigon join <master-ip> <join-token> --port 20194

# Verify node joined
# Check on master node
dimensigon gate list
```

### High Availability Setup

```bash
# Deploy at least 3 nodes for quorum
# Configure load balancer (Nginx/HAProxy)
# Set up health checks on load balancer
# Configure shared storage for logs (optional)
```

## Upgrade Procedures

### In-Place Upgrade

```bash
# Backup everything first
/opt/dimensigon/backup.sh

# Pull latest code
cd /opt/dimensigon/dimensigon
git pull origin master

# Update dependencies
source venv/bin/activate
pip install --upgrade -r requirements.txt

# Run database migrations (if any)
# Migrations are automatic in Dimensigon

# Restart service
sudo systemctl restart dimensigon

# Verify upgrade
curl -k https://localhost:20194/health
```

### Rolling Upgrade (Multi-Node)

```bash
# Upgrade nodes one at a time
# 1. Remove node from load balancer
# 2. Upgrade node
# 3. Test node
# 4. Add back to load balancer
# 5. Repeat for next node
```

## Production Checklist

- [ ] All nodes deployed and configured
- [ ] Database backups scheduled and tested
- [ ] SSL certificates installed and valid
- [ ] Firewall rules configured
- [ ] Monitoring and alerting active
- [ ] Log rotation configured
- [ ] Resource limits set appropriately
- [ ] Security hardening applied
- [ ] Documentation updated with environment details
- [ ] Disaster recovery plan documented and tested
- [ ] User accounts created with appropriate permissions
- [ ] Network connectivity between all nodes verified
- [ ] Health checks passing
- [ ] Performance baseline established

## Support and Resources

- **Documentation**: https://github.com/dimensigon/dimensigon
- **Issues**: https://github.com/dimensigon/dimensigon/issues
- **Community**: Contact maintainers via GitHub

## Appendix

### A. Port Reference

| Port  | Service           | Protocol | Required |
|-------|-------------------|----------|----------|
| 20194 | Dimensigon API    | HTTPS    | Yes      |
| 5432  | PostgreSQL        | TCP      | Yes      |
| 80    | HTTP Redirect     | HTTP     | Optional |
| 443   | Nginx Proxy       | HTTPS    | Optional |

### B. Directory Structure

```
/opt/dimensigon/
├── .dimensigon/          # Configuration directory
│   ├── .ssl/            # SSL certificates
│   ├── dimensigon.db    # SQLite database (if used)
│   └── dimensigon.log   # Application log
├── dimensigon/          # Application code
├── venv/                # Python virtual environment
└── backup.sh            # Backup script
```

### C. Environment Variable Reference

See `.env.example` for complete list of supported variables.

---

**Version**: 2.0.0
**Last Updated**: 2024-10-29
**Maintainer**: Joan Prat <joan.prat@dimensigon.com>
