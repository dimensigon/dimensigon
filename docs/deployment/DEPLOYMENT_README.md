# Dimensigon 2.0 Deployment Artifacts

This directory contains comprehensive production deployment artifacts for Dimensigon 2.0.

## Quick Start

### Docker Deployment (5 minutes)

```bash
# 1. Clone repository
git clone https://github.com/dimensigon/dimensigon.git
cd dimensigon

# 2. Create environment file
cp .env.example .env
nano .env  # Edit with your settings

# 3. Generate SSL certificates
mkdir -p ssl
openssl req -x509 -nodes -days 365 -newkey rsa:4096 \
  -keyout ssl/key.pem -out ssl/cert.pem

# 4. Create data directories
mkdir -p data/{postgres,redis,dimensigon/{config,logs,data},nginx/logs}

# 5. Start services
docker-compose -f docker-compose.production.yml up -d

# 6. Initialize dimension
docker-compose exec dimensigon dimensigon new production-cluster

# 7. Access Web GUI
# Navigate to: https://localhost:20194/
```

### Traditional Linux Deployment

See [DEPLOYMENT_GUIDE.md](/home/claude/dimensigon/DEPLOYMENT_GUIDE.md) for detailed instructions.

## File Structure

```
dimensigon/
├── DEPLOYMENT_GUIDE.md              # Comprehensive deployment guide
├── DEPLOYMENT_README.md             # This file
├── docker-compose.production.yml    # Production Docker Compose config
├── Dockerfile                       # Multi-stage production Dockerfile
├── Dockerfile.production            # Alternative Dockerfile
├── docker-entrypoint.sh             # Container entrypoint script
├── .env.example                     # Environment variables template
├── dimensigon.service               # Systemd service unit file
├── init-db.sql                      # PostgreSQL initialization script
├── nginx/
│   ├── nginx.conf                   # Nginx main configuration
│   └── conf.d/
│       └── dimensigon.conf          # Dimensigon virtual host
└── ssl/                             # SSL certificates (create yourself)
    ├── cert.pem
    └── key.pem
```

## Deployment Artifacts Overview

### 1. DEPLOYMENT_GUIDE.md
**Comprehensive production deployment documentation including:**
- System requirements and prerequisites
- Step-by-step installation for Docker and traditional deployments
- Database setup and configuration
- SSL/TLS configuration
- Monitoring, logging, and backup procedures
- Troubleshooting guide
- Performance tuning recommendations
- Security hardening guidelines

**Use this for:** Complete production deployment planning and execution.

### 2. docker-compose.production.yml
**Production-ready Docker Compose configuration featuring:**
- PostgreSQL 15 database with health checks
- Redis cache for future optimization
- Dimensigon application container
- Nginx reverse proxy with SSL termination
- Persistent volumes for data
- Comprehensive environment variable configuration
- Resource limits and logging

**Use this for:** Quick production deployment with Docker.

### 3. Dockerfile (Multi-stage)
**Optimized production Dockerfile with:**
- Multi-stage build for minimal image size
- Security best practices (non-root user)
- Python 3.11 base image
- Health checks
- Proper signal handling
- Optimized layer caching

**Use this for:** Building production container images.

### 4. docker-entrypoint.sh
**Smart container entrypoint script that:**
- Generates SSL certificates if missing
- Waits for database readiness
- Validates configuration
- Supports multiple startup modes
- Provides flexible command execution

**Use this for:** Container initialization and startup logic.

### 5. .env.example
**Comprehensive environment variables template including:**
- Security settings (secrets, passwords)
- Database configuration
- Application settings
- Gunicorn worker configuration
- Logging configuration
- Feature toggles
- Detailed comments and documentation

**Use this for:** Creating your production .env file.

### 6. dimensigon.service
**Systemd service unit file with:**
- Proper dependency management
- Security hardening options
- Resource limits
- Automatic restart configuration
- Comprehensive documentation in comments
- Pre/post start hooks

**Use this for:** Traditional Linux deployment with systemd.

### 7. nginx/nginx.conf
**High-performance Nginx main configuration:**
- Worker process optimization
- SSL/TLS configuration
- Gzip compression
- Rate limiting
- Security headers
- Connection pooling

**Use this for:** Nginx reverse proxy setup.

### 8. nginx/conf.d/dimensigon.conf
**Dimensigon-specific Nginx virtual host:**
- HTTP to HTTPS redirect
- SSL termination
- API endpoint proxying
- WebSocket support
- Static file caching
- Health check endpoints
- Error handling

**Use this for:** Dimensigon-specific Nginx configuration.

### 9. init-db.sql
**PostgreSQL initialization script:**
- Database permissions
- Schema setup
- Optional extensions
- Performance tuning hints

**Use this for:** Database initialization in Docker.

## Deployment Scenarios

### Scenario 1: Single Node Development/Testing

```bash
# Use simple docker-compose
docker-compose -f docker-compose.yml up -d
```

### Scenario 2: Single Node Production

```bash
# Use production docker-compose with all services
docker-compose -f docker-compose.production.yml up -d
```

### Scenario 3: Multi-Node Cluster

```bash
# Deploy first node
docker-compose -f docker-compose.production.yml up -d
docker-compose exec dimensigon dimensigon new production-cluster

# On additional nodes
docker-compose -f docker-compose.production.yml up -d
docker-compose exec dimensigon dimensigon join <master-ip> <token>
```

### Scenario 4: Traditional Linux with Systemd

```bash
# Install dependencies and Dimensigon
# See DEPLOYMENT_GUIDE.md section "Traditional Linux Deployment"

# Copy and configure systemd service
sudo cp dimensigon.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable dimensigon
sudo systemctl start dimensigon
```

### Scenario 5: Behind Load Balancer

```bash
# Deploy multiple Dimensigon instances
# Configure Nginx as load balancer
# Point load balancer to all Dimensigon nodes
# See DEPLOYMENT_GUIDE.md section "High Availability Setup"
```

## Configuration Checklist

### Before Deployment

- [ ] Review system requirements in DEPLOYMENT_GUIDE.md
- [ ] Copy .env.example to .env and customize all values
- [ ] Generate strong random secrets for DM_SECRET_KEY
- [ ] Set strong database passwords
- [ ] Prepare SSL/TLS certificates (production)
- [ ] Configure firewall rules (port 20194)
- [ ] Plan backup strategy
- [ ] Set up monitoring infrastructure

### During Deployment

- [ ] Create necessary directories with proper permissions
- [ ] Copy SSL certificates to correct locations
- [ ] Configure database connection strings
- [ ] Set appropriate worker counts based on CPU cores
- [ ] Configure log rotation
- [ ] Set resource limits
- [ ] Test database connectivity

### After Deployment

- [ ] Initialize dimension or join existing cluster
- [ ] Verify service health checks
- [ ] Test Web GUI access
- [ ] Configure automated backups
- [ ] Set up log aggregation
- [ ] Configure monitoring and alerting
- [ ] Document environment-specific settings
- [ ] Test failover procedures

## Security Considerations

### Critical Security Settings

1. **Change Default Secrets**
   - Generate new DM_SECRET_KEY (min 32 characters)
   - Set strong database passwords
   - Change Redis password

2. **SSL/TLS Certificates**
   - Use CA-signed certificates in production
   - Enable SSL verification between nodes
   - Configure certificate expiration monitoring

3. **Firewall Configuration**
   - Restrict access to port 20194
   - Allow only trusted IPs
   - Use network segmentation

4. **Database Security**
   - Use strong passwords
   - Enable SSL for database connections
   - Restrict database access by IP
   - Regular security updates

5. **Container Security**
   - Run as non-root user (already configured)
   - Keep base images updated
   - Scan images for vulnerabilities
   - Use read-only root filesystem where possible

## Performance Tuning

### Optimize for Your Workload

1. **Gunicorn Workers**
   ```bash
   # Calculate optimal workers: (2 x CPU cores) + 1
   WORKERS=$(($(nproc) * 2 + 1))
   ```

2. **Database Connection Pool**
   ```bash
   # Adjust based on workers and concurrent requests
   SQLALCHEMY_POOL_SIZE=20
   SQLALCHEMY_MAX_OVERFLOW=10
   ```

3. **System Resources**
   ```bash
   # Increase file descriptors
   ulimit -n 65536
   # See dimensigon.service for systemd limits
   ```

## Monitoring

### Key Metrics to Monitor

- **Application**: Response time, error rate, request count
- **System**: CPU, memory, disk I/O, network
- **Database**: Connection pool, query performance, size
- **Mesh Network**: Node connectivity, catalog sync status

### Health Check Endpoints

```bash
# Application health
curl -k https://localhost:20194/health

# API availability
curl -k https://localhost:20194/api/v1.0/

# Admin GUI
curl -k https://localhost:20194/admin/
```

## Backup and Recovery

### Automated Backup Script

```bash
#!/bin/bash
# /opt/dimensigon/backup.sh

BACKUP_DIR="/backup/dimensigon"
DATE=$(date +%Y%m%d_%H%M%S)

# Backup database
docker-compose exec -T postgres pg_dump -U dimensigon dimensigon | \
  gzip > $BACKUP_DIR/db_$DATE.sql.gz

# Backup configuration
tar -czf $BACKUP_DIR/config_$DATE.tar.gz /opt/dimensigon/.dimensigon/

# Remove old backups (30 days)
find $BACKUP_DIR -mtime +30 -delete
```

### Recovery Procedure

```bash
# Stop services
docker-compose down

# Restore database
gunzip -c /backup/dimensigon/db_20240101_020000.sql.gz | \
  docker-compose exec -T postgres psql -U dimensigon dimensigon

# Restore configuration
tar -xzf /backup/dimensigon/config_20240101_020000.tar.gz -C /

# Start services
docker-compose up -d
```

## Troubleshooting

### Common Issues

1. **Container won't start**
   ```bash
   docker-compose logs dimensigon
   docker-compose ps
   ```

2. **Database connection error**
   ```bash
   docker-compose exec postgres pg_isready
   docker-compose exec dimensigon env | grep DATABASE
   ```

3. **SSL certificate error**
   ```bash
   openssl x509 -in ssl/cert.pem -text -noout
   openssl verify ssl/cert.pem
   ```

4. **Port already in use**
   ```bash
   sudo netstat -tlnp | grep 20194
   sudo lsof -i :20194
   ```

For detailed troubleshooting, see DEPLOYMENT_GUIDE.md.

## Support

- **Documentation**: [DEPLOYMENT_GUIDE.md](/home/claude/dimensigon/DEPLOYMENT_GUIDE.md)
- **Issues**: https://github.com/dimensigon/dimensigon/issues
- **Source**: https://github.com/dimensigon/dimensigon

## Version Information

- **Dimensigon Version**: 2.0.0
- **Python Version**: 3.8+ (3.11 recommended)
- **Database**: PostgreSQL 12+ (recommended)
- **Container**: Docker 20.10+, Docker Compose 2.0+

## License

Dimensigon is licensed under GNU General Public License v3 or later (GPLv3+).

---

**Last Updated**: 2024-10-29
**Maintainer**: Joan Prat <joan.prat@dimensigon.com>
