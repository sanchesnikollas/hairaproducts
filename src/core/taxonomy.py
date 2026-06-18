# src/core/taxonomy.py
from __future__ import annotations

import re

HAIR_PRODUCT_TYPES: set[str] = {
    "shampoo",
    "conditioner",
    "mask",
    "treatment",
    "leave_in",
    "oil_serum",
    "tonic",
    "exfoliant",
    "scalp_treatment",
    "gel",
    "mousse",
    "spray",
    "pomade",
    "wax",
    "clay",
    "paste",
    "texturizer",
    "finisher",
    "ampule",
    "serum",
    "cream",
    "coloracao",
    "oxidante",
    "descolorante",
    "relaxante",
    "ativador",
    "protetor",
    "reconstructor",
    "reparador",
    "kit",
}

HAIR_KEYWORDS: list[str] = [
    "shampoo", "condicionador", "conditioner", "máscara capilar", "mascara capilar",
    "hair mask", "tratamento capilar", "leave-in", "leave in", "óleo capilar",
    "oil hair", "tônico capilar", "tonico capilar", "scalp", "couro cabeludo",
    "antiqueda", "anti-queda", "queda capilar", "crescimento capilar",
    "cabelo", "cabelos", "hair", "capilar", "fios",
    "gel fixador", "mousse", "spray fixador", "pomada", "cera capilar",
    "wax", "clay", "pasta modeladora", "texturizador", "finalizador",
    "ampola", "sérum capilar", "serum capilar", "creme para pentear",
    "creme de pentear", "alisamento", "progressiva", "reconstrução",
    "hidratação capilar", "nutrição capilar", "reparação",
    # Termos comuns de cuidado capilar
    "cachos", "crespos", "ondulados", "lisos", "antifrizz", "anti-frizz",
    "gelatina capilar", "gelatina para cabelos",
    "umectação", "umectacao", "umectante capilar",
    "co-wash", "cowash", "low-poo", "low poo", "no-poo", "no poo",
    "permanente", "transição capilar", "transicao capilar",
    "matizador", "tonalizador", "desamareladora", "desamarelador",
    # Nota: "bb cream" foi removido — colide com "BB Cream Make B." (maquiagem facial).
    # Casos hair-specific tipo "BB Cream Capilar" são raros e batem em "capilar".
]

EXCLUDE_KEYWORDS: list[str] = [
    "corpo", "corporal", "body", "facial", "face", "rosto",
    "maquiagem", "makeup", "perfume", "fragrance", "fragrância",
    "unhas", "nail", "acessório", "accessory",
    "protetor solar", "sunscreen", "desodorante", "deodorant",
    "sabonete líquido", "sabonete corporal",
    "hidratante corporal", "body lotion", "body cream",
    "batom", "lipstick", "rímel", "mascara para cílios",
    "água para roupas", "agua para roupas", "roupa", "roupas",
    "difusor", "vela", "sachê", "sache",
    "home spray", "aromatizador", "ambiente",
    "cheirinho", "perfume de ambiente",
    # Acessórios capilares (não são produtos químicos)
    "tiara", "touca", "bandana", "presilha", "elástico", "elastico",
    "pente", "escova", "secador", "babyliss", "chapinha",
    "prancha", "rolinho", "rolo", "bigudini", "bobby pin",
    "cetim",  # toalhas/toucas de cetim
    # Embalagens / bolsas / kits-presente sem produto químico
    "nécessaire", "necessaire", "necessaires", "bolsa",
    "estojo", "pochete", "neceser",
    # Outros itens não-capilares que estavam vazando
    "lenço", "lenco", "lencos", "lenços",
    "tesoura", "navalhete", "navalha", "alicate",
    "unha", "unhas", "palito", "esmalte",
    "cílio", "cilio", "cílios", "cilios",
    "roupão", "roupao",
    "frasqueira", "mochila", "porta", "porta-escova",
    "perfume", "fragrance", "fragrância", "fragrancia",
    "deo colônia", "deo colonia", "deo-colonia",
    # "malbec" removido — colide com Condicionador Antiqueda Malbec (linha hair masculina O Boticário)
    "glam by camila", "by camila queiroz",
    "talco", "antitranspirante",
    # Maquiagem (linhas inteiras + componentes)
    "make b.", "make b ",  # O Boticário makeup line
    "quem disse, berenice", "quem disse berenice", "qdb ", "qdb,", "berenice?",
    "niina secrets", "niina-secrets",
    "base líquida", "base liquida",
    # "bb cream" e "cc cream" removidos — colidem com Leave-in BB Cream da Amazônico Care (hair)
    "primer",  # makeup primer
    "pó solto", "po solto", "pó compacto", "po compacto",
    "delineador", "lápis de olho", "lapis de olho",
    "instamatte", "matte cream",  # QDB lines
    "blush", "contorno stick", "corretivo",
    "gloss labial", "lip gloss", "lipstick", "lip cream",  # gloss ambíguo (Elseve Gloss Shampoo é hair)
    "paleta de sombras",
    # "iluminador" removido — "Fluido Iluminador" é finalizador capilar comum
    # "gloss" sozinho removido — Hidratei Gloss SHRP / Bond Gloss Repair são hair
    # Perfumaria
    "eau de toilette", "eau de parfum", "eau de cologne",
    "edt ", "edp ", " edt", " edp",
    "colônia", "colonia",
    "rouge eau", "l'eau de", "leau de",
    # Pós-Barba / Pré-Barba / Barbear (faciais)
    "pós barba", "pos barba", "pós-barba", "pos-barba",
    "after shave", "aftershave",
    "creme de barbear", "creme para barbear",
    "shaving", "barbear",
    "espuma de barbear", "espuma para barbear", "espuma para barba",
    # Eletrodomésticos (Mondial)
    "cafeteira", "máquina de café", "maquina de cafe",
    "filtro de café", "filtro de cafe", "filtro permanente",
    "espresso", "café espresso",
    "liquidificador", "batedeira", "torradeira", "fritadeira",
    # Cuidados corporais/médicos
    "dermopes", "dermo pés", "dermo pes",
    "renovilc",
    "pomada descongestionante", "descongestionante",
    # "arnica" removido — Mustela Arnica Gel é body, mas Granado Arnica pode ser linha capilar
    # "anti-séptico" removido — pode aparecer em URL de categoria do site sem ser ruim
    # Loja de acessórios (Belliz, Vertix, Ricca)
    "capa de corte", "capa para corte",
    "pincel ", "pinceis",  # makeup brushes
    "lip oil", "magic lip", "labial", "lip ",  # lábios
    "difusor de cachos",  # accessory diffuser
    "chapa de cabelo", "chapa profissional",
    "lixa", "grampo", "piranha", "lamina", "lâmina",
    "bruma corporal", "ice mist", "spray corporal",
    "creme desodorante", "creme para mãos", "creme para maos",
    "creme hidratante", "creme das mãos", "hand cream",
    "elastico ", "elasticos", "elástico ", "elásticos",
    "cuba flexivel", "cuba flexível", "cuba ",  # acessório de salão
    "esc ", "esc.",  # "Esc Belliz" abreviado de Escova
    "rede de cabelo",
    # Feedback cliente 2026-06 — não-capilares vazando (Granado, Avatim):
    # difusor/aromatizador de ambiente, óleo de unhas, utensílios e banho.
    # Frases específicas pra vencer a prioridade 1 (EXCLUDE no nome) sobre
    # "óleo"→oil_serum que classificava errado como capilar.
    "difusor de ambiente", "difusor de ambientes", "aromatizador de ambiente",
    "óleo de unha", "oleo de unha", "óleo de unhas", "oleo de unhas",
    "óleo para unha", "oleo para unha", "óleo para unhas", "oleo para unhas",
    "esmalte de unha", "fortalecedor de unha",
    "sais de banho", "sal de banho", "bath salt", "espuma de banho",
    "sabonete em barra", "sabonete líquido para as mãos",
    "colher de madeira", "colher de bambu", "colher dosadora", "colher medidora",
    "balde", "varetas", "vareta de difusor", "varetas para difusor",
    "porta-sabonete", "saboneteira",
    "vela aromática", "vela perfumada", "incenso",
]

KIT_PATTERNS: list[str] = [
    r"/kit[-_]", r"/combo[-_]", r"/bundle[-_]", r"/set[-_]",
    r"/kit/", r"/combo/", r"/bundle/",
]

MALE_TARGETING_KEYWORDS: list[str] = [
    "masculino", "masculina", "men", "for men", "man",
    "barber", "barbearia",
]

KIDS_KEYWORDS: list[str] = [
    "kids", "infantil", "criança", "children", "baby",
]

_TYPE_MAP: list[tuple[list[str], str]] = [
    # --- Coloração / química (must come before generic matches) ---
    (["água oxigenada", "agua oxigenada", "oxidante", "ox "], "oxidante"),
    (["pó descolorante", "po descolorante", "descolorante"], "descolorante"),
    (["coloração", "coloracao", "tintura", "tonalizante", "color intensy", "color delicaté", "color delicate", "magnific color"], "coloracao"),
    (["relaxante", "relaxamento", "alisante", "guanidina"], "relaxante"),
    # --- Tratamento / reconstrução ---
    (["queratina líquida", "queratina liquida", "proteína capilar", "proteina capilar", "repositor de massa", "rmc system"], "reconstructor"),
    (["reconstrutor", "reconstrução", "reconstrutora", "overnight"], "reconstructor"),
    (["reparador de pontas", "reparador"], "reparador"),
    (["ativador de cachos", "ativador"], "ativador"),
    (["filtro solar", "defesa solar", "protetor da cor", "blindagem"], "protetor"),
    # --- Básicos ---
    (["shampoo", "xampu"], "shampoo"),
    (["condicionador", "conditioner"], "conditioner"),
    (["máscara", "mascara", "mask"], "mask"),
    (["leave-in", "leave in"], "leave_in"),
    (["creme de pentear", "creme para pentear"], "cream"),
    (["óleo", "oleo", "oil"], "oil_serum"),
    (["sérum", "serum"], "oil_serum"),
    (["tônico", "tonico", "tonic"], "tonic"),
    (["pomada", "pomade"], "pomade"),
    (["gel"], "gel"),
    (["mousse"], "mousse"),
    (["spray", "hair spray"], "spray"),
    (["cera", "wax"], "wax"),
    (["argila", "clay"], "clay"),
    (["pasta", "paste"], "paste"),
    (["ampola", "ampule"], "ampule"),
    (["finalizador", "finisher"], "finisher"),
    (["modelador", "modeladora"], "finisher"),
    (["fluido", "fluído"], "finisher"),
    (["seca sem frizz", "antifrizz"], "finisher"),
    # --- Cremes genéricos (catch-all, must be after creme de pentear) ---
    (["creme disciplinante", "creme nutritivo", "creme protetor", "creme reconstrutor"], "cream"),
    (["cream", "creme"], "cream"),
    (["tratamento", "treatment"], "treatment"),
    (["esfoliante", "exfoliant"], "exfoliant"),
    (["texturizador", "texturizer"], "texturizer"),
    (["emulsão neutralizante", "neutralizante"], "relaxante"),
    (["renovador capilar"], "treatment"),
]


CATEGORY_MAP: dict[str, str] = {
    "shampoo": "shampoo",
    "conditioner": "condicionador",
    "mask": "mascara",
    "treatment": "tratamento",
    "ampule": "tratamento",
    "scalp_treatment": "tratamento",
    "exfoliant": "tratamento",
    "tonic": "tratamento",
    "reconstructor": "tratamento",
    "reparador": "tratamento",
    "protetor": "tratamento",
    "leave_in": "leave_in",
    "cream": "leave_in",
    "ativador": "leave_in",
    "oil_serum": "oleo_serum",
    "serum": "oleo_serum",
    "gel": "styling",
    "mousse": "styling",
    "spray": "styling",
    "pomade": "styling",
    "wax": "styling",
    "clay": "styling",
    "paste": "styling",
    "texturizer": "styling",
    "finisher": "styling",
    "coloracao": "coloracao",
    "oxidante": "coloracao",
    "descolorante": "coloracao",
    "relaxante": "transformacao",
    "kit": "kit",
}

VALID_CATEGORIES: set[str] = {
    "shampoo", "condicionador", "mascara", "tratamento",
    "leave_in", "oleo_serum", "styling", "coloracao",
    "transformacao", "kit",
}

_COLORACAO_KEYWORDS: list[str] = [
    "coloração", "coloracao", "tintura", "tonalizante",
    "matizador", "matizadora", "oxidante", "ox ",
    "descolorante", "decolorante", "pó descolorante",
]


def normalize_category(product_type_normalized: str | None, product_name: str = "") -> str | None:
    """Map a normalized product type to a high-level category."""
    # Check coloração keywords first (product_type_normalized may be None for these)
    name_lower = product_name.lower()
    for kw in _COLORACAO_KEYWORDS:
        if kw in name_lower:
            return "coloracao"

    if not product_type_normalized:
        return None
    return CATEGORY_MAP.get(product_type_normalized)


def normalize_product_type(raw_name: str) -> str | None:
    lower = raw_name.lower()
    for keywords, normalized in _TYPE_MAP:
        for kw in keywords:
            if kw in lower:
                return normalized
    return None


def detect_gender_target(product_name: str, url: str) -> str:
    combined = f"{product_name} {url}".lower()
    if "unissex" in combined or "unisex" in combined:
        return "unisex"
    for kw in KIDS_KEYWORDS:
        if kw in combined:
            return "kids"
    for kw in MALE_TARGETING_KEYWORDS:
        if kw in combined:
            return "men"
    return "unknown"


def _kw_matches(text: str, keyword: str) -> bool:
    """Match com word boundary se keyword for curto (< 6 chars) e for uma palavra única.

    Resolve falsos positivos como "pente" pegando "pentear" ou "corpo" pegando
    "corporal". Para keywords compostos (com espaço ou hífen) ou longos, usa
    substring direto.
    """
    kw = keyword.lower()
    if " " in kw or "-" in kw or len(kw) >= 6:
        return kw in text
    # Single short word — usa word boundary
    return re.search(rf"\b{re.escape(kw)}\b", text) is not None


def is_hair_relevant_by_keywords(
    product_name: str, url: str, description: str = ""
) -> tuple[bool, str]:
    """Decide se um produto é capilar baseado em keywords.

    Regra com 4 níveis de prioridade:
    1. EXCLUDE_KEYWORD no NOME → não é cabelo (categoria forte tipo "Make B.",
       "Quem Disse Berenice", "Eau de Toilette", "Pós Barba" vencem sobre
       "kit"/"gel"/"mousse" que são ambíguos).
    2. HAIR_KEYWORD ou HAIR_PRODUCT_TYPE no NOME → é cabelo.
    3. EXCLUDE_KEYWORD no URL/desc → não é cabelo.
    4. HAIR_KEYWORD no URL/desc → é cabelo (fallback).
    5. Default → conservador (False).

    Retorna (is_hair, reason).
    """
    name_lower = (product_name or "").lower()
    desc_lower = (description or "").lower()
    url_lower = (url or "").lower()
    extra = f"{desc_lower} {url_lower}"

    # 1. EXCLUDE no NOME (categorias fortes)
    for ekw in EXCLUDE_KEYWORDS:
        if _kw_matches(name_lower, ekw):
            return False, f"non_hair:{ekw}"

    # 2. HAIR no NOME
    for hkw in HAIR_KEYWORDS:
        if _kw_matches(name_lower, hkw):
            return True, f"hair_keyword:{hkw}"
    for ptype in HAIR_PRODUCT_TYPES:
        if _kw_matches(name_lower, ptype):
            return True, f"hair_type:{ptype}"

    # 3. EXCLUDE no URL/desc
    for ekw in EXCLUDE_KEYWORDS:
        if _kw_matches(extra, ekw):
            return False, f"non_hair_url:{ekw}"

    # 4. HAIR no URL/desc (fallback)
    for hkw in HAIR_KEYWORDS:
        if _kw_matches(extra, hkw):
            return True, f"hair_keyword_url:{hkw}"

    # 5. Default conservador
    return False, "no_hair_keyword"


def is_kit_url(url: str) -> bool:
    lower_url = url.lower()
    for pattern in KIT_PATTERNS:
        if re.search(pattern, lower_url):
            return True
    return False
