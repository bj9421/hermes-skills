# Checkpoint Pattern for Resumable Stock Data Downloads

This pattern enables resumable processing of large stock datasets with timeout protection and progress tracking.

## Components

### 1. CheckpointManager Class
Handles saving and loading of processed stock codes to/from a JSON file.

```python
import json
from pathlib import Path

class CheckpointManager:
    def __init__(self, checkpoint_path: Path):
        self.checkpoint_path = checkpoint_path
        self.processed = self._load()
    
    def _load(self):
        """Load processed codes from checkpoint file."""
        if self.checkpoint_path.exists():
            try:
                with self.checkpoint_path.open() as f:
                    return set(json.load(f).get('processed', []))
            except Exception:
                return set()
        return set()
    
    def save(self):
        """Save current processed codes to checkpoint file."""
        try:
            with self.checkpoint_path.open('w') as f:
                json.dump({'processed': list(self.processed)}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f'Failed to save checkpoint: {e}')
    
    def mark_processed(self, item):
        """Mark an item as processed and save checkpoint."""
        self.processed.add(item)
        self.save()
    
    def is_processed(self, item):
        """Check if an item has been processed."""
        return item in self.processed
```

### 2. Batch Processing with Timeout Protection
Process stocks in batches while respecting maximum runtime limits.

```python
import time
import sqlite3
import twstock
from twstock import twse, tpex
from pathlib import Path

def download_stocks_with_checkpoint(stock_codes, batch_size=50, max_runtime_seconds=300):
    """
    Download stocks in batches with checkpointing and runtime timeout.
    
    Args:
        stock_codes: List of stock codes to process
        batch_size: Number of stocks per batch
        max_runtime_seconds: Maximum runtime before forced checkpoint save
    
    Returns:
        Total number of records inserted/updated
    """
    checkpoint = CheckpointManager(Path('step2_checkpoint.json'))
    limiter = TWSERateLimiter(max_per_minute=50)
    conn = sqlite3.connect('taiwan_stocks.db')
    
    # Get unprocessed stocks
    todo = [c for c in stock_codes if not checkpoint.is_processed(c)]
    print(f'Total stocks: {len(stock_codes)}, Remaining: {len(todo)}')
    
    start_time = time.time()
    total_inserted = 0
    
    for i in range(0, len(todo), batch_size):
        # Check runtime timeout
        if time.time() - start_time > max_runtime_seconds:
            print(f'Reached maximum runtime ({max_runtime_seconds}s), saving checkpoint and stopping.')
            break
        
        batch = todo[i:i+batch_size]
        print(f'\nProcessing batch {i//batch_size + 1}/{(len(todo)-1)//batch_size + 1}: {len(batch)} stocks')
        
        for code in batch:
            try:
                limiter.wait()
                stock = twstock.Stock(code)
                data = stock.fetch_from(2023, 1)  # Adjust start date as needed
                
                if not data:
                    print(f'  {code}: No data')
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
                    cur = conn.cursor()
                    cur.executemany('''
                        INSERT OR REPLACE INTO daily_prices
                        (date, stock_code, open, high, low, close, volume, turnover, transaction_count, amplitude)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', records)
                    conn.commit()
                    total_inserted += len(records)
                    print(f'  {code}: Inserted/updated {len(records)} records')
                else:
                    print(f'  {code}: No valid records')
                
                # Mark as processed after each stock
                checkpoint.mark_processed(code)
                
            except Exception as e:
                print(f'  {code}: Error - {e}')
                # Still mark as processed to avoid infinite retries on persistent errors
                checkpoint.mark_processed(code)
        
        print(f'Completed batch {i//batch_size + 1}')
    
    conn.close()
    print(f'\nFinished. Total records inserted/updated: {total_inserted}')
    return total_inserted
```

### 3. Usage Example
```python
# Initialize
twse.update()
tpex.update()
all_codes = {c: i for c, i in twstock.codes.items() if i.type == '股票'}

# Process in batches with 5-minute timeout
download_stocks_with_checkpoint(list(all_codes.keys()), batch_size=50, max_runtime_seconds=300)
```

### Benefits
- **Resumability**: Survives interruptions (timeouts, crashes, manual stops)
- **Progress Tracking**: Clear visibility into completion status
- **Timeout Protection**: Prevents runs from exceeding allocated time slots
- **Fault Tolerance**: Continues processing after individual stock failures
- **Lightweight**: Simple JSON file for checkpoint storage

### Best Practices
1. Set `max_runtime_seconds` slightly below your actual time limit (e.g., 300s for 5-minute cron jobs)
2. Use reasonable batch sizes (50-100 stocks) to balance checkpoint frequency with overhead
3. Always mark stocks as processed even after errors to avoid infinite retry loops
4. Store checkpoint file in a persistent location (not in temporary storage)
5. Consider backing up the checkpoint file alongside the database for critical operations