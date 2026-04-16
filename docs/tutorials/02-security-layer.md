# Securizer Layer Configuration Guide

## Overview

Dimensigon encrypts and signs inter-node communication using RSA key pairs.
The **securizer** layer wraps every API request/response with encryption and
signature verification. Dimensigon 3.0 introduces a configurable
`SECURIZER_MODE` setting that lets operators choose how aggressively encryption
is applied, trading off security against performance.

This tutorial explains the three modes, when to use each one, and how to verify
that the mode you selected is active.

## Prerequisites

- A running Dimensigon node (or a development environment)
- Access to the configuration file or environment variables
- Understanding of Dimensigon's dimension concept (a dimension is a group of
  nodes sharing a common RSA key pair)

## 1. SECURIZER_MODE Explained

The mode is set via the `SECURIZER_MODE` configuration key and accepts three
string values:

| Mode | Behaviour | Typical Use |
|---|---|---|
| `always` | Every request is encrypted and signed, regardless of origin. This is the legacy Dimensigon 1.x behaviour. | Air-gapped or high-security production deployments where all traffic must be encrypted even within the same dimension. |
| `auto` | Intra-dimension traffic (nodes in the same dimension) is sent in plain text. Cross-dimension traffic is encrypted. | Recommended for most production deployments. Saves CPU on internal mesh traffic while still protecting cross-dimension communication. |
| `never` | Encryption is completely disabled. | Development and testing only. Never use in production. |

The default mode is **`auto`**.

## 2. How Auto Mode Detects Traffic Type

When a request arrives, the securizer decorator calls `_should_encrypt()` in
`dimensigon/web/decorators.py`. In `auto` mode the logic is:

1. If the `D-Securizer` header is `plain`, skip encryption.
2. Otherwise, call `Dimension.is_same_dimension(source)` to check whether the
   source server is in the same dimension as the local node.
3. If same dimension, skip encryption and log:
   `Securizer skipped: intra-dimension traffic (mode=auto)`
4. If different dimension, apply encryption and log:
   `Securizer applied: cross-dimension traffic (mode=auto)`

The dimension check works as follows (from `dimensigon/domain/entities/dimension.py`):

- If the source is a `Server` object found in the local database, it is
  considered same-dimension (all servers in our catalog are part of our
  dimension).
- If the source is a string (IP or UUID), the code attempts a database lookup.
  If the server exists locally, it is same-dimension.
- If the source is unknown or `None`, the safe default is to assume
  same-dimension (no encryption).

## 3. Configuration

### Option A: Configuration class (recommended for code-based config)

Edit `dimensigon/web/config.py` or your custom configuration class:

```python
class ProductionConfig(Config):
    SECURIZER = True          # Master switch -- must be True for encryption
    SECURIZER_PLAIN = True    # Allow plain-text requests in 'always' mode
    SECURIZER_MODE = 'auto'   # 'auto', 'always', or 'never'
```

### Option B: Environment variable

Set the variable before starting the node:

```bash
export DM_SECURIZER_MODE=auto
```

Then reference it in your config class:

```python
import os

class Config:
    SECURIZER_MODE = os.environ.get('DM_SECURIZER_MODE', 'auto')
```

### Related configuration keys

| Key | Default | Description |
|---|---|---|
| `SECURIZER` | `True` | Master on/off switch for the encryption layer. If `False`, no encryption is ever applied regardless of mode. |
| `SECURIZER_PLAIN` | `True` | In `always` mode, whether to allow incoming requests with `D-Securizer: plain` header. If `False`, plain requests receive a 406 response. |
| `SECURIZER_MODE` | `'auto'` | One of `auto`, `always`, `never`. |

## 4. When to Use Each Mode

### Development (`never`)

```python
class DevelopmentConfig(Config):
    SECURIZER = False
    SECURIZER_MODE = 'never'
```

Use this for local development where you run a single node and do not need
encryption overhead. Requests are faster and easier to debug with plain JSON.

### Production -- standard (`auto`)

```python
class ProductionConfig(Config):
    SECURIZER = True
    SECURIZER_MODE = 'auto'
```

This is the recommended default. Internal mesh traffic between nodes in the
same dimension is transmitted in plain text (still over TLS if you use HTTPS),
while cross-dimension traffic is RSA-encrypted and signed. This gives you the
best balance of security and performance.

### Production -- high security (`always`)

```python
class ProductionConfig(Config):
    SECURIZER = True
    SECURIZER_PLAIN = False   # Reject any plain-text requests
    SECURIZER_MODE = 'always'
```

Use this in environments where regulatory requirements mandate encryption of
all inter-node traffic, even within the same dimension. Note that this has a
measurable CPU cost because every request is encrypted with RSA.

## 5. Verifying Security Mode via Logs

Dimensigon logs securizer decisions at DEBUG level under the `dm` logger.

### Enable debug logging

In `logconfig.yaml` or your logging configuration:

```yaml
loggers:
  dm:
    level: DEBUG
    handlers: [console]
```

### What to look for

```
# auto mode, intra-dimension
DEBUG dm: Securizer skipped: intra-dimension traffic (mode=auto)

# auto mode, cross-dimension
DEBUG dm: Securizer applied: cross-dimension traffic (mode=auto)

# never mode
DEBUG dm: Securizer skipped: mode=never
```

### Verifying with curl

Send a request without the `D-Securizer` header and check the response:

```bash
# If mode=never, you get plain JSON back
curl -s https://node1:5000/api/v1.0/servers \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# If mode=always and SECURIZER_PLAIN=False, a plain request returns 406
curl -s -w "\n%{http_code}\n" https://node1:5000/api/v1.0/servers \
  -H "Authorization: Bearer $TOKEN" \
  -H "D-Securizer: plain"
# Expected: 406 with {"error": "plain data is not allowed"}
```

## 6. Example: Switching from `always` to `auto` for Performance

Suppose you have a five-node cluster running in `always` mode and want to
reduce CPU usage without compromising cross-dimension security.

### Step 1 -- Verify current mode on each node

```bash
ssh node1 'grep SECURIZER_MODE /app/dimensigon/web/config.py'
# SECURIZER_MODE = 'always'
```

### Step 2 -- Update configuration on all nodes

Change the config class or set the environment variable:

```bash
# On each node:
export DM_SECURIZER_MODE=auto
```

Or update the config file:

```python
SECURIZER_MODE = 'auto'
```

### Step 3 -- Restart all nodes

```bash
# If using Docker Compose:
docker-compose restart

# If using systemd:
sudo systemctl restart dimensigon
```

### Step 4 -- Verify the change

Check the logs on each node for the expected debug messages:

```bash
journalctl -u dimensigon --since '5 min ago' | grep -i securizer
# Should see: Securizer skipped: intra-dimension traffic (mode=auto)
```

### Step 5 -- Measure improvement

Compare healthcheck response times before and after:

```bash
# Timed request
time curl -s -o /dev/null -w "%{time_total}" https://node1:5000/health
```

Intra-dimension API calls should be noticeably faster since they skip the
RSA encryption/decryption step.

## Troubleshooting

### Requests fail with 406 after switching to `always`

You set `SECURIZER_PLAIN = False` but some client is sending the
`D-Securizer: plain` header. Either:

- Remove the header from the client, or
- Set `SECURIZER_PLAIN = True` to allow plain requests in `always` mode.

### Cross-dimension traffic is not being encrypted in `auto` mode

Verify that the source server is not already in your local catalog. If it is,
`Dimension.is_same_dimension()` returns `True` and encryption is skipped. If a
server from another dimension was manually added to your catalog, remove it or
use `always` mode.

### Encryption works but signature verification fails

This usually means the RSA key pair has been rotated on one side but not the
other. Ensure both dimensions have exchanged updated public keys.

## Related Features

- [Authentication Tutorial](05-authentication.md) -- JWT-based auth layer
- [Health Endpoint Tutorial](04-health-endpoint.md) -- unauthenticated monitoring
- [Forward/Dispatch Fix](03-forward-dispatch-fix.md) -- request forwarding
- Source code: `dimensigon/web/decorators.py` (`securizer`, `_should_encrypt`)
- Source code: `dimensigon/domain/entities/dimension.py` (`Dimension.is_same_dimension`)
- Source code: `dimensigon/network/encryptation.py` (`pack_msg`, `unpack_msg`)
