#!/usr/bin/env python3
"""
Check progress of a data download task that uses a SQLite database and a checkpoint JSON file.
Usage: ./check_progress.py [db_path] [checkpoint_path] [total_est]
Defaults: db_path='/opt/data/taiwan_stocks.db', checkpoint_path='/opt/data/step2_checkpoint.json', total_est=1925
"""
import sqlite3
import json
import os
import sys

def main():
    db_path = sys.argv[1] if len(sys.argv) > 1 else '/opt/data/taiwan_stocks.db'
    cp_path = sys.argv[2] if len(sys.argv) > 2 else '/opt/data/step2_checkpoint.json'
    try:
        total_est = int(sys.argv[3]) if len(sys.argv) > 3 else 1925
    except ValueError:
        total_est = 1925

    # Initialize unknown values
    row_count = 'unknown'
    stock_count = 'unknown'
    date_min = date_max = 'unknown'

    # Try to get database stats - discover table name dynamically
    try:
        # Use read-only URI with timeout to avoid blocking writes
        conn = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True, timeout=5.0)
        c = conn.cursor()
        
        # Discover table name(s)
        c.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = c.fetchall()
        
        if tables:
            # Use the first table (or could be made configurable)
            table_name = tables[0][0]
            
            # Get statistics
            c.execute(f'SELECT COUNT(*) FROM "{table_name}"')
            row_count = c.fetchone()[0]
            
            c.execute(f'SELECT COUNT(DISTINCT stock_code) FROM "{table_name}"')
            stock_count = c.fetchone()[0]
            
            c.execute(f'SELECT MIN(date), MAX(date) FROM "{table_name}"')
            date_min, date_max = c.fetchone()
        
        conn.close()
    except sqlite3.OperationalError as e:
        # Database is likely locked - this is expected during active downloads
        # Keep values as 'unknown'
        pass
    except Exception:
        # Other errors - keep values as 'unknown'
        pass

    # Read checkpoint
    processed_count = 0
    if os.path.exists(cp_path):
        try:
            with open(cp_path) as f:
                data = json.load(f)
                processed_count = len(data.get('processed', []))
        except Exception:
            processed_count = 0

    msg = f'''Taiwan Stock Download Progress:
- Total rows in DB: {row_count}
- Distinct stocks: {stock_count}
- Date range: {date_min} to {date_max}
- Processed stocks (checkpoint): {processed_count}/{total_est} ({processed_count/total_est*100:.1f}%)'''
    print(msg)

if __name__ == '__main__':
    main()