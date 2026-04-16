"""Shell action generators for certificate management operations."""

from examples.generators.base_generator import ShellActionGenerator


class CertificatesGenerator(ShellActionGenerator):
    category = "shell.certificates"
    subcategory = "certificates"

    def seeds(self):
        return [
            {
                'name': 'openssl-self-signed',
                'template': {
                    'name': '{service}-self-signed-cert',
                    'action_type': 'SHELL',
                    'code': 'mkdir -p $(dirname {{input.cert_path}}) && openssl req -x509 -newkey rsa:{{input.key_bits}} -keyout {{input.key_path}} -out {{input.cert_path}} -sha256 -days {{input.days}} -nodes -subj "/CN={{input.common_name}}/O={{input.organization}}" 2>&1 && chmod 600 {{input.key_path}} && chmod 644 {{input.cert_path}} && echo "Self-signed certificate created:" && openssl x509 -in {{input.cert_path}} -noout -subject -dates -fingerprint 2>&1 || (echo "FAILED: Certificate generation error" >&2; exit 1)',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'common_name': {'type': 'string', 'description': 'Common Name (CN) for the certificate (e.g. example.com)'},
                            'organization': {'type': 'string', 'description': 'Organization name for the certificate'},
                            'cert_path': {'type': 'string', 'description': 'Output path for the certificate file'},
                            'key_path': {'type': 'string', 'description': 'Output path for the private key file'},
                            'days': {'type': 'integer', 'description': 'Certificate validity in days'},
                            'key_bits': {'type': 'integer', 'description': 'RSA key size in bits (2048, 4096)'},
                        },
                        'required': ['common_name', 'organization', 'cert_path', 'key_path', 'days', 'key_bits'],
                    },
                },
                'params': {'service': ['nginx', 'apache', 'haproxy', 'internal', 'dev', 'test']},
                'prompts': [
                    'Generate a self-signed SSL certificate for {service}',
                    'Create a DM action to create a self-signed cert for {service}',
                    'Write a shell action that generates a self-signed certificate for {service}',
                ],
                'explanation': 'Generates a self-signed SSL certificate and private key for the {service} service.',
                'features': ['schema_variables'],
            },
            {
                'name': 'certbot-letsencrypt',
                'template': {
                    'name': '{service}-certbot-request',
                    'action_type': 'SHELL',
                    'code': 'certbot certonly --non-interactive --agree-tos --email {{input.email}} --{{input.challenge_type}} -d {{input.domain}} --cert-name {{input.cert_name}} 2>&1; RC=$?; if [ $RC -eq 0 ]; then echo "Certificate issued for {{input.domain}}" && ls -la /etc/letsencrypt/live/{{input.cert_name}}/ 2>&1 && openssl x509 -in /etc/letsencrypt/live/{{input.cert_name}}/fullchain.pem -noout -subject -dates 2>&1; elif [ $RC -eq 1 ]; then echo "FAILED: certbot error" >&2; exit 1; else echo "Certificate may already exist, checking..." && certbot certificates --cert-name {{input.cert_name}} 2>&1; fi',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'domain': {'type': 'string', 'description': 'Domain name to request the certificate for'},
                            'email': {'type': 'string', 'description': 'Email for Let\'s Encrypt notifications'},
                            'challenge_type': {'type': 'string', 'description': 'ACME challenge type (webroot, standalone, nginx, apache)'},
                            'cert_name': {'type': 'string', 'description': 'Certificate name for certbot management'},
                        },
                        'required': ['domain', 'email', 'challenge_type', 'cert_name'],
                    },
                },
                'params': {'service': ['webapp', 'api', 'mail', 'portal', 'cdn']},
                'prompts': [
                    'Request a Let\'s Encrypt certificate for the {service} domain',
                    'Create a DM action to issue a certbot certificate for {service}',
                    'Write a shell action that obtains a Let\'s Encrypt cert for {service}',
                ],
                'explanation': 'Requests a Let\'s Encrypt certificate for the {service} domain using certbot with the specified challenge type.',
                'features': ['schema_variables'],
            },
            {
                'name': 'openssl-csr-gen',
                'template': {
                    'name': '{service}-csr-gen',
                    'action_type': 'SHELL',
                    'code': 'mkdir -p $(dirname {{input.key_path}}) && openssl genrsa -out {{input.key_path}} {{input.key_bits}} 2>&1 && chmod 600 {{input.key_path}} && openssl req -new -key {{input.key_path}} -out {{input.csr_path}} -subj "/C={{input.country}}/ST={{input.state}}/L={{input.city}}/O={{input.organization}}/CN={{input.common_name}}" 2>&1 && echo "CSR generated:" && openssl req -in {{input.csr_path}} -noout -subject -verify 2>&1 || (echo "FAILED: CSR generation error" >&2; exit 1)',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'common_name': {'type': 'string', 'description': 'Common Name (CN) for the certificate'},
                            'organization': {'type': 'string', 'description': 'Organization name'},
                            'country': {'type': 'string', 'description': 'Two-letter country code (e.g. US, GB)'},
                            'state': {'type': 'string', 'description': 'State or province name'},
                            'city': {'type': 'string', 'description': 'City or locality name'},
                            'key_path': {'type': 'string', 'description': 'Output path for the private key'},
                            'csr_path': {'type': 'string', 'description': 'Output path for the CSR file'},
                            'key_bits': {'type': 'integer', 'description': 'RSA key size in bits (2048, 4096)'},
                        },
                        'required': ['common_name', 'organization', 'country', 'state', 'city', 'key_path', 'csr_path', 'key_bits'],
                    },
                },
                'params': {'service': ['webapp', 'api', 'mail', 'vpn', 'wildcard']},
                'prompts': [
                    'Generate a CSR and private key for {service}',
                    'Create a DM action to generate an OpenSSL CSR for {service}',
                    'Write a shell action that creates a certificate signing request for {service}',
                ],
                'explanation': 'Generates an RSA private key and Certificate Signing Request (CSR) for the {service} service.',
                'features': ['schema_variables'],
            },
            {
                'name': 'cert-renewal-check',
                'template': {
                    'name': '{service}-cert-renewal',
                    'action_type': 'SHELL',
                    'code': 'if [ ! -f "{{input.cert_path}}" ]; then echo "FAILED: Certificate file not found: {{input.cert_path}}" >&2; exit 1; fi && EXPIRY=$(openssl x509 -in {{input.cert_path}} -noout -enddate 2>/dev/null | cut -d= -f2) && EXPIRY_EPOCH=$(date -d "$EXPIRY" +%s 2>/dev/null || date -j -f "%b %d %T %Y %Z" "$EXPIRY" +%s 2>/dev/null) && NOW_EPOCH=$(date +%s) && DAYS_LEFT=$(( (EXPIRY_EPOCH - NOW_EPOCH) / 86400 )) && SUBJECT=$(openssl x509 -in {{input.cert_path}} -noout -subject 2>/dev/null) && echo "Certificate: {{input.cert_path}}" && echo "Subject: $SUBJECT" && echo "Expires: $EXPIRY ($DAYS_LEFT days remaining)" && if [ "$DAYS_LEFT" -le "{{input.renew_days}}" ]; then echo "ACTION REQUIRED: Certificate needs renewal (threshold: {{input.renew_days}} days)" >&2; exit 1; else echo "OK: Certificate is valid, no renewal needed"; fi',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'cert_path': {'type': 'string', 'description': 'Path to the PEM certificate file to check'},
                            'renew_days': {'type': 'integer', 'description': 'Days before expiry to trigger renewal alert'},
                        },
                        'required': ['cert_path', 'renew_days'],
                    },
                },
                'params': {'service': ['webapp', 'api', 'mail', 'vpn', 'ldap', 'internal']},
                'prompts': [
                    'Check if the {service} certificate needs renewal',
                    'Create a DM action to monitor {service} certificate expiry',
                    'Write a shell action that alerts when {service} cert is nearing expiry',
                ],
                'explanation': 'Checks the {service} certificate expiry date and alerts if renewal is needed within the threshold period.',
                'features': ['schema_variables'],
            },
            {
                'name': 'java-keystore-import',
                'template': {
                    'name': '{service}-jks-import',
                    'action_type': 'SHELL',
                    'code': 'if [ ! -f "{{input.cert_path}}" ]; then echo "FAILED: Certificate not found: {{input.cert_path}}" >&2; exit 1; fi && keytool -importcert -trustcacerts -alias {{input.alias}} -file {{input.cert_path}} -keystore {{input.keystore_path}} -storepass {{input.store_password}} -noprompt 2>&1; RC=$?; if [ $RC -eq 0 ]; then echo "Certificate imported as alias {{input.alias}}" && keytool -list -alias {{input.alias}} -keystore {{input.keystore_path}} -storepass {{input.store_password}} 2>&1; else echo "FAILED: Keystore import error (may already exist)" >&2; keytool -list -alias {{input.alias}} -keystore {{input.keystore_path}} -storepass {{input.store_password}} 2>&1 || true; exit $RC; fi',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'cert_path': {'type': 'string', 'description': 'Path to the certificate file to import'},
                            'keystore_path': {'type': 'string', 'description': 'Path to the Java keystore (JKS) file'},
                            'alias': {'type': 'string', 'description': 'Alias name for the certificate in the keystore'},
                            'store_password': {'type': 'string', 'description': 'Keystore password'},
                        },
                        'required': ['cert_path', 'keystore_path', 'alias', 'store_password'],
                    },
                },
                'params': {'service': ['tomcat', 'spring', 'kafka', 'elasticsearch', 'jenkins']},
                'prompts': [
                    'Import a certificate into the {service} Java keystore',
                    'Create a DM action to add a cert to the {service} JKS',
                    'Write a shell action that imports a certificate into {service} keystore',
                ],
                'explanation': 'Imports a certificate into the {service} Java keystore (JKS) with a specified alias.',
                'features': ['schema_variables'],
                'difficulty': 'intermediate',
            },
            {
                'name': 'pem-to-pkcs12',
                'template': {
                    'name': '{service}-pem-to-p12',
                    'action_type': 'SHELL',
                    'code': 'if [ ! -f "{{input.cert_path}}" ] || [ ! -f "{{input.key_path}}" ]; then echo "FAILED: Certificate or key file not found" >&2; exit 1; fi && CHAIN_OPT="" && if [ -n "{{input.chain_path}}" ] && [ -f "{{input.chain_path}}" ]; then CHAIN_OPT="-certfile {{input.chain_path}}"; fi && openssl pkcs12 -export -out {{input.p12_path}} -inkey {{input.key_path}} -in {{input.cert_path}} $CHAIN_OPT -name {{input.friendly_name}} -passout pass:{{input.export_password}} 2>&1 && chmod 600 {{input.p12_path}} && echo "PKCS12 file created: {{input.p12_path}}" && openssl pkcs12 -in {{input.p12_path}} -passin pass:{{input.export_password}} -nokeys -info 2>&1 | head -5 || (echo "FAILED: PKCS12 conversion error" >&2; exit 1)',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'cert_path': {'type': 'string', 'description': 'Path to the PEM certificate file'},
                            'key_path': {'type': 'string', 'description': 'Path to the PEM private key file'},
                            'chain_path': {'type': 'string', 'description': 'Path to the CA chain file (optional, empty string to skip)'},
                            'p12_path': {'type': 'string', 'description': 'Output path for the PKCS12 file'},
                            'friendly_name': {'type': 'string', 'description': 'Friendly name for the certificate in the PKCS12 bundle'},
                            'export_password': {'type': 'string', 'description': 'Password to protect the PKCS12 file'},
                        },
                        'required': ['cert_path', 'key_path', 'p12_path', 'friendly_name', 'export_password'],
                    },
                },
                'params': {'service': ['webapp', 'iis', 'tomcat', 'exchange', 'loadbalancer']},
                'prompts': [
                    'Convert PEM certificate to PKCS12 for {service}',
                    'Create a DM action to convert PEM to P12 format for {service}',
                    'Write a shell action that creates a PKCS12 bundle for {service}',
                ],
                'explanation': 'Converts PEM certificate and key files to PKCS12 format for the {service} service, optionally including the CA chain.',
                'features': ['schema_variables'],
            },
            {
                'name': 'ca-chain-verify',
                'template': {
                    'name': '{service}-ca-chain-verify',
                    'action_type': 'SHELL',
                    'code': 'if [ ! -f "{{input.cert_path}}" ] || [ ! -f "{{input.ca_bundle}}" ]; then echo "FAILED: Certificate or CA bundle not found" >&2; exit 1; fi && echo "=== Certificate subject ===" && openssl x509 -in {{input.cert_path}} -noout -subject -issuer 2>&1 && echo "=== Chain verification ===" && openssl verify -CAfile {{input.ca_bundle}} {{input.cert_path}} 2>&1; RC=$?; if [ $RC -eq 0 ]; then echo "OK: Certificate chain is valid"; echo "=== Certificate dates ===" && openssl x509 -in {{input.cert_path}} -noout -dates 2>&1; else echo "FAILED: Certificate chain verification failed" >&2; echo "=== Chain details ===" && openssl x509 -in {{input.ca_bundle}} -noout -subject 2>&1; exit 1; fi',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'cert_path': {'type': 'string', 'description': 'Path to the certificate to verify'},
                            'ca_bundle': {'type': 'string', 'description': 'Path to the CA certificate bundle file'},
                        },
                        'required': ['cert_path', 'ca_bundle'],
                    },
                },
                'params': {'service': ['webapp', 'api', 'mail', 'ldap', 'internal']},
                'prompts': [
                    'Verify the CA chain for the {service} certificate',
                    'Create a DM action to validate {service} certificate chain',
                    'Write a shell action that checks {service} cert against its CA bundle',
                ],
                'explanation': 'Verifies the {service} certificate against its CA chain bundle and reports chain validity.',
                'features': ['schema_variables'],
            },
            {
                'name': 'cert-expiry-monitor',
                'template': {
                    'name': '{target}-cert-expiry-monitor',
                    'action_type': 'SHELL',
                    'code': 'CERT_DIR="{{input.cert_dir}}" && WARN_DAYS={{input.warning_days}} && echo "=== Certificate Expiry Report ===" && ISSUES=0 && for CERT in "$CERT_DIR"/*.pem "$CERT_DIR"/*.crt; do if [ ! -f "$CERT" ]; then continue; fi; SUBJECT=$(openssl x509 -in "$CERT" -noout -subject 2>/dev/null | sed "s/subject=//") && EXPIRY=$(openssl x509 -in "$CERT" -noout -enddate 2>/dev/null | cut -d= -f2) && if [ -z "$EXPIRY" ]; then continue; fi; EXPIRY_EPOCH=$(date -d "$EXPIRY" +%s 2>/dev/null || date -j -f "%b %d %T %Y %Z" "$EXPIRY" +%s 2>/dev/null) && NOW_EPOCH=$(date +%s) && DAYS_LEFT=$(( (EXPIRY_EPOCH - NOW_EPOCH) / 86400 )); if [ "$DAYS_LEFT" -le 0 ]; then echo "EXPIRED: $CERT ($SUBJECT) expired $((DAYS_LEFT * -1)) days ago"; ISSUES=$((ISSUES+1)); elif [ "$DAYS_LEFT" -le "$WARN_DAYS" ]; then echo "WARNING: $CERT ($SUBJECT) expires in $DAYS_LEFT days"; ISSUES=$((ISSUES+1)); else echo "OK: $CERT ($SUBJECT) expires in $DAYS_LEFT days"; fi; done && echo "=== Summary: $ISSUES issue(s) found ===" && if [ "$ISSUES" -gt 0 ]; then exit 1; fi',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'cert_dir': {'type': 'string', 'description': 'Directory containing certificate files to monitor'},
                            'warning_days': {'type': 'integer', 'description': 'Days before expiry to flag as warning'},
                        },
                        'required': ['cert_dir', 'warning_days'],
                    },
                },
                'params': {'target': ['server', 'infrastructure', 'production', 'cluster']},
                'prompts': [
                    'Monitor all certificate expiry dates on the {target}',
                    'Create a DM action to scan {target} certificates for upcoming expirations',
                    'Write a shell action that reports certificate expiry status across {target}',
                ],
                'explanation': 'Scans a directory for certificates on the {target} and reports expiry status for each, flagging those nearing expiration.',
                'features': ['schema_variables'],
            },
            {
                'name': 'ocsp-stapling-nginx',
                'template': {
                    'name': '{domain}-ocsp-stapling',
                    'action_type': 'SHELL',
                    'code': 'NGINX_CONF="{{input.nginx_conf}}" && cp "$NGINX_CONF" "${NGINX_CONF}.bak.$(date +%s)" && if grep -q "ssl_stapling" "$NGINX_CONF"; then echo "OCSP stapling directives already present in $NGINX_CONF"; else cat >> "$NGINX_CONF" <<OCSP\n\n    # OCSP Stapling\n    ssl_stapling on;\n    ssl_stapling_verify on;\n    ssl_trusted_certificate {{input.ca_chain_path}};\n    resolver {{input.resolver}} valid=300s;\n    resolver_timeout 5s;\nOCSP\nfi && nginx -t 2>&1 && systemctl reload nginx && echo "OCSP stapling configured in $NGINX_CONF" && echo "=== Verifying OCSP stapling ===" && sleep 2 && echo | openssl s_client -servername {{input.server_name}} -connect {{input.server_name}}:443 -status 2>/dev/null | grep -A 2 "OCSP Response" || echo "Note: OCSP response may take a moment to cache"',
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'nginx_conf': {'type': 'string', 'description': 'Path to the nginx server block config file'},
                            'ca_chain_path': {'type': 'string', 'description': 'Path to the CA chain/trusted certificate file'},
                            'resolver': {'type': 'string', 'description': 'DNS resolver for OCSP (e.g. 8.8.8.8 8.8.4.4)'},
                            'server_name': {'type': 'string', 'description': 'Server hostname for OCSP verification'},
                        },
                        'required': ['nginx_conf', 'ca_chain_path', 'resolver', 'server_name'],
                    },
                },
                'params': {'domain': ['webapp', 'api', 'portal', 'app', 'main']},
                'prompts': [
                    'Configure OCSP stapling in nginx for the {domain} site',
                    'Create a DM action to enable OCSP stapling for {domain} in nginx',
                    'Write a shell action that sets up OCSP stapling for the {domain} nginx config',
                ],
                'explanation': 'Configures OCSP stapling in the nginx server block for the {domain} site to improve TLS handshake performance.',
                'features': ['schema_variables'],
                'difficulty': 'intermediate',
            },
        ]


def get_generators():
    return [CertificatesGenerator()]
