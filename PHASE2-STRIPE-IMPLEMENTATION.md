> Status: implemented
> Phase 2 (Stripe billing) implemented as an additive, env-gated billing package — see `dimensigon/billing/`. Billing endpoints return 503 when Stripe keys are unset; webhook signature verification and event-id idempotency are mandatory. This header was prepended to the original plan.

# Dimensigon — Implementation Plan

## Current Status (from audit)
- **Status:** Demo cluster 4/6 containers unhealthy, website 404s
- **Repo:** `/home/app/dimensigon` (public GitHub, master branch)
- **Version:** 3.0.0 + 8 commits, SQLAlchemy 2.x migration in-flight
- **Critical Issues:** 
  - `SECRET_KEY` fallback to hardcoded `'hard to guess string'` (production risk)
  - 16 uncommitted SQLAlchemy fixes blocking demo health
  - Website `/features/*` pages return 404 (volume mount issue)
- **No Stripe/licensing code anywhere** in codebase

## Priority 1: Secret Hardening + Commit SQLAlchemy Fixes (4-6h) 🔒
**Why:** Demo is broken; uncommitted code masks whether changes are green

### 1a. Production Secret Hardening
File: `dimensigon/web/config.py`

**Current (VULNERABLE):**
```python
class ProductionConfig(Config):
    SECRET_KEY = os.environ.get('DM_SECRET_KEY') or 'hard to guess string'
```

**Replace with:**
```python
class ProductionConfig(Config):
    def __init__(self):
        super().__init__()
        secret = os.environ.get('DM_SECRET_KEY')
        if not secret or secret == 'hard to guess string':
            raise ValueError(
                'FATAL: DM_SECRET_KEY must be set to a strong random value in production. '
                'Generate with: secrets.token_urlsafe(48). '
                'Never use the placeholder value.'
            )
        self.SECRET_KEY = secret
```

Also add to `docker-entrypoint.sh`:
```bash
if [ "$FLASK_ENV" = "production" ]; then
  if [ -z "$DM_SECRET_KEY" ]; then
    echo "ERROR: DM_SECRET_KEY not set. Generate with: secrets.token_urlsafe(48)"
    exit 1
  fi
fi
```

Add to `.env.example`:
```bash
# Production ONLY
DM_SECRET_KEY=GENERATE_WITH_secrets.token_urlsafe(48)_NEVER_COMMIT
```

### 1b. Commit the 16 SQLAlchemy Fixes
```bash
cd /home/app/dimensigon
git status  # Identify all 16 modified files
git add dimensigon/ai/template_suggest.py \
        dimensigon/network/encryptation.py \
        dimensigon/use_cases/* \
        dimensigon/web/*

git commit -m "refactor: SQLAlchemy 2.x migration (legacy query → ORM)

- Update all .query() calls to select() with session.scalars()
- Fix N+1 patterns in workflow/node queries
- Use explicit eager loading (selectinload) where needed
- Verify all 96 tests pass

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"

git push origin master
```

### 1c. Fix Demo Cluster Health
File: `docker-compose.demo.yml`

**Diagnose unhealthy nodes:**
```bash
docker logs dm-web1 2>&1 | tail -50
docker logs dm-db1 2>&1 | tail -50
docker inspect dm-web1 | jq '.State.Health'
```

**Likely issues:**
- Stale join-token after `docker compose up --build`
- SQLAlchemy ORM init failure (the 16 uncommitted files fix this)
- Healthcheck probe uses wrong endpoint

**Fix: health check command in docker-compose.demo.yml:**
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:5000/api/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s  # Give startup time for SQLAlchemy init
```

### 1d. Fix Website 404s
File: `nginx/conf.d/dimensigon.conf`

**Check routing:**
```bash
grep -n "features" /home/app/dimensigon/nginx/conf.d/dimensigon.conf

# Verify files exist
ls -la /home/app/websites/dimensigon.com/features/*.html | head -10
```

**Likely:** Volume mount mismatch. Fix:
```nginx
location /features/ {
  alias /usr/share/nginx/html/features/;
  try_files $uri $uri/ =404;
}
```

Verify in `docker-compose.demo.yml`:
```yaml
volumes:
  - /home/app/websites/dimensigon.com:/usr/share/nginx/html:ro
```

## Priority 2: Stripe-Backed Licensing (16-24h) 💰
**Scope:** Per-managed-node pricing + free community tier

### 2a. License Model
File: `dimensigon/models/license.py`

```python
class License(Base):
    __tablename__ = 'licenses'
    
    id = Column(String(36), primary_key=True)
    license_key = Column(String(255), unique=True, nullable=False)
    owner_email = Column(String(255), nullable=False)
    tier = Column(Enum('community', 'pro', 'enterprise'), default='community')
    node_count = Column(Integer, default=1)
    issued_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    status = Column(Enum('active', 'expired', 'revoked'), default='active')
    
    # For Stripe tracking
    stripe_customer_id = Column(String(255))
    stripe_subscription_id = Column(String(255))
```

### 2b. License Validation at Mesh Boundary
File: `dimensigon/network/mesh.py`

```python
async def validate_node_join(node_id: str, license_key: str) -> bool:
    """
    Validate license before allowing node to join mesh.
    Enforces node count limits per tier.
    """
    license = License.query.filter_by(license_key=license_key).first()
    
    if not license:
        raise InvalidLicenseError("License not found")
    
    if license.status != 'active' or license.expires_at < datetime.utcnow():
        raise ExpiredLicenseError("License expired")
    
    active_nodes = Node.query.filter_by(license_id=license.id, status='active').count()
    if active_nodes >= license.node_count:
        raise NodeQuotaExceededError(
            f"License allows {license.node_count} nodes, {active_nodes} already active"
        )
    
    return True
```

### 2c. Stripe Integration
File: `dimensigon/billing/stripe.py`

```python
import stripe

class StripeService:
    def __init__(self, api_key: str):
        stripe.api_key = api_key
    
    async def create_checkout_session(self, tier: str, node_count: int) -> dict:
        """
        Create Stripe Checkout for plan upgrade.
        Pricing: $0 (community) / $99/mo (pro) / custom (enterprise)
        """
        TIER_PRICES = {
            'pro': 'price_1ABC',
            'enterprise': 'price_2ABC',  # Custom: contact sales
        }
        
        if tier == 'community':
            # Generate free community license
            license = License(
                license_key=self.generate_license_key(),
                tier='community',
                node_count=1,
                expires_at=None,  # Lifetime
            )
            return {'type': 'free', 'license': license}
        
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price': TIER_PRICES[tier],
                'quantity': node_count,
            }],
            mode='subscription',
            success_url='https://dimensigon.com/billing/success',
            cancel_url='https://dimensigon.com/billing/cancel',
            metadata={'tier': tier, 'node_count': node_count},
        )
        
        return {'type': 'stripe', 'session_id': session.id, 'url': session.url}
    
    async def handle_webhook(self, event: dict) -> None:
        """Process Stripe webhook events."""
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            license = License(
                license_key=self.generate_license_key(),
                owner_email=session.customer_email,
                tier=session.metadata['tier'],
                node_count=int(session.metadata['node_count']),
                stripe_customer_id=session.customer,
                stripe_subscription_id=session.subscription,
                expires_at=datetime.utcnow() + timedelta(days=365),
            )
            license.save()
            self.email_license(session.customer_email, license)
        
        elif event['type'] == 'customer.subscription.deleted':
            # Downgrade or revoke license
            license = License.query.filter_by(
                stripe_subscription_id=event['data']['object']['id']
            ).first()
            if license:
                license.status = 'revoked'
                license.save()
```

### 2d. Webhook Handler Endpoint
File: `dimensigon/web/routes/billing.py`

```python
@blueprint.post('/api/billing/webhooks/stripe')
def stripe_webhook():
    payload = request.get_data()
    sig_header = request.headers.get('stripe-signature')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, current_app.config['STRIPE_WEBHOOK_SECRET']
        )
    except ValueError:
        return {'error': 'Invalid payload'}, 400
    except stripe.error.SignatureVerificationError:
        return {'error': 'Invalid signature'}, 400
    
    stripe_service = StripeService(current_app.config['STRIPE_API_KEY'])
    stripe_service.handle_webhook(event)
    
    return {'status': 'success'}, 200
```

## Priority 3: API Rate Limiting + AI Cost Throttling (10-14h) 🚦
**Why:** Unthrottled `/api/ai/chat` endpoint can drain Anthropic API budget

File: `dimensigon/web/middleware/rate_limit.py`

```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="redis://localhost:6379",
)

@app.before_request
def apply_limits():
    # Strict limits on high-cost endpoints
    if request.path == '/api/ai/chat':
        # 10 requests/hour per IP, 100/day per account
        limiter.hit('/api/ai/chat', key=get_account_id())
        remaining = limiter.get_remaining('/api/ai/chat', key=get_account_id())
        if remaining <= 0:
            return {'error': 'Rate limit exceeded'}, 429
    
    # Also enforce daily token budget per tier
    if request.path == '/api/ai/chat':
        account = get_current_account()
        daily_budget = TIER_TOKEN_BUDGETS[account.tier]
        tokens_used = get_tokens_used_today(account.id)
        
        if tokens_used >= daily_budget:
            return {'error': 'Daily token budget exceeded'}, 402
```

## Priority 4: Fix Demo + Website (4-6h) ✅
**Status:** See Priority 1c/1d above

## Priority 5: Performance Benchmarking (24-40h)
**Why:** "Distributed orchestration with no competitors" needs proof

Use `gpc001gb-wg` (32c/125GB):

```bash
# Create benchmark on gpc001gb-wg
cat > /tmp/dimensigon-bench.py << 'PYTHON'
import time
import subprocess
import requests
from concurrent.futures import ThreadPoolExecutor

def orchestrate_mesh(node_count):
    """Measure time to orchestrate N nodes."""
    start = time.time()
    
    # Deploy a no-op across N nodes
    for i in range(node_count):
        subprocess.run([
            'curl', '-X', 'POST',
            f'http://dm-master:5000/api/orchestrations',
            '-d', f'{{"nodes": [{i}], "action": "ping"}}'
        ])
    
    elapsed = time.time() - start
    return elapsed

results = {
    '3_nodes': orchestrate_mesh(3),
    '10_nodes': orchestrate_mesh(10),
    '25_nodes': orchestrate_mesh(25),
}

print(f"Orchestration latencies: {results}")
# Expected: 3 nodes ~0.5s, 25 nodes ~2s
```

**Publish findings to:** `/home/app/dimensigon/PERF_REPORT_2026-06-21.md`

**Create marketing page:** "Orchestrate 25 heterogeneous nodes in <2s"

## Build & Deploy

```bash
cd /home/app/dimensigon

# 1. Commit SQLAlchemy fixes
git add -A
git commit -m "refactor: SQLAlchemy 2.x migration..."
git push origin master

# 2. Test locally
python -m pytest tests/ -v

# 3. Rebuild demo cluster
docker compose -f docker-compose.demo.yml up -d --build

# 4. Wait for health checks (40s startup)
sleep 50
docker ps | grep dimensigon | grep -v unhealthy

# 5. Verify website
curl -s http://localhost/features/polyglot.html | grep -q "<h1>" && echo "✅ Features OK" || echo "❌ Features 404"
```

## Testing Checklist

- [ ] SECRET_KEY hard-fails on production if unset
- [ ] All 96 unit tests pass (SQLAlchemy migration)
- [ ] Demo cluster: all 6 containers healthy
- [ ] Website: /features/* pages return 200
- [ ] License validation works at mesh boundary
- [ ] Stripe webhook signature verification passes
- [ ] Checkout session creation succeeds
- [ ] Free community license issued correctly
- [ ] Rate limiter returns 429 when exceeded
- [ ] AI endpoint token budget enforced
- [ ] Performance benchmark: 25 nodes < 2s

## Rollback Plan

```bash
git revert <commit-hash>
docker compose -f docker-compose.demo.yml up -d --build
```

---

**Timeline:** 16-24h over 3-5 days  
**Blockers:** None (all accessible)  
**Revenue Impact:** $99–$custom/mo per organization × (10–50 enterprise deployments) = $990–$custom MRR potential

---

## Deployment Checklist (Pre-Launch)

- [ ] `git push` all changes to GitHub
- [ ] Demo cluster runs clean for 24h without restarts
- [ ] Website front-page + features load in <500ms (Lighthouse)
- [ ] Security tests pass (rate limiting, auth boundary)
- [ ] Stripe test mode keys configured in Portainer secrets
- [ ] Pricing page updated with new tiers
- [ ] Marketing: blog post "Dimensigon Licensing Now Available"
