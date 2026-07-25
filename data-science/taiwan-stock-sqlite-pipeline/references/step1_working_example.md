# Step 1: Single Stock Download - Working Example

This is the verified working code from the session for downloading a single stock's data into SQLite.

## Key Learnings from Session:
- Use `stock.fetch_from(year, month)` not `stock.fetch()` 
- Handle date comparisons properly (both are datetime objects)
- "transaction" is a reserved word in SQLite - use "transaction_count" instead
- Rate limiting is crucial even for single stock if running frequently

## Verified Working Code:
```python
import twstock
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

def download_single_stock(stock_code='2330', days=30):
    # Initialize
    stock = twstock.Stock(stock_code)
    
    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    # Fetch data from start month onwards
    data = stock.fetch_from(start_date.year, start_date.month)
    
    # Keep only last `days` trading days (approximate)
    if len(data) > days:
        data = data[-days:]
    
    print(f"Fetched {len(data)} records for {stock_code}")
    
    # Setup database
    db_path = Path("taiwan_stocks.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_prices (
            date TEXT NOT NULL,
            stock_code TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER,
            turnover REAL,
            transaction_count INTEGER,
            amplitude REAL,
            PRIMARY KEY (date, stock_code)
        );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_stock ON daily_prices(stock_code);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_date ON daily_prices(date);")
    conn.commit()
    
    # Insert data
    records = []
    for d in data:
        records.append((
            d.date.strftime('%Y-%m-%d'),
            stock_code,
            float(d.open) if d.open is not None else None,
            float(d.high) if d.high is not None else None,
            float(d.low) if d.low is not None else None,
            float(d.close) if d.close is not None else None,
            int(d.capacity) if d.capacity is not None else None,
            float(d.turnover) if d.turnover is not None else None,
            int(d.transaction) if d.transaction is not None else None,
            float(getattr(d, 'amplitude', None)) if getattr(d, 'amplitude', None) is not None else None
        ))
    
    if records:
        cursor.executemany("""
            INSERT OR REPLACE INTO daily_prices 
            (date, stock_code, open, high, low, close, volume, turnover, transaction_count, amplitude)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, records)
        conn.commit()
        print(f"Inserted/updated {len(records)} records")
    
    # Verify
    cursor.execute("""
        SELECT date, close FROM daily_prices 
        WHERE stock_code = ? 
        ORDER BY date DESC 
        LIMIT 5
    """, (stock_code,))
    print("\nRecent 5 days closing prices:")
    for date, close in cursor.fetchall():
        print(f"  {date}: {close}")
    
    conn.close()
    return len(records)

if __name__ == "__main__":
    download_single_stock()
```