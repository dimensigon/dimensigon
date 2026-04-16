#!/bin/bash
cat << 'BANNER'

  ╔══════════════════════════════════════════════════════╗
  ║         DIMENSIGON - LIVE DEMO CLUSTER               ║
  ║         5 nodes · mesh network · DShell               ║
  ╠══════════════════════════════════════════════════════╣
  ║                                                       ║
  ║  Try these commands:                                  ║
  ║                                                       ║
  ║    server list          - see all mesh nodes           ║
  ║    action list          - list action templates        ║
  ║    orch list            - list orchestrations          ║
  ║    orch run <id> --target all=dm-master,dm-web1,...     ║
  ║    ping                 - ping the current server      ║
  ║    status               - cluster status               ║
  ║                                                       ║
  ║  AI Assistant:                                        ║
  ║    #ai create a shell action to check disk usage      ║
  ║    #ai deploy nginx across web servers with rollback  ║
  ║                                                       ║
  ║  This demo resets daily at 03:00 UTC.                  ║
  ║                                                       ║
  ╚══════════════════════════════════════════════════════╝

BANNER
