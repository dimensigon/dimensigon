# Dimensigon

![Version](https://img.shields.io/badge/version-2.0.0-blue)
![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![License](https://img.shields.io/badge/license-GPLv3%2B-green)
![Status](https://img.shields.io/badge/status-development-yellow)

**Dimensigon (DM)** is a distributed server management and orchestration platform designed for elastic service bootstrapping. Built with Python, it provides a powerful mesh networking solution for managing complex, heterogeneous infrastructures.

## Key Features

- **Polyglot Orchestration** - Technology-agnostic automation and orchestration
- **Mesh Networking** - Decentralized peer-to-peer communication
- **IoT 2.0** - Advanced decentralization for IoT environments
- **Distributed Server Management** - High-complexity orchestrations across infrastructure
- **Full RESTful API** - Easily embeddable and integrable
- **Distributed Vault** - Secure configuration and secrets management
- **Log Federation** - Centralized logging across all nodes
- **Double Encryption** - SSL/TLS + message-level encryption by default
- **Granular ACLs** - Fine-grained access control on top of OS security

## Why Dimensigon?

Dimensigon serves as a coordination layer for all automation technologies, making it an ideal standard for companies managing complex environments:

- Lower administrative costs
- Simplified management of hybrid multi-cloud infrastructures
- Unified interface for heterogeneous systems
- No vendor lock-in

## 100% Open Source

**Dimensigon is REAL Open Source** - No Freemium or Enterprise versions will ever be available. This is a commitment to true open source values.

## Quick Links

- [Quick Start Guide](docs/guides/QUICK_START.md) - Get up and running in minutes
- [Documentation](docs/README.md) - Complete documentation
- [API Reference](docs/api/API_REFERENCE.md) - RESTful API documentation
- [Architecture](docs/api/ARCHITECTURE.md) - System design and architecture
- [Deployment Guide](docs/deployment/DEPLOYMENT_GUIDE.md) - Production deployment
- [Security](docs/security/README.md) - Security guidelines and best practices

## Documentation Structure

```
docs/
├── README.md                    # Documentation overview and navigation
├── guides/                      # User guides and tutorials
│   ├── QUICK_START.md          # Quick start guide
│   ├── DM_WEBMANAGER_README.md # Web interface guide
│   └── GUI_IMPLEMENTATION_SUMMARY.md
├── deployment/                  # Deployment documentation
│   ├── DEPLOYMENT_GUIDE.md     # Comprehensive deployment guide
│   ├── DOCKER_DEPLOYMENT.md    # Container deployment
│   └── ...
├── api/                         # API and architecture docs
│   ├── API_REFERENCE.md        # Complete API reference
│   └── ARCHITECTURE.md         # System architecture
├── security/                    # Security documentation
│   ├── SECURITY_CHECKLIST.md   # Security validation
│   ├── SECURITY_AUDIT_PREP.md  # Audit preparation
│   └── VULNERABILITY_FIXES.md  # Security patches
└── development/                 # Developer resources
    └── CODE_QUALITY_REPORT.md  # Code quality metrics
```

## Quick Start

### Installation

```bash
# Install from source
git clone https://github.com/dimensigon/dimensigon.git
cd dimensigon
pip install -r requirements.txt
pip install -e .

# Or install from PyPI (when available)
pip install dimensigon
```

### Getting Started (3 Simple Steps)

Dimensigon uses a "dimension" concept - think of it as your management realm where all servers coordinate.

#### Step 1: Create Your First Dimension

```bash
# Create a new dimension (your management cluster)
dimensigon new my-cluster

# You'll be prompted for a root password:
Password for root user: ********
Re-type same password: ********

# Output:
# New dimension created successfully
#
# ----- JOIN TOKEN (valid for 30 minutes) -----
# eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
# ---------------- END TOKEN --------------------
```

**What just happened?**
- Created a dimension named "my-cluster"
- Generated RSA keys and SSL certificates
- Set up root user credentials
- Generated a JOIN token (save this if you want to add more servers!)

#### Step 2: Start Dimensigon

```bash
# Start the server
dimensigon start

# Server will start on port 20194 (default)
# Press Ctrl+C to stop when needed
```

#### Step 3: Access the Web Interface

Open your browser to:
- **Dashboard**: https://localhost:20194/dm-webmanager/dashboard
- **Admin Panel**: https://localhost:20194/admin
- **API v2.0**: https://localhost:20194/api/v2/

**Default Credentials:**
- Username: `root`
- Password: (the one you set in Step 1)

**Note**: You'll see an SSL certificate warning - this is expected for development. Click "Advanced" → "Proceed" to continue.

### Adding More Servers to Your Cluster

```bash
# On Server 1 (the one you just created), generate a token:
dimensigon token my-cluster

# Copy the token, then on Server 2:
dimensigon join 192.168.1.100 <paste-token-here> --port 20194

# Your cluster now has 2 servers working together!
```

### Need Help?

- **Complete Tutorial**: [Getting Started Guide](docs/guides/GETTING_STARTED.md) - Hands-on beginner tutorial
- **Dimension Concepts**: [Dimension Lifecycle](docs/guides/DIMENSION_LIFECYCLE.md) - Understanding dimensions
- **Quick Reference**: [Quick Start Guide](docs/guides/QUICK_START.md) - Fast reference

## System Requirements

- **Python**: 3.8 or higher
- **Database**: PostgreSQL or SQLite
- **Operating System**: Linux (POSIX-compliant)
- **Network**: TCP/IP connectivity between nodes
- **SSL**: Certificates for production deployment

## Use Cases

### Multi-Cloud Management
Manage infrastructure across multiple cloud providers and on-premise systems from a unified interface.

### Distributed Orchestration
Execute complex workflows across distributed systems with dependency management and error handling.

### Configuration Management
Centralize configuration and secrets with distributed vault and secure access controls.

### Log Aggregation
Collect and search logs from all infrastructure components in one place.

### IoT Device Management
Manage and orchestrate large fleets of IoT devices with decentralized architecture.

## Architecture Highlights

- **Decentralized Design** - No single point of failure
- **Mesh Networking** - Direct peer-to-peer communication
- **Security First** - Double encryption and ACLs
- **Scalable** - Horizontal scaling through mesh expansion
- **Technology Agnostic** - Work with any technology stack

Learn more in the [Architecture Documentation](docs/api/ARCHITECTURE.md).

## Development

### Running Tests

```bash
# Install test dependencies
pip install -r requirements-test.txt

# Run tests
pytest

# Run with coverage
pytest --cov=dimensigon
```

### Code Quality

```bash
# Linting
pylint dimensigon/

# Code formatting
black dimensigon/

# Type checking
mypy dimensigon/
```

See [Development Documentation](docs/development/README.md) for more details.

## Contributing

We welcome contributions! Here's how you can help:

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Run code quality checks
5. Submit a pull request

Please ensure:
- Code follows PEP 8 style guidelines
- All tests pass
- Documentation is updated
- Commit messages are clear

## Security

Security is a top priority for Dimensigon. Please review:

- [Security Checklist](docs/security/SECURITY_CHECKLIST.md)
- [Security Audit Preparation](docs/security/SECURITY_AUDIT_PREP.md)
- [Vulnerability Fixes](docs/security/VULNERABILITY_FIXES.md)

For security vulnerabilities, please follow responsible disclosure practices.

## Historical Reports

The following reports document the evolution of Dimensigon 2.0:

- [DIMENSIGON_2.0_FINAL_REPORT.md](DIMENSIGON_2.0_FINAL_REPORT.md) - Final report for version 2.0
- [UPGRADE_REPORT.md](UPGRADE_REPORT.md) - Python and Flask upgrade report
- [HIVE_MIND_RESUMPTION_REPORT.md](HIVE_MIND_RESUMPTION_REPORT.md) - Hive Mind session resumption
- [PRE_MERGE_ANALYSIS.md](PRE_MERGE_ANALYSIS.md) - Pre-merge analysis report
- [MERGE_READINESS.md](MERGE_READINESS.md) - Merge readiness assessment
- [CHANGELOG.md](CHANGELOG.md) - Version history and changes

## License

Dimensigon is licensed under the GNU General Public License v3 or later (GPLv3+).

See [LICENSE](LICENSE) file for details.

## Support

- **Documentation**: [docs/](docs/)
- **GitHub Issues**: Report bugs and request features
- **Website**: store.dimensigon.com

## Authors

- Joan Prat - joan.prat@dimensigon.com
- Daniel Moya

## Acknowledgments

Dimensigon is built with and for the open source community. Thank you to all contributors and users.

---

**Remember**: Dimensigon is 100% Open Source - No Freemium, No Enterprise versions, Ever.
