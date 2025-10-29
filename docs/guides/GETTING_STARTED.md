# Getting Started with Dimensigon

Welcome to Dimensigon! This beginner-friendly tutorial will take you from zero to running a multi-node Dimensigon cluster in about 30 minutes.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Tutorial 1: Single Server Setup](#tutorial-1-single-server-setup)
4. [Tutorial 2: Two-Server Cluster](#tutorial-2-two-server-cluster)
5. [Tutorial 3: Three-Server Production Cluster](#tutorial-3-three-server-production-cluster)
6. [Your First Orchestration](#your-first-orchestration)
7. [Common Errors and Fixes](#common-errors-and-fixes)
8. [Next Steps](#next-steps)

---

## Prerequisites

### System Requirements

- **Operating System**: Linux (Ubuntu 20.04+, CentOS 8+, RHEL 8+, Debian 10+)
- **Python**: 3.8 or higher (Python 3.9-3.12 recommended)
- **Memory**: Minimum 512 MB RAM (2 GB+ recommended)
- **Disk**: 1 GB free space
- **Network**: TCP connectivity on port 20194

### Check Your Python Version

```bash
python3 --version
```

Expected output:
```
Python 3.9.21
```

If your Python version is below 3.8, you'll need to upgrade.

### Install Python 3.9+ (if needed)

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install python3.9 python3.9-venv python3.9-dev
```

**CentOS/RHEL:**
```bash
sudo yum install python39 python39-devel
```

---

## Installation

### Option 1: Install from Source (Recommended for Development)

```bash
# Clone the repository
git clone https://github.com/dimensigon/dimensigon.git
cd dimensigon

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Linux/Mac
# venv\Scripts\activate   # On Windows

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Install Dimensigon in development mode
pip install -e .
```

### Option 2: Install from PyPI (When Available)

```bash
pip install dimensigon
```

### Verify Installation

```bash
dimensigon --version
```

Expected output:
```
dimensigon 2.0.0
```

### Test the Installation

```bash
python3 -c "from dimensigon.domain.entities import Server; print('✅ Dimensigon is ready!')"
```

If you see `✅ Dimensigon is ready!`, you're all set!

---

## Tutorial 1: Single Server Setup

This tutorial creates a single-node Dimensigon instance - perfect for development and testing.

### What You'll Learn
- Creating a Dimension
- Starting the server
- Accessing the web GUI
- Basic navigation

### Step 1: Create Your First Dimension

```bash
dimensigon new my-first-dimension
```

**You'll be prompted for a password:**
```
Password for root user: ********
Re-type same password: ********
```

**Choose a strong password** - you'll use this to access the web interface and API.

### Expected Output

```
New dimension created successfully

----- JOIN TOKEN (valid for 15 minutes) -----
eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTYzOTU4MjQwMCwidHlwZSI6ImFjY2VzcyIsInN1YiI6IjEyMzQ1Njc4LTEyMzQtMTIzNC0xMjM0LTEyMzQ1Njc4OTBhYiIsIm5iZiI6MTYzOTU4MjQwMCwiZXhwIjoxNjM5NTgzMzAwLCJhcHBsaWNhbnQiOm51bGx9.abc123def456ghi789jkl012mno345pqr678stu901vwx234yz
---------------- END TOKEN --------------------
```

### What Just Happened?

Let's look at what was created:

```bash
ls -la ~/.dimensigon/
```

**Output:**
```
drwxr-xr-x  4 user user  4096 Oct 29 10:30 .
drwxr-xr-x 25 user user  4096 Oct 29 10:30 ..
-rw-r--r--  1 user user 65536 Oct 29 10:30 dimensigon.db
-rw-r--r--  1 user user     0 Oct 29 10:30 access.log
-rw-r--r--  1 user user  1024 Oct 29 10:30 dimensigon.log
drwx------  2 user user  4096 Oct 29 10:30 .ssl
```

**Files created:**
- `dimensigon.db` - SQLite database with your Dimension data
- `.ssl/cert.pem` - SSL certificate (self-signed, 10-year validity)
- `.ssl/key.pem` - SSL private key (permissions: 0600)
- `dimensigon.log` - Server logs
- `access.log` - HTTP access logs

### Step 2: Start the Server

```bash
dimensigon run
```

Or simply:
```bash
dimensigon
```

### Expected Output

```
[2025-10-29 10:30:15 +0000] [12345] [INFO] Starting gunicorn 20.1.0
[2025-10-29 10:30:15 +0000] [12345] [INFO] Listening at: https://0.0.0.0:20194 (12345)
[2025-10-29 10:30:15 +0000] [12345] [INFO] Using worker: sync
[2025-10-29 10:30:15 +0000] [12346] [INFO] Booting worker with pid: 12346
[2025-10-29 10:30:16 +0000] [INFO] Dimension: my-first-dimension
[2025-10-29 10:30:16 +0000] [INFO] Server: my-hostname
[2025-10-29 10:30:16 +0000] [INFO] Catalog manager started
[2025-10-29 10:30:16 +0000] [INFO] Route table manager started
[2025-10-29 10:30:16 +0000] [INFO] Dimensigon is ready!
```

**The server is now running!** Keep this terminal open.

### Step 3: Access the Web Interface

Open a new terminal or browser and navigate to:

**Dashboard:**
```
https://localhost:20194/dm-webmanager/dashboard
```

**Admin Panel:**
```
https://localhost:20194/admin
```

**API:**
```
https://localhost:20194/api/v1.0/
```

### SSL Certificate Warning

You'll see a browser warning about the SSL certificate:

```
⚠️ Your connection is not private
Attackers might be trying to steal your information...
```

**This is expected!** We're using a self-signed certificate.

**Click "Advanced" → "Proceed to localhost (unsafe)"**

For production, use proper SSL certificates.

### Step 4: Log In

**Login Page:**
- Username: `root`
- Password: (the password you set earlier)

### Step 5: Explore the Dashboard

You should see:

```
┌─────────────────────────────────────────────────────────────┐
│                  DM-WEBMANAGER DASHBOARD                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Dimension: my-first-dimension                              │
│  Servers: 1                                                 │
│  Orchestrations: 0                                          │
│  Recent Executions: 0                                       │
│                                                              │
│  [View Servers] [View Orchestrations] [View Executions]    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Step 6: View Your Server

Navigate to: **Admin Panel → Servers**

You'll see your server:
- **Name**: Your hostname (e.g., `my-hostname`)
- **Gates**: Your IP addresses and ports
- **Status**: Online

### 🎉 Congratulations!

You've successfully:
- ✅ Created your first Dimension
- ✅ Started the Dimensigon server
- ✅ Accessed the web interface
- ✅ Logged in as root user

---

## Tutorial 2: Two-Server Cluster

Now let's create a real cluster with two servers communicating over the network.

### What You'll Learn
- Joining a server to an existing Dimension
- Managing join tokens
- Verifying cluster connectivity

### Scenario

We have:
- **Server A** (alpha): `192.168.1.100` - Already running (from Tutorial 1)
- **Server B** (beta): `192.168.1.101` - Will join the cluster

### Prerequisites

- Tutorial 1 completed (Server A running)
- Server B has Dimensigon installed
- Network connectivity between servers
- Port 20194 open on both servers

### Test Network Connectivity

From Server B, test connectivity to Server A:

```bash
telnet 192.168.1.100 20194
```

**Expected output:**
```
Trying 192.168.1.100...
Connected to 192.168.1.100.
```

Press `Ctrl+]` then type `quit` to exit.

### Step 1: Generate a Join Token (on Server A)

On **Server A** (the existing server), generate a join token:

```bash
dimensigon token
```

**Output:**
```
eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTYzOTU4NDEwMCwidHlwZSI6ImFjY2VzcyIsInN1YiI6IjEyMzQ1Njc4LTEyMzQtMTIzNC0xMjM0LTEyMzQ1Njc4OTBhYiIsIm5iZiI6MTYzOTU4NDEwMCwiZXhwIjoxNjM5NTg1MDAwfQ.xyz789abc123def456ghi789jkl012mno345pqr678stu901
```

**Copy this token** - you'll use it on Server B.

**Token expires in 15 minutes**, so proceed quickly!

### Step 2: Join the Cluster (on Server B)

On **Server B**, join the cluster:

```bash
dimensigon join 192.168.1.100 eyJ0eXAiOiJKV1Qi...
```

**Full example:**
```bash
dimensigon join 192.168.1.100 eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTYzOTU4NDEwMCwidHlwZSI6ImFjY2VzcyIsInN1YiI6IjEyMzQ1Njc4LTEyMzQtMTIzNC0xMjM0LTEyMzQ1Njc4OTBhYiIsIm5iZiI6MTYzOTU4NDEwMCwiZXhwIjoxNjM5NTg1MDAwfQ.xyz789abc123def456ghi789jkl012mno345pqr678stu901
```

### Expected Output

```
[2025-10-29 10:35:20] [INFO] Joining to dimension...
[2025-10-29 10:35:21] [INFO] Updating Catalog...
[2025-10-29 10:35:22] [INFO] Catalog updated.
[2025-10-29 10:35:22] [INFO] Joined to the dimension.
```

### What Just Happened?

1. **Authentication**: Server B authenticated with Server A using the token
2. **Data Transfer**: Server B received:
   - Dimension information
   - SSL certificates
   - Complete catalog (all servers, orchestrations, etc.)
   - Route information
3. **Registration**: Server B is now registered in the cluster
4. **Synchronization**: Both servers now know about each other

### Step 3: Start Server B

```bash
dimensigon run
```

**Expected output:**
```
[2025-10-29 10:36:15 +0000] [INFO] Dimension: my-first-dimension
[2025-10-29 10:36:15 +0000] [INFO] Server: beta-hostname
[2025-10-29 10:36:16 +0000] [INFO] Dimensigon is ready!
```

**Notice:** Server B shows the same Dimension name!

### Step 4: Verify the Cluster

**On Server A**, check the web interface:

Navigate to: `https://192.168.1.100:20194/admin/server/`

You should see **two servers**:
1. Server A (alpha-hostname)
2. Server B (beta-hostname)

**Via API** (from any machine):
```bash
curl -u root:password https://192.168.1.100:20194/api/v1.0/servers
```

**Output:**
```json
[
  {
    "id": "12345678-1234-1234-1234-123456789abc",
    "name": "alpha-hostname",
    "gates": [
      {"ip": "192.168.1.100", "port": 20194}
    ]
  },
  {
    "id": "87654321-4321-4321-4321-cba987654321",
    "name": "beta-hostname",
    "gates": [
      {"ip": "192.168.1.101", "port": 20194}
    ]
  }
]
```

### Step 5: Test Communication

**From Server B**, check catalog synchronization:

```bash
tail -f ~/.dimensigon/dimensigon.log
```

Look for:
```
[INFO] Catalog sync: received update from alpha-hostname
[INFO] Route table updated: direct route to alpha-hostname
```

### Cluster Visualization

Your cluster now looks like this:

```
┌─────────────────────────────────────────────────────────────┐
│                  TWO-SERVER CLUSTER                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   Server A (alpha)              Server B (beta)             │
│   192.168.1.100:20194          192.168.1.101:20194         │
│         │                              │                    │
│         │◄─────── Catalog ──────────►│                    │
│         │◄──────── Routes ───────────►│                    │
│         │◄────── Mesh Sync ──────────►│                    │
│                                                              │
│   Dimension: my-first-dimension                             │
│   Servers: 2                                                │
│   Communication: Bidirectional mesh                         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 🎉 Congratulations!

You've successfully:
- ✅ Generated a join token
- ✅ Joined a second server to the cluster
- ✅ Verified cluster connectivity
- ✅ Created a two-node mesh network

---

## Tutorial 3: Three-Server Production Cluster

Let's create a production-like cluster with three servers.

### What You'll Learn
- Building production-grade clusters
- Quorum concepts
- High availability basics
- Best practices for naming and organization

### Scenario

We're building a production cluster:
- **Server A** (web-prod-01): `192.168.1.100` - Web application server
- **Server B** (web-prod-02): `192.168.1.101` - Web application server
- **Server C** (db-prod-01): `192.168.1.102` - Database server

### Why Three Servers?

Three servers provide:
- **Quorum**: Majority consensus for distributed locking
- **High Availability**: System continues if one server fails
- **Load Distribution**: Spread work across multiple nodes

### Step 1: Create the Dimension (Server A)

On **Server A** (web-prod-01):

```bash
dimensigon new production-cluster
```

**Set a strong password:**
```
Password for root user: My$tr0ng!P@ssw0rd
Re-type same password: My$tr0ng!P@ssw0rd
```

### Step 2: Configure Server Name (Optional)

By default, Dimensigon uses your hostname. For production, you might want a specific name.

**Before starting** the server, you can set the hostname:
```bash
export HOSTNAME=web-prod-01
```

Or rename later via the database (advanced).

### Step 3: Start Server A

```bash
dimensigon run \
  --port 20194 \
  --threads 8 \
  --access-logfile /var/log/dimensigon/access.log \
  --error-logfile /var/log/dimensigon/error.log
```

**Production options explained:**
- `--port 20194`: Explicit port (default, but good to specify)
- `--threads 8`: Number of worker threads (adjust based on CPU cores)
- `--access-logfile`: HTTP access log location
- `--error-logfile`: Error log location

### Step 4: Generate Extended Token

Since we're joining two servers, generate a token with extended expiration:

```bash
dimensigon token --expire-time 60 --applicant web-prod-02
```

**Copy this token** - it's valid for 60 minutes.

### Step 5: Join Server B (web-prod-02)

On **Server B**:

```bash
# Set hostname
export HOSTNAME=web-prod-02

# Join the cluster
dimensigon join 192.168.1.100 <token-from-step-4>

# Start the server
dimensigon run \
  --port 20194 \
  --threads 8 \
  --access-logfile /var/log/dimensigon/access.log \
  --error-logfile /var/log/dimensigon/error.log
```

### Step 6: Generate Token for Server C

On **Server A** or **Server B** (both work now!):

```bash
dimensigon token --expire-time 60 --applicant db-prod-01
```

### Step 7: Join Server C (db-prod-01)

On **Server C**:

```bash
# Set hostname
export HOSTNAME=db-prod-01

# Join the cluster
dimensigon join 192.168.1.100 <token-from-step-6>

# Start the server
dimensigon run \
  --port 20194 \
  --threads 8 \
  --access-logfile /var/log/dimensigon/access.log \
  --error-logfile /var/log/dimensigon/error.log
```

### Step 8: Verify the Cluster

**Via Web Interface:**

Navigate to: `https://192.168.1.100:20194/admin/server/`

You should see **three servers**:
1. web-prod-01 (192.168.1.100)
2. web-prod-02 (192.168.1.101)
3. db-prod-01 (192.168.1.102)

**Via API:**
```bash
curl -u root:My\$tr0ng\!P@ssw0rd \
  https://192.168.1.100:20194/api/v1.0/servers | jq '.[] | {name, gates}'
```

**Expected output:**
```json
{
  "name": "web-prod-01",
  "gates": [{"ip": "192.168.1.100", "port": 20194}]
}
{
  "name": "web-prod-02",
  "gates": [{"ip": "192.168.1.101", "port": 20194}]
}
{
  "name": "db-prod-01",
  "gates": [{"ip": "192.168.1.102", "port": 20194}]
}
```

### Cluster Visualization

Your production cluster:

```
┌─────────────────────────────────────────────────────────────┐
│              THREE-SERVER PRODUCTION CLUSTER                 │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│     web-prod-01          web-prod-02         db-prod-01     │
│   192.168.1.100        192.168.1.101      192.168.1.102    │
│         │                    │                   │          │
│         │◄──────Mesh Network Topology───────────►│          │
│         │                    │                   │          │
│         └────────────────────┴───────────────────┘          │
│                                                              │
│   Dimension: production-cluster                             │
│   Servers: 3                                                │
│   Quorum: Enabled (minimum 5 servers for full quorum)      │
│   Replication: Full mesh (all-to-all communication)        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Step 9: Add Server Tags/Granules (Optional)

Granules allow you to target specific servers for orchestrations.

**Via API** (add "web" granule to web servers):
```bash
# web-prod-01
curl -u root:password -X PATCH \
  https://192.168.1.100:20194/api/v1.0/servers/web-prod-01 \
  -H "Content-Type: application/json" \
  -d '{"granules": ["web", "production"]}'

# web-prod-02
curl -u root:password -X PATCH \
  https://192.168.1.101:20194/api/v1.0/servers/web-prod-02 \
  -H "Content-Type: application/json" \
  -d '{"granules": ["web", "production"]}'

# db-prod-01
curl -u root:password -X PATCH \
  https://192.168.1.102:20194/api/v1.0/servers/db-prod-01 \
  -H "Content-Type: application/json" \
  -d '{"granules": ["database", "production"]}'
```

### 🎉 Congratulations!

You've successfully:
- ✅ Created a production-grade cluster
- ✅ Joined three servers with proper naming
- ✅ Configured production logging
- ✅ Added server classification (granules)
- ✅ Built a full mesh network

---

## Your First Orchestration

Now let's run a distributed workflow across your cluster.

### What is an Orchestration?

An orchestration is a workflow that executes steps across multiple servers. Think of it as a "distributed script."

### Example: Cluster Health Check

Let's create an orchestration that checks disk space on all servers.

### Step 1: Access the Admin Panel

Navigate to: `https://<any-server-ip>:20194/admin`

### Step 2: Create an Action Template

An Action Template is a reusable command.

1. Go to **Action Templates** → **Create**
2. Fill in:
   - **Name**: `check-disk-space`
   - **Description**: `Check disk space usage`
   - **Action Type**: `SHELL`
   - **Code**: `df -h / | tail -n 1 | awk '{print $5}'`
3. Click **Save**

### Step 3: Create an Orchestration

1. Go to **Orchestrations** → **Create**
2. Fill in:
   - **Name**: `cluster-health-check`
   - **Version**: `1`
   - **Description**: `Check disk space on all servers`
   - **Stop on Error**: ✓ (checked)
3. Click **Save**

### Step 4: Add Steps to the Orchestration

1. Click on your orchestration
2. Click **Add Step**
3. Configure:
   - **Action Template**: `check-disk-space`
   - **Target Server**: `all` (or select specific servers)
   - **Expected Return Code**: `0`
4. Click **Save**

### Step 5: Execute the Orchestration

**Via API:**
```bash
curl -u root:password -X POST \
  https://192.168.1.100:20194/api/v1.0/orchestrations/cluster-health-check/1/execute \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Via Web Interface:**
1. Go to **Orchestrations**
2. Find `cluster-health-check`
3. Click **Execute**

### Step 6: View Results

Navigate to: **Executions**

You'll see:
- Execution ID
- Status (SUCCESS, RUNNING, FAILED)
- Start and end times
- Results from each server

**Example output:**
```
Server: web-prod-01
Output: 45%
Status: SUCCESS

Server: web-prod-02
Output: 38%
Status: SUCCESS

Server: db-prod-01
Output: 72%
Status: SUCCESS
```

### What Just Happened?

1. **Orchestration Created**: Defined a workflow
2. **Distributed Execution**: Ran on all servers simultaneously
3. **Results Collected**: Each server reported back
4. **Centralized View**: See all results in one place

### More Orchestration Examples

**Example 1: Sequential Software Deployment**
```
Step 1: Stop application (on web servers)
Step 2: Deploy new version (on web servers)
Step 3: Update database schema (on db server)
Step 4: Start application (on web servers)
Step 5: Run smoke tests (on web servers)
```

**Example 2: Backup Workflow**
```
Step 1: Create database backup (on db-prod-01)
Step 2: Copy to backup server (transfer file)
Step 3: Verify backup integrity (checksum)
Step 4: Clean old backups (retention policy)
```

**Example 3: Log Collection**
```
Step 1: Compress logs (all servers, parallel)
Step 2: Upload to central storage (all servers, parallel)
Step 3: Rotate logs (all servers, parallel)
```

---

## Common Errors and Fixes

### Error 1: Token Has Expired

**Error message:**
```
[ERROR] Error on authentication: {'msg': 'Token has expired'}
```

**Fix:**
Generate a new token:
```bash
dimensigon token --expire-time 60
```

**Prevention:**
- Use `--expire-time` for longer validity
- Generate token just before use
- Complete joins quickly

---

### Error 2: Connection Refused

**Error message:**
```
[ERROR] Unable to contact to 192.168.1.100
```

**Troubleshooting checklist:**

1. **Check server is running:**
   ```bash
   ps aux | grep dimensigon
   ```

2. **Check port is listening:**
   ```bash
   netstat -tulpn | grep 20194
   ```

3. **Test network connectivity:**
   ```bash
   telnet 192.168.1.100 20194
   ```

4. **Check firewall:**
   ```bash
   # Ubuntu/Debian
   sudo ufw status
   sudo ufw allow 20194/tcp

   # CentOS/RHEL
   sudo firewall-cmd --list-all
   sudo firewall-cmd --permanent --add-port=20194/tcp
   sudo firewall-cmd --reload
   ```

5. **Verify SSL works:**
   ```bash
   curl -k https://192.168.1.100:20194/api/v1.0/ping
   ```

---

### Error 3: Only One Dimension Can Be Created

**Error message:**
```
Only one dimension can be created
```

**Explanation:**
Dimensigon supports one Dimension per installation.

**Fix:**
If you need to start over:

```bash
# CAUTION: This deletes all data!

# Stop Dimensigon
pkill -f dimensigon

# Backup (optional)
mv ~/.dimensigon ~/.dimensigon.backup

# Start fresh
dimensigon new new-dimension-name
```

---

### Error 4: Address Already in Use

**Error message:**
```
[ERROR] Address already in use: 0.0.0.0:20194
```

**Fix 1: Kill existing process**
```bash
pkill -f dimensigon
# Or
kill $(cat ~/.dimensigon/dimensigon.pid)
```

**Fix 2: Use different port**
```bash
dimensigon --port 8443
```

---

### Error 5: Database Locked

**Error message:**
```
[ERROR] database is locked
```

**Causes:**
- Another Dimensigon process is running
- SQLite journal file is stale
- Database file has wrong permissions

**Fix:**
```bash
# Stop all Dimensigon processes
pkill -f dimensigon

# Check for journal file
ls -la ~/.dimensigon/dimensigon.db-journal

# Remove if stale (older than a few minutes)
rm ~/.dimensigon/dimensigon.db-journal

# Fix permissions
chmod 644 ~/.dimensigon/dimensigon.db

# Restart
dimensigon run
```

---

### Error 6: Permission Denied on SSL Key

**Error message:**
```
[ERROR] Permission denied: '~/.dimensigon/.ssl/key.pem'
```

**Fix:**
```bash
chmod 600 ~/.dimensigon/.ssl/key.pem
chmod 644 ~/.dimensigon/.ssl/cert.pem
chown $USER:$USER ~/.dimensigon/.ssl/*
```

---

### Error 7: No Dimension Created

**Error message:**
```
No dimension created. Create or join to a dimension
```

**Explanation:**
You tried to run `dimensigon run` without creating or joining a Dimension first.

**Fix:**
Create a new Dimension:
```bash
dimensigon new my-cluster
```

Or join an existing one:
```bash
dimensigon join <server> <token>
```

---

## Next Steps

### Learning Path

**Beginner:**
1. ✅ Complete these tutorials
2. ✅ Explore the web interface
3. ✅ Create simple orchestrations
4. 📖 Read [Dimension Lifecycle](DIMENSION_LIFECYCLE.md)
5. 📖 Study [DM-WebManager Guide](DM_WEBMANAGER_README.md)

**Intermediate:**
1. 📖 Learn about [Action Templates](../api/API_REFERENCE.md#action-templates)
2. 📖 Understand [Orchestration Dependencies](../api/API_REFERENCE.md#orchestrations)
3. 📖 Explore [File Distribution](../api/API_REFERENCE.md#files)
4. 🔧 Practice with variables and parameters
5. 🔧 Build complex multi-step workflows

**Advanced:**
1. 📖 Study [Architecture Documentation](../api/ARCHITECTURE.md)
2. 📖 Review [Security Best Practices](../security/SECURITY_CHECKLIST.md)
3. 📖 Plan [Production Deployment](../deployment/DEPLOYMENT_GUIDE.md)
4. 🔧 Implement distributed locking
5. 🔧 Build custom integrations via API

### Practical Projects

**Project 1: Web Application Deployment**
- Create orchestration for zero-downtime deployment
- Implement health checks
- Add rollback capability

**Project 2: Backup Automation**
- Schedule daily backups
- Implement retention policies
- Add verification steps

**Project 3: Monitoring Integration**
- Collect metrics from all servers
- Send to centralized monitoring
- Create alerting workflows

**Project 4: Configuration Management**
- Distribute configuration files
- Implement secrets management
- Version control configurations

### Resources

**Documentation:**
- [Complete Documentation](../README.md)
- [API Reference](../api/API_REFERENCE.md)
- [Architecture Guide](../api/ARCHITECTURE.md)
- [Security Guide](../security/README.md)
- [Deployment Guide](../deployment/DEPLOYMENT_GUIDE.md)

**Community:**
- GitHub Issues: Report bugs and request features
- Documentation: Contribute improvements
- Examples: Share orchestration templates

---

## Quick Reference

### Essential Commands

```bash
# Create dimension
dimensigon new <name>

# Start server
dimensigon run

# Generate token
dimensigon token [--expire-time MINUTES]

# Join cluster
dimensigon join <server> <token> [--port PORT]

# View gates
dimensigon gate list

# Check version
dimensigon --version

# Debug mode
dimensigon --debug
```

### Default Locations

```
Config Directory:  ~/.dimensigon/
Database:         ~/.dimensigon/dimensigon.db
Logs:             ~/.dimensigon/dimensigon.log
SSL Certs:        ~/.dimensigon/.ssl/
Default Port:     20194
```

### Web Interfaces

```
Dashboard:        https://<server>:20194/dm-webmanager/dashboard
Admin Panel:      https://<server>:20194/admin
API v1.0:         https://<server>:20194/api/v1.0/
API v2.0:         https://<server>:20194/api/v2/
```

### Log Files

```bash
# Server logs
tail -f ~/.dimensigon/dimensigon.log

# Access logs
tail -f ~/.dimensigon/access.log

# Follow both
tail -f ~/.dimensigon/*.log
```

---

## Tips and Tricks

### Tip 1: Use Screen or Tmux for Long-Running Servers

Instead of keeping terminal open:

```bash
# Start in screen
screen -S dimensigon
dimensigon run
# Press Ctrl+A, then D to detach

# Reattach later
screen -r dimensigon
```

### Tip 2: Create Systemd Service (Production)

Create `/etc/systemd/system/dimensigon.service`:

```ini
[Unit]
Description=Dimensigon Server
After=network.target

[Service]
Type=simple
User=dimensigon
WorkingDirectory=/opt/dimensigon
ExecStart=/usr/local/bin/dimensigon run
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable dimensigon
sudo systemctl start dimensigon
sudo systemctl status dimensigon
```

### Tip 3: Use Environment Variables

```bash
# Set in ~/.bashrc or /etc/environment
export DIMENSIGON_PORT=20194
export DIMENSIGON_CONFIG_DIR=/opt/dimensigon/config
export FLASK_CONFIG=production
```

### Tip 4: Quick Health Check

```bash
# Check if server is responsive
curl -k https://localhost:20194/api/v1.0/ping

# Expected output:
{"status": "ok"}
```

### Tip 5: Backup Before Major Changes

```bash
# Backup configuration
tar -czf dimensigon-backup-$(date +%Y%m%d).tar.gz ~/.dimensigon/

# Restore if needed
tar -xzf dimensigon-backup-20251029.tar.gz -C ~/
```

---

## Troubleshooting Decision Tree

```
Problem?
│
├─ Can't create dimension
│  └─ Check: Already exists? → Remove ~/.dimensigon/ and retry
│
├─ Can't join cluster
│  ├─ Token expired? → Generate new token
│  ├─ Network issue? → Check firewall and connectivity
│  └─ Server not running? → Start server with `dimensigon run`
│
├─ Server won't start
│  ├─ Port in use? → Kill old process or use different port
│  ├─ Permission denied? → Check file permissions in ~/.dimensigon/
│  └─ Database locked? → Remove journal file if stale
│
├─ Can't access web interface
│  ├─ SSL warning? → Accept self-signed certificate
│  ├─ Wrong credentials? → Reset root password via database
│  └─ Server not responding? → Check logs in ~/.dimensigon/
│
└─ Orchestration fails
   ├─ Action not found? → Create Action Template first
   ├─ Target unreachable? → Check server connectivity
   └─ Permission issue? → Check user permissions on target
```

---

**Congratulations on completing the Getting Started guide!**

You now have the foundation to build powerful distributed automation with Dimensigon. Happy orchestrating!

---

**Document Version**: 1.0.0
**Last Updated**: 2025-10-29
**Dimensigon Version**: 2.0.0+
