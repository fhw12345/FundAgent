"""Real-time market data — fund intraday estimation + sector daily change.

All AkShare calls are wrapped with Redis caching to avoid rate-limiting:
- Full-market fund estimation: 5 min TTL (changes every minute during trading)
- Sector spot: 10 min TTL
"""

import asyncio
import json
from typing import Any

import structlog

from ..database.redis import RedisCache

logger = structlog.get_logger()

CACHE_KEY_FUND_EST = "market:fund_estimation_all"
CACHE_KEY_SECTORS = "market:sectors_today"
TTL_FUND_EST = 300
TTL_SECTORS = 600


# Keyword → Sina industry board name. Order matters (longer keys first for greedy match).
_SECTOR_KEYWORDS: list[tuple[str, str]] = [
    ("半导体", "电子信息"),
    ("芯片", "电子信息"),
    ("电子", "电子信息"),
    ("科技", "电子信息"),
    ("互联网", "传媒娱乐"),
    ("传媒", "传媒娱乐"),
    ("医药", "医药制造"),
    ("生物", "医药制造"),
    ("医疗", "医药制造"),
    ("健康", "医药制造"),
    ("消费", "食品行业"),
    ("食品", "食品行业"),
    ("白酒", "酿酒行业"),
    ("酒", "酿酒行业"),
    ("银行", "金融行业"),
    ("证券", "金融行业"),
    ("保险", "金融行业"),
    ("金融", "金融行业"),
    ("地产", "房地产"),
    ("房地产", "房地产"),
    ("新能源", "电力行业"),
    ("光伏", "电力行业"),
    ("电力", "电力行业"),
    ("汽车", "交通运输"),
    ("军工", "电器行业"),
    ("国防", "电器行业"),
    ("有色", "有色金属"),
    ("黄金", "有色金属"),
    ("煤炭", "煤炭行业"),
    ("钢铁", "钢铁行业"),
    ("化工", "化工行业"),
    ("农业", "农林牧渔"),
    ("基建", "建筑建材"),
    ("建筑", "建筑建材"),
]


async def _fetch_fund_estimation_df() -> list[dict[str, Any]]:
    """Fetch full-market intraday fund estimation. Returns list of dicts."""
    import akshare as ak

    loop = asyncio.get_event_loop()
    df = await loop.run_in_executor(None, ak.fund_value_estimation_em)
    if df is None or df.empty:
        return []

    # Find the dynamic column names (date-prefixed)
    est_value_col = next((c for c in df.columns if "估算数据-估算值" in c), None)
    est_pct_col = next((c for c in df.columns if "估算数据-估算增长率" in c), None)
    nav_col = next((c for c in df.columns if "公布数据-单位净值" in c), None)
    pub_pct_col = next((c for c in df.columns if "公布数据-日增长率" in c), None)

    rows: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        code = str(row.get("基金代码", "")).strip()
        if not code:
            continue
        rows.append({
            "fund_code": code,
            "est_value": _to_float(row.get(est_value_col)) if est_value_col else None,
            "est_pct": _to_pct(row.get(est_pct_col)) if est_pct_col else None,
            "published_nav": _to_float(row.get(nav_col)) if nav_col else None,
            "published_pct": _to_pct(row.get(pub_pct_col)) if pub_pct_col else None,
        })
    return rows


async def _fetch_sectors_df() -> list[dict[str, Any]]:
    """Sina industry sector spot — daily change per industry board."""
    import akshare as ak

    loop = asyncio.get_event_loop()
    df = await loop.run_in_executor(None, ak.stock_sector_spot)
    if df is None or df.empty:
        return []
    rows: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        name = str(row.get("板块", "")).strip()
        if not name:
            continue
        rows.append({
            "name": name,
            "change_pct": _to_float(row.get("涨跌幅")),
        })
    return rows


def _to_float(v: Any) -> float | None:
    try:
        if v is None or v == "" or v == "--":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _to_pct(v: Any) -> float | None:
    """Parse '2.04%' or numeric to float percent."""
    if v is None:
        return None
    if isinstance(v, str):
        s = v.replace("%", "").strip()
        if not s or s == "--":
            return None
        try:
            return float(s)
        except ValueError:
            return None
    return _to_float(v)


async def _cached(redis_cache: RedisCache, key: str, ttl: int, fetcher):
    if redis_cache.client:
        cached = await redis_cache.client.get(key)
        if cached:
            try:
                return json.loads(cached)
            except json.JSONDecodeError:
                pass
    try:
        data = await fetcher()
    except Exception as e:
        logger.warning("market_data fetch failed", key=key, error=str(e))
        return []
    if redis_cache.client and data:
        await redis_cache.client.setex(key, ttl, json.dumps(data))
    return data


async def get_fund_estimation_map(redis_cache: RedisCache) -> dict[str, dict[str, Any]]:
    """Returns { fund_code: {est_value, est_pct, published_nav, published_pct} }."""
    rows = await _cached(redis_cache, CACHE_KEY_FUND_EST, TTL_FUND_EST, _fetch_fund_estimation_df)
    return {r["fund_code"]: r for r in rows}


async def get_sectors_today(redis_cache: RedisCache) -> dict[str, float]:
    """Returns { sector_name: change_pct }."""
    rows = await _cached(redis_cache, CACHE_KEY_SECTORS, TTL_SECTORS, _fetch_sectors_df)
    return {r["name"]: r["change_pct"] for r in rows if r.get("change_pct") is not None}


def match_sectors_for_fund(fund_name: str, sectors_map: dict[str, float]) -> list[dict[str, Any]]:
    """Greedy keyword match from fund name → industry sectors. Dedup by sector name."""
    if not fund_name:
        return []
    matched: dict[str, float] = {}
    for keyword, sector in _SECTOR_KEYWORDS:
        if keyword in fund_name and sector in sectors_map:
            matched[sector] = sectors_map[sector]
    return [{"name": s, "change_pct": p} for s, p in matched.items()]
