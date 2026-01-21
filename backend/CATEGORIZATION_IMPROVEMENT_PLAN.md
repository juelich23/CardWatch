# Sport Categorization Improvement Plan

## Current State Analysis

### Problem Summary
- 51.3% of items (15,207) are categorized as "OTHER"
- Many sports cards are miscategorized because player names aren't in keyword lists
- Example: Anthony Edwards (115 items as OTHER, only 14 as BASKETBALL)

### Root Causes

1. **Incomplete Player Lists**: Current approach requires manually listing every player name
   - Missing: Anthony Edwards, Donovan Mitchell, Cooper Flagg, Derrick Rose, Shai Gilgeous-Alexander, Paolo Banchero, Michael Porter Jr., Lonzo Ball, Brandon Ingram, Stephon Castle, etc.

2. **Year Format Patterns Ignored**:
   - "2020-21" format = basketball/hockey season
   - "2024" format = baseball/football calendar year

3. **Card Manufacturer Context Lost**:
   - Panini primarily makes basketball, football, baseball, soccer cards
   - Topps primarily makes baseball cards
   - Upper Deck makes hockey, basketball cards

4. **Set Names Not Utilized**:
   - "National Treasures", "Prizm", "Select" - multi-sport Panini products
   - "Bowman", "Topps Chrome" - baseball-focused

5. **Non-Sports Items Mixed In**:
   - Star Wars, WWE/WWF, Pokemon, Magic: The Gathering, Yu-Gi-Oh
   - Should be explicitly categorized (maybe new category or explicit OTHER)

---

## Proposed Solution: Multi-Layer Detection

### Layer 1: Explicit Non-Sports Detection (First Pass)
Detect and categorize non-sports items immediately:

```python
NON_SPORTS_KEYWORDS = [
    # Trading Card Games
    "pokemon", "pikachu", "charizard", "magic: the gathering", "mtg",
    "yu-gi-oh", "yugioh",
    # Entertainment
    "star wars", "marvel", "dc comics", "disney",
    "wwe", "wwf", "wrestling",
    # Other Collectibles
    "garbage pail kids", "gpk"
]
```

### Layer 2: Enhanced Player Database
Massively expand player lists with current stars and rookies:

**Basketball Additions (~200+ players)**:
```python
# Current Stars (2020s)
"anthony edwards", "ant man", "ant edwards",
"tyrese haliburton", "tyrese maxey", "paolo banchero",
"victor wembanyama", "wemby", "chet holmgren",
"scottie barnes", "evan mobley", "franz wagner",
"donovan mitchell", "spida", "darius garland",
"trae young", "dejounte murray", "shai gilgeous-alexander", "sga",
"devin booker", "d-book", "bradley beal",
"damian lillard", "dame", "cj mccollum",
"karl-anthony towns", "kat", "rudy gobert",
"derrick rose", "d-rose",

# Recent Rookies (2023-2025)
"cooper flagg", "dylan harper", "ace bailey",
"stephon castle", "dalton knecht", "jared mccain",
"reed sheppard", "zaccharie risacher", "alex sarr",
"caitlin clark", "angel reese", "cameron brink",

# 2020s Draft Classes
"jalen green", "cade cunningham", "josh giddey",
"keegan murray", "bennedict mathurin", "jalen duren",
"ausar thompson", "amen thompson", "scoot henderson",
"brandon miller", "jarace walker", "taylor hendricks"
```

**Football Additions (~100+ players)**:
```python
# Recent QBs
"michael penix jr", "michael penix", "j.j. mccarthy", "jj mccarthy",
"bo nix", "spencer rattler", "sam howell", "will levis",

# Skill Position Stars
"amon-ra st. brown", "sun god", "sam laporta", "trey mcbride",
"de'von achane", "tank bigsby", "zay flowers", "quentin johnston"
```

**Baseball Additions (~100+ players)**:
```python
# Current Stars
"elly de la cruz", "gunnar henderson", "jackson holliday",
"corbin carroll", "julio rodriguez", "bobby witt jr",
"paul skenes", "jackson chourio", "evan carter",
"adley rutschman", "marcelo mayer", "james wood"

# Legends for vintage
"nolan ryan", "sandy koufax", "tom seaver", "bob gibson"
```

**Hockey Additions (~50+ players)**:
```python
"connor bedard", "adam fantilli", "leo carlsson",
"macklin celebrini", "logan cooley", "matty beniers",
"trevor zegras", "jason robertson", "roope hintz"
```

### Layer 3: Year Pattern Detection
Use card year format to disambiguate:

```python
def detect_year_pattern(title: str) -> Optional[str]:
    """
    Detect sport from year format in card titles.

    "2020-21" = basketball/hockey (split season)
    "2024" alone = baseball/football (calendar year)
    """
    # Split-year pattern: basketball/hockey
    split_year = re.search(r'(19|20)\d{2}-(1\d|2[0-5])\s+', title)
    if split_year:
        return "BASKETBALL_OR_HOCKEY"

    # Single year with Topps/Bowman = likely baseball
    if re.search(r'(19|20)\d{2}\s+(Topps|Bowman)', title):
        return "LIKELY_BASEBALL"

    return None
```

### Layer 4: Manufacturer + Set Name Context
Create product-to-sport mappings:

```python
PANINI_BASKETBALL_SETS = [
    "national treasures", "prizm", "select", "flawless", "immaculate",
    "noir", "one and one", "eminence", "origins", "contenders optic",
    "mosaic", "hoops", "donruss optic", "revolution", "spectra",
    "chronicles", "court kings", "crown royale"
]

PANINI_FOOTBALL_SETS = [
    "contenders", "score", "certified", "phoenix", "illusions",
    "plates & patches", "limited", "encased", "playbook"
]

TOPPS_BASEBALL_SETS = [
    "topps chrome", "bowman", "bowman chrome", "topps series",
    "stadium club", "gypsy queen", "allen & ginter", "heritage",
    "archives", "gallery", "inception", "dynasty", "luminaries",
    "definitive", "diamond icons", "sterling", "tribute", "tier one"
]

UPPER_DECK_HOCKEY_SETS = [
    "sp authentic", "sp game used", "the cup", "ultimate collection",
    "artifacts", "ice", "trilogy", "exquisite", "black diamond"
]
```

### Layer 5: Contextual Clues
Add sport-specific terminology patterns:

```python
BASKETBALL_CLUES = [
    r"rookie patch auto", r"rpa", r"jersey number",
    r"logoman", r"nba finals", r"all-star",
    r"#/\d+ - jersey", r"dual signed.*card"
]

BASEBALL_CLUES = [
    r"1st bowman", r"bowman chrome", r"sapphire",
    r"superfractor", r"printing plate",
    r"world series", r"all-star game"
]

FOOTBALL_CLUES = [
    r"rookie ticket", r"super bowl", r"pro bowl",
    r"draft picks", r"nfl shield"
]
```

---

## Implementation Plan

### Phase 1: Quick Wins (Immediate Impact)
1. Add 200+ missing player names to existing lists
2. Add non-sports detection as first pass
3. Re-run backfill

**Expected Impact**: Reduce OTHER from 51% to ~25-30%

### Phase 2: Pattern Detection
1. Implement year format detection
2. Add manufacturer + set name mappings
3. Implement contextual clue matching
4. Update scoring algorithm to weight layers

**Expected Impact**: Reduce OTHER to ~10-15%

### Phase 3: Refinement
1. Analyze remaining OTHER items
2. Add edge case handling
3. Consider ML-based classification for remaining items
4. Add "NON_SPORT" as explicit category option

---

## Updated Algorithm Flow

```
1. Check for non-sports keywords → NON_SPORT/OTHER
2. Check explicit player/team/league names → Direct match (high confidence)
3. Check year pattern → Narrow to sport family
4. Check manufacturer + set name → Further narrow
5. Apply contextual clues → Boost confidence
6. Calculate weighted score across all layers
7. Return highest confidence sport (or OTHER if below threshold)
```

---

## Files to Modify

| File | Changes |
|------|---------|
| `/backend/app/utils/sport_detection.py` | Add new layers, expand keywords |
| `/backend/scripts/backfill_sport.py` | Re-run after changes |

---

## Testing Strategy

1. Create test cases for known miscategorized items
2. Sample 100 random OTHER items before/after
3. Track distribution changes
4. Manual review of edge cases

---

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| OTHER % | 51.3% | <15% |
| BASKETBALL accuracy | ~10% of Edwards cards | >95% |
| False positives | Unknown | <2% |

---

## Timeline Estimate

- Phase 1: Immediate (can implement now)
- Phase 2: Follow-up session
- Phase 3: After analyzing Phase 2 results
