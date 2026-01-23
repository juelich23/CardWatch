"""
Item Type Detection Utility
Classifies auction items into categories: CARD, MEMORABILIA, AUTOGRAPH, SEALED, OTHER

Multi-layer detection system:
1. Grading company detection (graded items are cards)
2. Card brand/manufacturer detection
3. Memorabilia keywords
4. Autograph detection (non-card autographs)
5. Sealed product detection
"""
from enum import Enum
from typing import Optional, Dict, Any
import re


class ItemType(str, Enum):
    CARD = "CARD"
    MEMORABILIA = "MEMORABILIA"
    AUTOGRAPH = "AUTOGRAPH"
    SEALED = "SEALED"
    OTHER = "OTHER"


# Grading companies - if present, item is almost certainly a card
GRADING_COMPANIES = [
    "psa", "bgs", "sgc", "cgc", "bccg", "gma", "hga", "csg", "aga", "ksa",
    "beckett grading", "professional sports authenticator",
]

# Card-specific terms that strongly indicate trading cards
CARD_STRONG_INDICATORS = [
    # Grading terms
    "gem mint", "gem-mt", "mint 9", "mint 10", "nm-mt", "near mint",
    "psa 10", "psa 9", "psa 8", "psa 7", "psa 6", "bgs 10", "bgs 9.5", "bgs 9",
    "sgc 10", "sgc 9", "cgc 10", "cgc 9", "pristine 10", "black label",
    "pop 1", "pop 2", "low pop", "high grade",

    # Card terminology
    "rookie card", "rc", "1st bowman", "bowman chrome", "topps chrome",
    "refractor", "auto #", "autograph #", "/10", "/25", "/50", "/75", "/99",
    "/149", "/199", "/249", "/299", "/499", "/999",
    "serial numbered", "ssp", "sp ", "short print", "variation",
    "insert", "parallel", "base card", "rookie premiere",
    "patch card", "jersey card", "relic card", "game-used card",
    "memorabilia card", "dual relic", "triple relic",

    # Card brands/sets
    "topps", "panini", "upper deck", "bowman", "fleer", "donruss", "score",
    "leaf", "pinnacle", "pacific", "skybox", "hoops", "stadium club",
    "finest", "select", "prizm", "optic", "mosaic", "chronicles",
    "national treasures", "immaculate", "flawless", "one", "noir",
    "spectra", "gold standard", "crown royale", "absolute",
    "contenders", "playoff", "certified", "elite", "prestige",
    "limited", "origins", "phoenix", "obsidian", "clearly donruss",

    # Vintage card indicators
    "t206", "t205", "t3", "e90", "e92", "e98", "w517", "goudey",
    "play ball", "diamond stars", "1933 goudey", "1952 topps", "1951 bowman",
    "1948 leaf", "1954 topps", "1955 topps", "1956 topps", "1957 topps",
    "1958 topps", "1959 topps", "1960 topps", "1961 topps", "1962 topps",
    "1963 topps", "1964 topps", "1965 topps", "1966 topps", "1967 topps",
    "1968 topps", "1969 topps", "1970 topps", "1971 topps", "1972 topps",
    "1973 topps", "1974 topps", "1975 topps", "1976 topps", "1977 topps",
    "1978 topps", "1979 topps", "1980 topps", "1986 fleer", "1986-87 fleer",

    # TCG cards (Pokemon, MTG, etc.)
    "pokemon tcg", "pokemon card", "holo pokemon", "shadowless", "1st edition pokemon",
    "base set", "jungle", "fossil", "team rocket", "neo genesis",
    "magic the gathering", "mtg", "black lotus", "mox", "dual land",
    "yu-gi-oh", "yugioh", "blue-eyes", "dark magician",
]

# Memorabilia keywords - physical items that aren't cards
MEMORABILIA_KEYWORDS = [
    # Clothing/Equipment
    "jersey", "game-worn", "game worn", "game-used jersey", "player-worn",
    "uniform", "warm-up", "warmup", "shooting shirt", "practice jersey",
    "cleats", "shoes", "sneakers", "game-worn shoes", "player exclusive",
    "helmet", "batting helmet", "football helmet", "hockey helmet",
    "glove", "batting glove", "baseball glove", "mitt", "catcher's mitt",
    "bat", "game-used bat", "baseball bat", "cracked bat",
    "ball", "game-used ball", "baseball", "football", "basketball", "hockey puck",
    "puck", "game puck",

    # Equipment
    "equipment", "gear", "protective gear", "pads", "shin guards",
    "stick", "hockey stick", "goalie stick", "broken stick",
    "racket", "tennis racket", "racquet",
    "club", "golf club", "putter", "driver", "iron",
    "net", "goal net", "basketball net",

    # Awards/Trophies
    "trophy", "award", "medal", "championship ring", "ring", "world series ring",
    "super bowl ring", "nba championship ring", "stanley cup ring",
    "mvp award", "cy young", "heisman",

    # Display items
    "pennant", "banner", "flag", "championship banner",
    "bobblehead", "bobble head", "figurine", "statue", "bust",
    "plaque", "display", "shadowbox", "shadow box",

    # Documents/Paper (non-card)
    "ticket", "ticket stub", "full ticket", "unused ticket",
    "program", "game program", "yearbook", "media guide",
    "scorecard", "score card", "lineup card",
    "contract", "player contract", "document",
    "letter", "correspondence", "telegram",
    "check", "cancelled check", "paycheck",
    "certificate", "diploma",

    # Photos/Art
    "photograph", "photo", "original photo", "wire photo", "press photo",
    "snapshot", "candid", "vintage photo",
    "poster", "lithograph", "print", "artwork", "painting", "sketch",
    "canvas", "framed",

    # Publications
    "magazine", "sports illustrated", "newspaper", "headline",
    "publication", "book", "hardcover", "paperback",

    # Miscellaneous memorabilia
    "locker", "locker room", "locker nameplate", "nameplate",
    "seat", "stadium seat", "arena seat",
    "turf", "field turf", "game-used turf",
    "base", "home plate", "pitcher's rubber",
    "dugout", "bench",
]

# Autograph indicators for NON-CARD autographs
AUTOGRAPH_KEYWORDS = [
    "signed", "autographed", "autograph", "signature", "hand-signed",
    "hand signed", "inscribed", "inscription", "personalized",
    "jsa", "psa/dna", "beckett authenticated", "bas", "uda",
    "upper deck authenticated", "fanatics authenticated", "mlb authenticated",
    "steiner", "tristar", "mounted memories", "global authentics",
    "authentic autograph", "certified autograph", "coa", "certificate of authenticity",
    "witnessed", "in-person", "in person", "ip auto",
    "cut signature", "cut auto", "index card", "3x5",
    "multi-signed", "multi signed", "team-signed", "team signed",
]

# Sealed product keywords
SEALED_KEYWORDS = [
    "sealed", "factory sealed", "unopened", "mint sealed",
    "wax box", "wax pack", "hobby box", "retail box", "blaster box",
    "case", "sealed case", "master case",
    "pack", "foil pack", "cello pack", "rack pack", "jumbo pack", "fat pack",
    "hanger box", "mega box", "value box",
    "box break", "case break",
    "bbce", "bbce wrapped", "bbce certified",
    "fasc", "factory authenticated",
]

# Words that indicate NOT a card even if other card keywords present
MEMORABILIA_OVERRIDE = [
    "game-worn", "game worn", "game-used jersey", "game-used helmet",
    "game-used bat", "game-used ball", "game-used equipment",
    "player-worn", "match-worn", "match worn",
    "trophy", "championship ring", "ring ceremony",
    "original photo", "wire photo", "press photo",
    "full ticket", "ticket stub", "game program",
    "bobblehead", "figurine", "statue",
]


def detect_item_type(
    title: str,
    description: Optional[str] = None,
    category: Optional[str] = None,
    grading_company: Optional[str] = None,
    **kwargs
) -> ItemType:
    """
    Detect the item type from title, description, and other fields.

    Args:
        title: Item title (required)
        description: Item description (optional)
        category: Category from auction house (optional)
        grading_company: Grading company if present (optional)
        **kwargs: Additional fields that might help classification

    Returns:
        ItemType enum value
    """
    # Normalize text for matching
    title_lower = (title or "").lower()
    desc_lower = (description or "").lower()
    cat_lower = (category or "").lower()
    combined_text = f"{title_lower} {desc_lower} {cat_lower}"

    # Layer 1: Grading company detection
    # If item has a grading company field set, it's almost certainly a card
    if grading_company:
        return ItemType.CARD

    # Check for grading company mentions in title
    for grader in GRADING_COMPANIES:
        if grader in title_lower:
            # But check for memorabilia override first
            if not any(override in combined_text for override in MEMORABILIA_OVERRIDE):
                return ItemType.CARD

    # Layer 2: Check for sealed products
    # Sealed boxes/packs should be identified before cards
    sealed_score = sum(1 for kw in SEALED_KEYWORDS if kw in combined_text)
    if sealed_score >= 2:
        return ItemType.SEALED
    if sealed_score >= 1 and ("box" in title_lower or "pack" in title_lower or "case" in title_lower):
        return ItemType.SEALED

    # Layer 3: Check for memorabilia override
    # These terms indicate memorabilia even if card keywords present
    if any(override in combined_text for override in MEMORABILIA_OVERRIDE):
        return ItemType.MEMORABILIA

    # Layer 4: Strong card indicators
    card_score = sum(1 for kw in CARD_STRONG_INDICATORS if kw in combined_text)

    # Check for numbered cards pattern (e.g., "/99", "#/25")
    numbered_pattern = re.search(r'[#/]\s*\d{1,4}\b', title_lower)
    if numbered_pattern:
        card_score += 2

    # Layer 5: Memorabilia detection
    memo_score = sum(1 for kw in MEMORABILIA_KEYWORDS if kw in combined_text)

    # Layer 6: Autograph detection
    auto_score = sum(1 for kw in AUTOGRAPH_KEYWORDS if kw in combined_text)

    # Decision logic

    # High card score - definitely a card
    if card_score >= 3:
        return ItemType.CARD

    # High memorabilia score - definitely memorabilia
    if memo_score >= 3:
        return ItemType.MEMORABILIA

    # Card has precedence if scores are close
    if card_score >= 2 and card_score > memo_score:
        return ItemType.CARD

    # Memorabilia wins if it has more indicators
    if memo_score >= 2 and memo_score > card_score:
        # But if autograph score is high too, it might be signed memorabilia
        if auto_score >= 2:
            return ItemType.AUTOGRAPH  # Signed memorabilia goes to AUTOGRAPH
        return ItemType.MEMORABILIA

    # Autograph-only items (not cards, not memorabilia)
    if auto_score >= 2 and card_score < 2 and memo_score < 2:
        return ItemType.AUTOGRAPH

    # Lower threshold matches
    if card_score >= 1:
        return ItemType.CARD

    if memo_score >= 1:
        return ItemType.MEMORABILIA

    if auto_score >= 1:
        return ItemType.AUTOGRAPH

    # Default to OTHER if no clear match
    return ItemType.OTHER


def detect_item_type_from_dict(item: Dict[str, Any]) -> ItemType:
    """
    Convenience function to detect item type from a dictionary.

    Args:
        item: Dictionary with item data

    Returns:
        ItemType enum value
    """
    return detect_item_type(
        title=item.get("title", ""),
        description=item.get("description"),
        category=item.get("category"),
        grading_company=item.get("grading_company"),
    )


def get_item_type_string(item_type: ItemType) -> str:
    """Get a human-readable string for the item type."""
    return {
        ItemType.CARD: "Trading Card",
        ItemType.MEMORABILIA: "Memorabilia",
        ItemType.AUTOGRAPH: "Autograph",
        ItemType.SEALED: "Sealed Product",
        ItemType.OTHER: "Other",
    }.get(item_type, "Unknown")
