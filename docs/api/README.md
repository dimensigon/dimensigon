# API & Architecture Documentation

This directory contains API reference documentation and system architecture information for Dimensigon.

## Contents

### API Documentation

- **[API_REFERENCE.md](./API_REFERENCE.md)** - Complete RESTful API reference
  - Authentication endpoints
  - Server management APIs
  - Orchestration APIs
  - Vault and secrets management
  - Log federation APIs
  - Monitoring and metrics
  - WebSocket endpoints

### Architecture Documentation

- **[ARCHITECTURE.md](./ARCHITECTURE.md)** - System architecture and design
  - High-level architecture overview
  - Component interactions
  - Mesh networking design
  - Security architecture
  - Data flow diagrams
  - Technology stack
  - Design patterns and principles

## API Overview

Dimensigon provides a comprehensive RESTful API for:

### Core Functions
- **Server Management** - Register, monitor, and manage distributed servers
- **Orchestration** - Execute commands and workflows across the mesh network
- **Configuration Management** - Distributed vault for secrets and configuration
- **Log Federation** - Centralized logging across all nodes
- **ACL Management** - Granular access control and permissions

### Authentication
- JWT-based authentication
- Token management
- Role-based access control (RBAC)
- Multi-factor authentication support

### Communication
- RESTful HTTP/HTTPS endpoints
- WebSocket for real-time updates
- Double encryption (SSL + message-level encryption)
- Certificate-based node authentication

## Architecture Highlights

### Key Design Principles
- **Decentralization** - No single point of failure
- **Mesh Networking** - Peer-to-peer node communication
- **Polyglot Support** - Technology-agnostic orchestration
- **Security First** - Double encryption and ACLs by default
- **Scalability** - Horizontal scaling through mesh expansion

### System Components
- **Core Engine** - Orchestration and coordination logic
- **API Layer** - RESTful interface and WebSocket handlers
- **Mesh Network** - Peer-to-peer communication layer
- **Distributed Vault** - Secure configuration storage
- **Log Aggregator** - Federated logging system
- **Web Manager** - Administration interface

## Quick Links

- **Getting Started with API**: See [API_REFERENCE.md](./API_REFERENCE.md#getting-started)
- **Architecture Overview**: See [ARCHITECTURE.md](./ARCHITECTURE.md#overview)
- **Security Model**: See [ARCHITECTURE.md](./ARCHITECTURE.md#security)
- **Deployment Architecture**: See [../deployment/](../deployment/)

## API Base URL

```
http(s)://<server>:<port>/api/v1.0/
```

Default port: 5000 (configurable)

## Support

For API questions or architecture discussions:
- Review complete API documentation in [API_REFERENCE.md](./API_REFERENCE.md)
- Understand system design in [ARCHITECTURE.md](./ARCHITECTURE.md)
- Check deployment patterns in [../deployment/](../deployment/)
