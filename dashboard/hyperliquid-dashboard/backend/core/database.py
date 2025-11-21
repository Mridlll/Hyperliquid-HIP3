"""
Core Database Layer for HIP-3 Analytics Platform
Consolidated database with all platform, market, and user metrics
"""

import sqlite3
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import json


class HIP3Database:
    """Unified database for all HIP-3 analytics"""

    def __init__(self, db_path: str = "hip3_analytics.db"):
        self.db_path = db_path
        self.conn = None
        self.init_database()

    def get_connection(self):
        """Get or create database connection"""
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
        return self.conn

    def init_database(self):
        """Initialize all database tables"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # ===== TRADE DATA =====
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp_ms INTEGER NOT NULL,
                coin TEXT NOT NULL,
                side TEXT NOT NULL,
                price REAL NOT NULL,
                size REAL NOT NULL,
                user TEXT NOT NULL,
                fee REAL NOT NULL,
                oi REAL,
                funding_rate REAL
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp_ms)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_coin ON trades(coin)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_user ON trades(user)")

        # ===== MARKET SNAPSHOTS (for time-series analysis) =====
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS market_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp_ms INTEGER NOT NULL,
                coin TEXT NOT NULL,
                mark_price REAL NOT NULL,
                oracle_price REAL,
                open_interest REAL NOT NULL,
                open_interest_usd REAL NOT NULL,
                volume_24h REAL NOT NULL,
                funding_rate REAL NOT NULL,
                premium REAL,
                prev_day_price REAL,
                num_trades_24h INTEGER DEFAULT 0
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_timestamp ON market_snapshots(timestamp_ms)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_coin ON market_snapshots(coin)")

        # ===== ORACLE METRICS =====
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS oracle_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp_ms INTEGER NOT NULL,
                coin TEXT NOT NULL,
                mark_price REAL NOT NULL,
                oracle_price REAL NOT NULL,
                spread REAL NOT NULL,
                spread_pct REAL NOT NULL,
                premium REAL NOT NULL,
                tightness_score REAL
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_oracle_timestamp ON oracle_metrics(timestamp_ms)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_oracle_coin ON oracle_metrics(coin)")

        # ===== MARKET DEPTH SNAPSHOTS =====
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS market_depth (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp_ms INTEGER NOT NULL,
                coin TEXT NOT NULL,
                bid_depth_1pct REAL,
                bid_depth_5pct REAL,
                ask_depth_1pct REAL,
                ask_depth_5pct REAL,
                spread_bps REAL,
                depth_imbalance REAL,
                best_bid REAL,
                best_ask REAL
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_depth_timestamp ON market_depth(timestamp_ms)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_depth_coin ON market_depth(coin)")

        # ===== DAILY PLATFORM METRICS =====
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_platform_metrics (
                date TEXT PRIMARY KEY,
                total_volume REAL NOT NULL,
                total_fees REAL NOT NULL,
                unique_traders INTEGER NOT NULL,
                new_users INTEGER NOT NULL,
                total_trades INTEGER NOT NULL,
                avg_trade_size REAL NOT NULL,
                total_oi REAL NOT NULL,
                avg_oi REAL NOT NULL,
                active_markets INTEGER NOT NULL,
                platform_revenue REAL NOT NULL
            )
        """)

        # ===== PER-ASSET DAILY METRICS (for 16 assets) =====
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_asset_metrics (
                date TEXT NOT NULL,
                coin TEXT NOT NULL,
                volume_24h REAL NOT NULL,
                fees_collected REAL NOT NULL,
                num_trades INTEGER NOT NULL,
                avg_oi REAL NOT NULL,
                unique_traders INTEGER NOT NULL,
                avg_trade_size REAL NOT NULL,
                PRIMARY KEY (date, coin)
            )
        """)

        # ===== USER COHORTS =====
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_cohorts (
                user_address TEXT PRIMARY KEY,
                first_trade_date TEXT NOT NULL,
                cohort_week TEXT NOT NULL,
                total_volume REAL DEFAULT 0,
                total_trades INTEGER DEFAULT 0,
                total_fees_paid REAL DEFAULT 0,
                last_active_date TEXT,
                days_active INTEGER DEFAULT 0,
                favorite_asset TEXT
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cohort_week ON user_cohorts(cohort_week)")

        # ===== USER DAILY ACTIVITY =====
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_daily_activity (
                date TEXT NOT NULL,
                user_address TEXT NOT NULL,
                trades INTEGER DEFAULT 0,
                volume REAL DEFAULT 0,
                fees_paid REAL DEFAULT 0,
                assets_traded TEXT,
                PRIMARY KEY (date, user_address)
            )
        """)

        conn.commit()

    # ===== TRADE RECORDING =====

    def record_trade(self, trade_data: Dict):
        """Record a single trade with proper connection management"""
        max_retries = 3
        retry_delay = 0.1

        # Handle missing fields gracefully
        timestamp_ms = int(trade_data.get('timestamp', 0) * 1000) if trade_data.get('timestamp') else int(datetime.now().timestamp() * 1000)

        for attempt in range(max_retries):
            try:
                conn = self.get_connection()
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO trades (timestamp_ms, coin, side, price, size, user, fee, oi, funding_rate)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    timestamp_ms,
                    trade_data.get('coin'),
                    trade_data.get('side'),
                    trade_data.get('price'),
                    trade_data.get('size'),
                    trade_data.get('user'),
                    trade_data.get('fee', 0),
                    trade_data.get('oi'),
                    trade_data.get('funding_rate')
                ))

                conn.commit()
                return  # Success

            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    print(f"[DB] Database locked, retrying in {retry_delay}s (attempt {attempt + 1}/{max_retries})")
                    import time
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    print(f"[DB] Database error after {attempt + 1} attempts: {e}")
                    raise
            except Exception as e:
                print(f"[DB] Error recording trade (attempt {attempt + 1}): {e}")
                if attempt == max_retries - 1:
                    raise
                # Continue to next retry for other exceptions

    # ===== MARKET SNAPSHOTS =====

    def store_market_snapshot(self, coin: str, snapshot_data: Dict):
        """Store market snapshot for time-series analysis"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO market_snapshots (
                timestamp_ms, coin, mark_price, oracle_price, open_interest,
                open_interest_usd, volume_24h, funding_rate, premium,
                prev_day_price, num_trades_24h
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            int(datetime.now().timestamp() * 1000),
            coin,
            snapshot_data.get('mark_price'),
            snapshot_data.get('oracle_price'),
            snapshot_data.get('open_interest'),
            snapshot_data.get('open_interest_usd'),
            snapshot_data.get('volume_24h'),
            snapshot_data.get('funding_rate'),
            snapshot_data.get('premium'),
            snapshot_data.get('prev_day_price'),
            snapshot_data.get('num_trades_24h', 0)
        ))

        conn.commit()

    def get_market_snapshots(self, coin: str, hours_back: float = 24) -> List[Dict]:
        """Get historical market snapshots"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cutoff_time_ms = int((datetime.now().timestamp() - (hours_back * 3600)) * 1000)

        cursor.execute("""
            SELECT * FROM market_snapshots
            WHERE coin = ? AND timestamp_ms >= ?
            ORDER BY timestamp_ms ASC
        """, (coin, cutoff_time_ms))

        return [dict(row) for row in cursor.fetchall()]

    # ===== ORACLE METRICS =====

    def store_oracle_metrics(self, coin: str, metrics: Dict):
        """Store oracle tightness metrics"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO oracle_metrics (
                timestamp_ms, coin, mark_price, oracle_price, spread,
                spread_pct, premium, tightness_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            int(datetime.now().timestamp() * 1000),
            coin,
            metrics['mark_price'],
            metrics['oracle_price'],
            metrics['spread'],
            metrics['spread_pct'],
            metrics['premium'],
            metrics.get('tightness_score')
        ))

        conn.commit()

    def get_oracle_history(self, coin: str, hours_back: float = 24) -> List[Dict]:
        """Get oracle spread history"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cutoff_time_ms = int((datetime.now().timestamp() - (hours_back * 3600)) * 1000)

        cursor.execute("""
            SELECT * FROM oracle_metrics
            WHERE coin = ? AND timestamp_ms >= ?
            ORDER BY timestamp_ms ASC
        """, (coin, cutoff_time_ms))

        return [dict(row) for row in cursor.fetchall()]

    # ===== MARKET DEPTH =====

    def store_market_depth(self, coin: str, depth_data: Dict):
        """Store market depth snapshot"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO market_depth (
                timestamp_ms, coin, bid_depth_1pct, bid_depth_5pct,
                ask_depth_1pct, ask_depth_5pct, spread_bps,
                depth_imbalance, best_bid, best_ask
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            int(datetime.now().timestamp() * 1000),
            coin,
            depth_data.get('bid_depth_1pct'),
            depth_data.get('bid_depth_5pct'),
            depth_data.get('ask_depth_1pct'),
            depth_data.get('ask_depth_5pct'),
            depth_data.get('spread_bps'),
            depth_data.get('depth_imbalance'),
            depth_data.get('best_bid'),
            depth_data.get('best_ask')
        ))

        conn.commit()

    # ===== PLATFORM METRICS =====

    def get_platform_overview(self) -> Dict:
        """Get current platform overview metrics"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Get 24h metrics
        cutoff_24h_ms = int((datetime.now().timestamp() - (24 * 3600)) * 1000)

        # Total volume 24h
        cursor.execute("""
            SELECT SUM(price * size) as total_volume,
                   SUM(fee) as total_fees,
                   COUNT(DISTINCT user) as unique_traders,
                   COUNT(*) as total_trades,
                   AVG(price * size) as avg_trade_size
            FROM trades
            WHERE timestamp_ms >= ?
        """, (cutoff_24h_ms,))

        metrics = dict(cursor.fetchone())

        # Current total OI across all markets
        cursor.execute("""
            SELECT SUM(open_interest_usd) as total_oi,
                   AVG(open_interest_usd) as avg_oi,
                   COUNT(DISTINCT coin) as active_markets
            FROM (
                SELECT coin, open_interest_usd
                FROM market_snapshots
                WHERE (coin, timestamp_ms) IN (
                    SELECT coin, MAX(timestamp_ms)
                    FROM market_snapshots
                    GROUP BY coin
                )
            )
        """)

        oi_metrics = dict(cursor.fetchone())
        metrics.update(oi_metrics)

        # Platform revenue (= total fees)
        metrics['platform_revenue'] = metrics.get('total_fees', 0)

        return metrics

    def get_asset_metrics(self, coin: str, hours_back: float = 24) -> Dict:
        """Get metrics for a specific asset"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cutoff_time_ms = int((datetime.now().timestamp() - (hours_back * 3600)) * 1000)

        cursor.execute("""
            SELECT
                SUM(price * size) as volume,
                SUM(fee) as fees_collected,
                COUNT(*) as num_trades,
                COUNT(DISTINCT user) as unique_traders,
                AVG(price * size) as avg_trade_size
            FROM trades
            WHERE coin = ? AND timestamp_ms >= ?
        """, (coin, cutoff_time_ms))

        metrics = dict(cursor.fetchone())

        # Get latest OI
        cursor.execute("""
            SELECT open_interest_usd as current_oi
            FROM market_snapshots
            WHERE coin = ?
            ORDER BY timestamp_ms DESC
            LIMIT 1
        """, (coin,))

        oi_row = cursor.fetchone()
        if oi_row:
            metrics['current_oi'] = oi_row['current_oi']
            metrics['avg_oi'] = oi_row['current_oi']  # For now, use current as avg

        return metrics

    def get_all_assets_summary(self) -> List[Dict]:
        """Get summary metrics for all 16 XYZ assets"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cutoff_24h_ms = int((datetime.now().timestamp() - (24 * 3600)) * 1000)

        # Get all XYZ markets
        cursor.execute("""
            SELECT DISTINCT coin FROM trades WHERE coin LIKE 'xyz:%'
        """)

        coins = [row['coin'] for row in cursor.fetchall()]

        summaries = []
        for coin in coins:
            metrics = self.get_asset_metrics(coin, hours_back=24)
            metrics['coin'] = coin
            summaries.append(metrics)

        return summaries

    def get_key_indicators(self, hours: float = 24) -> Dict:
        """Get key trading indicators for specified timeframe"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cutoff_time_ms = int((datetime.now().timestamp() - (hours * 3600)) * 1000)

        # Volume metrics
        cursor.execute("""
            SELECT
                SUM(price * size) as total_volume,
                SUM(fee) as total_fees,
                COUNT(*) as total_trades,
                COUNT(DISTINCT user) as unique_traders,
                AVG(price * size) as avg_trade_size,
                AVG(fee) as avg_fee_per_trade
            FROM trades
            WHERE timestamp_ms >= ?
        """, (cutoff_time_ms,))
        volume_metrics = dict(cursor.fetchone())

        # OI metrics (current state)
        cursor.execute("""
            SELECT
                SUM(open_interest_usd) as total_oi,
                AVG(open_interest_usd) as avg_oi_per_asset,
                COUNT(DISTINCT coin) as active_assets
            FROM (
                SELECT coin, open_interest_usd
                FROM market_snapshots
                WHERE (coin, timestamp_ms) IN (
                    SELECT coin, MAX(timestamp_ms)
                    FROM market_snapshots
                    GROUP BY coin
                )
            )
        """)
        oi_metrics = dict(cursor.fetchone())

        # Asset breakdown
        cursor.execute("""
            SELECT
                coin,
                SUM(price * size) as volume,
                SUM(fee) as fees,
                COUNT(*) as trades,
                COUNT(DISTINCT user) as unique_traders
            FROM trades
            WHERE timestamp_ms >= ?
            GROUP BY coin
            ORDER BY volume DESC
        """, (cutoff_time_ms,))
        asset_breakdown = [dict(row) for row in cursor.fetchall()]

        # Oracle health
        cursor.execute("""
            SELECT
                AVG(tightness_score) as avg_tightness_score,
                AVG(spread_pct) as avg_spread_pct,
                COUNT(*) as assets_tracked
            FROM oracle_metrics
            WHERE timestamp_ms >= ?
        """, (cutoff_time_ms,))
        oracle_metrics = dict(cursor.fetchone())

        return {
            'volume_metrics': volume_metrics,
            'open_interest_metrics': oi_metrics,
            'asset_breakdown': asset_breakdown,
            'oracle_health': oracle_metrics,
            'timeframe_hours': hours
        }

    def get_top_traders_by_volume(self, hours: float = 24, limit: int = 50) -> List[Dict]:
        """Get top traders by volume for specified timeframe"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cutoff_time_ms = int((datetime.now().timestamp() - (hours * 3600)) * 1000)

        cursor.execute("""
            SELECT
                user as trader_address,
                SUM(price * size) as total_volume,
                SUM(fee) as total_fees_paid,
                COUNT(*) as total_trades,
                AVG(price * size) as avg_trade_size,
                MIN(price) as min_price,
                MAX(price) as max_price,
                COUNT(DISTINCT coin) as assets_traded
            FROM trades
            WHERE timestamp_ms >= ?
            GROUP BY user
            ORDER BY total_volume DESC
            LIMIT ?
        """, (cutoff_time_ms, limit))

        return [dict(row) for row in cursor.fetchall()]

    def get_trader_profile(self, address: str) -> Dict:
        """Get detailed profile for a specific trader"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Overall stats
        cursor.execute("""
            SELECT
                COUNT(*) as total_trades,
                SUM(price * size) as total_volume,
                SUM(fee) as total_fees_paid,
                COUNT(DISTINCT coin) as assets_traded,
                MIN(timestamp_ms) as first_trade_time,
                MAX(timestamp_ms) as last_trade_time
            FROM trades
            WHERE user = ?
        """, (address,))
        overall = dict(cursor.fetchone())

        # Recent activity (last 30 days)
        thirty_days_ago = int((datetime.now().timestamp() - (30 * 24 * 3600)) * 1000)
        cursor.execute("""
            SELECT
                COUNT(*) as trades_30d,
                SUM(price * size) as volume_30d,
                SUM(fee) as fees_30d
            FROM trades
            WHERE user = ? AND timestamp_ms >= ?
        """, (address, thirty_days_ago))
        recent = dict(cursor.fetchone())

        # Asset breakdown
        cursor.execute("""
            SELECT
                coin,
                COUNT(*) as trades,
                SUM(price * size) as volume,
                SUM(fee) as fees
            FROM trades
            WHERE user = ?
            GROUP BY coin
            ORDER BY volume DESC
        """, (address,))
        assets = [dict(row) for row in cursor.fetchall()]

        return {
            'trader_address': address,
            'overall_stats': overall,
            'recent_activity': recent,
            'asset_breakdown': assets,
            'profile_calculated_at': datetime.now().isoformat()
        }

    # ===== USER ANALYTICS =====

    def get_or_create_user_cohort(self, user_address: str, trade_date: datetime) -> Dict:
        """Get or create user cohort entry"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM user_cohorts WHERE user_address = ?
        """, (user_address,))

        cohort = cursor.fetchone()

        if not cohort:
            # New user - create cohort
            cohort_week = trade_date.strftime("%Y-W%U")
            cursor.execute("""
                INSERT INTO user_cohorts (
                    user_address, first_trade_date, cohort_week,
                    last_active_date, days_active
                ) VALUES (?, ?, ?, ?, 1)
            """, (
                user_address,
                trade_date.strftime("%Y-%m-%d"),
                cohort_week,
                trade_date.strftime("%Y-%m-%d")
            ))
            conn.commit()

            return {
                'user_address': user_address,
                'first_trade_date': trade_date.strftime("%Y-%m-%d"),
                'cohort_week': cohort_week,
                'is_new': True
            }

        return dict(cohort)

    def update_user_stats(self, user_address: str, volume: float, trades: int, fees: float, asset: str):
        """Update user statistics"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE user_cohorts
            SET total_volume = total_volume + ?,
                total_trades = total_trades + ?,
                total_fees_paid = total_fees_paid + ?,
                last_active_date = ?,
                favorite_asset = ?
            WHERE user_address = ?
        """, (volume, trades, fees, datetime.now().strftime("%Y-%m-%d"), asset, user_address))

        conn.commit()

    def get_cohort_analysis(self) -> Dict:
        """Get cohort retention analysis"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                cohort_week,
                COUNT(*) as cohort_size,
                AVG(total_volume) as avg_volume,
                AVG(total_trades) as avg_trades,
                SUM(CASE WHEN last_active_date >= date('now', '-7 days') THEN 1 ELSE 0 END) as active_last_week
            FROM user_cohorts
            GROUP BY cohort_week
            ORDER BY cohort_week DESC
            LIMIT 20
        """)

        cohorts = [dict(row) for row in cursor.fetchall()]

        # Calculate retention rates
        for cohort in cohorts:
            cohort['retention_rate'] = (cohort['active_last_week'] / cohort['cohort_size'] * 100) if cohort['cohort_size'] > 0 else 0

        return {'cohorts': cohorts}

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None
