# Dimensigon 3.0 Tutorials

A comprehensive set of tutorials covering all 25 features planned for Dimensigon 3.0, organized by implementation phase.

---

## Phase 1: Foundation

Core upgrades and fixes that establish the base for all subsequent features.

| # | Tutorial | Description |
|---|----------|-------------|
| 01 | [SQLAlchemy 2.x Migration](01-sqlalchemy-migration.md) | Migrate the ORM layer from SQLAlchemy 1.x to 2.x for async support and modern query patterns |
| 02 | [Security Layer Simplification](02-security-layer.md) | Simplify the double-encryption security layer for easier configuration and maintenance |
| 03 | [forward_or_dispatch Decorator Fix](03-forward-dispatch-fix.md) | Fix the request forwarding decorator to handle edge cases in multi-node routing |
| 04 | [Lightweight Health Endpoint](04-health-endpoint.md) | Add a fast, dependency-free health check endpoint for load balancers and monitoring |
| 05 | [Authentication Flow Rework](05-auth-flow.md) | Modernize the JWT authentication flow in the WebManager with refresh token rotation |

---

## Phase 2: Core UX

Dashboard and visualization improvements that transform the operator experience.

| # | Tutorial | Description |
|---|----------|-------------|
| 06 | [Real-time Execution Monitoring](06-realtime-monitoring.md) | Monitor orchestration execution live with WebSocket-powered progress updates and DAG visualization |
| 07 | [Visual Orchestration Builder](07-orchestration-builder.md) | Design orchestrations visually with a drag-and-drop DAG editor in the dashboard |
| 08 | [Server Topology Visualization](08-server-topology.md) | View your server mesh as an interactive network graph showing connections, routes, and health |
| 10 | [Dashboard Widgets](10-dashboard-widgets.md) | Customize the dashboard with configurable widgets for server status, recent executions, and alerts |
| 24 | [Prometheus Metrics Endpoint](24-prometheus-metrics.md) | Expose Dimensigon metrics in Prometheus format for integration with Grafana and alerting systems |

---

## Phase 3: Features

New capabilities for automation, scheduling, and operational control.

| # | Tutorial | Description |
|---|----------|-------------|
| 12 | [Webhook / Event System](12-webhooks.md) | Configure webhooks to trigger external systems on orchestration events (start, complete, fail) |
| 13 | [Scheduled Orchestrations (Cron)](13-scheduled-orchestrations.md) | Schedule orchestrations to run on cron expressions with timezone support and miss-fire policies |
| 14 | [Orchestration Versioning and Rollback](14-versioning-rollback.md) | Version orchestration definitions and roll back to previous versions with diff comparison |
| 16 | [Audit Log](16-audit-log.md) | Track all system actions with a searchable, filterable audit log for compliance and troubleshooting |
| 25 | [Container-Native Deployment](25-container-deployment.md) | Deploy Dimensigon as containers with Docker Compose and Kubernetes manifests |

---

## Phase 4: AI and Polish

AI-powered assistance and UX refinements.

| # | Tutorial | Description |
|---|----------|-------------|
| 09 | [Execution History with Diff](09-execution-history.md) | Compare orchestration executions side by side with diff views of outputs, timing, and parameters |
| 11 | [Orchestration Templates / Marketplace](11-templates-marketplace.md) | Browse, import, and share orchestration templates from a community marketplace |
| 17 | [Context-Aware AI in WebManager](17-context-aware-ai.md) | Use AI assistance in the dashboard that understands your servers, orchestrations, and history |
| 18 | [AI-Powered Troubleshooting](18-ai-troubleshooting.md) | Get AI-driven root cause analysis and fix suggestions when orchestrations fail |
| 22 | [Auto-Complete for Orchestration Parameters](22-auto-complete.md) | Context-aware auto-completion for parameter names and values in DShell |

---

## Phase 5: Advanced

Advanced features for debugging, cross-dimension operations, and AI-driven automation.

| # | Tutorial | Description |
|---|----------|-------------|
| 15 | [Multi-Dimension Federation](15-federation.md) | Connect multiple Dimensigon dimensions for cross-environment orchestration, shared templates, and failover routing |
| 19 | [Natural Language Orchestration Runner](19-natural-language-runner.md) | Run orchestrations using plain English with automatic intent resolution, target mapping, and parameter extraction |
| 20 | [Training Data Feedback Loop](20-training-feedback.md) | Review and approve AI-generated orchestrations to continuously improve the AI model through administrator-curated training data |
| 21 | [Interactive Step Debugger](21-step-debugger.md) | Debug orchestration failures interactively in DShell with step inspection, command modification, re-execution, and breakpoints |
| 23 | [Web Terminal](23-web-terminal.md) | Access the full DShell experience from your browser with an embedded xterm.js terminal, command history, and session management |

---

## Quick Reference: All Tutorials by Number

| # | Title | Phase | Category |
|---|-------|-------|----------|
| 01 | SQLAlchemy 2.x Migration | 1 | Core |
| 02 | Security Layer Simplification | 1 | Core |
| 03 | forward_or_dispatch Decorator Fix | 1 | Core |
| 04 | Lightweight Health Endpoint | 1 | Core |
| 05 | Authentication Flow Rework | 1 | WebManager |
| 06 | Real-time Execution Monitoring | 2 | WebManager |
| 07 | Visual Orchestration Builder | 2 | WebManager |
| 08 | Server Topology Visualization | 2 | WebManager |
| 09 | Execution History with Diff | 4 | WebManager |
| 10 | Dashboard Widgets | 2 | WebManager |
| 11 | Orchestration Templates / Marketplace | 4 | Features |
| 12 | Webhook / Event System | 3 | Features |
| 13 | Scheduled Orchestrations (Cron) | 3 | Features |
| 14 | Orchestration Versioning and Rollback | 3 | Features |
| 15 | Multi-Dimension Federation | 5 | Features |
| 16 | Audit Log | 3 | Features |
| 17 | Context-Aware AI in WebManager | 4 | AI |
| 18 | AI-Powered Troubleshooting | 4 | AI |
| 19 | Natural Language Orchestration Runner | 5 | AI |
| 20 | Training Data Feedback Loop | 5 | AI |
| 21 | Interactive Step Debugger | 5 | DShell |
| 22 | Auto-Complete for Orchestration Parameters | 4 | DShell |
| 23 | Web Terminal | 5 | DShell |
| 24 | Prometheus Metrics Endpoint | 2 | Infrastructure |
| 25 | Container-Native Deployment | 3 | Infrastructure |

---

## Getting Started

If you are new to Dimensigon, begin with the [Getting Started Guide](../guides/GETTING_STARTED.md) and the [Quick Start Guide](../guides/QUICK_START.md) before diving into these tutorials.

For the feature design details behind each tutorial, see the corresponding plan in the [plans/](../../plans/) directory.
