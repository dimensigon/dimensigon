# Dimensigon 2.0 Architecture Documentation

**Version:** 2.0.0
**Last Updated:** 2025-10-29

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Principles](#architecture-principles)
3. [Component Architecture](#component-architecture)
4. [Technology Stack](#technology-stack)
5. [Database Schema](#database-schema)
6. [Authentication Flow](#authentication-flow)
7. [Data Flow Diagrams](#data-flow-diagrams)
8. [Deployment Architecture](#deployment-architecture)
9. [Network Architecture](#network-architecture)
10. [Security Architecture](#security-architecture)
11. [Scalability & Performance](#scalability--performance)

---

## System Overview

Dimensigon is a distributed orchestration and automation platform designed for heterogeneous, multi-cloud environments. It provides a decentralized mesh network architecture for managing complex workflows across distributed servers.

### Key Characteristics

- **Decentralized**: No single point of failure, peer-to-peer coordination
- **Distributed**: Catalog-based data synchronization across cluster
- **Polyglot**: Support for multiple action types (Shell, Python, HTTP, etc.)
- **Mesh Networking**: Direct peer-to-peer communication between nodes
- **Double Encryption**: SSL + encrypted messaging for security
- **Real-time Monitoring**: Live execution tracking and metrics
- **Schema-driven**: JSON Schema validation for orchestrations and actions

### Core Capabilities

1. **Orchestration Engine**: Define and execute complex multi-step workflows
2. **Action Templates**: Reusable automation components
3. **Distributed Vault**: Secure configuration and secrets management
4. **Log Federation**: Centralized logging across distributed nodes
5. **File Distribution**: Synchronized file management across cluster
6. **Execution Monitoring**: Real-time visibility into workflow execution
7. **Data Dictionary**: Runtime introspection of all data models

---

## Architecture Principles

### 1. Decentralization

Every Dimensigon node is equal. There is no master/slave relationship. Any node can:
- Accept and process requests
- Execute orchestrations
- Synchronize data with peers
- Coordinate distributed operations

### 2. Eventual Consistency

The system uses a **catalog-based versioning mechanism** to achieve eventual consistency:
- Each entity change updates a catalog timestamp
- Nodes compare catalog versions to detect changes
- Synchronization occurs automatically when differences are detected
- Conflicts are resolved using last-write-wins with timestamp comparison

### 3. Peer-to-Peer Communication

Nodes communicate directly with each other through:
- **Gates**: Network endpoints (DNS/IP + port combinations)
- **Routes**: Routing information for reaching other nodes
- **Health Checks**: Periodic heartbeat monitoring

### 4. Separation of Concerns

The architecture separates:
- **Definition** (orchestrations, action templates) from **Execution** (execution records)
- **Distributed Entities** (replicated across cluster) from **Local Entities** (node-specific)
- **API Layer** from **Business Logic** from **Data Layer**

### 5. Polyglot Execution

Support for multiple execution types:
- **SHELL**: Execute shell scripts
- **PYTHON**: Execute Python code (RestrictedPython for security)
- **HTTP**: Make HTTP/REST API calls
- **ORCHESTRATION**: Nested orchestration execution

---

## Component Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Dimensigon Node                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐      │
│  │  Web Interface │  │  DM-WebManager │  │  DShell CLI    │      │
│  │   (Flask)      │  │   (Admin GUI)  │  │  (Interactive) │      │
│  └────────┬───────┘  └────────┬───────┘  └────────┬───────┘      │
│           │                   │                    │               │
│           └───────────────────┴────────────────────┘               │
│                              │                                     │
│  ┌────────────────────────────────────────────────────────┐       │
│  │              API Layer (Flask Blueprints)              │       │
│  ├────────────────────────────────────────────────────────┤       │
│  │  • API v2.0 (Data Dictionary, Executions Viewer)      │       │
│  │  • API v1.0 (REST Resources)                           │       │
│  │  • Authentication (JWT)                                │       │
│  │  • Error Handling                                      │       │
│  └────────────────────┬───────────────────────────────────┘       │
│                       │                                            │
│  ┌────────────────────────────────────────────────────────┐       │
│  │             Business Logic Layer                       │       │
│  ├────────────────────────────────────────────────────────┤       │
│  │  Use Cases:                                            │       │
│  │  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │       │
│  │  │ Orchestration│  │   Cluster    │  │ File Sync   │ │       │
│  │  │   Execution  │  │  Management  │  │             │ │       │
│  │  └──────────────┘  └──────────────┘  └─────────────┘ │       │
│  │  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │       │
│  │  │   Catalog    │  │   Routing    │  │   Locker    │ │       │
│  │  │     Sync     │  │              │  │ (Dist Lock) │ │       │
│  │  └──────────────┘  └──────────────┘  └─────────────┘ │       │
│  └────────────────────┬───────────────────────────────────┘       │
│                       │                                            │
│  ┌────────────────────────────────────────────────────────┐       │
│  │              Domain Layer (Entities)                   │       │
│  ├────────────────────────────────────────────────────────┤       │
│  │  Distributed Entities:                                 │       │
│  │  • Orchestration  • ActionTemplate  • Step            │       │
│  │  • Server         • Gate            • Route           │       │
│  │  • User           • File            • Software         │       │
│  │  • Vault          • Catalog                            │       │
│  │                                                         │       │
│  │  Local Entities:                                       │       │
│  │  • OrchExecution   • StepExecution                     │       │
│  │  • Log             • Transfer                          │       │
│  │  • Locker          • Parameter                         │       │
│  └────────────────────┬───────────────────────────────────┘       │
│                       │                                            │
│  ┌────────────────────────────────────────────────────────┐       │
│  │         Data Access Layer (SQLAlchemy ORM)             │       │
│  ├────────────────────────────────────────────────────────┤       │
│  │  • Query Builder                                       │       │
│  │  • Relationship Management                             │       │
│  │  • Transaction Management                              │       │
│  │  • Event Listeners (Catalog Updates)                   │       │
│  └────────────────────┬───────────────────────────────────┘       │
│                       │                                            │
│  ┌────────────────────────────────────────────────────────┐       │
│  │            Database (SQLite with WAL)                  │       │
│  │  • dimensigon.db                                       │       │
│  │  • WAL mode for concurrency                            │       │
│  │  • JSON column support                                 │       │
│  └────────────────────────────────────────────────────────┘       │
│                                                                     │
│  ┌────────────────────────────────────────────────────────┐       │
│  │           Network & Communication Layer                │       │
│  ├────────────────────────────────────────────────────────┤       │
│  │  • HTTP/HTTPS Client (requests)                        │       │
│  │  • SSL/TLS Encryption                                  │       │
│  │  • Message Encryption (cryptography)                   │       │
│  │  • Cluster Discovery & Heartbeat                       │       │
│  │  • Route Management                                    │       │
│  └────────────────────────────────────────────────────────┘       │
│                                                                     │
│  ┌────────────────────────────────────────────────────────┐       │
│  │         Background Workers (Executor)                  │       │
│  ├────────────────────────────────────────────────────────┤       │
│  │  • Cluster Manager (health monitoring)                 │       │
│  │  • File Sync Worker                                    │       │
│  │  • Catalog Sync Worker                                 │       │
│  │  • Task Executor (async operations)                    │       │
│  └────────────────────────────────────────────────────────┘       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘

         Network Communication (Mesh)
                    │
    ┌───────────────┼───────────────┐
    │               │               │
┌───▼────┐    ┌─────▼────┐    ┌────▼───┐
│ Node 1 │◄───► Node 2   │◄───► Node 3 │
└────────┘    └──────────┘    └────────┘
```

### Component Descriptions

#### 1. Web Interface (Flask)

- **Framework**: Flask 2.3+
- **Responsibilities**:
  - HTTP request handling
  - Request routing
  - Response formatting
  - Middleware execution
- **Key Components**:
  - Blueprint registration
  - Error handlers
  - Context management
  - JWT integration

#### 2. API Layer

##### API v2.0 (New)
- **Data Dictionary API**: Schema introspection and documentation
- **Executions Viewer API**: Real-time execution monitoring and metrics
- **Features**:
  - Pagination support
  - Advanced filtering
  - Search capabilities
  - JSON Schema introspection

##### API v1.0 (Legacy)
- **REST Resources**: Full CRUD operations for all entities
- **Features**:
  - Flask-RESTful resources
  - Query filtering
  - Relationship endpoints
  - Forward/dispatch pattern for distributed operations

#### 3. Business Logic Layer (Use Cases)

##### Orchestration Execution
- Workflow parsing and validation
- Dependency graph resolution (DAG)
- Step scheduling and execution
- Error handling and rollback (undo)
- Result aggregation

##### Cluster Management
- Node discovery
- Health monitoring (heartbeat)
- Failure detection
- Cluster membership

##### Catalog Synchronization
- Entity change tracking
- Version comparison
- Delta synchronization
- Conflict resolution

##### Routing
- Path discovery between nodes
- Route optimization
- Gateway management
- Network topology mapping

##### Distributed Locking
- Cluster-wide locks
- Deadlock prevention
- Lock scopes (GLOBAL, CATALOG, etc.)
- Timeout management

##### File Synchronization
- File distribution across cluster
- Checksum verification
- Delta synchronization
- Version tracking

#### 4. Domain Layer (Entities)

##### Distributed Entities
Replicated across all cluster nodes:

- **Orchestration**: Workflow definitions with steps and dependencies
- **ActionTemplate**: Reusable action definitions
- **Step**: Individual workflow steps
- **Server**: Node definitions with gates and granules
- **Gate**: Network endpoints (DNS/IP + port)
- **Route**: Routing information between nodes
- **User**: User accounts and authentication
- **File**: File distribution definitions
- **Software**: Software inventory tracking
- **Vault**: Secure configuration storage
- **Catalog**: Entity version tracking

##### Local Entities
Specific to each node:

- **OrchExecution**: Orchestration execution records
- **StepExecution**: Step execution records with stdout/stderr
- **Log**: Federation logging
- **Transfer**: File transfer tracking
- **Locker**: Distributed lock state
- **Parameter**: Node-specific parameters

#### 5. Data Access Layer

- **ORM**: SQLAlchemy 3.0+
- **Database**: SQLite with WAL mode
- **Features**:
  - Lazy loading relationships
  - Eager loading for optimization
  - Query filtering and pagination
  - Event listeners for catalog updates
  - Transaction management
  - Connection pooling

#### 6. Network & Communication Layer

- **HTTP Client**: requests library
- **Security**:
  - SSL/TLS for transport encryption
  - Message-level encryption using cryptography library
  - JWT for authentication
- **Features**:
  - Retry logic with exponential backoff
  - Timeout management
  - Connection pooling
  - Bearer token authentication

#### 7. Background Workers

- **Cluster Manager**: Monitors node health, manages cluster membership
- **File Sync Worker**: Synchronizes files across cluster
- **Catalog Sync Worker**: Detects and synchronizes entity changes
- **Task Executor**: Executes long-running tasks asynchronously

---

## Technology Stack

### Core Technologies

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| **Language** | Python | 3.8+ | Primary programming language |
| **Web Framework** | Flask | 2.3+ | HTTP server and routing |
| **WSGI Server** | Gunicorn | 22.0+ | Production WSGI server |
| **Database** | SQLite | 3.x | Local data storage |
| **ORM** | SQLAlchemy | 3.0+ | Database abstraction |
| **Authentication** | Flask-JWT-Extended | 4.6+ | JWT token management |
| **REST API** | Flask-RESTful | 0.3.10+ | REST resource framework |
| **Admin GUI** | Flask-Admin | 1.6+ | Web-based admin interface |

### Security & Cryptography

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| **Encryption** | cryptography | 42.0+ | Message encryption |
| **Password Hashing** | passlib | 1.7.4+ | Secure password storage |
| **RSA** | rsa | 4.9+ | Public key cryptography |
| **SSL/TLS** | Built-in | - | Transport encryption |

### Data & Serialization

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| **JSON Schema** | jsonschema | 4.21+ | Schema validation |
| **YAML** | PyYAML | 6.0+ | Configuration files |
| **Templates** | Jinja2 | 3.1+ | Template rendering |
| **JSON** | Built-in | - | Data serialization |

### Networking & Communication

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| **HTTP Client** | requests | 2.32+ | HTTP communication |
| **Async HTTP** | aiohttp | 3.9+ | Asynchronous HTTP |
| **Network Info** | netifaces | 0.11+ | Network interface detection |

### Development & Tooling

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| **CLI** | Click | 8.1+ | Command-line interface |
| **Interactive Shell** | prompt_toolkit | 3.0+ | Interactive CLI |
| **Syntax Highlighting** | Pygments | 2.18+ | Code highlighting |
| **Testing** | pytest | - | Unit and integration tests |
| **Code Execution** | RestrictedPython | 7.0+ | Sandboxed Python execution |

### Utilities

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| **Date/Time** | python-dateutil | 2.9+ | Date parsing and manipulation |
| **Serialization** | dill | 0.3+ | Python object serialization |
| **File Watching** | watchdog | 4.0+ | File system monitoring |
| **Packaging** | packaging | 24.0+ | Version parsing |
| **Forms** | WTForms | 3.0+ | Form validation |

---

## Database Schema

### Schema Overview

Dimensigon uses a SQLite database with two categories of tables:

- **Distributed Tables** (prefix: `D_`): Replicated across all nodes
- **Local Tables** (prefix: `L_`): Node-specific data

### Entity Relationship Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                    DISTRIBUTED ENTITIES (D_*)                        │
└──────────────────────────────────────────────────────────────────────┘

┌─────────────────┐          ┌─────────────────┐
│  D_orchestration│          │ D_action_template│
├─────────────────┤          ├─────────────────┤
│ id (UUID) PK    │          │ id (UUID) PK    │
│ name            │          │ name            │
│ version         │          │ version         │
│ description     │          │ action_type     │
│ stop_on_error   │          │ description     │
│ undo_on_error   │          │ code            │
│ created_at      │          │ expected_stdout │
│ last_modified_at│          │ expected_stderr │
└────────┬────────┘          │ expected_rc     │
         │                   │ pre_process     │
         │ 1:N               │ post_process    │
         │                   │ schema (JSON)   │
         ▼                   │ system_kwargs   │
┌─────────────────┐          │ last_modified_at│
│    D_step       │          └────────┬────────┘
├─────────────────┤                   │
│ id (UUID) PK    │◄──────────────────┘ N:1
│ orchestration_id│ FK
│ action_template_id│ FK
│ undo            │
│ step_name       │
│ step_description│
│ step_code       │
│ target          │
│ created_on      │
└─────────────────┘

         ┌────────────────────┐
         │    D_step_parent   │  (Self-referential M:N)
         ├────────────────────┤
         │ parent_step_id  FK │
         │ child_step_id   FK │
         └────────────────────┘

┌─────────────────┐         ┌─────────────────┐
│    D_server     │         │     D_gate      │
├─────────────────┤         ├─────────────────┤
│ id (UUID) PK    │ 1:N     │ id (UUID) PK    │
│ name            │◄────────┤ server_id    FK │
│ granules (LIST) │         │ dns             │
│ me              │         │ ip              │
│ created_on      │         │ port            │
│ last_modified_at│         └─────────────────┘
└────────┬────────┘
         │ 1:1
         ▼
┌─────────────────┐
│     D_route     │
├─────────────────�┤
│ id (UUID) PK    │
│ destination_id FK│ -> D_server.id
│ proxy_server_id FK│ (nullable)
│ cost            │
│ last_modified_at│
└─────────────────┘

┌─────────────────┐
│     D_user      │
├─────────────────┤
│ id (UUID) PK    │
│ name            │
│ password (hash) │
│ email           │
│ created_at      │
│ is_active       │
│ groups (LIST)   │
│ last_modified_at│
└─────────────────┘

┌─────────────────┐         ┌─────────────────────────┐
│     D_file      │         │ D_file_server_association│
├─────────────────┤ 1:N     ├─────────────────────────┤
│ id (UUID) PK    │◄────────┤ file_id              FK │
│ source_server_id│ FK      │ destination_server_id FK│
│ target          │         │ path                    │
│ checksum        │         └─────────────────────────┘
│ content (BLOB)  │
│ last_modified_at│
└─────────────────┘

┌─────────────────┐         ┌──────────────────────────┐
│   D_software    │         │ D_software_server_assoc  │
├─────────────────┤ 1:N     ├──────────────────────────┤
│ id (UUID) PK    │◄────────┤ software_id           FK │
│ name            │         │ server_id             FK │
│ version         │         │ path                     │
│ filename        │         └──────────────────────────┘
│ last_modified_at│
└─────────────────┘

┌─────────────────┐
│     D_vault     │
├─────────────────┤
│ id (UUID) PK    │
│ scope           │
│ name            │
│ value           │
│ last_modified_at│
└─────────────────┘
UNIQUE(scope, name)

┌─────────────────┐
│    D_catalog    │
├─────────────────┤
│ entity (name) PK│
│ last_modified_at│
└─────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│                      LOCAL ENTITIES (L_*)                            │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────┐         ┌──────────────────┐
│ L_orch_execution │         │ L_step_execution │
├──────────────────┤ 1:N     ├──────────────────┤
│ id (UUID) PK     │◄────────┤ id (UUID) PK     │
│ orchestration_id │ FK      │ step_id       FK │
│ start_time       │         │ server_id     FK │
│ end_time         │         │ orch_execution_id│ FK
│ target (JSON)    │         │ start_time       │
│ params (JSON)    │         │ end_time         │
│ executor_id   FK │         │ params (JSON)    │
│ service_id    FK │         │ rc               │
│ server_id     FK │         │ stdout           │
│ success          │         │ stderr           │
│ undo_success     │         │ success          │
│ message          │         │ pre_process_time │
└──────────────────┘         │ execution_time   │
                             │ post_process_time│
                             │ child_orch_exec_id│ (nullable)
                             └──────────────────┘

┌──────────────────┐
│      L_log       │
├──────────────────┤
│ id (UUID) PK     │
│ src_server_id FK │
│ dst_server_id FK │
│ mode             │
│ target           │
│ message          │
│ level            │
│ timestamp        │
└──────────────────┘

┌──────────────────┐
│   L_transfer     │
├──────────────────┤
│ id (UUID) PK     │
│ src_server_id FK │
│ dst_server_id FK │
│ status           │
│ num_files        │
│ size             │
└──────────────────┘

┌──────────────────┐
│    L_locker      │
├──────────────────┤
│ id (INT) PK      │
│ scope            │
│ state            │
│ applicant_id  FK │
│ set_on           │
└──────────────────┘

┌──────────────────┐
│   L_parameter    │
├──────────────────┤
│ name (STR) PK    │
│ value            │
└──────────────────┘
```

### Key Tables

#### D_orchestration

Workflow definitions with metadata and configuration.

```sql
CREATE TABLE D_orchestration (
    id UUID PRIMARY KEY,
    name VARCHAR(80) NOT NULL,
    version INTEGER NOT NULL,
    description TEXT,
    stop_on_error BOOLEAN,
    stop_undo_on_error BOOLEAN,
    undo_on_error BOOLEAN,
    created_at DATETIME,
    last_modified_at DATETIME,
    UNIQUE(name, version)
);
```

#### D_step

Individual workflow steps with dependencies.

```sql
CREATE TABLE D_step (
    id UUID PRIMARY KEY,
    orchestration_id UUID NOT NULL,
    action_template_id UUID,
    undo BOOLEAN,
    step_name VARCHAR(255),
    step_description TEXT,
    step_code TEXT,
    step_action_type VARCHAR(50),
    target TEXT,
    created_on DATETIME,
    FOREIGN KEY(orchestration_id) REFERENCES D_orchestration(id),
    FOREIGN KEY(action_template_id) REFERENCES D_action_template(id)
);
```

Step dependencies are managed through a self-referential many-to-many relationship:

```sql
CREATE TABLE D_step_parent (
    parent_step_id UUID NOT NULL,
    child_step_id UUID NOT NULL,
    PRIMARY KEY(parent_step_id, child_step_id),
    FOREIGN KEY(parent_step_id) REFERENCES D_step(id),
    FOREIGN KEY(child_step_id) REFERENCES D_step(id)
);
```

#### D_action_template

Reusable action definitions with code and schemas.

```sql
CREATE TABLE D_action_template (
    id UUID PRIMARY KEY,
    name VARCHAR(80) NOT NULL,
    version INTEGER NOT NULL,
    action_type VARCHAR(50) NOT NULL,
    description TEXT,
    code TEXT,
    expected_stdout TEXT,
    expected_stderr TEXT,
    expected_rc INTEGER,
    pre_process TEXT,
    post_process TEXT,
    schema JSON,
    system_kwargs TEXT,
    last_modified_at DATETIME,
    UNIQUE(name, version)
);
```

#### D_server

Node definitions with granules (tags) for targeting.

```sql
CREATE TABLE D_server (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    granules TEXT,  -- Stored as list
    me BOOLEAN DEFAULT FALSE,
    created_on DATETIME,
    last_modified_at DATETIME
);
```

#### D_gate

Network endpoints for server communication.

```sql
CREATE TABLE D_gate (
    id UUID PRIMARY KEY,
    server_id UUID NOT NULL,
    dns VARCHAR(255),
    ip VARCHAR(45),
    port INTEGER NOT NULL,
    FOREIGN KEY(server_id) REFERENCES D_server(id)
);
```

#### D_user

User accounts with password hashes and groups.

```sql
CREATE TABLE D_user (
    id UUID PRIMARY KEY,
    name VARCHAR(30) NOT NULL UNIQUE,
    password VARCHAR(256),
    email VARCHAR(255),
    created_at DATETIME,
    is_active BOOLEAN NOT NULL,
    groups TEXT,  -- Stored as list
    last_modified_at DATETIME
);
```

#### L_orch_execution

Orchestration execution records (local to node).

```sql
CREATE TABLE L_orch_execution (
    id UUID PRIMARY KEY,
    orchestration_id UUID NOT NULL,
    start_time DATETIME NOT NULL,
    end_time DATETIME,
    target JSON,
    params JSON,
    executor_id UUID,
    service_id UUID,
    server_id UUID,
    success BOOLEAN,
    undo_success BOOLEAN,
    message TEXT,
    FOREIGN KEY(orchestration_id) REFERENCES D_orchestration(id),
    FOREIGN KEY(executor_id) REFERENCES D_user(id),
    FOREIGN KEY(server_id) REFERENCES D_server(id)
);
```

#### L_step_execution

Step execution records with stdout/stderr and timings.

```sql
CREATE TABLE L_step_execution (
    id UUID PRIMARY KEY,
    step_id UUID NOT NULL,
    server_id UUID,
    orch_execution_id UUID,
    start_time DATETIME NOT NULL,
    end_time DATETIME,
    params JSON,
    rc INTEGER,
    stdout TEXT,
    stderr TEXT,
    success BOOLEAN,
    pre_process_elapsed_time FLOAT,
    execution_elapsed_time FLOAT,
    post_process_elapsed_time FLOAT,
    child_orch_execution_id UUID,
    FOREIGN KEY(step_id) REFERENCES D_step(id),
    FOREIGN KEY(server_id) REFERENCES D_server(id),
    FOREIGN KEY(orch_execution_id) REFERENCES L_orch_execution(id)
);
```

#### D_catalog

Entity version tracking for synchronization.

```sql
CREATE TABLE D_catalog (
    entity VARCHAR(80) PRIMARY KEY,
    last_modified_at DATETIME NOT NULL
);
```

### Database Features

#### WAL Mode

SQLite is configured with Write-Ahead Logging (WAL) for better concurrency:

```python
dbapi_con.execute("PRAGMA journal_mode=WAL")
```

Benefits:
- Readers don't block writers
- Writers don't block readers
- Better performance for concurrent access

#### JSON Column Support

SQLite 3.9+ JSON support is used for flexible schema:
- `params`: Execution parameters
- `target`: Target specification (servers/granules)
- `schema`: JSON Schema definitions

#### Custom Types

Dimensigon uses custom SQLAlchemy types:
- `UUID`: UUID storage and conversion
- `UtcDateTime`: Timezone-aware datetime
- `ScalarListType`: List storage as colon-separated string

#### Automatic Timestamp Updates

Entity timestamps are automatically updated on modification:

```python
@event.listens_for(entity, 'before_update')
def receive_before_update(mapper, connection, target):
    target.last_modified_at = get_now()
```

---

## Authentication Flow

### JWT-based Authentication

Dimensigon uses JSON Web Tokens (JWT) for stateless authentication.

```
┌──────────┐                                    ┌──────────┐
│  Client  │                                    │  Server  │
└────┬─────┘                                    └────┬─────┘
     │                                               │
     │  1. POST /login                               │
     │     {username, password}                      │
     ├──────────────────────────────────────────────►│
     │                                               │
     │                                        2. Verify
     │                                         credentials
     │                                               │
     │  3. 200 OK                                    │
     │     {access_token, refresh_token}             │
     │◄──────────────────────────────────────────────┤
     │                                               │
     │  Store tokens                                 │
     │                                               │
     │  4. GET /api/v2/executions                    │
     │     Authorization: Bearer <access_token>      │
     ├──────────────────────────────────────────────►│
     │                                               │
     │                                        5. Verify
     │                                          JWT token
     │                                               │
     │  6. 200 OK                                    │
     │     {executions: [...]}                       │
     │◄──────────────────────────────────────────────┤
     │                                               │
     │  ... (token expires) ...                      │
     │                                               │
     │  7. POST /refresh                             │
     │     Authorization: Bearer <refresh_token>     │
     ├──────────────────────────────────────────────►│
     │                                               │
     │                                        8. Issue new
     │                                         access token
     │                                               │
     │  9. 200 OK                                    │
     │     {access_token}                            │
     │◄──────────────────────────────────────────────┤
     │                                               │
```

### Authentication Components

#### 1. User Model

Users are stored in the `D_user` table:
- Password hashed with SHA-256 (passlib)
- Active/inactive status
- Group-based authorization
- Distributed across cluster

#### 2. Login Process

```python
@root_bp.route('/login', methods=['POST'])
def login():
    user = User.get_by_name(request.json['username'])
    if user and user.verify_password(request.json['password']):
        return {
            'access_token': create_access_token(identity=str(user.id), fresh=True),
            'refresh_token': create_refresh_token(identity=str(user.id))
        }
    return {"error": "Bad username or password"}, 401
```

#### 3. Token Validation

All protected endpoints use the `@jwt_required()` decorator:

```python
@data_dict_bp.route('/entities', methods=['GET'])
@jwt_required()
def list_entities():
    # JWT is validated automatically
    user_id = get_jwt_identity()
    # ... endpoint logic ...
```

#### 4. Token Types

- **Access Token**: Short-lived (default: 15 minutes), used for API calls
- **Refresh Token**: Long-lived (default: 30 days), used to obtain new access tokens
- **Fresh Token**: Required for sensitive operations

#### 5. Security Features

- Tokens are signed with a secret key (JWT_SECRET_KEY)
- Token expiration is enforced
- Optional token blacklisting for logout
- Bearer token scheme (RFC 6750)

---

## Data Flow Diagrams

### Orchestration Execution Flow

```
┌────────────┐
│   Client   │
└─────┬──────┘
      │
      │ 1. POST /api/v1.0/orchestrations/{id}/execute
      │    {params: {...}, target: "production"}
      ▼
┌──────────────────────────────────────────────────────────┐
│                  API Layer                               │
│  • Authenticate JWT                                      │
│  • Validate request schema                               │
│  • Extract orchestration ID and params                   │
└────────┬─────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────┐
│            Orchestration Use Case                        │
│  1. Load orchestration from database                     │
│  2. Validate parameters against schema                   │
│  3. Resolve target servers/granules                      │
│  4. Build dependency graph (DAG)                         │
└────────┬─────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────┐
│         Create OrchExecution Record                      │
│  • execution_id = UUID                                   │
│  • start_time = now()                                    │
│  • status = "running"                                    │
└────────┬─────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────┐
│           Execute Steps (DAG Traversal)                  │
│                                                          │
│  For each step in topological order:                     │
│                                                          │
│    ┌─────────────────────────────────────┐             │
│    │  1. Wait for parent steps           │             │
│    └──────────────┬──────────────────────┘             │
│                   ▼                                      │
│    ┌─────────────────────────────────────┐             │
│    │  2. Create StepExecution record     │             │
│    └──────────────┬──────────────────────┘             │
│                   ▼                                      │
│    ┌─────────────────────────────────────┐             │
│    │  3. Resolve target server(s)        │             │
│    └──────────────┬──────────────────────┘             │
│                   ▼                                      │
│    ┌─────────────────────────────────────┐             │
│    │  4. Load action template            │             │
│    └──────────────┬──────────────────────┘             │
│                   ▼                                      │
│    ┌─────────────────────────────────────┐             │
│    │  5. Pre-process (variable subst)    │             │
│    └──────────────┬──────────────────────┘             │
│                   ▼                                      │
│    ┌─────────────────────────────────────┐             │
│    │  6. Execute action                  │             │
│    │     • SHELL: subprocess              │             │
│    │     • PYTHON: RestrictedPython       │             │
│    │     • HTTP: requests                 │             │
│    │     • ORCH: recursive orchestration  │             │
│    └──────────────┬──────────────────────┘             │
│                   ▼                                      │
│    ┌─────────────────────────────────────┐             │
│    │  7. Post-process (parse output)     │             │
│    └──────────────┬──────────────────────┘             │
│                   ▼                                      │
│    ┌─────────────────────────────────────┐             │
│    │  8. Update StepExecution            │             │
│    │     • end_time = now()               │             │
│    │     • rc, stdout, stderr             │             │
│    │     • success = (rc == 0)            │             │
│    └──────────────┬──────────────────────┘             │
│                   ▼                                      │
│    ┌─────────────────────────────────────┐             │
│    │  9. Check stop_on_error              │             │
│    └─────────────────────────────────────┘             │
│                                                          │
└────────┬─────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────┐
│        Update OrchExecution Record                       │
│  • end_time = now()                                      │
│  • success = all_steps_succeeded                         │
│  • message = summary or error                            │
└────────┬─────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────┐
│             Handle Errors (if any)                       │
│  • If undo_on_error:                                     │
│    - Execute undo steps in reverse order                 │
│  • Update undo_success flag                              │
└────────┬─────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────┐
│             Return Response                              │
│  {                                                        │
│    "execution_id": "...",                                │
│    "status": "success",                                  │
│    "message": "..."                                      │
│  }                                                        │
└──────────────────────────────────────────────────────────┘
```

### Catalog Synchronization Flow

```
┌──────────┐                         ┌──────────┐
│  Node A  │                         │  Node B  │
└────┬─────┘                         └────┬─────┘
     │                                    │
     │  1. Entity modified (e.g., new     │
     │     orchestration created)         │
     │                                    │
┌────▼──────────────────────────┐        │
│  SQLAlchemy Event Listener    │        │
│  • before_insert              │        │
│  • before_update              │        │
│  • Set last_modified_at       │        │
└────┬──────────────────────────┘        │
     │                                    │
┌────▼──────────────────────────┐        │
│  after_commit Event           │        │
│  • Update D_catalog table     │        │
│  • Set entity timestamp       │        │
└────┬──────────────────────────┘        │
     │                                    │
     │  2. POST /healthcheck              │
     │     {catalog_version: "2025-10-29"}│
     ├───────────────────────────────────►│
     │                                    │
     │                             3. Compare
     │                              catalog_version
     │                              with local
     │                                    │
     │                             4. If different:
     │                              GET /api/v1.0/catalog
     │◄───────────────────────────────────┤
     │                                    │
     │  5. Return catalog details         │
     │     [                              │
     │       {entity: "Orchestration",    │
     │        last_modified_at: "..."}    │
     │     ]                              │
     ├───────────────────────────────────►│
     │                                    │
     │                             6. For each
     │                              outdated entity:
     │                              GET /api/v1.0/...
     │◄───────────────────────────────────┤
     │                                    │
     │  7. Return entities                │
     │     [updated entities...]          │
     ├───────────────────────────────────►│
     │                                    │
     │                             8. Update local
     │                              database
     │                              (upsert)
     │                                    │
     │                             9. Update local
     │                              catalog table
     │                                    │
```

### Distributed Execution Flow

```
┌──────────┐                    ┌──────────┐                    ┌──────────┐
│  Node A  │                    │  Node B  │                    │  Node C  │
│(Executor)│                    │(Executor)│                    │(Worker)  │
└────┬─────┘                    └────┬─────┘                    └────┬─────┘
     │                               │                               │
     │  1. Execute orchestration     │                               │
     │     with steps targeting      │                               │
     │     multiple servers          │                               │
     │                               │                               │
┌────▼─────────────────────────┐    │                               │
│  Step 1: Target = "Node B"   │    │                               │
│  • Determine target server   │    │                               │
│  • Check if local or remote  │    │                               │
└────┬─────────────────────────┘    │                               │
     │                               │                               │
     │  2. POST /api/v1.0/execute_step │                             │
     │     {step_id, params}         │                               │
     ├──────────────────────────────►│                               │
     │                               │                               │
     │                          3. Execute step                      │
     │                            locally                            │
     │                               │                               │
     │                          4. Return result                     │
     │     {rc, stdout, stderr}      │                               │
     │◄──────────────────────────────┤                               │
     │                               │                               │
     │  5. Store StepExecution       │                               │
     │     in local database         │                               │
     │                               │                               │
┌────▼─────────────────────────┐    │                               │
│  Step 2: Target = "Node C"   │    │                               │
└────┬─────────────────────────┘    │                               │
     │                               │                               │
     │  6. POST /api/v1.0/execute_step                               │
     │     {step_id, params}                                         │
     ├──────────────────────────────────────────────────────────────►│
     │                               │                               │
     │                               │                          7. Execute
     │                               │                            step
     │                               │                               │
     │                               │                          8. Return
     │     {rc, stdout, stderr}                                   result
     │◄──────────────────────────────────────────────────────────────┤
     │                               │                               │
     │  9. Store StepExecution       │                               │
     │                               │                               │
     │  10. Complete orchestration   │                               │
     │      Update OrchExecution     │                               │
     │                               │                               │
```

---

## Deployment Architecture

### Single-Node Deployment

```
┌─────────────────────────────────────────────┐
│              Physical/Virtual Host           │
│                                             │
│  ┌────────────────────────────────────────┐ │
│  │        Dimensigon Process              │ │
│  │  ┌──────────────────────────────────┐  │ │
│  │  │        Gunicorn WSGI Server      │  │ │
│  │  │  • Workers: 4-8                  │  │ │
│  │  │  • Bind: 0.0.0.0:5000            │  │ │
│  │  │  • Timeout: 300s                 │  │ │
│  │  └──────────────┬───────────────────┘  │ │
│  │                 │                       │ │
│  │  ┌──────────────▼───────────────────┐  │ │
│  │  │    Flask Application             │  │ │
│  │  │  • API v2.0, API v1.0            │  │ │
│  │  │  • DM-WebManager                 │  │ │
│  │  └──────────────┬───────────────────┘  │ │
│  │                 │                       │ │
│  │  ┌──────────────▼───────────────────┐  │ │
│  │  │    Background Workers            │  │ │
│  │  │  • Cluster Manager (disabled)    │  │ │
│  │  │  • Task Executor                 │  │ │
│  │  └──────────────────────────────────┘  │ │
│  └────────────────────────────────────────┘ │
│                                             │
│  ┌────────────────────────────────────────┐ │
│  │       SQLite Database                  │ │
│  │  • dimensigon.db                       │ │
│  │  • WAL mode                            │ │
│  └────────────────────────────────────────┘ │
│                                             │
│  ┌────────────────────────────────────────┐ │
│  │       File System                      │ │
│  │  • Logs: /var/log/dimensigon/          │ │
│  │  • Data: /var/lib/dimensigon/          │ │
│  │  • Config: /etc/dimensigon/            │ │
│  └────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
```

### Multi-Node Cluster Deployment

```
┌──────────────────────────────────────────────────────────────────┐
│                        Load Balancer                             │
│                      (Optional - for API)                        │
│                  https://api.example.com                         │
└────────────┬─────────────────────────┬───────────────────────────┘
             │                         │
             ▼                         ▼
┌────────────────────────┐  ┌────────────────────────┐
│      Node 1            │  │      Node 2            │
│  Production - Web      │  │  Production - Web      │
│                        │  │                        │
│  Dimensigon:5000       │◄─┤  Dimensigon:5000       │
│  • Orchestrations      │  │  • Orchestrations      │
│  • API Endpoints       │  │  • API Endpoints       │
│  • Catalog Sync        │  │  • Catalog Sync        │
│  • Cluster Manager     │  │  • Cluster Manager     │
│                        │  │                        │
│  Granules:             │  │  Granules:             │
│  - production          │  │  - production          │
│  - web                 │  │  - web                 │
└────────────────────────┘  └────────────────────────┘
             │                         │
             │  Mesh Network           │
             │  (All nodes can         │
             │   communicate)          │
             │                         │
             ▼                         ▼
┌────────────────────────┐  ┌────────────────────────┐
│      Node 3            │  │      Node 4            │
│  Production - DB       │  │  Staging - Web         │
│                        │  │                        │
│  Dimensigon:5000       │◄─┤  Dimensigon:5000       │
│  • Orchestrations      │  │  • Orchestrations      │
│  • API Endpoints       │  │  • API Endpoints       │
│  • Catalog Sync        │  │  • Catalog Sync        │
│  • Cluster Manager     │  │  • Cluster Manager     │
│                        │  │                        │
│  Granules:             │  │  Granules:             │
│  - production          │  │  - staging             │
│  - database            │  │  - web                 │
└────────────────────────┘  └────────────────────────┘
```

### Container Deployment (Docker)

```
┌─────────────────────────────────────────────────────────────┐
│                     Docker Host                             │
│                                                             │
│  ┌────────────────────────────────────────────────────┐    │
│  │       Dimensigon Container                         │    │
│  │  ┌──────────────────────────────────────────────┐  │    │
│  │  │  Base Image: python:3.8-slim                 │  │    │
│  │  │                                              │  │    │
│  │  │  Install:                                    │  │    │
│  │  │  • dimensigon package                        │  │    │
│  │  │  • dependencies from requirements.txt        │  │    │
│  │  │                                              │  │    │
│  │  │  Entrypoint:                                 │  │    │
│  │  │  gunicorn -b 0.0.0.0:5000 \                 │  │    │
│  │  │    --workers 4 \                             │  │    │
│  │  │    --timeout 300 \                           │  │    │
│  │  │    dimensigon.web:create_app()               │  │    │
│  │  └──────────────────────────────────────────────┘  │    │
│  │                                                     │    │
│  │  Exposed Ports:                                    │    │
│  │  • 5000/tcp                                        │    │
│  │                                                     │    │
│  │  Volumes:                                          │    │
│  │  • /var/lib/dimensigon (database, state)          │    │
│  │  • /etc/dimensigon (configuration)                 │    │
│  │  • /var/log/dimensigon (logs)                      │    │
│  └────────────────────────────────────────────────────┘    │
│                                                             │
│  ┌────────────────────────────────────────────────────┐    │
│  │       Docker Network                               │    │
│  │  • Bridge mode (single host)                       │    │
│  │  • Host mode (cluster)                             │    │
│  │  • Overlay mode (Swarm/K8s)                        │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### Kubernetes Deployment

```
┌─────────────────────────────────────────────────────────────┐
│                  Kubernetes Cluster                         │
│                                                             │
│  ┌────────────────────────────────────────────────────┐    │
│  │         Dimensigon StatefulSet                     │    │
│  │  ┌──────────────┐  ┌──────────────┐              │    │
│  │  │  Pod: dm-0   │  │  Pod: dm-1   │              │    │
│  │  │              │  │              │              │    │
│  │  │  Container:  │  │  Container:  │              │    │
│  │  │  dimensigon  │  │  dimensigon  │   ...        │    │
│  │  │              │  │              │              │    │
│  │  │  PVC:        │  │  PVC:        │              │    │
│  │  │  dm-data-0   │  │  dm-data-1   │              │    │
│  │  └──────────────┘  └──────────────┘              │    │
│  └────────────────────────────────────────────────────┘    │
│                                                             │
│  ┌────────────────────────────────────────────────────┐    │
│  │         Service: dimensigon-api                    │    │
│  │  Type: LoadBalancer                                │    │
│  │  Port: 5000                                        │    │
│  │  Selector: app=dimensigon                          │    │
│  └────────────────────────────────────────────────────┘    │
│                                                             │
│  ┌────────────────────────────────────────────────────┐    │
│  │         Service: dimensigon-headless               │    │
│  │  Type: ClusterIP (None)                            │    │
│  │  For peer discovery                                │    │
│  └────────────────────────────────────────────────────┘    │
│                                                             │
│  ┌────────────────────────────────────────────────────┐    │
│  │         ConfigMap: dimensigon-config               │    │
│  │  • HTTP configuration                              │    │
│  │  • Cluster configuration                           │    │
│  └────────────────────────────────────────────────────┘    │
│                                                             │
│  ┌────────────────────────────────────────────────────┐    │
│  │         Secret: dimensigon-secrets                 │    │
│  │  • JWT secret key                                  │    │
│  │  • Root user credentials                           │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### Deployment Best Practices

1. **High Availability**:
   - Deploy at least 3 nodes for quorum
   - Use load balancer for API endpoints
   - Enable automatic restart on failure

2. **Data Persistence**:
   - Mount persistent volumes for database
   - Regular database backups
   - Use NFS/block storage for shared data

3. **Security**:
   - Use TLS/SSL certificates
   - Secure JWT secret keys
   - Network isolation (VPN, firewall rules)
   - Regular security updates

4. **Monitoring**:
   - Health check endpoints
   - Log aggregation (ELK, Splunk)
   - Metrics collection (Prometheus)
   - Alerting (PagerDuty, Slack)

5. **Scalability**:
   - Horizontal scaling by adding nodes
   - Granule-based workload distribution
   - Resource limits (CPU, memory)

---

## Network Architecture

### Mesh Networking

Dimensigon uses a mesh network topology where all nodes can communicate directly:

```
                    Node A
                   /   |   \
                  /    |    \
                 /     |     \
              Node B - Node C - Node D
                 \     |     /
                  \    |    /
                   \   |   /
                    Node E

Each node maintains:
• Direct connections to neighbors
• Routing table to all nodes
• Health status of peers
```

### Node Discovery

#### 1. Bootstrap Discovery

When a new node joins:

```
┌────────────┐                    ┌────────────┐
│  New Node  │                    │ Join Server│
└─────┬──────┘                    └─────┬──────┘
      │                                 │
      │  1. POST /api/v1.0/join         │
      │     {node_info, gates}          │
      ├────────────────────────────────►│
      │                                 │
      │                          2. Add node to
      │                            cluster
      │                                 │
      │                          3. Distribute
      │                            to all nodes
      │                                 │
      │  4. 200 OK                      │
      │     {cluster_info}              │
      │◄────────────────────────────────┤
      │                                 │
      │  5. Sync catalog                │
      │                                 │
```

#### 2. Heartbeat Mechanism

Nodes periodically send heartbeats:

```python
# Every 30 seconds
POST /healthcheck
{
  "me": "<node_id>",
  "heartbeat": "2025-10-29T15:30:00.000000"
}
```

#### 3. Failure Detection

- If no heartbeat received for 90 seconds: Mark as "in_coma"
- After 5 minutes: Mark as "dead"
- Automatic recovery when heartbeat resumes

### Routing

#### Route Table

Each node maintains a route table:

```sql
SELECT * FROM D_route;
+--------------------------------------+--------------------------------------+-------------------+------+
| id                                   | destination_id                       | proxy_server_id   | cost |
+--------------------------------------+--------------------------------------+-------------------+------+
| route-1                              | node-2-id                            | NULL              | 1    |
| route-2                              | node-3-id                            | node-2-id         | 2    |
+--------------------------------------+--------------------------------------+-------------------+------+
```

#### Route Discovery

Routes are discovered through:
1. Direct connectivity testing
2. Neighbor advertisement
3. Path cost calculation
4. Automatic failover

#### Routing Algorithm

```python
def find_route(destination):
    # 1. Check for direct route
    route = Route.query.filter_by(destination_id=destination, proxy_server_id=None).first()
    if route and test_connectivity(route):
        return route

    # 2. Check for indirect route through proxy
    routes = Route.query.filter_by(destination_id=destination).all()
    for route in sorted(routes, key=lambda r: r.cost):
        if test_connectivity(route):
            return route

    # 3. No route found
    raise NoRouteError(f"No route to {destination}")
```

### Gates (Network Endpoints)

Each server can have multiple gates (network interfaces):

```python
server = Server(
    name="prod-server-01",
    gates=[
        {"dns": "server01.internal.example.com", "port": 5000},
        {"ip": "192.168.1.100", "port": 5000},
        {"ip": "10.0.0.100", "port": 5000}  # VPN interface
    ]
)
```

Benefits:
- Multi-homed servers
- Failover between interfaces
- Network segmentation

---

## Security Architecture

### Multi-Layer Security

```
┌─────────────────────────────────────────────────────────┐
│                  Security Layers                        │
│                                                         │
│  Layer 1: Network Security                             │
│  ┌──────────────────────────────────────────────────┐  │
│  │  • Firewall rules (only port 5000 exposed)      │  │
│  │  • VPN/Private network recommended              │  │
│  │  • IP whitelisting                               │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  Layer 2: Transport Security (SSL/TLS)                 │
│  ┌──────────────────────────────────────────────────┐  │
│  │  • HTTPS required for production                │  │
│  │  • TLS 1.2+ enforced                            │  │
│  │  • Certificate validation                        │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  Layer 3: Message Encryption                           │
│  ┌──────────────────────────────────────────────────┐  │
│  │  • Double encryption (SSL + message-level)      │  │
│  │  • cryptography library (Fernet)                │  │
│  │  • Symmetric key encryption                      │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  Layer 4: Authentication (JWT)                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │  • JWT token validation                          │  │
│  │  • Token expiration enforcement                  │  │
│  │  • Fresh token requirement for sensitive ops    │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  Layer 5: Authorization                                │
│  ┌──────────────────────────────────────────────────┐  │
│  │  • Group-based access control                    │  │
│  │  • User active/inactive status                   │  │
│  │  • Granule-based resource isolation             │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  Layer 6: Code Execution Security                      │
│  ┌──────────────────────────────────────────────────┐  │
│  │  • RestrictedPython for Python actions          │  │
│  │  • Subprocess isolation for shell commands      │  │
│  │  • Timeout enforcement                           │  │
│  │  • Resource limits                               │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  Layer 7: Data Security                                │
│  ┌──────────────────────────────────────────────────┐  │
│  │  • Password hashing (SHA-256)                    │  │
│  │  • Vault encryption for secrets                  │  │
│  │  • Database encryption at rest (optional)        │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Authentication Details

#### User Roles and Groups

```python
# Pre-defined user IDs
ROOT = '00000000-0000-0000-0000-000000000001'
OPS = '00000000-0000-0000-0000-000000000002'
REPORTER = '00000000-0000-0000-0000-000000000003'
JOIN = '00000000-0000-0000-0000-000000000004'

# Group-based authorization
user = User(
    name="operator",
    groups=["operators", "viewers"],
    active=True
)
```

#### Password Security

```python
from passlib.hash import sha256_crypt

# Password hashing
hashed = sha256_crypt.hash(password)

# Password verification
is_valid = sha256_crypt.verify(password, hashed)
```

### Vault (Secrets Management)

The Vault provides encrypted storage for sensitive data:

```python
# Store secret
Vault.set(scope="global", name="api_key", value="secret_value")

# Retrieve secret
secret = Vault.get(scope="global", name="api_key")
```

Vault features:
- Scope-based isolation (global, server-specific, etc.)
- Automatic encryption
- Distributed across cluster
- Access control via JWT

### Code Execution Security

#### RestrictedPython

Python actions use RestrictedPython to limit capabilities:

```python
from RestrictedPython import compile_restricted, safe_builtins

# Restricted execution environment
restricted_globals = {
    '__builtins__': safe_builtins,
    'server': server_obj,
    'params': params_obj
}

code = compile_restricted(action_code, '<string>', 'exec')
exec(code, restricted_globals)
```

Restrictions:
- No file system access (except explicit)
- No network access (except HTTP action type)
- No subprocess execution
- Limited builtins
- Timeout enforcement

#### Shell Command Security

Shell commands are executed in isolated subprocesses:

```python
import subprocess

result = subprocess.run(
    command,
    shell=True,
    capture_output=True,
    timeout=timeout,
    cwd=working_dir,
    env=restricted_env
)
```

Security measures:
- Command timeout
- Environment variable restrictions
- Working directory isolation
- Output size limits

---

## Scalability & Performance

### Horizontal Scalability

Dimensigon scales horizontally by adding nodes:

```
Performance Characteristics:
• 1 node:  ~100 concurrent orchestrations
• 3 nodes: ~300 concurrent orchestrations
• 10 nodes: ~1000 concurrent orchestrations

Linear scaling based on:
• Workload distribution via granules
• Mesh network efficiency
• Database per node (no shared DB bottleneck)
```

### Performance Optimizations

#### 1. Database Optimization

```python
# WAL mode for concurrency
PRAGMA journal_mode=WAL

# Index on frequently queried columns
CREATE INDEX idx_execution_start_time ON L_orch_execution(start_time);
CREATE INDEX idx_execution_orchestration ON L_orch_execution(orchestration_id);

# Query optimization with eager loading
orchestrations = Orchestration.query.options(
    joinedload(Orchestration.steps)
).all()
```

#### 2. Caching

- Entity relationships cached in-memory
- Routing table cached
- Catalog version cached for quick comparison

#### 3. Asynchronous Operations

- Background workers for long-running tasks
- Non-blocking catalog synchronization
- Asynchronous HTTP requests (aiohttp)

#### 4. Query Filtering

API endpoints support efficient filtering:

```python
# Filter at database level
query = Orchestration.query.filter(
    Orchestration.name.contains(search_term)
).paginate(page=1, per_page=50)
```

### Load Distribution

#### Granule-based Targeting

Orchestrations target servers by granules:

```python
orchestration = Orchestration(
    name="Deploy Web App",
    steps=[
        Step(target="production,web"),  # Only production web servers
        Step(target="production,database"),  # Only production DB servers
    ]
)
```

#### Work Distribution Algorithm

1. Parse target specification (granules, server names, IDs)
2. Resolve to list of target servers
3. Distribute steps across target servers
4. Execute in parallel where possible (DAG allows)
5. Aggregate results

### Monitoring & Metrics

Key performance metrics:

- **Execution metrics**:
  - Orchestrations per minute
  - Average execution duration
  - Success rate
  - Concurrent executions

- **System metrics**:
  - API response time
  - Database query time
  - Network latency between nodes
  - Catalog sync duration

- **Resource metrics**:
  - CPU utilization
  - Memory usage
  - Database size
  - Network bandwidth

Access via API v2.0:

```bash
GET /api/v2/executions/stats?hours=24
```

---

## Appendix

### Configuration Files

#### dimensigon.conf

```yaml
http:
  bind:
    - 0.0.0.0:5000
  workers: 4
  timeout: 300

database:
  path: /var/lib/dimensigon/dimensigon.db
  wal_mode: true

security:
  jwt_secret_key: <random-secret-key>
  jwt_access_token_expires: 900  # 15 minutes
  jwt_refresh_token_expires: 2592000  # 30 days

cluster:
  heartbeat_interval: 30
  heartbeat_timeout: 90
  catalog_sync_interval: 60

logging:
  level: INFO
  path: /var/log/dimensigon/
```

### Environment Variables

```bash
# Flask configuration
FLASK_APP=dimensigon.web:create_app
FLASK_ENV=production

# Database
DM_DATABASE_PATH=/var/lib/dimensigon/dimensigon.db

# Security
DM_JWT_SECRET_KEY=<random-secret-key>

# HTTP Server
DM_HTTP_BIND=0.0.0.0:5000
DM_HTTP_WORKERS=4

# Cluster
DM_JOIN_SERVER=<server-id-or-url>
```

### File Locations

```
/opt/dimensigon/              # Installation directory
├── bin/
│   └── dimensigon           # Main executable
├── lib/                      # Python libraries
└── etc/                      # Configuration templates

/etc/dimensigon/              # Configuration
├── dimensigon.conf          # Main configuration
└── ssl/                      # SSL certificates
    ├── cert.pem
    └── key.pem

/var/lib/dimensigon/          # Data directory
├── dimensigon.db            # SQLite database
├── dimensigon.db-wal        # WAL file
├── dimensigon.db-shm        # Shared memory
└── files/                    # File storage

/var/log/dimensigon/          # Logs
├── dimensigon.log           # Application logs
├── access.log               # HTTP access logs
└── error.log                # Error logs
```

---

**End of Architecture Documentation**

For API reference, see [API_REFERENCE.md](./API_REFERENCE.md)
