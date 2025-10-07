# Dimensigon 2.0 - Docker Deployment Guide

## Overview

This guide covers deploying Dimensigon 2.0 with DM-WebManager using Docker.

---

## Prerequisites

- Docker 20.10+ or Docker Desktop
- Docker Compose 2.0+ (optional, for orchestration)
- 2GB RAM minimum
- 10GB disk space

---

## Quick Start - Docker Compose (Recommended)

### 1. Deploy with Docker Compose

```bash
cd /home/claude/Dimensigon/dimensigon
docker-compose up -d
```

### 2. Verify Deployment

```bash
# Check container status
docker ps | grep dimensigon

# View logs
docker-compose logs -f

# Check health
docker inspect dimensigon-2.0 | grep -A 10 Health
```

### 3. Access DM-WebManager

- **Dashboard**: http://localhost:5000/dm-webmanager/dashboard
- **Admin Panel**: http://localhost:5000/admin
- **API v2**: http://localhost:5000/api/v2/data-dictionary/entities

---

## Manual Docker Build

### Build Production Image

```bash
cd /home/claude/Dimensigon/dimensigon

# Build image
docker build -f Dockerfile.production -t dimensigon:2.0 .

# Run container
docker run -d \
  --name dimensigon-2.0 \
  -p 5000:5000 \
  -e SECRET_KEY=your-secret-key-change-me \
  -e DATABASE_URL=sqlite:////app/data/dimensigon.db \
  -v dimensigon_data:/app/data \
  dimensigon:2.0
```

### Verify Container

```bash
# Check logs
docker logs -f dimensigon-2.0

# Test health endpoint
curl http://localhost:5000/

# Access shell
docker exec -it dimensigon-2.0 bash
```

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FLASK_ENV` | `production` | Flask environment mode |
| `SECRET_KEY` | Random | JWT secret key (CHANGE IN PRODUCTION!) |
| `DATABASE_URL` | `sqlite:///...` | Database connection string |
| `WORKERS` | `2` | Gunicorn worker processes |
| `TIMEOUT` | `120` | Request timeout (seconds) |

### Custom Configuration

Create `.env` file:

```bash
# .env
SECRET_KEY=your-very-long-random-secret-key
DATABASE_URL=postgresql://user:pass@db:5432/dimensigon
WORKERS=4
TIMEOUT=180
```

Use with Docker Compose:

```yaml
# docker-compose.yml
services:
  dimensigon:
    env_file: .env
    # ...
```

---

## Production Deployment

### PostgreSQL Backend

```yaml
version: '3.8'

services:
  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: dimensigon
      POSTGRES_USER: dimensigon
      POSTGRES_PASSWORD: secure_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  dimensigon:
    build:
      context: .
      dockerfile: Dockerfile.production
    depends_on:
      - db
    environment:
      - DATABASE_URL=postgresql://dimensigon:secure_password@db:5432/dimensigon
      - SECRET_KEY=${SECRET_KEY}
    ports:
      - "5000:5000"
    restart: unless-stopped

volumes:
  postgres_data:
```

### HTTPS with Nginx Reverse Proxy

```yaml
services:
  nginx:
    image: nginx:alpine
    ports:
      - "443:443"
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./certs:/etc/nginx/certs:ro
    depends_on:
      - dimensigon
    restart: unless-stopped

  dimensigon:
    # ... (same as above)
    expose:
      - "5000"
    # Remove ports mapping
```

**nginx.conf**:

```nginx
upstream dimensigon {
    server dimensigon:5000;
}

server {
    listen 443 ssl http2;
    server_name dimensigon.example.com;

    ssl_certificate /etc/nginx/certs/fullchain.pem;
    ssl_certificate_key /etc/nginx/certs/privkey.pem;

    location / {
        proxy_pass http://dimensigon;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 120s;
        proxy_read_timeout 120s;
    }
}
```

---

## Health Checks

### Docker Health Check (Built-in)

The production Dockerfile includes a health check:

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5000/', timeout=5)" || exit 1
```

### Manual Health Check

```bash
# Check if container is healthy
docker inspect --format='{{.State.Health.Status}}' dimensigon-2.0

# View health check logs
docker inspect --format='{{range .State.Health.Log}}{{.Output}}{{end}}' dimensigon-2.0
```

---

## Data Persistence

### Backup Database

```bash
# SQLite backup
docker exec dimensigon-2.0 sqlite3 /app/data/dimensigon.db ".backup /app/data/backup.db"
docker cp dimensigon-2.0:/app/data/backup.db ./dimensigon-backup-$(date +%Y%m%d).db

# PostgreSQL backup
docker exec postgres pg_dump -U dimensigon dimensigon > dimensigon-backup-$(date +%Y%m%d).sql
```

### Restore Database

```bash
# SQLite restore
docker cp ./dimensigon-backup.db dimensigon-2.0:/app/data/dimensigon.db
docker restart dimensigon-2.0

# PostgreSQL restore
cat dimensigon-backup.sql | docker exec -i postgres psql -U dimensigon dimensigon
```

---

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker logs dimensigon-2.0

# Common issues:
# 1. Port 5000 already in use
docker ps | grep 5000
lsof -i :5000

# 2. Database connection failed
# Verify DATABASE_URL is correct
docker exec dimensigon-2.0 env | grep DATABASE_URL

# 3. Permission issues
docker exec dimensigon-2.0 ls -la /app/data
```

### DM-WebManager Not Accessible

```bash
# 1. Verify Flask app is running
docker exec dimensigon-2.0 ps aux | grep gunicorn

# 2. Test from inside container
docker exec dimensigon-2.0 curl http://localhost:5000/admin/

# 3. Check firewall rules
sudo iptables -L -n | grep 5000
```

### Database Errors

```bash
# View SQLAlchemy errors
docker logs dimensigon-2.0 2>&1 | grep -i "sqlalchemy\|sqlite\|database"

# Initialize database (if needed)
docker exec dimensigon-2.0 flask --app "dimensigon.web:create_app('production')" db upgrade

# Check database file
docker exec dimensigon-2.0 sqlite3 /app/data/dimensigon.db ".tables"
```

### Performance Issues

```bash
# Check resource usage
docker stats dimensigon-2.0

# Increase workers (edit docker-compose.yml)
command: ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--timeout", "180", "dimensigon.web:create_app('production')"]

# Restart container
docker-compose restart
```

---

## Monitoring

### Logs

```bash
# Follow logs
docker-compose logs -f

# Filter by service
docker-compose logs -f dimensigon

# Last 100 lines
docker-compose logs --tail=100 dimensigon

# Since timestamp
docker-compose logs --since 2025-10-06T00:00:00Z
```

### Metrics

```bash
# Container stats
docker stats --no-stream dimensigon-2.0

# Disk usage
docker system df
docker volume ls
docker volume inspect dimensigon_dimensigon_data

# Network
docker network inspect dimensigon_default
```

---

## Scaling

### Horizontal Scaling (Multiple Containers)

```yaml
services:
  dimensigon:
    # ...
    deploy:
      replicas: 3

  load_balancer:
    image: nginx:alpine
    ports:
      - "5000:80"
    volumes:
      - ./nginx-lb.conf:/etc/nginx/nginx.conf:ro
```

### Vertical Scaling (Resource Limits)

```yaml
services:
  dimensigon:
    # ...
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 512M
```

---

## Security Best Practices

### 1. Change Default Secret Key

```bash
# Generate secure secret key
python3 -c "import secrets; print(secrets.token_hex(32))"

# Set in .env file
echo "SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))')" >> .env
```

### 2. Use Non-Root User

The production Dockerfile already uses a non-root user (`dimensigon:1000`).

### 3. Network Isolation

```yaml
services:
  dimensigon:
    networks:
      - backend

  nginx:
    networks:
      - frontend
      - backend

networks:
  frontend:
    driver: bridge
  backend:
    driver: bridge
    internal: true  # No external access
```

### 4. Read-Only Filesystem

```yaml
services:
  dimensigon:
    read_only: true
    tmpfs:
      - /tmp
      - /app/.cache
```

---

## Uninstall

```bash
# Stop and remove containers
docker-compose down

# Remove volumes (WARNING: deletes all data)
docker-compose down -v

# Remove images
docker rmi dimensigon:2.0

# Clean up all Docker resources
docker system prune -a --volumes
```

---

## Testing Deployment

### Automated Test Suite

```bash
# Run deployment tests (requires Python 3.9+)
python test_deployment.py
```

### Manual Testing

```bash
# 1. Test server is running
curl http://localhost:5000/

# 2. Test DM-WebManager dashboard
curl http://localhost:5000/dm-webmanager/dashboard

# 3. Test API v2.0 endpoints
curl http://localhost:5000/api/v2/data-dictionary/entities

# 4. Test Flask-Admin
curl http://localhost:5000/admin/

# 5. Check health
curl http://localhost:5000/health
```

---

## Additional Resources

- **Quick Start Guide**: `QUICK_START.md`
- **DM-WebManager User Guide**: `DM_WEBMANAGER_README.md`
- **Upgrade Report**: `UPGRADE_REPORT.md`
- **Final Report**: `DIMENSIGON_2.0_FINAL_REPORT.md`

---

## Support

For issues or questions:

1. Check logs: `docker-compose logs -f`
2. Review troubleshooting section above
3. Consult documentation files
4. Check GitHub issues (if available)

---

**Version**: 2.0.0
**Last Updated**: 2025-10-06
**Status**: Production Ready ✅
