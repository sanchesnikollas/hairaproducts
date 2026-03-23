#!/bin/bash
# Scrape all brands with blueprints and migrate to production
set -e

cd /Users/nikollasanches/Documents/hairaproducts
source .venv/bin/activate
export PYTHONPATH=/Users/nikollasanches/Documents/hairaproducts

BRANDS=(
  eudora granado o-boticario avatim mustela johnsons-baby
  loccitane loccitane-us loreal-professionel redken inoar
  griffus haskell salon-line bio-extratus widi-care hidratei
  lola-cosmetics brae truss all-nature aneethun acquaflora
  natura kerastase aussie batiste beleza-natural
  apice-cosmeticos alva amazonico-care b-hulmann b-o-b-bars
  b-urb balai alphahall-cosmetiques arvensis-cosmeticos-naturais
  abela-cosmetics agilise-cosmeticos american-desire wella
)

LOGFILE="scripts/scrape_all.log"
echo "=== Scrape All Brands - $(date) ===" > "$LOGFILE"
echo "Total brands: ${#BRANDS[@]}" >> "$LOGFILE"

COMPLETED=0
FAILED=0

for BRAND in "${BRANDS[@]}"; do
  echo ""
  echo "========================================"
  echo "[$(date +%H:%M:%S)] Processing: $BRAND"
  echo "========================================"
  echo "[$(date +%H:%M:%S)] START: $BRAND" >> "$LOGFILE"

  if python3 -m src.cli.main scrape --brand "$BRAND" --headless 2>&1 | tee -a "$LOGFILE"; then
    echo "[$(date +%H:%M:%S)] SCRAPE OK: $BRAND" >> "$LOGFILE"

    # Run labels
    python3 -m src.cli.main labels --brand "$BRAND" 2>&1 | tee -a "$LOGFILE" || true
    echo "[$(date +%H:%M:%S)] LABELS OK: $BRAND" >> "$LOGFILE"

    COMPLETED=$((COMPLETED + 1))
  else
    echo "[$(date +%H:%M:%S)] FAILED: $BRAND" >> "$LOGFILE"
    FAILED=$((FAILED + 1))
  fi

  echo "[$(date +%H:%M:%S)] Progress: $COMPLETED completed, $FAILED failed out of ${#BRANDS[@]}" >> "$LOGFILE"
done

echo ""
echo "=== DONE ==="
echo "Completed: $COMPLETED"
echo "Failed: $FAILED"
echo "=== DONE: $COMPLETED completed, $FAILED failed - $(date) ===" >> "$LOGFILE"

# Show final DB stats
python3 -c "
import sqlite3
conn = sqlite3.connect('haira.db')
rows = conn.execute('SELECT brand_slug, COUNT(*) FROM products GROUP BY brand_slug ORDER BY COUNT(*) DESC').fetchall()
print(f'\nTotal products: {sum(r[1] for r in rows)}')
print(f'Total brands: {len(rows)}')
for slug, count in rows:
    print(f'  {slug}: {count}')
conn.close()
"
