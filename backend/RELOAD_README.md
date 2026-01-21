# Database Reload Scripts

Quick reference for reloading auction data from all sources.

## Quick Start

### Reload Everything (Default)
```bash
./reload.sh
```
This will fetch 1000 items from each auction house and update the database.

### Clear Database and Reload
```bash
./reload.sh --clear
```
Deletes the existing database and fetches fresh data from all sources.

## Advanced Usage

### Only Reload Specific Auction Houses
```bash
# Only reload Goldin and Fanatics
./reload.sh --only goldin fanatics

# Only reload REA
./reload.sh --only rea
```

### Skip Specific Auction Houses
```bash
# Reload all except Pristine
./reload.sh --skip pristine

# Skip both Goldin and REA
./reload.sh --skip goldin rea
```

### Customize Item Count
```bash
# Fetch 500 items per auction house
./reload.sh --max-items 500

# Fetch 2000 items per auction house
./reload.sh --max-items 2000
```

### Combine Options
```bash
# Clear DB, fetch 500 items from only Goldin and Fanatics
./reload.sh --clear --only goldin fanatics --max-items 500
```

## Direct Python Usage

If you prefer to use Python directly:

```bash
source venv/bin/activate
python reload_all_auctions.py --help
```

## Available Auction Houses

- `goldin` - Goldin Auctions (API-based)
- `fanatics` - Fanatics Collect (API-based)
- `pristine` - Pristine Auction (HTML scraping)
- `rea` - Robert Edward Auctions Marketplace (HTML scraping)

## Examples

### Fresh Start
```bash
# Start completely fresh with 1000 items per house
./reload.sh --clear
```

### Quick Update
```bash
# Just update existing data without clearing
./reload.sh
```

### Test with Small Dataset
```bash
# Clear DB and load just 100 items per house for testing
./reload.sh --clear --max-items 100
```

### Production Load
```bash
# Full production load with maximum items
./reload.sh --clear --max-items 5000
```

## Expected Runtime

Approximate times (will vary based on network speed):

| Auction House | Items | Approximate Time |
|---------------|-------|------------------|
| Goldin | 1000 | 2-3 minutes |
| Fanatics | 1000 | 2-3 minutes |
| Pristine | 30-100 | 30-60 seconds |
| REA | 900+ | 1-2 minutes |

**Total for all 4 houses**: ~6-10 minutes for default settings

## Troubleshooting

### Script not executable
```bash
chmod +x reload.sh
```

### Virtual environment not found
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Database locked
Make sure the backend server is not running:
```bash
# Stop any running uvicorn processes
pkill -f uvicorn
```

## Output

The script provides detailed progress information:
- Which auction house is being scraped
- Number of items found
- Any errors encountered
- Final summary with total items and time elapsed

Example output:
```
================================================================================
🔄 RELOADING ALL AUCTION DATA
================================================================================
Started at: 2025-12-02 15:30:00

🔧 Initializing database...
✅ Database initialized

================================================================================
📦 GOLDIN AUCTIONS
================================================================================
🔍 Fetching items from Goldin Auctions...
...

================================================================================
📊 SUMMARY
================================================================================
✅ GOLDIN       - 1,000 items
✅ FANATICS     - 1,000 items
✅ PRISTINE     - 30 items
✅ REA          - 922 items

📈 Total items fetched: 2,952
⏱️  Total time: 487.3 seconds
🏁 Completed at: 2025-12-02 15:38:07
================================================================================
```
