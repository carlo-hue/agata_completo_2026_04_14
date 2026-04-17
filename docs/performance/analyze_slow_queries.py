#!/usr/bin/env python3
"""
Analyze AGATA slow queries from MariaDB log

Usage:
    python analyze_slow_queries.py                 # Last 2000 lines
    python analyze_slow_queries.py --tail 5000     # Last 5000 lines
    python analyze_slow_queries.py --since 1h      # Last 1 hour

Requirements:
    - sudo access to read /var/log/mysql/mariadb-slow.log
    - MariaDB slow query log enabled with query_plan,explain verbosity
"""

import subprocess
import re
import sys
from datetime import datetime, timedelta
from collections import defaultdict
from typing import List, Dict, Optional

class SlowQueryAnalyzer:
    """Parse and analyze MariaDB slow query log."""

    def __init__(self, log_file: str = '/var/log/mysql/mariadb-slow.log'):
        self.log_file = log_file
        self.queries: List[Dict] = []

    def parse_log(self, lines: int = 2000) -> List[Dict]:
        """Parse MariaDB slow query log and extract query statistics."""

        try:
            result = subprocess.run(
                ['sudo', 'tail', '-' + str(lines), self.log_file],
                capture_output=True, text=True, check=True
            )
        except subprocess.CalledProcessError as e:
            print(f"❌ Error reading log file: {e}")
            return []

        log_lines = result.stdout.split('\n')
        queries = []
        current_entry = {}

        for line in log_lines:
            if line.startswith('# Time:'):
                if current_entry and 'query_time' in current_entry:
                    queries.append(current_entry)
                current_entry = {'timestamp': line[7:].strip()}

            elif line.startswith('# User@Host:'):
                # Parse: # User@Host: root[root] @ localhost []
                parts = line[13:].split('@')
                user_part = parts[0].strip() if parts else 'unknown'
                current_entry['user'] = user_part.split('[')[0] if '[' in user_part else user_part

            elif line.startswith('# Query_time:'):
                # Parse: # Query_time: 1.234567  Lock_time: 0.000123  Rows_sent: 100  Rows_examined: 50000
                match = re.search(
                    r'Query_time: ([\d.]+)\s+Lock_time: ([\d.]+)\s+Rows_sent: (\d+)\s+Rows_examined: (\d+)',
                    line
                )
                if match:
                    current_entry['query_time'] = float(match.group(1))
                    current_entry['lock_time'] = float(match.group(2))
                    current_entry['rows_sent'] = int(match.group(3))
                    current_entry['rows_examined'] = int(match.group(4))

            elif line.startswith('# Rows_affected:'):
                # Parse: # Rows_affected: 0
                match = re.search(r'Rows_affected: (\d+)', line)
                if match:
                    current_entry['rows_affected'] = int(match.group(1))

            elif line.startswith('# Bytes_sent:'):
                # Parse: # Bytes_sent: 12345
                match = re.search(r'Bytes_sent: (\d+)', line)
                if match:
                    current_entry['bytes_sent'] = int(match.group(1))

            elif line.startswith('use '):
                # Parse database: use catalogo;
                db_match = re.search(r'use (\w+)', line)
                if db_match:
                    current_entry['database'] = db_match.group(1)

            elif line and not line.startswith('#') and not line.startswith('SET ') and line.strip():
                if 'query' not in current_entry:
                    current_entry['query'] = line.strip()[:150]

        if current_entry and 'query_time' in current_entry:
            queries.append(current_entry)

        self.queries = queries
        return queries

    def print_summary(self):
        """Print overall statistics."""

        if not self.queries:
            print("❌ No slow queries found in log")
            return

        total_queries = len(self.queries)
        total_time = sum(q.get('query_time', 0) for q in self.queries)
        avg_time = total_time / total_queries if total_queries > 0 else 0
        max_time = max(q.get('query_time', 0) for q in self.queries) if self.queries else 0
        total_rows_examined = sum(q.get('rows_examined', 0) for q in self.queries)

        print("\n" + "=" * 90)
        print("📊 SLOW QUERY LOG SUMMARY")
        print("=" * 90)
        print(f"  Total slow queries (>1s):  {total_queries}")
        print(f"  Total time spent:          {total_time:,.2f} seconds")
        print(f"  Average query time:        {avg_time:.3f} seconds")
        print(f"  Max query time:            {max_time:.3f} seconds")
        print(f"  Total rows examined:       {total_rows_examined:,}")
        print("=" * 90)

    def print_top_queries(self, limit: int = 10):
        """Print top N slowest queries."""

        if not self.queries:
            return

        sorted_queries = sorted(
            self.queries,
            key=lambda x: x.get('query_time', 0),
            reverse=True
        )

        print(f"\n🔴 TOP {limit} SLOWEST QUERIES:\n")
        print(f"{'Time (s)':>10} | {'Lock (ms)':>10} | {'Rows Ex.':>12} | {'DB':>8} | Query")
        print("-" * 100)

        for i, q in enumerate(sorted_queries[:limit], 1):
            time_s = q.get('query_time', 0)
            lock_ms = q.get('lock_time', 0) * 1000
            rows_ex = q.get('rows_examined', 0)
            db = q.get('database', '?')
            query = q.get('query', 'N/A')[:55].replace('\n', ' ')

            print(f"{time_s:>10.3f} | {lock_ms:>10.1f} | {rows_ex:>12,} | {db:>8} | {query}...")

    def print_by_user(self):
        """Print query statistics grouped by user."""

        user_stats = defaultdict(lambda: {'count': 0, 'total_time': 0.0, 'max_time': 0.0})

        for q in self.queries:
            user = q.get('user', 'unknown')
            query_time = q.get('query_time', 0)
            user_stats[user]['count'] += 1
            user_stats[user]['total_time'] += query_time
            user_stats[user]['max_time'] = max(user_stats[user]['max_time'], query_time)

        print(f"\n👤 QUERIES BY USER:\n")
        print(f"{'User':20} | {'Count':>6} | {'Total (s)':>10} | {'Max (s)':>8} | Avg (s)")
        print("-" * 70)

        for user, stats in sorted(user_stats.items(), key=lambda x: x[1]['total_time'], reverse=True):
            avg_time = stats['total_time'] / stats['count'] if stats['count'] > 0 else 0
            print(f"{user:20} | {stats['count']:>6} | {stats['total_time']:>10.2f} | {stats['max_time']:>8.3f} | {avg_time:.3f}")

    def print_by_database(self):
        """Print query statistics grouped by database."""

        db_stats = defaultdict(lambda: {'count': 0, 'total_time': 0.0, 'rows_examined': 0})

        for q in self.queries:
            db = q.get('database', 'unknown')
            query_time = q.get('query_time', 0)
            rows_ex = q.get('rows_examined', 0)
            db_stats[db]['count'] += 1
            db_stats[db]['total_time'] += query_time
            db_stats[db]['rows_examined'] += rows_ex

        print(f"\n🗄️  QUERIES BY DATABASE:\n")
        print(f"{'Database':20} | {'Count':>6} | {'Total (s)':>10} | {'Rows Examined':>15}")
        print("-" * 65)

        for db, stats in sorted(db_stats.items(), key=lambda x: x[1]['total_time'], reverse=True):
            print(f"{db:20} | {stats['count']:>6} | {stats['total_time']:>10.2f} | {stats['rows_examined']:>15,}")

    def print_by_query_type(self):
        """Print query statistics grouped by query type (SELECT, UPDATE, INSERT, etc)."""

        type_stats = defaultdict(lambda: {'count': 0, 'total_time': 0.0})

        for q in self.queries:
            query = q.get('query', '').strip()
            query_type = query.split()[0].upper() if query else 'UNKNOWN'
            query_time = q.get('query_time', 0)
            type_stats[query_type]['count'] += 1
            type_stats[query_type]['total_time'] += query_time

        print(f"\n📝 QUERIES BY TYPE:\n")
        print(f"{'Type':15} | {'Count':>6} | {'Total (s)':>10} | Avg (s)")
        print("-" * 45)

        for qtype, stats in sorted(type_stats.items(), key=lambda x: x[1]['total_time'], reverse=True):
            avg_time = stats['total_time'] / stats['count'] if stats['count'] > 0 else 0
            print(f"{qtype:15} | {stats['count']:>6} | {stats['total_time']:>10.2f} | {avg_time:.3f}")

    def analyze_agata_specific(self):
        """Analyze queries specific to AGATA tables."""

        agata_tables = [
            'agata_vast_results',
            'agata_vast_jobs',
            'agata_projects',
            'agata_catalog_attributes',
            'agata_catalog_imports',
            'cataloghi_esterni',
            'agata_users'
        ]

        table_queries = defaultdict(lambda: {'count': 0, 'total_time': 0.0, 'max_time': 0.0})

        for q in self.queries:
            query = q.get('query', '').lower()
            query_time = q.get('query_time', 0)

            for table in agata_tables:
                if table.lower() in query:
                    table_queries[table]['count'] += 1
                    table_queries[table]['total_time'] += query_time
                    table_queries[table]['max_time'] = max(table_queries[table]['max_time'], query_time)

        if table_queries:
            print(f"\n🎯 AGATA-SPECIFIC TABLE QUERIES:\n")
            print(f"{'Table':30} | {'Count':>6} | {'Total (s)':>10} | {'Max (s)':>8}")
            print("-" * 65)

            for table, stats in sorted(table_queries.items(), key=lambda x: x[1]['total_time'], reverse=True):
                print(f"{table:30} | {stats['count']:>6} | {stats['total_time']:>10.2f} | {stats['max_time']:>8.3f}")
        else:
            print(f"\n🎯 AGATA-SPECIFIC TABLE QUERIES: None found")

    def run_full_analysis(self, lines: int = 2000):
        """Run complete analysis."""

        print(f"\n📖 Reading last {lines} lines from slow query log...")
        self.parse_log(lines)

        if not self.queries:
            print("❌ No slow queries found")
            return

        self.print_summary()
        self.print_top_queries(limit=10)
        self.print_by_user()
        self.print_by_database()
        self.print_by_query_type()
        self.analyze_agata_specific()

        print("\n" + "=" * 90)
        print("✅ Analysis complete")
        print("=" * 90 + "\n")

if __name__ == '__main__':
    lines = 2000

    if '--tail' in sys.argv:
        idx = sys.argv.index('--tail')
        if idx + 1 < len(sys.argv):
            lines = int(sys.argv[idx + 1])

    analyzer = SlowQueryAnalyzer()
    analyzer.run_full_analysis(lines=lines)
