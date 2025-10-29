# Dimension Lifecycle - Complete Guide

## Table of Contents

1. [What is a Dimension?](#what-is-a-dimension)
2. [Core Concepts](#core-concepts)
3. [Dimension Lifecycle Stages](#dimension-lifecycle-stages)
4. [Creating Your First Dimension](#creating-your-first-dimension)
5. [Understanding What Gets Created](#understanding-what-gets-created)
6. [Joining Additional Servers](#joining-additional-servers)
7. [Managing Dimensions](#managing-dimensions)
8. [Working with Gates](#working-with-gates)
9. [Troubleshooting](#troubleshooting)
10. [Best Practices](#best-practices)

---

## What is a Dimension?

A **Dimension** in Dimensigon is a logical cluster of servers that work together as a unified distributed system. Think of it as a "team" of servers that can coordinate, communicate, and orchestrate tasks across each other.

### The Analogy

Imagine you're organizing a company:
- **Dimension** = Your entire company
- **Servers** = Individual employees
- **Gates** = Contact information (phone numbers, email addresses)
- **Orchestrations** = Company-wide projects
- **Catalog** = Shared company knowledge base

Just as employees in a company need to know about each other and coordinate on projects, servers in a Dimension share information and execute distributed workflows together.

### Key Characteristics

A Dimension provides:
- **Identity**: A unique name and cryptographic identity
- **Security**: Built-in encryption keys and SSL certificates
- **Coordination**: Shared catalog of all servers and resources
- **Communication**: Mesh networking between all nodes
- **Orchestration**: Ability to run distributed workflows

---

## Core Concepts

### Server
A physical or virtual machine running Dimensigon. Each server has:
- A unique name (e.g., `web-server-01`, `db-master`)
- One or more **Gates** (network endpoints)
- Access to the shared Dimension catalog

### Gate
A network endpoint (IP:PORT or DNS:PORT) where a server can be reached. A server can have multiple gates:
- Public IP for external access
- Private IP for internal communication
- Localhost for local operations

### Catalog
A distributed database containing:
- All servers in the Dimension
- Orchestrations (workflow definitions)
- Action templates
- Routes between servers
- Configuration data

The catalog is automatically synchronized across all servers in the Dimension.

### Token
A time-limited authentication credential used to join new servers to a Dimension. Tokens:
- Expire after 15 minutes by default (configurable)
- Grant one-time join access
- Can be regenerated at any time

---

## Dimension Lifecycle Stages

```
┌─────────────────────────────────────────────────────────────┐
│                    DIMENSION LIFECYCLE                       │
└─────────────────────────────────────────────────────────────┘

1. NEW                    2. RUNNING                3. JOINED
┌─────────────┐          ┌─────────────┐          ┌─────────────┐
│   dimensigon │          │  dimensigon │          │  dimensigon │
│   new [name] │──────────▶  run        │          │   join ...  │
│             │   Create  │             │          │             │
└─────────────┘          └─────────────┘          └─────────────┘
      │                        │                         │
      │ Creates:               │ Starts:                 │ Receives:
      │ • Dimension            │ • Web server            │ • Dimension info
      │ • SSL certs            │ • API endpoints         │ • Catalog
      │ • Database             │ • GUI                   │ • SSL certs
      │ • Root user            │ • Mesh networking       │ • Routes
      │ • Join token           │                         │
      │                        │                         │
      ▼                        ▼                         ▼
[First Server]           [Operational]           [Cluster Member]
```

### Stage 1: NEW (Dimension Creation)
- **Command**: `dimensigon new [dimension-name]`
- **Who**: The first server in the cluster
- **Output**: Join token for other servers
- **Result**: A new Dimension with one server

### Stage 2: RUNNING (Server Started)
- **Command**: `dimensigon run` or just `dimensigon`
- **Who**: Any server with a Dimension
- **Result**: Server is operational and can handle requests

### Stage 3: JOINED (Additional Servers)
- **Command**: `dimensigon join <server> <token>`
- **Who**: New servers joining an existing Dimension
- **Result**: Server becomes part of the cluster

---

## Creating Your First Dimension

### Prerequisites

Before creating a Dimension, ensure:
- Dimensigon is installed (`pip install dimensigon`)
- You have a clean environment (no existing Dimension)
- You have network connectivity between servers (if clustering)

### Step 1: Create the Dimension

On your first server (let's call it `server-alpha`):

```bash
dimensigon new my-production-cluster
```

**What happens:**

```
$ dimensigon new my-production-cluster

Password for root user: ********
Re-type same password: ********

New dimension created successfully

----- JOIN TOKEN (valid for 15 minutes) -----
eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTYzOTU4MjQwMCwidHlwZSI6ImFjY2VzcyIsInN1YiI6IjEyMzQ1Njc4LTEyMzQtMTIzNC0xMjM0LTEyMzQ1Njc4OTBhYiIsIm5iZiI6MTYzOTU4MjQwMCwiZXhwIjoxNjM5NTgzMzAwLCJhcHBsaWNhbnQiOm51bGx9.abc123def456ghi789jkl012mno345pqr678stu901vwx234yz
---------------- END TOKEN --------------------
```

**What just happened?**

1. **Dimension Created**: A new dimension named `my-production-cluster` was created
2. **SSL Certificates Generated**: Self-signed certificates for HTTPS communication
3. **Database Initialized**: SQLite database with initial schema
4. **Root User Created**: Administrative user with the password you provided
5. **Join User Created**: System user for joining operations
6. **Token Generated**: A 15-minute token for joining other servers

### Step 2: Save the Token

**IMPORTANT**: Copy and save this token immediately. You'll need it to join other servers.

The token is valid for **15 minutes** by default. If it expires, you can generate a new one (see [Regenerating Tokens](#regenerating-tokens)).

### Step 3: Start the Server

```bash
dimensigon run
```

Or simply:

```bash
dimensigon
```

**Expected output:**

```
[2025-10-29 10:30:15] [INFO] Starting Dimensigon...
[2025-10-29 10:30:15] [INFO] Dimension: my-production-cluster
[2025-10-29 10:30:15] [INFO] Server: server-alpha
[2025-10-29 10:30:15] [INFO] Listening on https://0.0.0.0:20194
[2025-10-29 10:30:16] [INFO] Catalog manager started
[2025-10-29 10:30:16] [INFO] Route table manager started
[2025-10-29 10:30:16] [INFO] Dimensigon is ready!
```

### Step 4: Access the Web Interface

Open your browser to:
- **GUI Dashboard**: `https://<server-ip>:20194/dm-webmanager/dashboard`
- **Admin Panel**: `https://<server-ip>:20194/admin`
- **API**: `https://<server-ip>:20194/api/v1.0/`

**Login Credentials:**
- Username: `root`
- Password: The password you set during `dimensigon new`

**SSL Certificate Warning**: Since we're using self-signed certificates, your browser will show a security warning. This is expected. Click "Advanced" and proceed.

---

## Understanding What Gets Created

When you run `dimensigon new`, several important files and database entries are created:

### Directory Structure

```
~/.dimensigon/                    # Default config directory
├── dimensigon.db                 # SQLite database
├── dimensigon.log               # Server log file
├── access.log                   # HTTP access log
├── dimensigon.pid               # Process ID file
├── .ssl/                        # SSL certificates directory
│   ├── cert.pem                 # SSL certificate
│   └── key.pem                  # SSL private key
└── _gunicorn.conf.py           # Gunicorn configuration
```

**Note**: On Linux, the config directory is `~/.dimensigon`. The location can be changed with `--config-dir`.

### Database Contents

The SQLite database (`dimensigon.db`) contains:

#### 1. Dimension Record
```sql
-- L_dimension table
id              : <uuid>
name            : my-production-cluster
private         : <RSA private key>
public          : <RSA public key>
current         : true
created_at      : 2025-10-29 10:30:15.123456+00:00
```

#### 2. Server Record (Yourself)
```sql
-- D_server table
id              : <uuid>
name            : server-alpha (or your hostname)
me              : true
created_on      : 2025-10-29 10:30:15.123456+00:00
granules        : []
```

#### 3. Gate Record (Network Endpoint)
```sql
-- D_gate table
id              : <uuid>
server_id       : <server-uuid>
ip              : 192.168.1.100 (your IP)
port            : 20194
hidden          : false
```

#### 4. Users
```sql
-- User table
- root (admin user - the one you created)
- join (system user for join operations)
```

### SSL Certificates

Two files are created in `~/.dimensigon/.ssl/`:

**cert.pem** - SSL Certificate
```
Subject: CN=my-production-cluster, O=KnowTrade S.L.
Issuer: Self-signed
Valid: 10 years from creation
```

**key.pem** - Private Key
```
RSA 2048-bit private key
Permissions: 0600 (owner read/write only)
```

These certificates enable HTTPS communication between servers.

---

## Joining Additional Servers

Once you have a Dimension, you can add more servers to create a cluster.

### Prerequisites for Joining

1. **Token**: A valid join token from the first server
2. **Network Access**: The new server must reach the existing server
3. **Port Open**: TCP port 20194 (or custom port) must be accessible
4. **Clean Installation**: No existing Dimension on the joining server

### Join Process Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    JOIN PROCESS FLOW                         │
└─────────────────────────────────────────────────────────────┘

New Server                          Existing Server
(server-beta)                       (server-alpha)
     │                                     │
     │  1. Request public key              │
     │ ──────────────────────────────────▶ │
     │  GET /api/v1.0/join/public          │
     │                                     │
     │  2. Receive public key              │
     │ ◀────────────────────────────────── │
     │  (RSA public key)                   │
     │                                     │
     │  3. Send encrypted server info      │
     │ ──────────────────────────────────▶ │
     │  POST /api/v1.0/join                │
     │  (name, gates, metadata)            │
     │                                     │
     │  4. Receive dimension & catalog     │
     │ ◀────────────────────────────────── │
     │  (dimension info, SSL certs,        │
     │   entire catalog, routes)           │
     │                                     │
     │  5. Send acknowledgment             │
     │ ──────────────────────────────────▶ │
     │  POST /api/v1.0/join/acknowledge    │
     │                                     │
     │  6. Join complete                   │
     │ ◀────────────────────────────────── │
     ▼                                     ▼
```

### Example: Joining a Second Server

On your second server (`server-beta`):

```bash
dimensigon join server-alpha.example.com <token>
```

**With custom port:**
```bash
dimensigon join server-alpha.example.com <token> --port 20194
```

**With IP address:**
```bash
dimensigon join 192.168.1.100 <token>
```

**Without SSL (not recommended for production):**
```bash
dimensigon join server-alpha.example.com <token> --no-ssl
```

### Join Command Output

```
$ dimensigon join server-alpha.example.com eyJ0eXAiOiJKV1Qi...

[2025-10-29 10:35:20] [INFO] Joining to dimension...
[2025-10-29 10:35:21] [INFO] Updating Catalog...
[2025-10-29 10:35:23] [INFO] Catalog updated.
[2025-10-29 10:35:23] [INFO] Joined to the dimension.
```

**What just happened?**

1. **Authentication**: Token validated with server-alpha
2. **Key Exchange**: Encrypted communication established
3. **Server Registration**: server-beta added to the cluster
4. **Catalog Sync**: All cluster data downloaded to server-beta
5. **SSL Certs Copied**: Same certificates as server-alpha
6. **Route Created**: Direct route to server-alpha established

### Verify the Join

Start the newly joined server:

```bash
dimensigon run
```

Check the logs for:
```
[2025-10-29 10:36:15] [INFO] Dimension: my-production-cluster
[2025-10-29 10:36:15] [INFO] Server: server-beta
```

### Check Cluster Status

On any server in the cluster, you can verify all members:

**Via CLI** (requires dshell):
```bash
dimensigon-shell
> servers
```

**Via API**:
```bash
curl -u root:password https://server-alpha:20194/api/v1.0/servers
```

**Via GUI**:
Navigate to `https://server-alpha:20194/admin/server/`

---

## Managing Dimensions

### Regenerating Tokens

If your join token expires (after 15 minutes), generate a new one:

```bash
dimensigon token
```

**Specify dimension explicitly:**
```bash
dimensigon token my-production-cluster
```

**Custom expiration time (in minutes):**
```bash
dimensigon token --expire-time 60
```

**With applicant identifier:**
```bash
dimensigon token --applicant server-gamma
```

### Listing Current Dimension

To see which Dimension you're part of:

```bash
dimensigon run --help
```

Or check the database:
```bash
sqlite3 ~/.dimensigon/dimensigon.db "SELECT name, current FROM L_dimension;"
```

### Multiple Dimensions

**Important**: Dimensigon currently supports **one Dimension per installation**.

If you try to create a second Dimension, you'll see:
```
Error: Only one dimension can be created
```

To join a different Dimension:
1. Back up your current configuration
2. Remove `~/.dimensigon/`
3. Join the new Dimension

---

## Working with Gates

Gates are network endpoints where your server can be reached. A server can have multiple gates for different network scenarios.

### Understanding Gates

```
┌─────────────────────────────────────────────────────────┐
│                    SERVER WITH GATES                     │
├─────────────────────────────────────────────────────────┤
│  Server: web-server-01                                  │
│                                                         │
│  Gates:                                                 │
│  ┌───────────────────────────────────────────────┐     │
│  │ 1. Public: 203.0.113.45:20194                 │     │
│  │    (Internet access)                          │     │
│  ├───────────────────────────────────────────────┤     │
│  │ 2. Private: 10.0.1.10:20194                   │     │
│  │    (Internal network)                         │     │
│  ├───────────────────────────────────────────────┤     │
│  │ 3. Localhost: 127.0.0.1:20194                 │     │
│  │    (Local only)                               │     │
│  └───────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────┘
```

### Creating Gates

**Add a new gate:**
```bash
dimensigon gate create 203.0.113.45 20194
```

**Add with DNS:**
```bash
dimensigon gate create web-server-01.example.com 20194
```

**Add hidden gate** (not advertised to other servers):
```bash
dimensigon gate create 10.0.1.10 20194 --hidden
```

### Listing Gates

```bash
dimensigon gate list
```

**Output:**
```
203.0.113.45:20194
10.0.1.10:20194 (hidden)
web-server-01.example.com:20194
```

### Updating Gate Port

Change the port for all gates on current server:

```bash
dimensigon gate port 8443
```

### Deleting Gates

```bash
dimensigon gate delete 203.0.113.45 20194
```

**Delete by DNS:**
```bash
dimensigon gate delete web-server-01.example.com 20194
```

### When to Use Multiple Gates

Use multiple gates when:
- **Multi-homed server**: Server has multiple network interfaces
- **NAT/Firewall**: Different IPs for internal vs external access
- **Load balancing**: Multiple endpoints for redundancy
- **Security**: Hidden gates for administrative access

---

## Troubleshooting

### Common Issues and Solutions

#### 1. Token Expired

**Problem:**
```
[ERROR] Error on authentication: {'msg': 'Token has expired'}
```

**Solution:**
Generate a new token on the dimension server:
```bash
dimensigon token
```

#### 2. Connection Refused

**Problem:**
```
[ERROR] Unable to contact to server-alpha.
```

**Solutions:**
- Verify the server is running: `ps aux | grep dimensigon`
- Check the port is correct (default: 20194)
- Verify firewall allows TCP port 20194
- Ensure network connectivity: `telnet server-alpha 20194`
- Check if server is listening: `netstat -tulpn | grep 20194`

#### 3. SSL Certificate Errors

**Problem:**
```
[ERROR] SSL: CERTIFICATE_VERIFY_FAILED
```

**Solution:**
Use `--verify` flag to skip certificate verification (development only):
```bash
dimensigon join server-alpha <token> --verify
```

For production, use proper SSL certificates.

#### 4. Port Already in Use

**Problem:**
```
[ERROR] Address already in use: 0.0.0.0:20194
```

**Solutions:**
- Check if Dimensigon is already running: `ps aux | grep dimensigon`
- Kill existing process: `kill $(cat ~/.dimensigon/dimensigon.pid)`
- Use a different port: `dimensigon --port 8443`

#### 5. Permission Denied on Key File

**Problem:**
```
[ERROR] Permission denied: '~/.dimensigon/.ssl/key.pem'
```

**Solution:**
Fix permissions:
```bash
chmod 600 ~/.dimensigon/.ssl/key.pem
chmod 644 ~/.dimensigon/.ssl/cert.pem
```

#### 6. Database Locked

**Problem:**
```
[ERROR] database is locked
```

**Solutions:**
- Another Dimensigon process is running
- SQLite database is being accessed by another tool
- Check for `.dimensigon.db-journal` file and remove if stale

#### 7. No Dimension Created

**Problem:**
```
No dimension created. Create or join to a dimension
```

**Solution:**
You must first create a dimension:
```bash
dimensigon new my-cluster
```

Or join an existing one:
```bash
dimensigon join <server> <token>
```

### Debug Mode

For detailed logging, use debug mode:

```bash
dimensigon --debug
```

Or check log files:
```bash
tail -f ~/.dimensigon/dimensigon.log
tail -f ~/.dimensigon/access.log
```

### Getting Help

**Check version:**
```bash
dimensigon --version
```

**View help:**
```bash
dimensigon --help
dimensigon join --help
dimensigon new --help
```

---

## Best Practices

### 1. Dimension Naming

Choose meaningful names:
- ✅ `production-cluster`
- ✅ `staging-environment`
- ✅ `dev-mesh`
- ❌ `cluster1`
- ❌ `test`

### 2. Server Naming

Use descriptive server names:
- ✅ `web-prod-01`, `web-prod-02`
- ✅ `db-master`, `db-replica-01`
- ✅ `app-east-1a`, `app-west-2b`
- ❌ `server1`, `server2`

### 3. Token Management

- Generate tokens just before use
- Don't store tokens in scripts or version control
- Use `--expire-time` for extended maintenance windows
- Use `--applicant` to track which server used which token

### 4. Network Planning

- Use private networks for server-to-server communication
- Keep public gates for external access only
- Use `--hidden` for administrative gates
- Document your network topology

### 5. Security

- Always use SSL in production (`--no-ssl` is for testing only)
- Use proper SSL certificates (not self-signed) for production
- Rotate root password regularly
- Keep firewall rules restrictive
- Monitor access logs regularly

### 6. High Availability

For production clusters:
- Deploy at least 3 servers for quorum
- Distribute servers across availability zones
- Monitor catalog synchronization
- Set up backup and recovery procedures

### 7. Monitoring

Monitor key metrics:
- Server reachability
- Catalog synchronization status
- Route table health
- Orchestration execution logs
- Disk space in config directory

### 8. Configuration Management

- Use `--config-dir` to specify custom locations
- Keep config directories in backups
- Document custom ports and settings
- Use environment variables for automation:
  - `HTTP_HOST` - Bind address
  - `PORT` - Listen port
  - `FLASK_CONFIG` - Flask configuration

### 9. Lifecycle Management

**Development:**
```bash
dimensigon new dev-cluster
dimensigon --debug
```

**Staging:**
```bash
dimensigon new staging-cluster
dimensigon --port 20194 --threads 4
```

**Production:**
```bash
dimensigon new production-cluster
dimensigon --port 20194 --threads 8 \
  --access-logfile /var/log/dimensigon/access.log \
  --error-logfile /var/log/dimensigon/error.log \
  --cert-file /etc/ssl/dimensigon/cert.pem \
  --key-file /etc/ssl/dimensigon/key.pem
```

### 10. Backup and Recovery

**Backup these files:**
```bash
# Configuration and data
~/.dimensigon/dimensigon.db
~/.dimensigon/.ssl/

# Important logs
~/.dimensigon/dimensigon.log
```

**Recovery:**
```bash
# Stop Dimensigon
kill $(cat ~/.dimensigon/dimensigon.pid)

# Restore backup
cp backup/dimensigon.db ~/.dimensigon/
cp -r backup/.ssl ~/.dimensigon/

# Restart
dimensigon run
```

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────────────────┐
│              DIMENSIGON QUICK REFERENCE                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  CREATE DIMENSION     dimensigon new [name]                 │
│  START SERVER         dimensigon run                        │
│  JOIN CLUSTER         dimensigon join <server> <token>      │
│  GENERATE TOKEN       dimensigon token                      │
│                                                              │
│  CREATE GATE          dimensigon gate create <ip> [port]    │
│  LIST GATES           dimensigon gate list                  │
│  DELETE GATE          dimensigon gate delete <ip> [port]    │
│                                                              │
│  DEFAULT PORT         20194                                 │
│  CONFIG DIRECTORY     ~/.dimensigon                         │
│  WEB GUI              https://<server>:20194/dm-webmanager  │
│  ADMIN PANEL          https://<server>:20194/admin          │
│  API                  https://<server>:20194/api/v1.0/      │
│                                                              │
│  TOKEN VALIDITY       15 minutes (default)                  │
│  LOG FILE             ~/.dimensigon/dimensigon.log          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Next Steps

Now that you understand the Dimension lifecycle:

1. **Tutorial**: Follow the [Getting Started Guide](GETTING_STARTED.md) for a hands-on walkthrough
2. **Orchestration**: Learn to create and run distributed workflows
3. **Web GUI**: Explore the [DM-WebManager Guide](DM_WEBMANAGER_README.md)
4. **API**: Review the [API Reference](../api/API_REFERENCE.md)
5. **Production**: Read the [Deployment Guide](../deployment/DEPLOYMENT_GUIDE.md)

---

**Document Version**: 1.0.0
**Last Updated**: 2025-10-29
**Dimensigon Version**: 2.0.0+
