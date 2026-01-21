#!/bin/bash
# Test script for the scraper scheduler
# Run from the backend directory: ./test_scheduler.sh

BASE_URL="http://localhost:8000"

echo "=========================================="
echo "       CardWatch Scheduler Test"
echo "=========================================="
echo ""

# Check if server is running
echo "1. Checking server health..."
HEALTH=$(curl -s "$BASE_URL/health" 2>/dev/null)
if [ -z "$HEALTH" ]; then
    echo "   ERROR: Server not running. Start it with:"
    echo "   uvicorn app.main:app --host 0.0.0.0 --port 8000"
    exit 1
fi
echo "   Server is healthy"
echo ""

# Check scheduler status
echo "2. Checking scheduler status..."
STATUS=$(curl -s "$BASE_URL/api/scheduler/status")
RUNNING=$(echo $STATUS | python3 -c "import sys,json; print(json.load(sys.stdin)['running'])")
JOB_COUNT=$(echo $STATUS | python3 -c "import sys,json; print(json.load(sys.stdin)['job_count'])")
echo "   Scheduler running: $RUNNING"
echo "   Active jobs: $JOB_COUNT"
echo ""

# List available jobs
echo "3. Available scraper jobs:"
curl -s "$BASE_URL/api/scheduler/jobs/available" | python3 -c "
import sys, json
jobs = json.load(sys.stdin)
for job_id, config in jobs.items():
    print(f'   - {job_id}: {config[\"description\"]} (every {config[\"default_interval\"]} min)')
"
echo ""

# Enable CardHobby if not already enabled
echo "4. Enabling CardHobby scraper..."
curl -s -X POST "$BASE_URL/api/scheduler/jobs/cardhobby/enable" | python3 -c "import sys,json; print('   ' + json.load(sys.stdin)['message'])"
echo ""

# Show current jobs
echo "5. Currently scheduled jobs:"
curl -s "$BASE_URL/api/scheduler/jobs" | python3 -c "
import sys, json
jobs = json.load(sys.stdin)
if not jobs:
    print('   No jobs scheduled')
else:
    for job in jobs:
        status = 'PAUSED' if job['paused'] else 'ACTIVE'
        print(f'   - {job[\"id\"]}: {status}, next run: {job[\"next_run\"]}')
"
echo ""

# Trigger immediate run
echo "6. Triggering immediate CardHobby scrape..."
curl -s -X POST "$BASE_URL/api/scheduler/jobs/cardhobby/run" | python3 -c "import sys,json; print('   ' + json.load(sys.stdin)['message'])"
echo ""
echo "   Waiting 45 seconds for scrape to complete..."
sleep 45

# Check database
echo ""
echo "7. Checking database results..."
python3 << 'EOF'
import sqlite3
conn = sqlite3.connect('./auction_data.db')
c = conn.cursor()

c.execute('SELECT COUNT(*) FROM auction_items WHERE auction_house = "cardhobby"')
total = c.fetchone()[0]

c.execute('SELECT MAX(updated_at) FROM auction_items WHERE auction_house = "cardhobby"')
last_update = c.fetchone()[0]

c.execute('SELECT current_bid, bid_count, title FROM auction_items WHERE auction_house = "cardhobby" ORDER BY current_bid DESC LIMIT 3')
top_items = c.fetchall()

print(f'   Total CardHobby items: {total}')
print(f'   Last updated: {last_update}')
print(f'   Top 3 items:')
for item in top_items:
    print(f'     ${item[0]:,.2f} ({item[1]} bids) - {item[2][:40]}...')

conn.close()
EOF

echo ""
echo "=========================================="
echo "   Test complete!"
echo "=========================================="
echo ""
echo "Useful commands:"
echo "  Enable all scrapers:    for job in cardhobby goldin fanatics pristine; do curl -X POST \"$BASE_URL/api/scheduler/jobs/\$job/enable\"; done"
echo "  Check status:           curl $BASE_URL/api/scheduler/status | jq"
echo "  Run job now:            curl -X POST $BASE_URL/api/scheduler/jobs/cardhobby/run"
echo "  Disable job:            curl -X POST $BASE_URL/api/scheduler/jobs/cardhobby/disable"
echo ""
