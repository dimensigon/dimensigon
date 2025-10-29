# Dimensigon 2.0 - Deployment Artifacts Index

## Quick Navigation

This index provides direct links to all deployment artifacts and their primary use cases.

---

## 🚀 Quick Start Guides

1. **First-time Docker deployment**: [DEPLOYMENT_README.md](/home/claude/dimensigon/DEPLOYMENT_README.md#quick-start)
2. **Production planning**: [DEPLOYMENT_GUIDE.md](/home/claude/dimensigon/DEPLOYMENT_GUIDE.md)
3. **Architecture understanding**: [DEPLOYMENT_ADR.md](/home/claude/dimensigon/DEPLOYMENT_ADR.md)

---

## 📚 Documentation (4 files, 75KB)

### Primary Documentation

| File | Size | Purpose | When to Use |
|------|------|---------|-------------|
| [DEPLOYMENT_GUIDE.md](/home/claude/dimensigon/DEPLOYMENT_GUIDE.md) | 28KB | Comprehensive deployment guide | Production deployment planning |
| [DEPLOYMENT_README.md](/home/claude/dimensigon/DEPLOYMENT_README.md) | 11KB | Quick reference | Fast deployment, overview |
| [DEPLOYMENT_ADR.md](/home/claude/dimensigon/DEPLOYMENT_ADR.md) | 18KB | Architecture decisions | Understanding design choices |
| [DEPLOYMENT_ARTIFACTS_SUMMARY.md](/home/claude/dimensigon/DEPLOYMENT_ARTIFACTS_SUMMARY.md) | 18KB | Complete artifacts summary | Artifact reference |

---

## 🐳 Docker Deployment (3 files, 15KB)

| File | Size | Purpose | When to Use |
|------|------|---------|-------------|
| [docker-compose.production.yml](/home/claude/dimensigon/docker-compose.production.yml) | 6KB | Production Docker Compose | Multi-container deployment |
| [Dockerfile](/home/claude/dimensigon/Dockerfile) | 4.7KB | Multi-stage container build | Building production images |
| [docker-entrypoint.sh](/home/claude/dimensigon/docker-entrypoint.sh) | 4.8KB | Container initialization | Automatic container setup |

---

## ⚙️ Configuration (3 files, 17KB)

| File | Size | Purpose | When to Use |
|------|------|---------|-------------|
| [.env.example](/home/claude/dimensigon/.env.example) | 8KB | Environment variables template | Initial configuration |
| [logconfig.yaml](/home/claude/dimensigon/logconfig.yaml) | 7.8KB | Python logging configuration | Custom logging setup |
| [init-db.sql](/home/claude/dimensigon/init-db.sql) | 1.6KB | Database initialization | PostgreSQL first-time setup |

---

## 🖥️ Traditional Linux (1 file, 7KB)

| File | Size | Purpose | When to Use |
|------|------|---------|-------------|
| [dimensigon.service](/home/claude/dimensigon/dimensigon.service) | 7KB | Systemd service unit | Non-Docker deployment |

---

## 🌐 Nginx Configuration (2 files, 9KB)

| File | Size | Purpose | When to Use |
|------|------|---------|-------------|
| [nginx/nginx.conf](/home/claude/dimensigon/nginx/nginx.conf) | 3.1KB | Main Nginx configuration | Reverse proxy setup |
| [nginx/conf.d/dimensigon.conf](/home/claude/dimensigon/nginx/conf.d/dimensigon.conf) | 5.9KB | Dimensigon virtual host | SSL termination, load balancing |

---

## 🔧 Automation (1 file, 8.5KB)

| File | Size | Purpose | When to Use |
|------|------|---------|-------------|
| [deploy.sh](/home/claude/dimensigon/deploy.sh) | 8.5KB | Automated deployment script | Quick automated setup |

---

## 📋 Use Case Index

### I want to...

#### Deploy for the first time
1. Read: [DEPLOYMENT_README.md - Quick Start](/home/claude/dimensigon/DEPLOYMENT_README.md#quick-start)
2. Run: `./deploy.sh`
3. Reference: [DEPLOYMENT_GUIDE.md](/home/claude/dimensigon/DEPLOYMENT_GUIDE.md)

#### Deploy to production with Docker
1. Read: [DEPLOYMENT_GUIDE.md - Docker Deployment](/home/claude/dimensigon/DEPLOYMENT_GUIDE.md#docker-deployment-recommended)
2. Copy: `.env.example` → `.env`
3. Deploy: `docker-compose -f docker-compose.production.yml up -d`
4. Initialize: `docker-compose exec dimensigon dimensigon new cluster-name`

#### Deploy to traditional Linux
1. Read: [DEPLOYMENT_GUIDE.md - Traditional Linux](/home/claude/dimensigon/DEPLOYMENT_GUIDE.md#traditional-linux-deployment)
2. Install: Python, PostgreSQL, dependencies
3. Configure: `dimensigon.service`
4. Start: `sudo systemctl start dimensigon`

#### Configure Nginx reverse proxy
1. Read: [DEPLOYMENT_GUIDE.md - Nginx Configuration](/home/claude/dimensigon/DEPLOYMENT_GUIDE.md#step-8-configure-nginx-reverse-proxy)
2. Copy: `nginx/nginx.conf` → `/etc/nginx/`
3. Copy: `nginx/conf.d/dimensigon.conf` → `/etc/nginx/conf.d/`
4. Reload: `sudo systemctl reload nginx`

#### Set up monitoring and logging
1. Configure: [logconfig.yaml](/home/claude/dimensigon/logconfig.yaml)
2. Read: [DEPLOYMENT_GUIDE.md - Monitoring](/home/claude/dimensigon/DEPLOYMENT_GUIDE.md#monitoring-and-logging)
3. Set up log rotation
4. Configure health checks

#### Create a multi-node cluster
1. Read: [DEPLOYMENT_GUIDE.md - Multi-Node](/home/claude/dimensigon/DEPLOYMENT_GUIDE.md#multi-node-cluster-deployment)
2. Deploy master node
3. Generate join token
4. Deploy and join additional nodes

#### Troubleshoot deployment issues
1. Check: [DEPLOYMENT_GUIDE.md - Troubleshooting](/home/claude/dimensigon/DEPLOYMENT_GUIDE.md#troubleshooting)
2. Review logs: `docker-compose logs` or `journalctl -u dimensigon`
3. Verify configuration: `.env` and service files

#### Understand architecture decisions
1. Read: [DEPLOYMENT_ADR.md](/home/claude/dimensigon/DEPLOYMENT_ADR.md)
2. Review: Architecture diagrams
3. Understand: Trade-offs and rationale

#### Configure SSL certificates
1. Generate: Self-signed (development) or obtain CA-signed (production)
2. Read: [DEPLOYMENT_GUIDE.md - SSL/TLS](/home/claude/dimensigon/DEPLOYMENT_GUIDE.md#ssltls-configuration)
3. Place: `ssl/cert.pem` and `ssl/key.pem`
4. Configure: Environment variables

#### Set up backups
1. Read: [DEPLOYMENT_GUIDE.md - Backup](/home/claude/dimensigon/DEPLOYMENT_GUIDE.md#backup-and-recovery)
2. Create: Backup script (example provided)
3. Schedule: Cron job for automated backups
4. Test: Recovery procedure

#### Optimize performance
1. Read: [DEPLOYMENT_GUIDE.md - Performance Tuning](/home/claude/dimensigon/DEPLOYMENT_GUIDE.md#performance-tuning)
2. Adjust: Worker count based on CPU
3. Tune: Database settings
4. Configure: Caching (Redis)

#### Harden security
1. Read: [DEPLOYMENT_GUIDE.md - Security](/home/claude/dimensigon/DEPLOYMENT_GUIDE.md#security-hardening)
2. Review: [DEPLOYMENT_ADR.md - Security](/home/claude/dimensigon/DEPLOYMENT_ADR.md#security)
3. Configure: Firewall, SSL, secrets
4. Apply: Security best practices

---

## 📊 File Statistics

| Category | Files | Total Size | Lines |
|----------|-------|-----------|-------|
| Documentation | 4 | 75KB | ~2,500 |
| Docker | 3 | 15KB | ~300 |
| Configuration | 3 | 17KB | ~400 |
| Linux | 1 | 7KB | ~250 |
| Nginx | 2 | 9KB | ~250 |
| Automation | 1 | 8.5KB | ~250 |
| **TOTAL** | **14** | **~132KB** | **~4,000** |

---

## 🎯 Deployment Scenarios

### Scenario 1: Quick Development Setup
**Time**: 5 minutes
```bash
./deploy.sh
```
**Files Used**: All Docker files + automation

### Scenario 2: Single-Node Production
**Time**: 15-30 minutes
**Files Used**: 
- docker-compose.production.yml
- .env.example → .env
- SSL certificates
- nginx/* (optional)

**Steps**:
1. Configure .env
2. Generate/provide SSL certificates
3. `docker-compose -f docker-compose.production.yml up -d`
4. Initialize dimension

### Scenario 3: Multi-Node Cluster
**Time**: 1-2 hours
**Files Used**: Same as Scenario 2, per node

**Steps**:
1. Deploy master node (Scenario 2)
2. Generate join token
3. Deploy additional nodes
4. Join nodes to cluster

### Scenario 4: Traditional Linux with Systemd
**Time**: 30-60 minutes
**Files Used**:
- dimensigon.service
- .env.example → /etc/dimensigon/dimensigon.conf
- logconfig.yaml

**Steps**:
1. Install dependencies
2. Install Python packages
3. Configure systemd service
4. Start and enable service

### Scenario 5: High Availability Production
**Time**: 2-4 hours
**Files Used**: All files

**Steps**:
1. Deploy multiple Dimensigon nodes
2. Configure PostgreSQL replication
3. Set up Redis cluster
4. Configure Nginx load balancer
5. Set up monitoring and backups

---

## 📖 Reading Order Recommendations

### For Developers
1. [DEPLOYMENT_README.md](/home/claude/dimensigon/DEPLOYMENT_README.md) - Overview
2. `docker-compose.production.yml` - Service structure
3. `Dockerfile` - Build process
4. `.env.example` - Configuration options

### For Operations Teams
1. [DEPLOYMENT_GUIDE.md](/home/claude/dimensigon/DEPLOYMENT_GUIDE.md) - Full guide
2. [DEPLOYMENT_ADR.md](/home/claude/dimensigon/DEPLOYMENT_ADR.md) - Architecture
3. `dimensigon.service` - Systemd setup
4. `nginx/*` - Reverse proxy configuration

### For Security Teams
1. [DEPLOYMENT_ADR.md - Security](/home/claude/dimensigon/DEPLOYMENT_ADR.md#security)
2. [DEPLOYMENT_GUIDE.md - Security](/home/claude/dimensigon/DEPLOYMENT_GUIDE.md#security-hardening)
3. `.env.example` - Secrets management
4. `Dockerfile` - Container security

### For Architects
1. [DEPLOYMENT_ADR.md](/home/claude/dimensigon/DEPLOYMENT_ADR.md) - All decisions
2. [DEPLOYMENT_GUIDE.md - Architecture](/home/claude/dimensigon/DEPLOYMENT_GUIDE.md#deployment-methods)
3. [DEPLOYMENT_ARTIFACTS_SUMMARY.md](/home/claude/dimensigon/DEPLOYMENT_ARTIFACTS_SUMMARY.md) - Overview

---

## 🔍 Quick Reference Commands

### Docker Commands
```bash
# Deploy production
docker-compose -f docker-compose.production.yml up -d

# View logs
docker-compose -f docker-compose.production.yml logs -f dimensigon

# Execute commands
docker-compose exec dimensigon dimensigon <command>

# Stop services
docker-compose -f docker-compose.production.yml down

# Rebuild
docker-compose -f docker-compose.production.yml build --no-cache
```

### Systemd Commands
```bash
# Start service
sudo systemctl start dimensigon

# Check status
sudo systemctl status dimensigon

# View logs
sudo journalctl -u dimensigon -f

# Restart
sudo systemctl restart dimensigon
```

### Health Checks
```bash
# Application health
curl -k https://localhost:20194/health

# Container health
docker-compose ps

# Service status
systemctl status dimensigon
```

### Backup Commands
```bash
# Backup database (Docker)
docker-compose exec postgres pg_dump -U dimensigon dimensigon | gzip > backup.sql.gz

# Backup configuration
tar -czf config-backup.tar.gz .dimensigon/

# List backups
ls -lh *.sql.gz
```

---

## ✅ Deployment Checklist

- [ ] Read [DEPLOYMENT_README.md](/home/claude/dimensigon/DEPLOYMENT_README.md)
- [ ] Choose deployment method (Docker or Traditional)
- [ ] Review system requirements
- [ ] Prepare environment (.env or systemd config)
- [ ] Generate/obtain SSL certificates
- [ ] Create data directories
- [ ] Deploy services
- [ ] Initialize dimension or join cluster
- [ ] Verify health checks
- [ ] Configure monitoring
- [ ] Set up backups
- [ ] Test failover (production)
- [ ] Document environment-specific settings

---

## 🆘 Support Resources

- **Documentation**: All .md files in this directory
- **Issues**: https://github.com/dimensigon/dimensigon/issues
- **Source**: https://github.com/dimensigon/dimensigon
- **Email**: joan.prat@dimensigon.com

---

## 📝 Version Information

- **Dimensigon Version**: 2.0.0
- **Deployment Artifacts Version**: 1.0.0
- **Last Updated**: 2024-10-29
- **Maintainer**: Joan Prat <joan.prat@dimensigon.com>

---

**License**: GNU General Public License v3 or later (GPLv3+)
