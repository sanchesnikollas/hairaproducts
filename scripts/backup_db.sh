#!/bin/bash
# Backup local haira.db with timestamp
# Usage: ./scripts/backup_db.sh

BACKUP_DIR="backups"
DB_FILE="haira.db"
TIMESTAMP=$(date +%Y-%m-%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/haira_${TIMESTAMP}.db"

mkdir -p "$BACKUP_DIR"

if [ ! -f "$DB_FILE" ]; then
    echo "ERROR: $DB_FILE not found"
    exit 1
fi

cp "$DB_FILE" "$BACKUP_FILE"
SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo "Backup created: $BACKUP_FILE ($SIZE)"

# Keep only last 10 backups
ls -t "$BACKUP_DIR"/haira_*.db 2>/dev/null | tail -n +11 | xargs rm -f 2>/dev/null
TOTAL=$(ls "$BACKUP_DIR"/haira_*.db 2>/dev/null | wc -l | tr -d ' ')
echo "Total backups: $TOTAL"
