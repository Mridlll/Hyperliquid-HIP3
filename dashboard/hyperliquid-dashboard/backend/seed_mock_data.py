"""
Quick Database Seeder - Populates realistic synthetic data for all assets
"""

import sys
import os
import sqlite3
import time
import random
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# All 16+ XYZ equity assets
ALL_ASSETS = [
    "xyz:XYZ100", "xyz:TSLA", "xyz:NVDA", "xyz:GOLD", "xyz:HOOD", "xyz:INTC",
    "xyz:PLTR", "xyz:COIN", "xyz:META", "xyz:AAPL", "xyz:MSFT", "xyz:ORCL",
    "xyz:GOOGL", "xyz:AMZN", "xyz:AMD", "xyz:MU",
    "flx:TSLA", "flx:NVDA", "flx:CRCL",
    "vntl:SPACEX", "vntl:OPENAI"
]

# Mock prices for each asset (approximate current values)
MOCK_PRICES = {
    "xyz:XYZ100": 24000.0,
    "xyz:TSLA": 400.0,
    "xyz:NVDA": 180.0,
    "xyz:GOLD": 2600.0,
    "xyz:HOOD": 20.0,
    "xyz:INTC": 25.0,
    "xyz:PLTR": 150.0,
    "xyz:COIN": 250.0,
    "xyz:META": 590.0,
    "xyz:AAPL": 220.0,
    "xyz:MSFT": 400.0,
    "xyz:ORCL": 150.0,
    "xyz:GOOGL": 170.0,
    "xyz:AMZN": 180.0,
    "xyz:AMD": 120.0,
    "xyz:MU": 90.0,
    "flx:TSLA": 400.0,
    "flx:NVDA": 180.0,
    "flx:CRCL": 50.0,
    "vntl:SPACEX": 100.0,
    "vntl:OPENAI": 75.0
}

def seed_all_data():
    """Seed all data tables with synthetic but realistic data"""

    db_path = "api/hip3_analytics.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("="*80)
    print("SEEDING DATABASE WITH REALISTIC MOCK DATA")
    print("="*80)
    print(f"Assets to seed: {len(ALL_ASSETS)}")
    print()

    # Seed market_snapshots (7 days of historical data)
    print("[1] Seeding market_snapshots table...")
    current_time = int(time.time() * 1000)

    for coin in ALL_ASSETS:
        base_price = MOCK_PRICES.get(coin, 100.0)
        base_oi = random.uniform(50000, 200000)  # $50k to $200k OI

        for day in range(7, 0, -1):
            timestamp_ms = current_time - (day * 24 * 60 * 60 * 1000)

            # Add some realistic variation
            price_variation = random.uniform(0.95, 1.05)
            oi_variation = random.uniform(0.9, 1.1)
            volume_variation = random.uniform(0.7, 1.3)

            mark_price = base_price * price_variation
            oracle_price = mark_price * random.uniform(0.999, 1.001)
            open_interest = base_oi * oi_variation
            open_interest_usd = open_interest * mark_price

            cursor.execute("""
                INSERT OR REPLACE INTO market_snapshots
                (timestamp_ms, coin, mark_price, oracle_price, open_interest, open_interest_usd,
                 volume_24h, funding_rate, premium, prev_day_price, num_trades_24h)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                timestamp_ms,
                coin,
                mark_price,
                oracle_price,
                open_interest,
                open_interest_usd,
                random.uniform(100000, 1000000) * volume_variation,  # 24h volume
                random.uniform(-0.0005, 0.0005),  # funding rate
                (mark_price - oracle_price) / oracle_price * 100,  # premium %
                mark_price * random.uniform(0.98, 1.02),  # prev day price
                random.randint(50, 500)  # num trades
            ))

        print(f"  [OK] {coin} - 7 days of snapshots")

    conn.commit()
    print()

    # Seed oracle_metrics (current tightness data)
    print("[2] Seeding oracle_metrics table...")

    for coin in ALL_ASSETS:
        mark_price = MOCK_PRICES.get(coin, 100.0)
        oracle_price = mark_price * random.uniform(0.999, 1.001)

        spread = abs(mark_price - oracle_price)
        spread_pct = (spread / oracle_price) * 100

        # Calculate tightness score
        if spread_pct < 0.01:
            tightness_score = 100
        elif spread_pct < 0.1:
            tightness_score = 100 - (spread_pct * 100)
        elif spread_pct < 1:
            tightness_score = 90 - (spread_pct * 10)
        else:
            tightness_score = max(0, 50 - spread_pct)

        cursor.execute("""
            INSERT INTO oracle_metrics
            (timestamp_ms, coin, mark_price, oracle_price, spread, spread_pct, premium, tightness_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            current_time,
            coin,
            mark_price,
            oracle_price,
            spread,
            spread_pct,
            mark_price - oracle_price,
            tightness_score
        ))

        print(f"  [OK] {coin} - Spread: {spread_pct:.4f}%, Score: {tightness_score:.1f}/100")

    conn.commit()
    print()

    # Seed trades if empty (add some synthetic trades)
    print("[3] Checking trades table...")
    cursor.execute("SELECT COUNT(*) FROM trades")
    trade_count = cursor.fetchone()[0]

    if trade_count == 0:
        print("  Adding sample trades...")
        for _ in range(1000):
            coin = random.choice(ALL_ASSETS)
            price = MOCK_PRICES.get(coin, 100.0) * random.uniform(0.98, 1.02)
            size = random.uniform(0.1, 5.0)

            cursor.execute("""
                INSERT INTO trades
                (timestamp_ms, coin, side, price, size, user, fee, oi, funding_rate)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                current_time - random.randint(0, 7 * 24 * 60 * 60 * 1000),  # Random time in last 7 days
                coin,
                random.choice(['B', 'A']),
                price,
                size,
                f"0x{random.randint(100000000000000000000, 999999999999999999999):039d}",
                price * size * 0.0005,  # 0.05% fee
                random.uniform(50000, 200000),
                random.uniform(-0.0005, 0.0005)
            ))

        conn.commit()
        print(f"  [OK] Added 1000 sample trades")
    else:
        print(f"  Skipping - {trade_count} trades already exist")

    print()

    # Update statistics
    cursor.execute("SELECT COUNT(*) FROM market_snapshots")
    snapshot_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM oracle_metrics")
    oracle_count = cursor.fetchone()[0]

    print("="*80)
    print("SEEDING COMPLETE!")
    print("="*80)
    print(f"Market Snapshots: {snapshot_count} rows ({len(ALL_ASSETS)} assets * 7 days)")
    print(f"Oracle Metrics: {oracle_count} rows ({len(ALL_ASSETS)} assets)")
    print(f"Total Assets: {len(ALL_ASSETS)}")
    print()
    print("Dashboard should now show:")
    print("  ✓ Non-zero OI values for all assets")
    print("  ✓ Oracle health scores")
    print("  ✓ Market health matrix")
    print("  ✓ Fee calculations")
    print("  ✓ Volume charts")
    print("="*80)

    conn.close()

if __name__ == "__main__":
    seed_all_data()
