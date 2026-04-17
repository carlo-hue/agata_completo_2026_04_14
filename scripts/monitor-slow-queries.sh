#!/bin/bash
#
# Monitor AGATA slow queries in real-time or batch mode
# Usage: ./monitor-slow-queries.sh [realtime|batch|stats]
#

set -e

LOG_FILE="/var/log/mysql/mariadb-slow.log"
MODE="${1:-stats}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if log file exists (check with sudo if needed)
if ! sudo test -f "$LOG_FILE" 2>/dev/null; then
    echo -e "${RED}❌ Log file not found: $LOG_FILE${NC}"
    echo "Enable slow query log first:"
    echo "  sudo mysql -e \"SET GLOBAL slow_query_log = ON;\""
    exit 1
fi

case "$MODE" in
    realtime)
        echo -e "${BLUE}🔴 Monitoring slow queries in real-time...${NC}"
        echo "Press Ctrl+C to stop"
        echo ""
        sudo tail -f "$LOG_FILE" | grep -E "^# Query_time:|^SELECT|^UPDATE|^INSERT|^DELETE"
        ;;

    batch)
        echo -e "${BLUE}📊 Batch analysis of last 2000 lines...${NC}"
        echo ""
        python docs/performance/analyze_slow_queries.py
        ;;

    stats)
        echo -e "${BLUE}📈 Current slow query statistics...${NC}"
        echo ""
        echo "✅ Slow query log status:"
        sudo mysql -e "SHOW VARIABLES LIKE 'slow_query%';" | column -t
        echo ""
        echo "✅ Recent entries in log:"
        sudo tail -20 "$LOG_FILE" | head -10
        echo ""
        echo "✅ Log file size:"
        sudo ls -lh "$LOG_FILE" | awk '{print "   " $5 " - " $9}'
        ;;

    top10)
        echo -e "${BLUE}🔴 Top 10 slowest queries...${NC}"
        echo ""
        sudo mysqldumpslow -s at "$LOG_FILE" | head -20
        ;;

    top-count)
        echo -e "${BLUE}📊 Top queries by frequency...${NC}"
        echo ""
        sudo mysqldumpslow -s c "$LOG_FILE" | head -20
        ;;

    cleanup)
        echo -e "${YELLOW}🧹 Cleaning old slow query logs...${NC}"
        sudo logrotate -f /etc/logrotate.d/mysql-slow-query
        echo -e "${GREEN}✅ Cleanup complete${NC}"
        ;;

    disable)
        echo -e "${YELLOW}⚠️  Disabling slow query log...${NC}"
        sudo mysql -e "SET GLOBAL slow_query_log = OFF;"
        echo -e "${GREEN}✅ Disabled${NC}"
        ;;

    *)
        echo "Usage: $0 {realtime|batch|stats|top10|top-count|cleanup|disable}"
        echo ""
        echo "Modes:"
        echo "  realtime    - Stream slow queries as they arrive"
        echo "  batch       - Run full Python analysis (detailed statistics)"
        echo "  stats       - Show current status and recent entries"
        echo "  top10       - Show 10 slowest queries by total time"
        echo "  top-count   - Show most frequent slow queries"
        echo "  cleanup     - Rotate and clean old log files"
        echo "  disable     - Turn off slow query logging"
        echo ""
        echo "Examples:"
        echo "  ./monitor-slow-queries.sh stats      # Quick overview"
        echo "  ./monitor-slow-queries.sh batch      # Full analysis"
        echo "  ./monitor-slow-queries.sh realtime   # Live monitoring"
        exit 1
        ;;
esac
