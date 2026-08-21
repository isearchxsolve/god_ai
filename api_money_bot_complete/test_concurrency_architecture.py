import threading
import time
import pytest
from src.api_money_bot_v3 import RevenueTracker
from src.earnings_engine import TradingBalanceTracker
import json

def test_revenue_tracker_concurrency(tmp_path):
    # Setup temporary file
    test_file = tmp_path / "revenue_log.json"
    
    # We subclass to override the file path
    class TestTracker(RevenueTracker):
        FILE = str(test_file)
        
    tracker = TestTracker()
    
    # Try concurrent writes
    def worker(platform, num):
        for i in range(100):
            tracker.record(platform, f"event_{i}", 1.0)
            
    threads = [
        threading.Thread(target=worker, args=(f"P{j}", j))
        for j in range(10)
    ]
    
    for t in threads:
        t.start()
    for t in threads:
        t.join()
        
    # Validation
    # In a race condition with json.dump, the file usually ends up corrupted or missing records.
    try:
        with open(test_file) as f:
            data = json.load(f)
        assert len(data) == 1000, f"Expected 1000 records, got {len(data)}"
    except json.JSONDecodeError:
        pytest.fail("JSON file got corrupted due to race conditions")


def test_trading_balance_concurrency(tmp_path):
    import src.earnings_engine as ee
    
    ee.TRADE_BALANCE_FILE = str(tmp_path / "trade_balance.json")
    tracker = TradingBalanceTracker()
    
    def worker():
        for _ in range(100):
            tracker.deposit(1.0)
            
    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
        
    assert tracker.balance == 1000.0, f"Expected 1000.0, got {tracker.balance}"
