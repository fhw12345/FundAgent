"""Generic caching utilities for tool execution."""


def generate_tool_cache_key(tool_source: str, tool_name: str, params: dict) -> str:
    sorted_params = sorted(params.items())
    param_str = ":".join(f"{k}={v}" for k, v in sorted_params)
    return f"{tool_source}:{tool_name}:{param_str}"


TOOL_TTL_MAP: dict[str, int] = {
    "fund_nav": 86400,
    "fund_holdings": 604800,
    "fund_ranking": 86400,
    "fund_info": 86400,
    "macro_data": 86400,
}


def get_tool_ttl(tool_name: str, interval: str | None = None) -> int:
    return TOOL_TTL_MAP.get(tool_name, 1800)
