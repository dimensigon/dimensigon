"""Monitoring Python action generators - 10 seeds for system metrics, health checks, Prometheus."""

from examples.generators.base_generator import PythonActionGenerator


class MonitoringGenerator(PythonActionGenerator):
    category = "python.monitoring"
    subcategory = "monitoring"

    def seeds(self):
        return [
            {
                'name': 'cpu-usage-check',
                'template': {
                    'name': 'Check CPU usage',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import sys\n'
                        'import os\n\n'
                        'threshold = float("{{input.threshold}}" or "80")\n\n'
                        'def get_cpu_usage():\n'
                        '    with open("/proc/stat", "r") as f:\n'
                        '        line = f.readline()\n'
                        '    parts = line.split()\n'
                        '    idle = int(parts[4])\n'
                        '    total = sum(int(p) for p in parts[1:])\n'
                        '    return idle, total\n\n'
                        'import time\n'
                        'idle1, total1 = get_cpu_usage()\n'
                        'time.sleep(1)\n'
                        'idle2, total2 = get_cpu_usage()\n\n'
                        'idle_delta = idle2 - idle1\n'
                        'total_delta = total2 - total1\n'
                        'usage = (1.0 - idle_delta / total_delta) * 100.0 if total_delta > 0 else 0.0\n'
                        'cpu_count = os.cpu_count() or 1\n\n'
                        'result = {{\n'
                        '    "cpu_percent": round(usage, 2),\n'
                        '    "cpu_count": cpu_count,\n'
                        '    "threshold": threshold,\n'
                        '    "status": "critical" if usage > threshold else "ok",\n'
                        '}}\n'
                        'print(json.dumps(result))\n'
                        'if usage > threshold:\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'threshold': {'type': 'string', 'description': 'CPU usage percent threshold (default 80)'},
                        },
                        'required': [],
                    },
                },
                'params': {'threshold_level': ['70', '80', '90', '95']},
                'prompts': [
                    'Create a Python action to check if CPU usage exceeds {threshold_level}%',
                    'Python script that monitors CPU utilization with a {threshold_level}% threshold',
                ],
                'explanation': 'Python action that reads /proc/stat to compute CPU usage percentage and alerts if it exceeds the threshold.',
            },
            {
                'name': 'memory-usage-check',
                'template': {
                    'name': 'Check memory usage',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import sys\n\n'
                        'threshold = float("{{input.threshold}}" or "80")\n\n'
                        'meminfo = {{}}\n'
                        'with open("/proc/meminfo", "r") as f:\n'
                        '    for line in f:\n'
                        '        parts = line.split()\n'
                        '        key = parts[0].rstrip(":")\n'
                        '        meminfo[key] = int(parts[1])\n\n'
                        'total = meminfo.get("MemTotal", 0)\n'
                        'available = meminfo.get("MemAvailable", 0)\n'
                        'used = total - available\n'
                        'pct = (used / total) * 100.0 if total > 0 else 0.0\n\n'
                        'result = {{\n'
                        '    "total_mb": round(total / 1024, 1),\n'
                        '    "used_mb": round(used / 1024, 1),\n'
                        '    "available_mb": round(available / 1024, 1),\n'
                        '    "percent_used": round(pct, 2),\n'
                        '    "threshold": threshold,\n'
                        '    "status": "critical" if pct > threshold else "ok",\n'
                        '}}\n'
                        'print(json.dumps(result))\n'
                        'if pct > threshold:\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'threshold': {'type': 'string', 'description': 'Memory usage percent threshold (default 80)'},
                        },
                        'required': [],
                    },
                },
                'params': {'threshold_level': ['70', '80', '90', '95']},
                'prompts': [
                    'Create a Python action to check if memory usage exceeds {threshold_level}%',
                    'Python script that monitors RAM utilization with a {threshold_level}% threshold',
                ],
                'explanation': 'Python action that reads /proc/meminfo to compute memory usage and alerts if it exceeds the threshold.',
            },
            {
                'name': 'disk-io-metrics',
                'template': {
                    'name': 'Collect disk I/O metrics',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import sys\n\n'
                        'device = "{{input.device}}" or "sda"\n\n'
                        'def read_diskstats(dev):\n'
                        '    with open("/proc/diskstats", "r") as f:\n'
                        '        for line in f:\n'
                        '            parts = line.split()\n'
                        '            if len(parts) >= 14 and parts[2] == dev:\n'
                        '                return {{\n'
                        '                    "reads_completed": int(parts[3]),\n'
                        '                    "reads_merged": int(parts[4]),\n'
                        '                    "sectors_read": int(parts[5]),\n'
                        '                    "read_time_ms": int(parts[6]),\n'
                        '                    "writes_completed": int(parts[7]),\n'
                        '                    "writes_merged": int(parts[8]),\n'
                        '                    "sectors_written": int(parts[9]),\n'
                        '                    "write_time_ms": int(parts[10]),\n'
                        '                    "io_in_progress": int(parts[11]),\n'
                        '                    "io_time_ms": int(parts[12]),\n'
                        '                }}\n'
                        '    return None\n\n'
                        'stats = read_diskstats(device)\n'
                        'if stats is None:\n'
                        '    print(json.dumps({{"status": "error", "message": f"Device {{device}} not found"}}))\n'
                        '    sys.exit(1)\n\n'
                        'stats["device"] = device\n'
                        'stats["status"] = "ok"\n'
                        'print(json.dumps(stats))\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'device': {'type': 'string', 'description': 'Disk device name (default sda)'},
                        },
                        'required': [],
                    },
                },
                'params': {'device': ['sda', 'sdb', 'nvme0n1', 'vda', 'xvda']},
                'prompts': [
                    'Create a Python action to collect disk I/O metrics for {device}',
                    'Python script that reads I/O statistics for disk device {device}',
                ],
                'explanation': 'Python action that reads /proc/diskstats to collect I/O metrics for disk device {device}.',
            },
            {
                'name': 'process-count',
                'template': {
                    'name': 'Count {service} processes',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import os\n'
                        'import sys\n\n'
                        'process_name = "{{input.process_name}}"\n'
                        'min_count = int("{{input.min_count}}" or "1")\n\n'
                        'count = 0\n'
                        'pids = []\n'
                        'for pid in os.listdir("/proc"):\n'
                        '    if not pid.isdigit():\n'
                        '        continue\n'
                        '    try:\n'
                        '        with open(f"/proc/{{pid}}/comm", "r") as f:\n'
                        '            comm = f.read().strip()\n'
                        '        if process_name in comm:\n'
                        '            count += 1\n'
                        '            pids.append(int(pid))\n'
                        '    except (IOError, OSError):\n'
                        '        continue\n\n'
                        'result = {{\n'
                        '    "process": process_name,\n'
                        '    "count": count,\n'
                        '    "pids": pids[:20],\n'
                        '    "min_expected": min_count,\n'
                        '    "status": "ok" if count >= min_count else "critical",\n'
                        '}}\n'
                        'print(json.dumps(result))\n'
                        'if count < min_count:\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'process_name': {'type': 'string', 'description': 'Process name to search for'},
                            'min_count': {'type': 'string', 'description': 'Minimum expected process count (default 1)'},
                        },
                        'required': ['process_name'],
                    },
                },
                'params': {'service': ['nginx', 'postgres', 'redis', 'java', 'python', 'node']},
                'prompts': [
                    'Create a Python action to count running {service} processes',
                    'Python script that checks the number of {service} processes and alerts if below minimum',
                ],
                'explanation': 'Python action that counts running {service} processes by scanning /proc and alerts if count is below minimum.',
            },
            {
                'name': 'open-file-descriptors',
                'template': {
                    'name': 'Check open file descriptors',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import sys\n\n'
                        'threshold_pct = float("{{input.threshold_pct}}" or "80")\n\n'
                        'with open("/proc/sys/fs/file-nr", "r") as f:\n'
                        '    parts = f.read().strip().split()\n'
                        '    allocated = int(parts[0])\n'
                        '    free = int(parts[1])\n'
                        '    maximum = int(parts[2])\n\n'
                        'used = allocated - free\n'
                        'pct = (used / maximum) * 100.0 if maximum > 0 else 0.0\n\n'
                        'result = {{\n'
                        '    "allocated": allocated,\n'
                        '    "free": free,\n'
                        '    "used": used,\n'
                        '    "maximum": maximum,\n'
                        '    "percent_used": round(pct, 2),\n'
                        '    "threshold": threshold_pct,\n'
                        '    "status": "critical" if pct > threshold_pct else "ok",\n'
                        '}}\n'
                        'print(json.dumps(result))\n'
                        'if pct > threshold_pct:\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'threshold_pct': {'type': 'string', 'description': 'Usage threshold percentage (default 80)'},
                        },
                        'required': [],
                    },
                },
                'params': {'threshold': ['70', '80', '90', '95']},
                'prompts': [
                    'Create a Python action to check open file descriptor usage against {threshold}% threshold',
                    'Python script that monitors system file descriptor usage',
                ],
                'explanation': 'Python action that reads /proc/sys/fs/file-nr to check system-wide open file descriptor usage.',
            },
            {
                'name': 'network-connections-count',
                'template': {
                    'name': 'Count network connections',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import sys\n\n'
                        'port = "{{input.port}}"\n'
                        'threshold = int("{{input.threshold}}" or "1000")\n\n'
                        'states = {{}}\n'
                        'total = 0\n'
                        'tcp_state_map = {{\n'
                        '    "01": "ESTABLISHED", "02": "SYN_SENT", "03": "SYN_RECV",\n'
                        '    "04": "FIN_WAIT1", "05": "FIN_WAIT2", "06": "TIME_WAIT",\n'
                        '    "07": "CLOSE", "08": "CLOSE_WAIT", "09": "LAST_ACK",\n'
                        '    "0A": "LISTEN", "0B": "CLOSING",\n'
                        '}}\n\n'
                        'try:\n'
                        '    with open("/proc/net/tcp", "r") as f:\n'
                        '        lines = f.readlines()[1:]  # skip header\n'
                        '    for line in lines:\n'
                        '        parts = line.split()\n'
                        '        local_port = int(parts[1].split(":")[1], 16)\n'
                        '        state_code = parts[3]\n'
                        '        if port and str(local_port) != port:\n'
                        '            continue\n'
                        '        state = tcp_state_map.get(state_code, "UNKNOWN")\n'
                        '        states[state] = states.get(state, 0) + 1\n'
                        '        total += 1\n'
                        'except Exception as e:\n'
                        '    print(json.dumps({{"status": "error", "message": str(e)}}))\n'
                        '    sys.exit(1)\n\n'
                        'result = {{\n'
                        '    "total": total,\n'
                        '    "by_state": states,\n'
                        '    "threshold": threshold,\n'
                        '    "status": "critical" if total > threshold else "ok",\n'
                        '}}\n'
                        'print(json.dumps(result))\n'
                        'if total > threshold:\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'port': {'type': 'string', 'description': 'Filter by local port number (optional)'},
                            'threshold': {'type': 'string', 'description': 'Max connection count threshold (default 1000)'},
                        },
                        'required': [],
                    },
                },
                'params': {'port': ['80', '443', '8080', '5432', '3306']},
                'prompts': [
                    'Create a Python action to count TCP connections on port {port}',
                    'Python script that monitors network connection count on port {port}',
                ],
                'explanation': 'Python action that reads /proc/net/tcp to count TCP connections by state, optionally filtering by port {port}.',
            },
            {
                'name': 'system-uptime',
                'template': {
                    'name': 'Check system uptime',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import sys\n\n'
                        'min_uptime_hours = float("{{input.min_uptime_hours}}" or "0")\n\n'
                        'with open("/proc/uptime", "r") as f:\n'
                        '    uptime_seconds = float(f.read().split()[0])\n\n'
                        'days = int(uptime_seconds // 86400)\n'
                        'hours = int((uptime_seconds % 86400) // 3600)\n'
                        'minutes = int((uptime_seconds % 3600) // 60)\n'
                        'uptime_hours = uptime_seconds / 3600.0\n\n'
                        'result = {{\n'
                        '    "uptime_seconds": round(uptime_seconds, 1),\n'
                        '    "uptime_human": f"{{days}}d {{hours}}h {{minutes}}m",\n'
                        '    "days": days,\n'
                        '    "hours": hours,\n'
                        '    "minutes": minutes,\n'
                        '    "status": "ok" if uptime_hours >= min_uptime_hours else "recently_rebooted",\n'
                        '}}\n'
                        'print(json.dumps(result))\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'min_uptime_hours': {'type': 'string', 'description': 'Minimum expected uptime in hours (default 0)'},
                        },
                        'required': [],
                    },
                },
                'params': {'context': ['routine', 'post-deployment', 'incident', 'maintenance']},
                'prompts': [
                    'Create a Python action to check system uptime during {context} monitoring',
                    'Python script that reads system uptime for {context} health check',
                ],
                'explanation': 'Python action that reads /proc/uptime and reports system uptime in human-readable format for {context} monitoring.',
            },
            {
                'name': 'load-average',
                'template': {
                    'name': 'Check system load average',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import os\n'
                        'import sys\n\n'
                        'threshold_multiplier = float("{{input.threshold_multiplier}}" or "1.5")\n\n'
                        'with open("/proc/loadavg", "r") as f:\n'
                        '    parts = f.read().split()\n\n'
                        'load_1 = float(parts[0])\n'
                        'load_5 = float(parts[1])\n'
                        'load_15 = float(parts[2])\n'
                        'cpu_count = os.cpu_count() or 1\n'
                        'threshold = cpu_count * threshold_multiplier\n\n'
                        'result = {{\n'
                        '    "load_1min": load_1,\n'
                        '    "load_5min": load_5,\n'
                        '    "load_15min": load_15,\n'
                        '    "cpu_count": cpu_count,\n'
                        '    "threshold": threshold,\n'
                        '    "status": "critical" if load_1 > threshold else "ok",\n'
                        '}}\n'
                        'print(json.dumps(result))\n'
                        'if load_1 > threshold:\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'threshold_multiplier': {'type': 'string', 'description': 'Load threshold as CPU count multiplier (default 1.5)'},
                        },
                        'required': [],
                    },
                },
                'params': {'multiplier': ['1.0', '1.5', '2.0', '3.0']},
                'prompts': [
                    'Create a Python action to check load average with {multiplier}x CPU threshold',
                    'Python script that monitors system load average against {multiplier}x CPU count',
                ],
                'explanation': 'Python action that reads /proc/loadavg and alerts if 1-minute load exceeds {multiplier}x the CPU count.',
            },
            {
                'name': 'temperature-sensor',
                'template': {
                    'name': 'Read temperature sensors',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import os\n'
                        'import glob\n'
                        'import sys\n\n'
                        'threshold_c = float("{{input.threshold_c}}" or "85")\n\n'
                        'sensors = []\n'
                        'thermal_zones = glob.glob("/sys/class/thermal/thermal_zone*/temp")\n\n'
                        'for path in sorted(thermal_zones):\n'
                        '    zone = os.path.basename(os.path.dirname(path))\n'
                        '    type_path = os.path.join(os.path.dirname(path), "type")\n'
                        '    try:\n'
                        '        with open(path, "r") as f:\n'
                        '            temp_mc = int(f.read().strip())\n'
                        '        temp_c = temp_mc / 1000.0\n'
                        '        sensor_type = "unknown"\n'
                        '        if os.path.isfile(type_path):\n'
                        '            with open(type_path, "r") as f:\n'
                        '                sensor_type = f.read().strip()\n'
                        '        sensors.append({{"zone": zone, "type": sensor_type, "temp_c": temp_c}})\n'
                        '    except Exception:\n'
                        '        continue\n\n'
                        'max_temp = max((s["temp_c"] for s in sensors), default=0.0)\n'
                        'result = {{\n'
                        '    "sensors": sensors,\n'
                        '    "max_temp_c": max_temp,\n'
                        '    "threshold_c": threshold_c,\n'
                        '    "status": "critical" if max_temp > threshold_c else "ok",\n'
                        '}}\n'
                        'print(json.dumps(result))\n'
                        'if max_temp > threshold_c:\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'threshold_c': {'type': 'string', 'description': 'Temperature threshold in Celsius (default 85)'},
                        },
                        'required': [],
                    },
                },
                'params': {'threshold': ['75', '80', '85', '90', '95']},
                'prompts': [
                    'Create a Python action to check thermal sensors against {threshold}C threshold',
                    'Python script that reads CPU/system temperature and alerts above {threshold}C',
                ],
                'explanation': 'Python action that reads thermal zone sensors from /sys/class/thermal and alerts if any exceed the temperature threshold.',
            },
            {
                'name': 'prometheus-pushgateway',
                'template': {
                    'name': 'Push metric to Prometheus',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import urllib.request\n'
                        'import sys\n\n'
                        'pushgateway_url = "{{input.pushgateway_url}}"\n'
                        'job_name = "{{input.job_name}}"\n'
                        'metric_name = "{{input.metric_name}}"\n'
                        'metric_value = "{{input.metric_value}}"\n'
                        'metric_help = "{{input.metric_help}}" or "Custom metric"\n'
                        'metric_type = "{{input.metric_type}}" or "gauge"\n\n'
                        'body = (\n'
                        '    f"# HELP {{metric_name}} {{metric_help}}\\n"\n'
                        '    f"# TYPE {{metric_name}} {{metric_type}}\\n"\n'
                        '    f"{{metric_name}} {{metric_value}}\\n"\n'
                        ')\n\n'
                        'url = f"{{pushgateway_url}}/metrics/job/{{job_name}}"\n'
                        'req = urllib.request.Request(url, data=body.encode("utf-8"), method="POST")\n'
                        'req.add_header("Content-Type", "text/plain")\n'
                        'try:\n'
                        '    resp = urllib.request.urlopen(req, timeout=10)\n'
                        '    print(json.dumps({{\n'
                        '        "status": "pushed",\n'
                        '        "metric": metric_name,\n'
                        '        "value": metric_value,\n'
                        '        "job": job_name,\n'
                        '    }}))\n'
                        'except Exception as e:\n'
                        '    print(json.dumps({{"status": "error", "message": str(e)}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'pushgateway_url': {'type': 'string', 'description': 'Prometheus Pushgateway base URL'},
                            'job_name': {'type': 'string', 'description': 'Job label for the metric'},
                            'metric_name': {'type': 'string', 'description': 'Metric name'},
                            'metric_value': {'type': 'string', 'description': 'Metric value'},
                            'metric_help': {'type': 'string', 'description': 'Metric help text (optional)'},
                            'metric_type': {'type': 'string', 'description': 'Metric type: gauge, counter (default gauge)'},
                        },
                        'required': ['pushgateway_url', 'job_name', 'metric_name', 'metric_value'],
                    },
                },
                'params': {'metric_type': ['gauge', 'counter']},
                'prompts': [
                    'Create a Python action to push a {metric_type} metric to Prometheus Pushgateway',
                    'Python script that sends a custom {metric_type} metric to Prometheus',
                ],
                'explanation': 'Python action that pushes a custom {metric_type} metric to Prometheus Pushgateway for monitoring.',
            },
            {
                'name': 'log-tail-pattern',
                'template': {
                    'name': 'Tail log file for {service} patterns',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import re\n'
                        'import os\n'
                        'import sys\n\n'
                        'log_file = "{{input.log_file}}"\n'
                        'pattern = "{{input.pattern}}"\n'
                        'max_lines = int("{{input.max_lines}}" or "1000")\n\n'
                        'if not os.path.isfile(log_file):\n'
                        '    print(json.dumps({{"status": "error", "message": f"Log file not found: {{log_file}}"}}))\n'
                        '    sys.exit(1)\n\n'
                        'try:\n'
                        '    regex = re.compile(pattern)\n'
                        'except re.error as e:\n'
                        '    print(json.dumps({{"status": "error", "message": f"Invalid regex: {{e}}"}}))\n'
                        '    sys.exit(1)\n\n'
                        'matches = []\n'
                        'with open(log_file, "r", errors="replace") as f:\n'
                        '    lines = f.readlines()[-max_lines:]\n'
                        '    for i, line in enumerate(lines):\n'
                        '        if regex.search(line):\n'
                        '            matches.append(line.strip())\n\n'
                        'result = {{\n'
                        '    "status": "ok",\n'
                        '    "log_file": log_file,\n'
                        '    "pattern": pattern,\n'
                        '    "lines_scanned": len(lines),\n'
                        '    "matches_found": len(matches),\n'
                        '    "recent_matches": matches[-20:],\n'
                        '}}\n'
                        'print(json.dumps(result))\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'log_file': {'type': 'string', 'description': 'Path to the log file to scan'},
                            'pattern': {'type': 'string', 'description': 'Regex pattern to match in log lines'},
                            'max_lines': {'type': 'string', 'description': 'Maximum number of recent lines to scan (default 1000)'},
                        },
                        'required': ['log_file', 'pattern'],
                    },
                },
                'params': {'service': ['nginx', 'apache', 'application', 'syslog', 'auth']},
                'prompts': [
                    'Create a Python action to scan {service} log file for pattern matches',
                    'Python script that tails a {service} log and finds lines matching a regex',
                ],
                'explanation': 'Python action that scans the tail of a {service} log file for lines matching a regex pattern and returns matches.',
            },
            {
                'name': 'systemd-journal-query',
                'template': {
                    'name': 'Query systemd journal for {service}',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import subprocess\n'
                        'import sys\n\n'
                        'unit = "{{input.unit}}"\n'
                        'since = "{{input.since}}" or "1 hour ago"\n'
                        'priority = "{{input.priority}}" or "err"\n'
                        'max_entries = int("{{input.max_entries}}" or "50")\n\n'
                        'try:\n'
                        '    cmd = [\n'
                        '        "journalctl", "-u", unit,\n'
                        '        "--since", since,\n'
                        '        "--priority", priority,\n'
                        '        "--no-pager", "-o", "json",\n'
                        '        "-n", str(max_entries),\n'
                        '    ]\n'
                        '    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)\n'
                        '    entries = []\n'
                        '    for line in result.stdout.strip().split("\\n"):\n'
                        '        if line.strip():\n'
                        '            try:\n'
                        '                entries.append(json.loads(line))\n'
                        '            except json.JSONDecodeError:\n'
                        '                continue\n'
                        '    summary = {{\n'
                        '        "status": "ok",\n'
                        '        "unit": unit,\n'
                        '        "since": since,\n'
                        '        "priority": priority,\n'
                        '        "entry_count": len(entries),\n'
                        '        "messages": [e.get("MESSAGE", "") for e in entries[-20:]],\n'
                        '    }}\n'
                        '    print(json.dumps(summary))\n'
                        'except subprocess.TimeoutExpired:\n'
                        '    print(json.dumps({{"status": "error", "message": "journalctl timed out"}}))\n'
                        '    sys.exit(1)\n'
                        'except Exception as e:\n'
                        '    print(json.dumps({{"status": "error", "message": str(e)}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'unit': {'type': 'string', 'description': 'Systemd unit name to query'},
                            'since': {'type': 'string', 'description': 'Time range (default "1 hour ago")'},
                            'priority': {'type': 'string', 'description': 'Minimum priority level (default "err")'},
                            'max_entries': {'type': 'string', 'description': 'Maximum entries to return (default 50)'},
                        },
                        'required': ['unit'],
                    },
                },
                'params': {'service': ['nginx', 'postgresql', 'docker', 'sshd', 'redis']},
                'prompts': [
                    'Create a Python action to query systemd journal entries for {service}',
                    'Python script that reads {service} journal logs filtered by priority',
                ],
                'explanation': 'Python action that queries the systemd journal for {service} entries filtered by time range and priority level.',
            },
            {
                'name': 'container-resource-usage',
                'template': {
                    'name': 'Monitor {service} container resources',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import subprocess\n'
                        'import sys\n\n'
                        'container = "{{input.container_name}}"\n'
                        'cpu_threshold = float("{{input.cpu_threshold}}" or "80")\n'
                        'mem_threshold = float("{{input.mem_threshold}}" or "80")\n\n'
                        'try:\n'
                        '    result = subprocess.run(\n'
                        '        ["docker", "stats", "--no-stream", "--format",\n'
                        '         "{{.CPUPerc}}|{{.MemPerc}}|{{.MemUsage}}|{{.NetIO}}|{{.BlockIO}}|{{.PIDs}}",\n'
                        '         container],\n'
                        '        capture_output=True, text=True, timeout=15\n'
                        '    )\n'
                        '    if result.returncode != 0:\n'
                        '        print(json.dumps({{"status": "error", "message": result.stderr.strip()}}))\n'
                        '        sys.exit(1)\n'
                        '    parts = result.stdout.strip().split("|")\n'
                        '    cpu_pct = float(parts[0].strip().rstrip("%"))\n'
                        '    mem_pct = float(parts[1].strip().rstrip("%"))\n'
                        '    status = "ok"\n'
                        '    if cpu_pct > cpu_threshold or mem_pct > mem_threshold:\n'
                        '        status = "warning"\n'
                        '    output = {{\n'
                        '        "status": status,\n'
                        '        "container": container,\n'
                        '        "cpu_percent": cpu_pct,\n'
                        '        "mem_percent": mem_pct,\n'
                        '        "mem_usage": parts[2].strip(),\n'
                        '        "net_io": parts[3].strip(),\n'
                        '        "block_io": parts[4].strip(),\n'
                        '        "pids": parts[5].strip(),\n'
                        '    }}\n'
                        '    print(json.dumps(output))\n'
                        '    if status == "warning":\n'
                        '        sys.exit(1)\n'
                        'except Exception as e:\n'
                        '    print(json.dumps({{"status": "error", "message": str(e)}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'container_name': {'type': 'string', 'description': 'Docker container name to monitor'},
                            'cpu_threshold': {'type': 'string', 'description': 'CPU usage warning threshold percent (default 80)'},
                            'mem_threshold': {'type': 'string', 'description': 'Memory usage warning threshold percent (default 80)'},
                        },
                        'required': ['container_name'],
                    },
                },
                'params': {'service': ['webapp', 'api', 'postgres', 'redis', 'worker']},
                'prompts': [
                    'Create a Python action to monitor {service} Docker container resource usage',
                    'Python script that checks {service} container CPU and memory against thresholds',
                ],
                'explanation': 'Python action that monitors {service} Docker container CPU, memory, network, and block I/O usage with threshold alerting.',
            },
            {
                'name': 'network-latency-test',
                'template': {
                    'name': 'Test network latency to {service}',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import socket\n'
                        'import time\n'
                        'import sys\n\n'
                        'host = "{{input.host}}"\n'
                        'port = int("{{input.port}}")\n'
                        'count = int("{{input.count}}" or "5")\n'
                        'threshold_ms = float("{{input.threshold_ms}}" or "100")\n\n'
                        'latencies = []\n'
                        'failures = 0\n\n'
                        'for i in range(count):\n'
                        '    try:\n'
                        '        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n'
                        '        sock.settimeout(5)\n'
                        '        start = time.time()\n'
                        '        sock.connect((host, port))\n'
                        '        elapsed_ms = (time.time() - start) * 1000\n'
                        '        sock.close()\n'
                        '        latencies.append(round(elapsed_ms, 2))\n'
                        '    except Exception:\n'
                        '        failures += 1\n\n'
                        'if not latencies:\n'
                        '    print(json.dumps({{"status": "error", "message": "All connection attempts failed"}}))\n'
                        '    sys.exit(1)\n\n'
                        'avg = round(sum(latencies) / len(latencies), 2)\n'
                        'result = {{\n'
                        '    "status": "ok" if avg <= threshold_ms else "warning",\n'
                        '    "host": host,\n'
                        '    "port": port,\n'
                        '    "avg_ms": avg,\n'
                        '    "min_ms": min(latencies),\n'
                        '    "max_ms": max(latencies),\n'
                        '    "samples": len(latencies),\n'
                        '    "failures": failures,\n'
                        '    "threshold_ms": threshold_ms,\n'
                        '}}\n'
                        'print(json.dumps(result))\n'
                        'if avg > threshold_ms:\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'host': {'type': 'string', 'description': 'Target hostname or IP'},
                            'port': {'type': 'string', 'description': 'Target TCP port'},
                            'count': {'type': 'string', 'description': 'Number of connection attempts (default 5)'},
                            'threshold_ms': {'type': 'string', 'description': 'Max acceptable avg latency in ms (default 100)'},
                        },
                        'required': ['host', 'port'],
                    },
                },
                'params': {'service': ['database', 'api', 'cache', 'storage', 'dns']},
                'prompts': [
                    'Create a Python action to test TCP connection latency to {service}',
                    'Python script that measures network latency to a {service} endpoint',
                ],
                'explanation': 'Python action that measures TCP connection latency to a {service} endpoint over multiple samples and alerts on high latency.',
            },
        ]


def get_generators():
    return [MonitoringGenerator()]
