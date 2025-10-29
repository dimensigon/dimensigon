# Dimensigon 2.0 - Quick Start Guide

## 🚀 Get Up and Running in Minutes

This quick start guide will help you install Dimensigon and create your first dimension in minutes.

---

## Prerequisites

- **Python**: 3.8 or higher
- **Operating System**: Linux (POSIX-compliant)
- **Network**: TCP/IP connectivity
- **Disk Space**: 100MB minimum

---

## Step 1: Installation

### Install from Source

```bash
# Clone the repository
git clone https://github.com/dimensigon/dimensigon.git
cd dimensigon

# Install dependencies and Dimensigon
pip install -r requirements.txt
pip install -e .
```

### Verify Installation

```bash
# Check that Dimensigon is installed
dimensigon --version

# Verify core imports work
python -c "from dimensigon.domain.entities import Server; print('✅ Dimensigon Ready!')"
```

**Expected output:**
```
dimensigon 2.0.0
✅ Dimensigon Ready!
```

---

## Step 2: Create Your First Dimension

### What is a Dimension?

A **dimension** is your management realm - a logical cluster of servers that work together. Think of it like a company where the dimension is the organization and servers are employees.

Before you can start Dimensigon, you need to either:
- **Create a new dimension** (if this is your first server), OR
- **Join an existing dimension** (if you're adding to a cluster)

### Create a New Dimension

```bash
# Create a dimension with a custom name
dimensigon new my-cluster

# OR let Dimensigon generate a cool name for you
dimensigon new
```

**You'll be prompted for a password:**
```
Password for root user: ********
Re-type same password: ********
```

**Output:**
```
New dimension created successfully

----- JOIN TOKEN (valid for 30 minutes) -----
eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpYXQiOjE2OTg3...
---------------- END TOKEN --------------------
```

### 📝 What Just Happened?

1. **Dimension Created**: A new dimension with your chosen name
2. **RSA Keys Generated**: Public/private keys for secure communication (4096-bit)
3. **SSL Certificates**: Self-signed certificates created (valid 10 years)
4. **Root User**: Administrator account with your password
5. **JOIN Token**: A 30-minute token to add more servers to this dimension

**Files Created:**
```
~/.dimensigon/
├── dimensigon.db          # SQLite database
└── ssl/
    ├── cert.pem          # SSL certificate
    └── key.pem           # SSL private key
```

**💡 Tip**: Save that JOIN token if you plan to add more servers! You can always generate a new one later with `dimensigon token my-cluster`.

---

## Step 3: Start Dimensigon

```bash
# Start the server
dimensigon start

# The server will start on port 20194 (default)
# You'll see output like:
# [2025-10-29 10:00:00] Starting Dimensigon...
# [2025-10-29 10:00:01] Server running on https://0.0.0.0:20194
```

**To run in the background:**
```bash
# Use screen
screen -S dimensigon
dimensigon start
# Press Ctrl+A then D to detach

# Or use nohup
nohup dimensigon start > dimensigon.log 2>&1 &
```

---

## Step 4: Access the Web Interface

### DM-WebManager Dashboard

Open your browser to: **https://localhost:20194/dm-webmanager/dashboard**

**Default Credentials:**
- Username: `root`
- Password: (the password you set when creating the dimension)

### 🔐 SSL Certificate Warning

You'll see a security warning because we're using self-signed certificates. This is **normal and expected** for development.

**To proceed:**
1. Click "Advanced" or "Show Details"
2. Click "Proceed to localhost (unsafe)" or "Accept the Risk"

### Available Interfaces

| Interface | URL | Purpose |
|-----------|-----|---------|
| **Dashboard** | https://localhost:20194/dm-webmanager/dashboard | Real-time metrics and monitoring |
| **Admin Panel** | https://localhost:20194/admin | CRUD operations for all entities |
| **API v1.0** | https://localhost:20194/api/v1.0/ | Legacy REST API |
| **API v2.0** | https://localhost:20194/api/v2/ | New REST API endpoints |

---

## Step 5: Explore the Dashboard

Once logged in, you'll see the **DM-WebManager Dashboard**:

### Dashboard Features:
- **Total Executions** (last 24 hours)
- **Currently Running** executions
- **Success/Failure** statistics
- **Top 5 Orchestrations** most executed
- **Recent Failures** with details

### Navigation Tabs:
1. **Dashboard** - Real-time metrics
2. **Orchestrations** - View and manage workflows
3. **Actions** - Browse action templates
4. **Executions** - Monitor execution history
5. **Data Dictionary** - Explore database schema

---

## Adding More Servers to Your Cluster

Want to expand your dimension to multiple servers? Follow these steps:

### On Your First Server (Already Running)

```bash
# Generate a new JOIN token
dimensigon token my-cluster

# Output:
# eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpYXQiOjE2OTg3...
```

**💡 Tip**: Tokens expire in 30 minutes. For longer validity, use `--expire-time`:
```bash
dimensigon token my-cluster --expire-time 120  # Valid for 2 hours
```

### On Your Second Server

```bash
# Install Dimensigon (same as Step 1)
pip install -e .

# Join the existing dimension
dimensigon join 192.168.1.100 <paste-token-here> --port 20194

# Replace 192.168.1.100 with your first server's IP
```

**Expected output:**
```
Joining to dimension...
Updating Catalog...
Catalog updated.
Joined to the dimension.
```

### Verify the Cluster

```bash
# Start the second server
dimensigon start

# On either server, check the web interface
# You should now see 2 servers in the cluster!
```

**Visual:**
```
┌─────────────────────────────────────┐
│     TWO-SERVER CLUSTER              │
├─────────────────────────────────────┤
│  Server A ◄──Mesh Network──► Server B
│  (Master)                   (Joined)│
└─────────────────────────────────────┘
```

---

## Common Commands Reference

### Dimension Management

```bash
# Create a new dimension
dimensigon new [name]

# Generate a JOIN token
dimensigon token <dimension-name>

# Join an existing dimension
dimensigon join <server-ip> <token> --port <port>

# Start the server
dimensigon start

# Start with custom port
dimensigon start --port 20194

# Start with debug mode
dimensigon start --debug
```

### Gate (Network Endpoint) Management

```bash
# List all gates for current server
dimensigon gate list

# Create a new gate
dimensigon gate create 192.168.1.100 20194

# Update port for all gates
dimensigon gate port 20194

# Delete a gate
dimensigon gate delete 192.168.1.100 20194
```

---

## Troubleshooting

### Error: "No dimension created"

**Problem**: You tried to run `dimensigon start` without creating a dimension first.

**Solution**:
```bash
# Create a dimension first
dimensigon new my-cluster

# Then start
dimensigon start
```

### Error: "Address already in use"

**Problem**: Port 20194 is already in use.

**Solution**:
```bash
# Use a different port
dimensigon start --port 20195
```

### Error: "Unable to contact to server"

**Problem**: Cannot reach the server during `join` operation.

**Solution**:
1. Check network connectivity: `ping <server-ip>`
2. Verify firewall allows port 20194: `telnet <server-ip> 20194`
3. Ensure the server is running: `ps aux | grep dimensigon`

### SSL Certificate Warnings

**Problem**: Browser shows security warnings.

**This is normal** for development with self-signed certificates. For production, use proper SSL certificates from a Certificate Authority (CA).

---

## Next Steps

### 🎓 Learn More

1. **[Getting Started Tutorial](GETTING_STARTED.md)** - Hands-on tutorial with practical examples
2. **[Dimension Lifecycle](DIMENSION_LIFECYCLE.md)** - Deep dive into dimensions, tokens, and clustering
3. **[DM-WebManager Guide](DM_WEBMANAGER_README.md)** - Complete GUI documentation

### 🚀 Build Something

1. **Create an Orchestration** - Define a multi-step workflow
2. **Deploy an Action** - Automate tasks across your cluster
3. **Set Up Monitoring** - Use the executions viewer
4. **Configure the Vault** - Store secrets securely

### 📚 Reference Documentation

- [API Reference](../api/API_REFERENCE.md) - Complete REST API docs
- [Architecture](../api/ARCHITECTURE.md) - System design deep-dive
- [Deployment Guide](../deployment/DEPLOYMENT_GUIDE.md) - Production deployment
- [Security Checklist](../security/SECURITY_CHECKLIST.md) - Security best practices

---

## Quick Reference Card

### Essential Commands

```bash
# Setup
dimensigon new <name>          # Create dimension
dimensigon start               # Start server

# Clustering
dimensigon token <name>        # Generate token
dimensigon join <ip> <token>   # Join cluster

# Management
dimensigon gate list           # List endpoints
dimensigon --version           # Check version
```

### Default Values

| Setting | Default Value | Environment Variable |
|---------|--------------|---------------------|
| Port | 20194 | `PORT` |
| Config Dir | `~/.dimensigon` | `DIMENSIGON_CONFIG` |
| Database | `~/.dimensigon/dimensigon.db` | - |
| SSL Cert | `~/.dimensigon/ssl/cert.pem` | - |
| SSL Key | `~/.dimensigon/ssl/key.pem` | - |

### Web Interfaces

| Interface | URL |
|-----------|-----|
| Dashboard | `https://localhost:20194/dm-webmanager/dashboard` |
| Admin | `https://localhost:20194/admin` |
| API v2 | `https://localhost:20194/api/v2/` |

---

## What's New in 2.0

### ✨ Major Features

- ✅ **DM-WebManager GUI** - Complete web administration interface
- ✅ **API v2.0** - 14 new REST endpoints for data-dictionary and executions
- ✅ **Security Fixes** - All critical vulnerabilities patched (RCE, CVEs)
- ✅ **Python 3.8+** - Supports Python 3.8 through 3.12
- ✅ **Modern Stack** - Flask 2.3+, SQLAlchemy 3.0+
- ✅ **Cyberpunk Theme** - Beautiful neon purple interface

### 🔒 Security Improvements

- **RCE Vulnerability**: Fixed pickle deserialization issue
- **CVE-2024-26130**: Updated cryptography (3.4.5 → 42.0.8)
- **CVE-2024-22195**: Updated jinja2 (2.11.3 → 3.1.4)
- **10+ CVEs Fixed**: All dependencies updated to secure versions

### 📊 Statistics

- **Files Changed**: 72
- **Lines Added**: 22,974+
- **Documentation**: 15,893 lines
- **Test Pass Rate**: 95.3%

---

## Support & Community

### Getting Help

- **Documentation**: Check the [docs/](../) directory
- **GitHub Issues**: Report bugs and request features
- **Examples**: See [GETTING_STARTED.md](GETTING_STARTED.md) for tutorials

### Contributing

We welcome contributions! Please:
1. Fork the repository
2. Create a feature branch
3. Add tests for your changes
4. Submit a pull request

---

## License

Dimensigon is licensed under **GNU General Public License v3 or later (GPLv3+)**.

**100% Open Source** - No Freemium or Enterprise versions, ever.

---

**Version**: 2.0.0
**Status**: Production Ready
**Updated**: October 29, 2025

🚀 **Happy orchestrating with Dimensigon!**
