#!/usr/bin/env python3
"""
Template for batch downloading Taiwan stock data with timeout handling and checkpointing.
Based on session learnings from Taiwan stock data pipeline development.
"""

import json
import time
import sqlite3
import twstock
from pathlib import Path
from twstock import twse, tpex


class RateLimiter:
    """Rate limiter to respect TWSE API limits."""
    def __init__(self, per_minute=50):
        self.min_interval = 60.0 / per_minute
        self._last = 0.0
    
    def wait(self):
        now = time.time()
        elapsed = now - self._last
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last = now


class CheckpointManager:
    """Manages checkpointing for resumable processing."""
    def __init__(self, checkpoint_path: Path):
        self.checkpoint_path = checkpoint_path
        self.processed = self._load()
    
    def _load(self):
        if self.checkpoint_path.exists():
            try:
                with self.checkpoint_path.open() as f:
                    return set(json.load(f).get('processed', []))
            except Exception:
                return set()
        return set()
    
    def save(self):
        try:
            with self.checkpoint_path.open('w') as f:
                json.dump({'processed': list(self.processed)}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f'Failed to save checkpoint: {e}')
    
    def mark_processed(self, item):
        self.processed.add(item)
        self.save()
    
    def is_processed(self, item):
        return item in self.processed


def download_stocks_batch(stock_codes, batch_size=50, max_runtime_seconds=300, start_year=2023, start_month=1):
    """
    Download stocks in batches with checkpointing and runtime timeout.
    
    Args:
        stock_codes: List of stock codes to process
        batch_size: Number of stocks per batch
        max_runtime_seconds: Maximum runtime before forced checkpoint save
        start_year: Start year for historical data
        start_month: Start month for historical data
    
    Returns:
        Total number of records inserted/updated
    """
    # Initialize
    db_path = Path('taiwan_stocks.db')
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Ensure table exists
    cur.execute('''
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
    ''')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_stock ON daily_prices(stock_code);')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_date ON daily_prices(date);')
    conn.commit()
    
    # Setup managers
    checkpoint = CheckpointManager(Path('step2_checkpoint.json'))
    limiter = RateLimiter(per_minute=50)
    
    # Get unprocessed stocks
    todo = [c for c in stock_codes if not checkpoint.is_processed(c)]
    print(f'Total stocks: {len(stock_codes)}, Remaining: {len(todo)}')
    
    start_time = time.time()
    total_inserted = 0
    newly_processed = []
    
    try:
        for i in range(0, len(todo), batch_size):
            # Check runtime timeout
            if time.time() - start_time > max_runtime_seconds:
                print(f'Reached maximum runtime ({max_runtime_seconds}s), saving checkpoint and stopping.')
                break
            
            batch = todo[i:i+batch_size]
            batch_num = i//batch_size + 1
            total_batches = (len(todo)-1)//batch_size + 1
            print(f'\nProcessing batch {batch_num}/{total_batches}: {len(batch)} stocks')
            
            for code in batch:
                try:
                    limiter.wait()
                except Exception:
                    continue

                # Stock() constructor can throw TooManyRedirects (transient TWSE issue)
                try:
                    stock = twstock.Stock(code)
                except Exception as e:
                    print(f'  {code}: Stock() init failed - {e}')
                    newly_processed.append(code)
                    checkpoint.mark_processed(code)
                    continue

                try:
                    data = stock.fetch_from(start_year, start_month)
                except Exception as e:
                    print(f'  {code}: fetch failed - {e}')
                    newly_processed.append(code)
                    checkpoint.mark_processed(code)
                    continue
                    
                    if not data:
                        print(f'  {code}: No data')
                        newly_processed.append(code)
                        checkpoint.mark_processed(code)
                        continue
                    
                    records = []
                    for d in data:
                        records.append((
                            d.date.strftime('%Y-%m-%d'),
                            code,
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
                        cur.executemany('''
                            INSERT OR REPLACE INTO daily_prices
                            (date, stock_code, open, high, low, close, volume, turnover, transaction_count, amplitude)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', records)
                        conn.commit()
                        total_inserted += len(records)
                        newly_processed.append(code)
                        print(f'  {code}: Inserted/updated {len(records)} records')
                    else:
                        newly_processed.append(code)
                        print(f'  {code}: No valid records')
                    
                    # Update checkpoint after each stock
                    checkpoint.mark_processed(code)
                    
                except Exception as e:
                    print(f'  {code}: Error - {e}')
                    # Still mark as processed to avoid infinite retries
                    newly_processed.append(code)
                    checkpoint.mark_processed(code)
            
            print(f'Completed batch {batch_num}')
        
        print(f'\nFinished. Total records inserted/updated: {total_inserted}')
        print(f'Stocks processed in this run: {len(newly_processed)}')
        return total_inserted
        
    finally:
        conn.close()


def main():
    """Main function to run the batch download."""
    # Update stock lists
    print("Updating stock lists...")
    twse.update()
    tpex.update()
    
    # Get all stock codes
    all_codes = {c: i for c, i in twstock.codes.items() if i.type == '股票'}
    stock_codes = list(all_codes.keys())
    print(f'Found {len(stock_codes)} stocks')
    
    # Run batch download with 5-minute timeout (adjust as needed)
    download_stocks_batch(
        stock_codes=stock_codes,
        batch_size=50,
        max_runtime_seconds=300,  # 5 minutes
        start_year=2023,
        start_month=1
    )


if __name__ == '__main__':
    main()