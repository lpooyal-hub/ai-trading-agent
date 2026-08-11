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


def symbol_name(symbol: str) -> str | None:
    return KRX_SYMBOL_NAMES.get(symbol.upper())
