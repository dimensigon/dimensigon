# Deployment Documentation

This directory contains all deployment-related documentation for Dimensigon.

## Contents

### Core Deployment Guides

- **[DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md)** - Comprehensive deployment guide covering all deployment scenarios and configurations
- **[DEPLOYMENT_README.md](./DEPLOYMENT_README.md)** - Deployment overview, prerequisites, and quick reference
- **[DEPLOYMENT_INDEX.md](./DEPLOYMENT_INDEX.md)** - Complete index of all deployment documentation

### Docker & Container Deployment

- **[DOCKER_DEPLOYMENT.md](./DOCKER_DEPLOYMENT.md)** - Docker-based deployment instructions and configurations
- **[DEPLOYMENT_TEST_RESULTS.md](./DEPLOYMENT_TEST_RESULTS.md)** - Results from deployment testing and validation

### Architecture & Decisions

- **[DEPLOYMENT_ADR.md](./DEPLOYMENT_ADR.md)** - Architecture Decision Records for deployment choices
- **[DEPLOYMENT_ARTIFACTS_SUMMARY.md](./DEPLOYMENT_ARTIFACTS_SUMMARY.md)** - Summary of deployment artifacts and their purposes

## Quick Start

For a quick deployment, follow these steps:

1. Review prerequisites in [DEPLOYMENT_README.md](./DEPLOYMENT_README.md)
2. Choose your deployment method:
   - Traditional: [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md)
   - Docker: [DOCKER_DEPLOYMENT.md](./DOCKER_DEPLOYMENT.md)
3. Validate deployment using [DEPLOYMENT_TEST_RESULTS.md](./DEPLOYMENT_TEST_RESULTS.md)

## Deployment Options

Dimensigon supports multiple deployment scenarios:

- **Standalone Server** - Single node deployment
- **Cluster Deployment** - Multi-node mesh network
- **Docker Container** - Containerized deployment
- **Docker Compose** - Multi-container orchestration
- **Production Deployment** - High-availability configurations

## Prerequisites

Before deploying Dimensigon, ensure you have:

- Python 3.8+
- PostgreSQL or SQLite
- SSL certificates (for production)
- Network connectivity between nodes
- Appropriate system permissions

## Support

For deployment issues or questions, refer to:
- Architecture decisions in [DEPLOYMENT_ADR.md](./DEPLOYMENT_ADR.md)
- Test results in [DEPLOYMENT_TEST_RESULTS.md](./DEPLOYMENT_TEST_RESULTS.md)
- Complete documentation index in [DEPLOYMENT_INDEX.md](./DEPLOYMENT_INDEX.md)
