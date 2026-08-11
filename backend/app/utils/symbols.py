KRX_SYMBOL_NAMES: dict[str, str] = {
    "005930": "삼성전자",
    "000660": "SK하이닉스",
    "402340": "SK스퀘어",
    "009150": "삼성전기",
    "373220": "LG에너지솔루션",
    "005380": "현대차",
    "207940": "삼성바이오로직스",
    "105560": "KB금융",
    "032830": "삼성생명",
    "012450": "한화에어로스페이스",
    "028260": "삼성물산",
    "329180": "HD현대중공업",
    "000270": "기아",
    "034020": "두산에너빌리티",
    "055550": "신한지주",
    "068270": "셀트리온",
    "012330": "현대모비스",
    "034730": "SK",
    "006400": "삼성SDI",
    "086790": "하나금융지주",
    "035420": "NAVER",
    "010120": "LS ELECTRIC",
    "066570": "LG전자",
    "000810": "삼성화재",
    "009540": "HD한국조선해양",
    "042660": "한화오션",
    "267260": "HD현대일렉트릭",
    "298040": "효성중공업",
    "005490": "POSCO홀딩스",
    "010130": "고려아연",
    "316140": "우리금융지주",
    "015760": "한국전력",
    "096770": "SK이노베이션",
    "138040": "메리츠금융지주",
    "011200": "HMM",
    "042700": "한미반도체",
    "006800": "미래에셋증권",
    "051910": "LG화학",
    "010140": "삼성중공업",
    "000150": "두산",
    "033780": "KT&G",
    "017670": "SK텔레콤",
    "018260": "삼성에스디에스",
    "035720": "카카오",
    "267250": "HD현대",
    "079550": "LIG넥스원",
    "003550": "LG",
}

# Sector metadata for the default ALLOWED_SYMBOLS (KRX market-cap top ~50,
# config.py -- ETFs and preferred shares excluded from the ranking, see
# docs/plans/ for how this list was built). Shared by the mock and real
# market data clients so the mapping doesn't drift between them. Falls back
# to "unknown" for anything outside this map.
KRX_SYMBOL_SECTORS: dict[str, str] = {
    "005930": "semiconductor",
    "000660": "semiconductor",
    "402340": "holding",         # SK Square (semiconductor/IT holding)
    "009150": "electronics",     # Samsung Electro-Mechanics
    "373220": "battery",
    "005380": "automobile",
    "207940": "bio",
    "105560": "finance",
    "032830": "finance",         # Samsung Life (insurance)
    "012450": "defense",         # Hanwha Aerospace
    "028260": "holding",         # Samsung C&T
    "329180": "shipbuilding",    # HD Hyundai Heavy Industries
    "000270": "automobile",
    "034020": "heavy_industry",  # Doosan Enerbility
    "055550": "finance",
    "068270": "bio",
    "012330": "automobile",      # Hyundai Mobis (parts)
    "034730": "holding",         # SK
    "006400": "battery",         # Samsung SDI
    "086790": "finance",
    "035420": "internet",
    "010120": "electrical_equipment",  # LS ELECTRIC
    "066570": "electronics",     # LG Electronics
    "000810": "finance",         # Samsung Fire & Marine (insurance)
    "009540": "shipbuilding",    # HD Korea Shipbuilding
    "042660": "shipbuilding",    # Hanwha Ocean
    "267260": "electrical_equipment",  # HD Hyundai Electric
    "298040": "heavy_industry",  # Hyosung Heavy Industries
    "005490": "steel",
    "010130": "metals",          # Korea Zinc
    "316140": "finance",         # Woori Financial
    "015760": "utility",         # KEPCO
    "096770": "energy",          # SK Innovation
    "138040": "finance",         # Meritz Financial
    "011200": "shipping",        # HMM
    "042700": "semiconductor",   # Hanmi Semiconductor (equipment)
    "006800": "finance",         # Mirae Asset Securities
    "051910": "chemicals",       # LG Chem
    "010140": "shipbuilding",    # Samsung Heavy Industries
    "000150": "holding",         # Doosan
    "033780": "consumer",        # KT&G
    "017670": "telecom",         # SK Telecom
    "018260": "it_services",     # Samsung SDS
    "035720": "internet",
    "267250": "holding",         # HD Hyundai
    "079550": "defense",         # LIG Nex1
    "003550": "holding",         # LG
}


def symbol_name(symbol: str) -> str | None:
    return KRX_SYMBOL_NAMES.get(symbol.upper())


def symbol_sector(symbol: str) -> str | None:
    return KRX_SYMBOL_SECTORS.get(symbol.upper())
