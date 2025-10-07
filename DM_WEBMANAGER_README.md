# DM-WebManager - Dimensigon Administration GUI

## Overview

**DM-WebManager** is the official web-based administration interface for Dimensigon 2.0, providing comprehensive management capabilities for orchestrations, action templates, and execution monitoring.

### Key Features

- 🎯 **Dashboard** - Real-time metrics and execution statistics
- 🔄 **Orchestrations Management** - CRUD operations via REST API
- ⚡ **Action Templates Browser** - View and manage action templates
- 📊 **Executions Viewer** - Real-time execution monitoring with filtering
- 📚 **Data Dictionary Browser** - Comprehensive schema introspection
- 🎨 **Cyberpunk Neon Theme** - Sleek deep-purple inspired design

---

## Architecture

DM-WebManager is a **standalone component** within the Dimensigon repository, consisting of:

### Backend Components

```
dimensigon/web/admin/
├── __init__.py                 # Flask-Admin initialization
├── data_dictionary.py          # Schema introspection API
├── executions_viewer.py        # Execution monitoring API
└── routes.py                   # Dashboard routes
```

### Frontend Components

```
templates/admin/
├── dashboard.html              # Main cyberpunk-themed dashboard
└── custom_base.html            # Flask-Admin base template
```

### API Endpoints

#### API v2.0 - New Admin Endpoints

**Data Dictionary:**
- `GET /api/v2/data-dictionary/entities` - List all entities
- `GET /api/v2/data-dictionary/entities/<entity_key>` - Get entity schema
- `GET /api/v2/data-dictionary/orchestrations` - List orchestrations with schema info
- `GET /api/v2/data-dictionary/orchestrations/<id>` - Get orchestration details
- `GET /api/v2/data-dictionary/action-templates` - List action templates
- `GET /api/v2/data-dictionary/action-templates/<id>` - Get action template details
- `GET /api/v2/data-dictionary/search?q=<query>` - Search across data dictionary

**Executions Viewer:**
- `GET /api/v2/executions` - List executions (paginated, filterable)
- `GET /api/v2/executions/<id>` - Get execution details
- `GET /api/v2/executions/<id>/steps` - Get step executions
- `GET /api/v2/executions/stats` - Execution statistics
- `GET /api/v2/executions/running` - Currently running executions
- `GET /api/v2/executions/recent` - Recent executions
- `GET /api/v2/executions/step-executions/<id>` - Step execution details

#### API v1.0 - Existing Endpoints (Used by GUI)

- `GET /api/1.0/orchestrations` - List orchestrations
- `GET /api/1.0/action_templates` - List action templates
- All other existing v1.0 endpoints remain available

---

## Installation

### Dependencies

DM-WebManager requires the following additional packages (already added to requirements.txt):

```bash
Flask-Admin>=1.6.1,<2.0.0
WTForms>=3.0.0,<4.0.0
```

### Install

```bash
pip install -e .
```

---

## Usage

### Accessing DM-WebManager

1. **Start Dimensigon:**
   ```bash
   dimensigon start
   ```

2. **Access the GUI:**
   - Dashboard: `http://localhost:5000/dm-webmanager/dashboard`
   - Flask-Admin: `http://localhost:5000/admin`
   - API v2 Docs: `http://localhost:5000/api/v2/`

3. **Authentication:**
   - DM-WebManager uses JWT authentication from existing Dimensigon auth
   - Login via standard Dimensigon authentication endpoints
   - Token stored in localStorage

### Navigation

The dashboard provides access to:

- **Dashboard** - Overview with real-time stats (auto-refreshes every 30s)
- **Orchestrations** - View and manage workflow definitions
- **Action Templates** - Browse available actions
- **Executions** - Monitor running and completed executions
- **Data Dictionary** - Explore data model schemas

---

## Features in Detail

### 1. Dashboard

Real-time metrics including:
- Total executions (last 24h)
- Currently running executions
- Success/failure counts
- Success rate percentage
- Top executed orchestrations
- Recent failures

Auto-refreshes every 30 seconds.

### 2. Data Dictionary Browser

Comprehensive schema introspection for:
- **Orchestrations** - Full schema with step dependencies, DAG structure
- **Action Templates** - Input/output schemas, system kwargs
- **All Entities** - Column definitions, relationships, constraints

### 3. Executions Viewer

Advanced filtering:
- **Status:** running, success, failed
- **Time range:** start_date, end_date
- **Orchestration:** filter by orchestration ID
- **Server:** filter by server ID
- **Search:** full-text search in orchestration names and messages

Pagination: Up to 200 executions per page

### 4. Flask-Admin Views

Traditional admin interface for:
- Orchestrations (CRUD with export to CSV/JSON)
- Action Templates (CRUD with export)
- Steps (view and manage)
- Executions (read-only monitoring)
- Servers (infrastructure management)

---

## Design System

### Cyberpunk Neon Theme

Inspired by Dimensigon and Scaleway, featuring:

**Color Palette:**
- Primary: Deep Purple (`#4c2889`, `#2d1552`)
- Accent: Neon Purple (`#b084ff`)
- Highlights: Cyan Neon (`#00ffff`), Pink Neon (`#ff00ff`)
- Background: Dark (`#0a0118`, `#050010`)
- Text: Light gray (`#e5e7eb`)

**Typography:**
- Headers: Inter (700 weight)
- Code/Data: JetBrains Mono
- Body: Inter (400-600 weight)

**Effects:**
- Neon glow on hover
- Gradient borders
- Backdrop blur
- Smooth transitions
- Animated statistics

**Components:**
- Glassmorphic cards
- Gradient buttons with glow
- Neon-bordered tables
- Custom scrollbars
- Status badges with glow effects

---

## API Response Examples

### Execution Stats

```json
{
  "time_range": "Last 24 hours",
  "total_executions": 145,
  "running": 3,
  "successful": 130,
  "failed": 12,
  "success_rate": 91.55,
  "top_orchestrations": [
    {"name": "deploy-app", "version": 1, "count": 45},
    {"name": "backup-db", "version": 2, "count": 32}
  ],
  "recent_failures": [...]
}
```

### Orchestration Schema

```json
{
  "id": "uuid",
  "name": "deploy-app",
  "version": 1,
  "schema": {...},
  "dependencies": {...},
  "root_steps": ["step-id-1"],
  "steps": [
    {
      "id": "step-id-1",
      "name": "checkout-code",
      "action_type": "SHELL",
      "schema": {...},
      "target": ["all"],
      "parents": [],
      "children": ["step-id-2"]
    }
  ]
}
```

---

## Security

### Authentication

- All admin endpoints require JWT authentication
- Uses `@jwt_required()` decorator
- Token validation via Flask-JWT-Extended

### Authorization

- Future enhancement: Role-based access control (RBAC)
- Currently: Any authenticated user can access admin

### API Security

- CORS headers configured
- Input validation via JSON schemas
- SQL injection prevention via SQLAlchemy ORM
- XSS prevention via template escaping

---

## Performance

### Optimizations

- **Pagination:** All list endpoints support pagination (default 50/page)
- **Caching:** Browser caching for static assets
- **Lazy Loading:** Data loaded on demand
- **Auto-refresh:** Intelligent refresh intervals (30s for dashboard)

### Database Queries

- Optimized with eager loading (see Optimizer agent recommendations)
- Indexed columns for common filters
- Query result limiting

---

## Development

### Adding New Views

1. Create view class in `dimensigon/web/admin/__init__.py`:
   ```python
   class MyEntityView(SecureModelView):
       column_list = ['field1', 'field2']
       # ... configuration
   ```

2. Register in `init_admin()`:
   ```python
   admin.add_view(MyEntityView(db.session, name='My Entity'))
   ```

### Adding New API Endpoints

1. Create blueprint in `dimensigon/web/admin/`:
   ```python
   my_api_bp = Blueprint('my_api', __name__, url_prefix='/api/v2/my-api')

   @my_api_bp.route('/')
   @jwt_required()
   def my_endpoint():
       return jsonify({...})
   ```

2. Register in `dimensigon/web/__init__.py`:
   ```python
   from dimensigon.web.admin.my_api import my_api_bp
   app.register_blueprint(my_api_bp)
   ```

### Customizing Theme

Edit color variables in `templates/admin/dashboard.html`:
```css
:root {
    --purple-neon: #b084ff;
    --bg-dark: #0a0118;
    /* ... */
}
```

---

## Troubleshooting

### GUI not loading

1. Check Flask app is running: `http://localhost:5000/`
2. Verify templates directory exists
3. Check browser console for errors
4. Ensure JWT token is valid

### Authentication errors

1. Login via `/api/1.0/token` endpoint
2. Store token in localStorage: `dm_token`
3. Verify token in request headers: `Authorization: Bearer <token>`

### Data not displaying

1. Check API endpoints are registered: `/api/v2/executions/stats`
2. Verify database has data
3. Check browser network tab for API errors
4. Ensure CORS is configured correctly

---

## Future Enhancements

### Planned Features

- [ ] **Real-time WebSocket Updates** - Live execution monitoring
- [ ] **DAG Visualization** - Interactive workflow graphs (vis.js)
- [ ] **Orchestration Builder** - Drag-and-drop step creation
- [ ] **Role-Based Access Control** - Fine-grained permissions
- [ ] **Audit Logging** - Track all admin actions
- [ ] **Dark/Light Mode Toggle** - Theme switching
- [ ] **Export/Import** - Orchestration templates
- [ ] **Execution Replay** - Re-run failed executions
- [ ] **Performance Metrics** - Detailed timing charts
- [ ] **Mobile Responsive** - Optimized mobile views

### Integration Roadmap

- Integration with existing Dimensigon CLI (`dshell`)
- Integration with monitoring systems (Prometheus/Grafana)
- OpenTelemetry tracing support
- GraphQL API alternative

---

## Credits

**DM-WebManager** developed as part of Dimensigon 2.0 upgrade.

**Technologies:**
- Flask-Admin 1.6.1
- Bootstrap 5.3
- Bootstrap Icons 1.10
- JetBrains Mono & Inter fonts

**Design Inspiration:**
- Dimensigon branding
- Scaleway cloud platform UI
- Cyberpunk aesthetic
- Modern SaaS admin interfaces

---

## Support

For issues, feature requests, or questions:
- GitHub Issues: https://github.com/dimensigon/dimensigon/issues
- Documentation: See `UPGRADE_REPORT.md` for migration guide

---

**Version:** 2.0.0
**Status:** ✅ Production Ready
**Last Updated:** 2025-10-06
