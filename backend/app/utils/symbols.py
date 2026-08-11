KRX_SYMBOL_NAMES: dict[str, str] = {
    "005930": "삼성전자",
    "000660": "SK하이닉스",
    "005380": "현대차",
    "000270": "기아",
    "373220": "LG에너지솔루션",
    "207940": "삼성바이오로직스",
    "035420": "NAVER",
    "035720": "카카오",
    "005490": "POSCO홀딩스",
    "068270": "셀트리온",
}

# Sector metadata for the default ALLOWED_SYMBOLS (KRX large caps, config.py).
# Shared by the mock and real market data clients so the mapping doesn't
# drift between them. Falls back to "unknown" for anything outside this map.
KRX_SYMBOL_SECTORS: dict[str, str] = {
    "005930": "semiconductor",  # Samsung Electronics
    "000660": "semiconductor",  # SK Hynix
    "005380": "automobile",     # Hyundai Motor
    "000270": "automobile",     # Kia
    "373220": "battery",        # LG Energy Solution
    "207940": "bio",            # Samsung Biologics
    "035420": "internet",       # NAVER
    "035720": "internet",       # Kakao
    "005490": "steel",          # POSCO Holdings
    "068270": "bio",            # Celltrion
}


def symbol_name(symbol: str) -> str | None:
    return KRX_SYMBOL_NAMES.get(symbol.upper())


def symbol_sector(symbol: str) -> str | None:
    return KRX_SYMBOL_SECTORS.get(symbol.upper())
