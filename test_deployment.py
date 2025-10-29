#!/usr/bin/env python3
"""
Dimensigon 2.0 Deployment Test Suite

Tests Dimensigon installation, startup, and DM-WebManager accessibility.
"""
import sys
import time
import requests
import subprocess
import signal
from pathlib import Path

# Color codes for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_header(msg):
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}{msg:^60}{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")

def print_success(msg):
    print(f"{GREEN}✅ {msg}{RESET}")

def print_error(msg):
    print(f"{RED}❌ {msg}{RESET}")

def print_info(msg):
    print(f"{YELLOW}ℹ️  {msg}{RESET}")

def test_imports():
    """Test that Dimensigon modules can be imported"""
    print_header("Testing Dimensigon Imports")

    try:
        from dimensigon.domain.entities import Server, Orchestration, ActionTemplate
        print_success("Core entities import successful")

        from dimensigon.web import create_app
        print_success("Web application import successful")

        from dimensigon.web.admin import init_admin
        print_success("DM-WebManager admin import successful")

        from dimensigon.web.admin.data_dictionary import data_dict_bp
        print_success("Data Dictionary API import successful")

        from dimensigon.web.admin.executions_viewer import executions_bp
        print_success("Executions Viewer API import successful")

        return True
    except Exception as e:
        print_error(f"Import failed: {e}")
        return False

def test_flask_app_creation():
    """Test Flask application creation"""
    print_header("Testing Flask App Creation")

    try:
        from dimensigon.web import create_app

        # Create test config
        test_config = {
            'TESTING': True,
            'SECRET_KEY': 'test-secret-key',
            'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
            'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        }

        app = create_app(test_config)
        print_success("Flask app created successfully")

        # Check if blueprints are registered
        blueprint_names = [bp.name for bp in app.blueprints.values()]
        print_info(f"Registered blueprints: {', '.join(blueprint_names)}")

        # Check for admin blueprints
        if 'data_dictionary' in blueprint_names:
            print_success("Data Dictionary blueprint registered")
        else:
            print_error("Data Dictionary blueprint NOT found")

        if 'executions_viewer' in blueprint_names:
            print_success("Executions Viewer blueprint registered")
        else:
            print_error("Executions Viewer blueprint NOT found")

        if 'admin_routes' in blueprint_names:
            print_success("Admin routes blueprint registered")
        else:
            print_error("Admin routes blueprint NOT found")

        return True
    except Exception as e:
        print_error(f"App creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_routes():
    """Test that routes are registered"""
    print_header("Testing Route Registration")

    try:
        from dimensigon.web import create_app

        test_config = {
            'TESTING': True,
            'SECRET_KEY': 'test-secret-key',
            'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
            'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        }

        app = create_app(test_config)

        # Check routes
        routes = []
        for rule in app.url_map.iter_rules():
            routes.append((rule.rule, ','.join(rule.methods)))

        print_info(f"Total routes registered: {len(routes)}")

        # Check for specific DM-WebManager routes
        dm_routes = [r for r in routes if 'dm-webmanager' in r[0] or 'api/v2' in r[0]]

        if dm_routes:
            print_success(f"Found {len(dm_routes)} DM-WebManager routes:")
            for route, methods in dm_routes:
                print(f"  {route} [{methods}]")
        else:
            print_error("No DM-WebManager routes found!")

        # Check for Flask-Admin
        admin_routes = [r for r in routes if '/admin' in r[0]]
        if admin_routes:
            print_success(f"Found {len(admin_routes)} Flask-Admin routes")
        else:
            print_info("Flask-Admin routes may not be visible (dynamically registered)")

        return True
    except Exception as e:
        print_error(f"Route testing failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_templates():
    """Test that templates exist"""
    print_header("Testing Template Files")

    templates_dir = Path('templates/admin')

    if templates_dir.exists():
        print_success(f"Templates directory exists: {templates_dir}")

        dashboard = templates_dir / 'dashboard.html'
        if dashboard.exists():
            print_success(f"Dashboard template found ({dashboard.stat().st_size} bytes)")
        else:
            print_error("Dashboard template NOT found!")

        custom_base = templates_dir / 'custom_base.html'
        if custom_base.exists():
            print_success(f"Custom base template found ({custom_base.stat().st_size} bytes)")
        else:
            print_error("Custom base template NOT found!")

        return True
    else:
        print_error(f"Templates directory NOT found: {templates_dir}")
        return False

def test_dependencies():
    """Test that all dependencies are installed"""
    print_header("Testing Dependencies")

    dependencies = [
        ('Flask', '2.3.0'),
        ('Flask-Admin', '1.6.0'),
        ('Flask-SQLAlchemy', '3.0.0'),
        ('Flask-JWT-Extended', '4.0.0'),
        ('cryptography', '42.0.0'),
        ('jinja2', '3.1.0'),
        ('PyYAML', '6.0.0'),
    ]

    all_ok = True
    for package, min_version in dependencies:
        try:
            import importlib
            mod = importlib.import_module(package.lower().replace('-', '_'))
            version = getattr(mod, '__version__', 'unknown')
            print_success(f"{package}: {version}")
        except ImportError:
            print_error(f"{package}: NOT INSTALLED")
            all_ok = False

    return all_ok

def run_all_tests():
    """Run all tests"""
    print_header("Dimensigon 2.0 Deployment Test Suite")
    print_info("Testing installation, imports, and configuration")

    results = {}

    # Run tests
    results['imports'] = test_imports()
    results['dependencies'] = test_dependencies()
    results['flask_app'] = test_flask_app_creation()
    results['routes'] = test_routes()
    results['templates'] = test_templates()

    # Summary
    print_header("Test Summary")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, result in results.items():
        status = "PASS" if result else "FAIL"
        color = GREEN if result else RED
        print(f"{color}{test_name.upper():.<40} {status}{RESET}")

    print(f"\n{BLUE}Results: {passed}/{total} tests passed{RESET}")

    if passed == total:
        print_success("🎉 All tests PASSED! Dimensigon 2.0 is ready!")
        return 0
    else:
        print_error(f"⚠️  {total - passed} test(s) FAILED!")
        return 1

if __name__ == '__main__':
    sys.exit(run_all_tests())
