"""
Sport Detection Utility
Detects the sport category from auction item title, description, and category.
Multi-layer detection system:
1. Non-sports detection (Pokemon, MTG, Yu-Gi-Oh, Star Wars, WWE, etc.)
2. Player/team/league name matching
3. Sport-specific terminology
"""
from enum import Enum
from typing import Optional


# Non-sports keywords - items that should NOT be categorized as sports cards
NON_SPORTS_KEYWORDS = [
    # Trading Card Games
    "pokemon", "pokémon", "pikachu", "charizard", "mewtwo", "blastoise", "venusaur",
    "bulbasaur", "squirtle", "charmander", "eevee", "jigglypuff", "snorlax", "gengar",
    "dragonite", "mew", "lugia", "ho-oh", "rayquaza", "gyarados", "alakazam", "machamp",
    "arcanine", "lapras", "vaporeon", "jolteon", "flareon", "espeon", "umbreon",
    "tyranitar", "salamence", "metagross", "garchomp", "lucario", "greninja", "mimikyu",
    "sylveon", "gardevoir", "darkrai", "dialga", "palkia", "giratina", "arceus",
    "reshiram", "zekrom", "kyurem", "xerneas", "yveltal", "zygarde", "solgaleo",
    "lunala", "necrozma", "zacian", "zamazenta", "eternatus", "calyrex",
    "pokemon tcg", "pokemon card", "pokemon cards", "holo pokemon", "shadowless",
    "1st edition pokemon", "base set pokemon", "jungle pokemon", "fossil pokemon",
    "team rocket pokemon", "gym heroes", "gym challenge", "neo genesis", "neo discovery",
    "scarlet violet", "paldea", "obsidian flames", "crown zenith", "silver tempest",

    # Magic: The Gathering
    "magic the gathering", "magic: the gathering", "mtg", "black lotus", "planeswalker",
    "mox pearl", "mox sapphire", "mox jet", "mox ruby", "mox emerald", "time walk",
    "ancestral recall", "timetwister", "underground sea", "tropical island", "volcanic island",
    "tundra", "savannah", "scrubland", "bayou", "badlands", "taiga", "plateau",
    "jace", "liliana", "chandra", "nissa", "gideon", "ajani", "sorin", "elspeth",
    "karn", "ugin", "nicol bolas", "teferi", "vraska", "garruk", "nahiri",
    "phyrexia", "phyrexian", "dominaria", "ravnica", "innistrad", "zendikar", "theros",
    "amonkhet", "ixalan", "eldraine", "ikoria", "kaldheim", "strixhaven", "kamigawa",
    "commander", "edh", "modern horizons", "double masters", "masters set",
    "wizards of the coast", "wotc mtg",

    # Yu-Gi-Oh
    "yu-gi-oh", "yugioh", "yu gi oh", "ygo", "blue-eyes white dragon", "blue eyes white dragon",
    "dark magician", "exodia", "red-eyes black dragon", "red eyes black dragon",
    "black luster soldier", "dark magician girl", "kuriboh", "summoned skull",
    "celtic guardian", "flame swordsman", "gaia the fierce knight", "curse of dragon",
    "time wizard", "baby dragon", "thousand dragon", "blue-eyes ultimate dragon",
    "slifer the sky dragon", "obelisk the tormentor", "winged dragon of ra",
    "egyptian god card", "millennium puzzle", "duel monsters", "konami yugioh",
    "synchro", "xyz monster", "pendulum", "link monster", "fusion monster",
    "yugi muto", "seto kaiba",

    # Other TCGs
    "flesh and blood", "fab tcg", "disney lorcana", "lorcana", "one piece card game",
    "one piece tcg", "optcg", "digimon card game", "digimon tcg", "cardfight vanguard",
    "vanguard tcg", "weiss schwarz", "force of will", "final fantasy tcg", "fftcg",
    "dragon ball super card game", "dbs card game", "metazoo", "sorcery contested realm",
    "grand archive", "altered tcg", "star wars unlimited", "union arena",
    "battle spirits", "buddyfight", "keyforge", "netrunner", "legend of the five rings",
    "l5r", "arkham horror lcg", "lord of the rings lcg", "marvel champions lcg",

    # Star Wars
    "star wars", "starwars", "darth vader", "luke skywalker", "han solo", "yoda",
    "princess leia", "leia organa", "chewbacca", "chewie", "obi-wan kenobi", "obi wan",
    "anakin skywalker", "padme amidala", "mace windu", "qui-gon jinn", "count dooku",
    "emperor palpatine", "darth sidious", "darth maul", "kylo ren", "rey skywalker",
    "poe dameron", "bb-8", "bb8", "r2-d2", "r2d2", "c-3po", "c3po",
    "mandalorian", "mando", "grogu", "baby yoda", "boba fett", "jango fett",
    "din djarin", "ahsoka tano", "ahsoka", "clone trooper", "stormtrooper",
    "death star", "millennium falcon", "lightsaber", "jedi", "sith", "galactic empire",
    "rebel alliance", "first order", "resistance", "clone wars", "bad batch",
    "andor", "rogue one", "book of boba fett", "acolyte",
    "topps star wars", "star wars galaxy", "masterwork star wars",

    # Marvel (non-sports)
    "marvel", "marvel comics", "spider-man", "spiderman", "spider man", "peter parker",
    "miles morales", "iron man", "tony stark", "captain america", "steve rogers",
    "thor", "hulk", "bruce banner", "black widow", "natasha romanoff", "hawkeye",
    "clint barton", "avengers", "x-men", "xmen", "wolverine", "logan", "cyclops",
    "jean grey", "storm", "magneto", "professor x", "charles xavier", "beast",
    "rogue", "gambit", "nightcrawler", "colossus", "iceman", "angel", "psylocke",
    "deadpool", "wade wilson", "venom", "carnage", "thanos", "loki", "doctor strange",
    "scarlet witch", "wanda maximoff", "vision", "black panther", "tchalla",
    "captain marvel", "carol danvers", "ant-man", "wasp", "falcon",
    "winter soldier", "bucky barnes", "guardians of the galaxy", "star-lord",
    "groot", "rocket raccoon", "gamora", "drax", "nebula", "nick fury", "shield",
    "fantastic four", "mister fantastic", "invisible woman", "human torch", "thing",
    "silver surfer", "galactus", "doctor doom", "daredevil", "punisher", "elektra",
    "ghost rider", "moon knight", "ms marvel", "kamala khan", "she-hulk",
    "eternals", "shang-chi", "blade", "morbius", "kang", "modok",
    "marvel masterpieces", "marvel universe", "marvel annual", "fleer ultra marvel",
    "skybox marvel", "impel marvel",

    # DC Comics
    "dc comics", "dc universe", "batman", "bruce wayne", "superman", "clark kent",
    "kal-el", "wonder woman", "diana prince", "aquaman", "arthur curry", "flash",
    "barry allen", "wally west", "green lantern", "hal jordan", "john stewart",
    "martian manhunter", "cyborg", "hawkgirl", "hawkman", "green arrow", "oliver queen",
    "black canary", "zatanna", "constantine", "john constantine", "swamp thing",
    "justice league", "justice society", "teen titans", "doom patrol", "suicide squad",
    "joker", "harley quinn", "catwoman", "selina kyle", "penguin", "riddler",
    "two-face", "scarecrow", "bane", "poison ivy", "mr freeze", "ra's al ghul",
    "talia al ghul", "deathstroke", "lex luthor", "brainiac", "darkseid", "doomsday",
    "general zod", "sinestro", "black adam", "reverse flash", "captain cold",
    "robin", "nightwing", "dick grayson", "jason todd", "tim drake", "damian wayne",
    "batgirl", "barbara gordon", "supergirl", "kara zor-el", "superboy", "shazam",
    "gotham", "metropolis", "themyscira", "atlantis", "arkham asylum", "wayne manor",
    "batcave", "fortress of solitude", "hall of justice", "watchtower",

    # Disney
    "disney", "mickey mouse", "minnie mouse", "donald duck", "daisy duck", "goofy",
    "pluto", "chip and dale", "disney princess", "cinderella", "snow white",
    "sleeping beauty", "aurora", "ariel", "little mermaid", "belle", "beauty and the beast",
    "jasmine", "aladdin", "pocahontas", "mulan", "tiana", "rapunzel", "tangled",
    "merida", "brave", "moana", "elsa", "anna", "frozen", "olaf",
    "simba", "lion king", "nala", "timon", "pumbaa", "scar", "mufasa",
    "woody", "buzz lightyear", "toy story", "pixar", "finding nemo", "dory",
    "monsters inc", "mike wazowski", "sulley", "incredibles", "wall-e", "up",
    "coco", "inside out", "zootopia", "encanto", "luca", "turning red", "elemental",
    "disney villains", "maleficent", "ursula", "cruella", "jafar", "hades",

    # Harry Potter
    "harry potter", "hogwarts", "hermione granger", "ron weasley", "albus dumbledore",
    "severus snape", "voldemort", "he who must not be named", "tom riddle",
    "draco malfoy", "hagrid", "sirius black", "remus lupin", "neville longbottom",
    "luna lovegood", "ginny weasley", "fred and george", "dobby", "hedwig",
    "gryffindor", "slytherin", "hufflepuff", "ravenclaw", "quidditch", "golden snitch",
    "deathly hallows", "horcrux", "patronus", "expecto patronum",
    "elder wand", "invisibility cloak", "marauders map", "sorting hat",
    "diagon alley", "hogsmeade", "azkaban", "ministry of magic",
    "wizarding world", "fantastic beasts", "newt scamander",

    # Lord of the Rings
    "lord of the rings", "lotr", "middle earth", "middle-earth", "tolkien",
    "frodo baggins", "frodo", "samwise gamgee", "sam gamgee", "gandalf", "aragorn",
    "legolas", "gimli", "boromir", "merry", "pippin", "bilbo baggins", "bilbo",
    "gollum", "smeagol", "sauron", "saruman", "nazgul", "ringwraith", "balrog",
    "shire", "rivendell", "mordor", "gondor", "rohan", "minas tirith", "mount doom",
    "one ring", "fellowship of the ring", "two towers", "return of the king",
    "hobbit", "silmarillion", "rings of power",

    # Wrestling (not a traditional sport card category)
    "wwe", "wwf", "wrestling", "pro wrestling", "professional wrestling",
    "world wrestling", "world wrestling entertainment", "world wrestling federation",
    "hulk hogan", "hulkamania", "the rock", "dwayne johnson", "stone cold",
    "steve austin", "stone cold steve austin", "john cena", "undertaker",
    "the undertaker", "deadman", "shawn michaels", "hbk", "heartbreak kid",
    "bret hart", "ric flair", "nature boy", "randy savage",
    "macho man", "ultimate warrior", "andre the giant", "rowdy roddy piper",
    "triple h", "hhh", "randy orton", "rko", "edge", "rated r superstar",
    "batista", "rey mysterio", "619", "eddie guerrero", "chris jericho", "y2j",
    "big show", "kane", "mick foley", "mankind", "cactus jack", "dude love",
    "kurt angle", "goldberg", "brock lesnar", "roman reigns", "tribal chief",
    "seth rollins", "dean ambrose", "the shield", "becky lynch",
    "charlotte flair", "sasha banks", "bayley", "asuka", "bianca belair",
    "kofi kingston", "new day", "kevin owens", "aj styles", "phenomenal one",
    "drew mcintyre", "braun strowman", "fiend", "bray wyatt", "cody rhodes",
    "dusty rhodes", "american dream", "goldust", "booker t", "cm punk",
    "daniel bryan", "yes movement", "miz", "dolph ziggler", "sheamus",
    "wrestlemania", "royal rumble", "summerslam", "survivor series",
    "raw", "smackdown", "nxt", "monday night raw", "friday night smackdown",
    "aew", "all elite wrestling", "kenny omega", "young bucks", "jon moxley",
    "hangman adam page", "mjf", "jade cargill", "britt baker",
    "wcw", "world championship wrestling", "nwo", "new world order",
    "ecw", "extreme championship wrestling", "tna", "impact wrestling",
    "njpw", "new japan pro wrestling", "roh", "ring of honor",
    "lucha libre", "luchador",

    # Other Franchises
    "game of thrones", "house of the dragon", "jon snow", "daenerys targaryen",
    "tyrion lannister", "cersei lannister", "night king", "white walkers", "westeros",
    "stranger things", "eleven", "demogorgon", "upside down", "hawkins",
    "jurassic park", "jurassic world", "t-rex", "velociraptor", "dinosaur",
    "ghostbusters", "back to the future", "e.t.", "gremlins", "goonies",
    "indiana jones", "james bond", "007", "terminator", "alien", "aliens", "predator",
    "matrix", "neo matrix", "john wick", "mad max", "blade runner",
    "godzilla", "king kong", "kaiju", "pacific rim",
    "teenage mutant ninja turtles", "tmnt", "leonardo", "donatello", "raphael", "michelangelo",
    "power rangers", "mighty morphin", "voltron", "thundercats", "he-man", "masters of the universe",
    "gi joe", "g.i. joe", "cobra commander", "my little pony", "mlp",
    "anime", "manga", "naruto", "dragon ball", "dragon ball z", "dbz", "goku", "vegeta",
    "one piece", "luffy", "attack on titan", "demon slayer", "jujutsu kaisen",
    "my hero academia", "sailor moon", "studio ghibli", "totoro", "spirited away",
    "evangelion", "gundam", "cowboy bebop", "death note", "fullmetal alchemist",
    "bleach anime", "hunter x hunter", "one punch man", "mob psycho",

    # Transformers
    "transformers", "optimus prime", "megatron", "bumblebee", "starscream",
    "soundwave", "shockwave", "grimlock", "jazz", "ironhide", "ratchet",
    "autobots", "decepticons", "cybertron", "energon", "all spark",

    # Garbage Pail Kids & Other Non-Sport
    "garbage pail kids", "gpk", "adam bomb", "nasty nick", "topps gpk",
    "garbage pail", "wacky packages", "mars attacks",
    "non-sport", "nonsport", "non sport",
]


# =============================================================================
# PHASE 2: YEAR PATTERN DETECTION
# =============================================================================
# Basketball and Hockey use split-season format: "2020-21", "2023-24"
# Baseball and Football use single calendar year: "2024", "2023"
import re

# Pattern for split-year seasons (basketball/hockey): "2020-21", "2023-24"
SPLIT_YEAR_PATTERN = re.compile(r'(19|20)\d{2}-(0\d|1\d|2[0-5])\s+')

# Pattern for single year with Topps/Bowman (likely baseball): "2024 Topps", "2023 Bowman"
TOPPS_YEAR_PATTERN = re.compile(r'(19|20)\d{2}\s+(topps|bowman)', re.IGNORECASE)


# =============================================================================
# PHASE 2: MANUFACTURER + SET NAME MAPPINGS
# =============================================================================
# Maps card manufacturers and set names to likely sports


class Sport(Enum):
    """Enum of supported sport categories"""
    BASKETBALL = "BASKETBALL"
    BASEBALL = "BASEBALL"
    FOOTBALL = "FOOTBALL"
    HOCKEY = "HOCKEY"
    SOCCER = "SOCCER"
    GOLF = "GOLF"
    BOXING = "BOXING"
    RACING = "RACING"
    OTHER = "OTHER"


# Panini sets by sport (Panini makes cards for multiple sports)
PANINI_BASKETBALL_SETS = [
    "national treasures basketball", "prizm basketball", "select basketball",
    "flawless basketball", "immaculate basketball", "noir basketball",
    "one and one", "eminence", "origins basketball", "contenders optic basketball",
    "mosaic basketball", "hoops", "donruss optic basketball", "revolution",
    "spectra basketball", "chronicles basketball", "court kings", "crown royale basketball",
    "absolute basketball", "certified basketball", "status basketball",
]

PANINI_FOOTBALL_SETS = [
    "national treasures football", "prizm football", "select football",
    "contenders football", "score", "certified football", "phoenix",
    "illusions", "plates & patches", "limited football", "encased",
    "playbook", "obsidian football", "mosaic football", "donruss football",
    "chronicles football", "absolute football", "prestige", "origins football",
]

# Topps is primarily baseball (but also makes some football/soccer)
TOPPS_BASEBALL_SETS = [
    "topps chrome", "bowman", "bowman chrome", "bowman draft", "bowman 1st",
    "topps series", "topps update", "stadium club", "gypsy queen",
    "allen & ginter", "allen and ginter", "heritage", "archives",
    "gallery", "inception", "dynasty", "luminaries", "definitive",
    "diamond icons", "sterling", "tribute", "tier one", "five star",
    "topps finest", "topps gold label", "topps triple threads",
    "museum collection baseball", "clearly authentic",
]

# Upper Deck is primarily hockey
UPPER_DECK_HOCKEY_SETS = [
    "sp authentic", "sp game used", "the cup", "ultimate collection",
    "artifacts", "ice", "trilogy", "exquisite hockey", "black diamond",
    "upper deck series", "o-pee-chee", "opc", "synergy", "mvp hockey",
    "upper deck hockey", "young guns", "ud canvas", "ud portraits",
]

# Topps soccer sets
TOPPS_SOCCER_SETS = [
    "topps chrome soccer", "topps finest soccer", "merlin", "match attax",
    "topps ucl", "champions league", "topps bundesliga", "topps mls",
]

# Panini soccer sets
PANINI_SOCCER_SETS = [
    "prizm soccer", "select soccer", "national treasures soccer",
    "immaculate soccer", "flawless soccer", "obsidian soccer",
    "mosaic soccer", "donruss soccer", "chronicles soccer", "world cup",
    "euro", "copa america stickers", "fifa", "adrenalyn",
]

# Generic manufacturer indicators (without specific set names)
MANUFACTURER_SPORT_HINTS = {
    # Strong baseball indicators
    "bowman": Sport.BASEBALL,
    "topps chrome baseball": Sport.BASEBALL,
    "topps baseball": Sport.BASEBALL,
    "topps series 1": Sport.BASEBALL,
    "topps series 2": Sport.BASEBALL,
    "topps update": Sport.BASEBALL,
    "gypsy queen": Sport.BASEBALL,
    "allen & ginter": Sport.BASEBALL,
    "allen and ginter": Sport.BASEBALL,
    "stadium club baseball": Sport.BASEBALL,

    # Strong hockey indicators
    "upper deck hockey": Sport.HOCKEY,
    "o-pee-chee": Sport.HOCKEY,
    "opc hockey": Sport.HOCKEY,
    "sp authentic hockey": Sport.HOCKEY,
    "the cup hockey": Sport.HOCKEY,
    "young guns": Sport.HOCKEY,

    # Strong basketball indicators
    "hoops basketball": Sport.BASKETBALL,
    "nba hoops": Sport.BASKETBALL,
    "court kings": Sport.BASKETBALL,
    "crown royale basketball": Sport.BASKETBALL,

    # Strong football indicators
    "score football": Sport.FOOTBALL,
    "playoff contenders": Sport.FOOTBALL,
    "panini contenders football": Sport.FOOTBALL,
}


# Keywords mapped to each sport - ordered by specificity
# Player names, leagues, teams, and common terms
SPORT_KEYWORDS: dict[Sport, list[str]] = {
    Sport.BASKETBALL: [
        # Leagues
        "nba", "wnba", "ncaa basketball", "nba finals", "all-star",
        # Teams
        "lakers", "celtics", "bulls", "warriors", "knicks", "nets", "heat", "spurs",
        "mavericks", "mavs", "rockets", "clippers", "suns", "bucks", "76ers", "sixers",
        "pelicans", "grizzlies", "timberwolves", "wolves", "thunder", "jazz", "nuggets",
        "trail blazers", "blazers", "kings", "hawks", "hornets", "cavaliers", "cavs",
        "pistons", "pacers", "magic", "raptors", "wizards",

        # ============================================================
        # CURRENT NBA STARS (2020s Era)
        # ============================================================
        "anthony edwards", "ant edwards", "ant man edwards", "a1 from day 1",
        "tyrese haliburton", "haliburton",
        "tyrese maxey", "maxey",
        "paolo banchero", "banchero",
        "victor wembanyama", "wembanyama", "wemby", "the alien",
        "chet holmgren", "holmgren", "chet",
        "scottie barnes", "barnes",
        "evan mobley", "mobley",
        "franz wagner", "wagner",
        "donovan mitchell", "spida", "spida mitchell",
        "trae young", "ice trae", "trae",
        "dejounte murray", "murray",
        "shai gilgeous-alexander", "sga", "shai", "gilgeous-alexander",
        "devin booker", "d-book", "booker", "book",
        "damian lillard", "dame", "dame time", "dame lillard", "lillard",
        "karl-anthony towns", "kat", "towns", "karl anthony towns",
        "derrick rose", "d-rose", "d rose", "rose",
        "jimmy butler", "jimmy buckets", "butler",
        "bam adebayo", "adebayo", "bam",
        "jaylen brown", "j brown", "brown",
        "domantas sabonis", "sabonis",
        "de'aaron fox", "fox", "deaaron fox", "swipa",
        "fred vanvleet", "vanvleet", "fvv",
        "jrue holiday", "holiday",
        "khris middleton", "middleton",
        "pascal siakam", "siakam", "spicy p",
        "og anunoby", "anunoby",
        "mikal bridges", "bridges",
        "anfernee simons", "ant simons", "simons",
        "jarrett allen", "allen",
        "darius garland", "garland",
        "alperen sengun", "sengun",
        "jalen brunson", "brunson",
        "julius randle", "randle",
        "brandon ingram", "ingram", "bi", "b ingram",
        "cj mccollum", "c.j. mccollum", "mccollum",
        "desmond bane", "bane",
        "jaren jackson jr", "jjj", "jaren jackson", "triple j",
        "jamal murray", "j murray",
        "michael porter jr", "mpj", "michael porter", "porter jr",
        "aaron gordon", "gordon", "ag",
        "lauri markkanen", "markkanen", "lauri",
        "tyler herro", "herro", "boy wonder",
        "immanuel quickley", "quickley", "iq",
        "jalen williams", "j williams", "jwill",
        "josh hart", "hart",
        "austin reaves", "reaves", "ar-15", "hillbilly kobe",
        "max strus", "strus",
        "coby white", "white",

        # ============================================================
        # RECENT DRAFT CLASSES (2020-2025)
        # ============================================================
        "jalen green", "j green", "green",
        "cade cunningham", "cade", "cunningham",
        "josh giddey", "giddey",
        "keegan murray", "k murray",
        "bennedict mathurin", "mathurin", "benn mathurin",
        "jaden ivey", "ivey",
        "darius bazley", "bazley",
        "de'andre hunter", "deandre hunter", "hunter",
        "matisse thybulle", "thybulle",
        "jabari smith jr", "jabari smith", "jabari",
        "scoot henderson", "henderson", "scoot",
        "amen thompson", "thompson",
        "ausar thompson",
        "brandon miller", "b miller", "miller",
        "jarace walker", "walker",
        "gradey dick", "dick",
        "taylor hendricks", "hendricks",
        "keyonte george", "george",
        "cam whitmore", "whitmore",
        "bilal coulibaly", "coulibaly",
        "dereck lively ii", "lively", "dereck lively",
        "cooper flagg", "flagg",
        "dylan harper", "harper",
        "ace bailey", "bailey",
        "vj edgecombe", "edgecombe",
        "kon knueppel", "knueppel",
        "tre johnson", "t johnson",
        "kasparas jakucionis", "jakucionis",
        "airious bailey", "a bailey",
        "nolan traore", "traore",
        "egor demin", "demin",
        "khaman maluach", "maluach",
        "reed sheppard", "sheppard",
        "stephon castle", "castle",
        "dalton knecht", "knecht",
        "donovan clingan", "clingan",
        "rob dillingham", "dillingham",
        "matas buzelis", "buzelis",
        "zach edey", "edey",
        "tidjane salaun", "salaun",
        "devin carter", "d carter",
        "johnny furphy", "furphy",
        "cody williams", "c williams",
        "jared mccain", "mccain",
        "ron holland", "holland",
        "ja'kobe walter", "jakobe walter", "walter",
        "zaccharie risacher", "risacher",
        "alex sarr", "sarr",

        # ============================================================
        # WNBA STARS
        # ============================================================
        "caitlin clark", "clark", "caitlin",
        "angel reese", "reese", "angel", "bayou barbie",
        "cameron brink", "cam brink", "brink",
        "a'ja wilson", "aja wilson", "a'ja", "wilson",
        "breanna stewart", "stewie", "stewart",
        "sabrina ionescu", "ionescu", "sabrina",
        "kelsey plum", "plum",
        "chelsea gray", "gray",
        "jackie young", "j young",
        "alyssa thomas", "a thomas",
        "jonquel jones", "jj", "jones",
        "candace parker", "parker", "candace",
        "diana taurasi", "taurasi", "diana", "dee", "the goat",
        "sue bird", "bird",
        "brittney griner", "griner", "bg",
        "elena delle donne", "delle donne", "edd",
        "nneka ogwumike", "ogwumike",
        "courtney williams", "court williams",
        "dearica hamby", "hamby",
        "napheesa collier", "collier",
        "kayla mcbride", "mcbride",
        "skylar diggins-smith", "diggins", "skylar",
        "maya moore", "moore",
        "lisa leslie", "leslie",
        "sheryl swoopes", "swoopes",
        "tina thompson", "t thompson",
        "tamika catchings", "catchings",
        "lauren jackson", "l jackson",
        "becky hammon", "hammon",
        "aliyah boston", "boston", "aliyah",
        "rhyne howard", "howard",
        "deja kelly", "d kelly",
        "arike ogunbowale", "arike",
        "jewell loyd", "loyd",
        "paige bueckers", "bueckers", "paige",
        "juju watkins", "watkins", "juju",
        "hailey van lith", "van lith",
        "flau'jae johnson", "flaujae", "flau'jae",

        # ============================================================
        # CURRENT/RECENT LEGENDS (Still Active or Recently Retired)
        # ============================================================
        "lebron james", "lebron", "king james", "lbj", "the king", "bron",
        "stephen curry", "steph curry", "curry", "steph", "chef curry", "baby faced assassin",
        "kevin durant", "kd", "durant", "the slim reaper", "easy money sniper",
        "giannis antetokounmpo", "giannis", "greek freak", "the greek freak",
        "luka doncic", "luka", "doncic", "luka magic", "the don",
        "ja morant", "ja", "morant", "twelve",
        "jayson tatum", "tatum", "jt", "the problem",
        "joel embiid", "embiid", "the process", "troel",
        "nikola jokic", "jokic", "the joker", "joker", "big honey",
        "kawhi leonard", "kawhi", "leonard", "the klaw", "the claw", "fun guy",
        "paul george", "pg", "pg13", "playoff p",
        "chris paul", "cp3", "the point god",
        "kyrie irving", "kyrie", "uncle drew", "kai",
        "james harden", "harden", "the beard",
        "russell westbrook", "westbrook", "russ", "brodie", "mr triple double",
        "anthony davis", "ad", "the brow", "street clothes",
        "zion williamson", "zion", "williamson",
        "lamelo ball", "lamelo", "melo ball", "melo",
        "lonzo ball", "lonzo", "zo",
        "draymond green", "draymond", "day day",
        "klay thompson", "klay", "thompson", "splash brother",
        "andrew wiggins", "wiggins", "wiggs",
        "jordan poole", "poole",
        "deandre ayton", "ayton",

        # ============================================================
        # CLASSIC LEGENDS (Retired)
        # ============================================================
        "michael jordan", "jordan", "mj", "his airness", "air jordan", "the goat",
        "kobe bryant", "kobe", "black mamba", "mamba", "kb24", "bean",
        "shaquille o'neal", "shaq", "shaquille", "o'neal", "the big diesel",
        "the big aristotle", "shaq diesel", "superman",
        "magic johnson", "magic", "earvin johnson", "earvin",
        "larry bird", "bird", "larry legend", "the hick from french lick",
        "kareem abdul-jabbar", "kareem", "abdul-jabbar", "cap", "the captain",
        "wilt chamberlain", "wilt", "chamberlain", "wilt the stilt", "the big dipper",
        "bill russell", "russell", "mr eleven rings",
        "oscar robertson", "oscar", "the big o", "big o",
        "jerry west", "west", "the logo", "mr clutch",
        "elgin baylor", "baylor", "elgin",
        "bob cousy", "cousy", "the houdini of the hardwood",
        "john havlicek", "havlicek", "hondo",
        "julius erving", "dr j", "dr. j", "doctor j", "erving", "julius",
        "moses malone", "moses", "malone", "chairman of the boards",
        "george mikan", "mikan", "mr basketball",
        "bob pettit", "pettit",
        "dave cowens", "cowens",
        "willis reed", "reed",
        "earl monroe", "earl the pearl", "monroe",
        "dave bing", "bing",
        "nate archibald", "tiny archibald", "nate tiny archibald", "archibald",
        "pete maravich", "pistol pete", "maravich", "pistol",
        "walt frazier", "clyde", "frazier",
        "bernard king", "king",
        "dominique wilkins", "dominique", "wilkins", "the human highlight film",
        "human highlight reel", "nique",
        "clyde drexler", "drexler", "the glide", "clyde the glide",
        "gary payton", "payton", "the glove", "gp",
        "john stockton", "stockton", "stock",
        "karl malone", "malone", "the mailman", "mailman",
        "allen iverson", "iverson", "ai", "the answer", "a.i.",
        "dirk nowitzki", "dirk", "nowitzki", "the german wunderkind",
        "the tall baller from the g",
        "tim duncan", "duncan", "the big fundamental", "timmy",
        "dwyane wade", "wade", "d-wade", "flash", "d wade",
        "scottie pippen", "pippen", "pip", "no tippin pippen",
        "charles barkley", "barkley", "sir charles", "the round mound of rebound", "chuck",
        "hakeem olajuwon", "hakeem", "olajuwon", "the dream", "dream",
        "david robinson", "robinson", "the admiral", "admiral",
        "patrick ewing", "ewing", "pat ewing",
        "isiah thomas", "isiah", "zeke",
        "reggie miller", "reggie", "miller",
        "ray allen", "ray", "jesus shuttlesworth", "ray ray",
        "paul pierce", "pierce", "the truth", "truth",
        "kevin garnett", "kg", "garnett", "the big ticket", "big ticket",
        "vince carter", "vinsanity", "carter", "vc", "half man half amazing", "air canada",
        "tracy mcgrady", "tmac", "t-mac", "mcgrady",
        "grant hill", "hill",
        "penny hardaway", "penny", "hardaway", "anfernee hardaway",
        "alonzo mourning", "mourning", "zo",
        "chris webber", "webber", "c-webb", "cwebb",
        "jason kidd", "kidd", "j kidd",
        "steve nash", "nash",
        "amare stoudemire", "amare", "stoudemire", "stat",
        "yao ming", "yao", "ming",
        "manu ginobili", "manu", "ginobili",
        "tony parker", "tp", "parker",
        "pau gasol", "pau", "gasol",
        "marc gasol", "marc",
        "carmelo anthony", "melo", "carmelo", "me7o",
        "dwight howard", "dwight", "howard", "d12", "superman",
        "chris bosh", "bosh", "cb4",
        "blake griffin", "blake", "griffin",
        "derrick rose", "drose", "d rose", "mvp rose",
        "rajon rondo", "rondo", "playoff rondo",
        "john wall", "wall", "j wall",
        "demarcus cousins", "cousins", "boogie",
        "demar derozan", "derozan", "deebo",
        "gordon hayward", "hayward",
        "kemba walker", "kemba", "cardiac kemba",
        "ben simmons", "simmons",
        "markelle fultz", "fultz",
        "rj barrett", "barrett", "rj",
        "collin sexton", "sexton", "young bull",

        # ============================================================
        # HISTORICAL/VINTAGE GREATS
        # ============================================================
        "george gervin", "gervin", "iceman", "the iceman",
        "adrian dantley", "dantley",
        "alex english", "english",
        "robert parish", "parish", "the chief",
        "james worthy", "worthy", "big game james",
        "dennis rodman", "rodman", "the worm", "worm",
        "bill laimbeer", "laimbeer",
        "joe dumars", "dumars",
        "rick barry", "barry",
        "elvin hayes", "hayes", "the big e",
        "wes unseld", "unseld",
        "bill walton", "walton",
        "jack sikma", "sikma",
        "dan issel", "issel",
        "artis gilmore", "gilmore", "the a-train",
        "spencer haywood", "haywood",
        "connie hawkins", "hawkins", "the hawk",
        "sam jones", "s jones",
        "k.c. jones", "kc jones",
        "tom heinsohn", "heinsohn",
        "dolph schayes", "schayes",
        "paul arizin", "arizin",
        "hal greer", "greer",
        "billy cunningham", "cunningham", "kangaroo kid",
        "dave debusschere", "debusschere",
        "jerry lucas", "lucas",
        "nate thurmond", "thurmond",
        "lenny wilkens", "wilkens",
        "kevin mchale", "mchale",
        "dennis johnson", "dj", "d johnson",
        "sidney moncrief", "moncrief", "sid",
        "marques johnson", "m johnson",
        "bob lanier", "lanier",
        "lou hudson", "hudson", "sweet lou",
        "chet walker", "c walker",
        "gail goodrich", "goodrich",
        "jerry sloan", "sloan",
        "dick van arsdale", "van arsdale",
        "tom van arsdale",
        "calvin murphy", "murphy",
        "world b free", "lloyd free",
        "maurice cheeks", "mo cheeks", "cheeks",
        "fat lever", "lever",
        "mark aguirre", "aguirre",
        "terry cummings", "cummings",
        "jack twyman", "twyman",
        "maurice lucas", "lucas",
        "darryl dawkins", "dawkins", "chocolate thunder",
        "george mcginnis", "mcginnis",

        # ============================================================
        # MODERN ROLE PLAYERS & NOTABLE NAMES
        # ============================================================
        "andre iguodala", "iguodala", "iggy",
        "al horford", "horford",
        "marcus smart", "smart",
        "robert williams", "timelord", "rob williams",
        "grant williams", "g williams",
        "brook lopez", "lopez",
        "bobby portis", "portis", "bobby buckets",
        "malik monk", "monk",
        "kelly oubre", "oubre", "tsunami papi",
        "norman powell", "powell",
        "gary trent jr", "gary trent", "gtj",
        "precious achiuwa", "achiuwa",
        "nikola vucevic", "vucevic", "vooch",
        "jonas valanciunas", "valanciunas", "jv",
        "clint capela", "capela",
        "john collins", "collins",
        "rudy gobert", "gobert", "the stifle tower", "gobzilla",
        "mike conley", "conley",
        "malik beasley", "beasley",
        "terry rozier", "rozier", "scary terry",
        "miles bridges", "m bridges",
        "myles turner", "turner",
        "buddy hield", "hield", "buddy buckets",
        "monte morris", "m morris",
        "bruce brown", "b brown",
        "derrick white", "d white",
        "marcus morris", "mook",
        "markieff morris", "kief",
        "kyle kuzma", "kuzma", "kuz",
        "cameron johnson", "cam johnson",
        "spencer dinwiddie", "dinwiddie",
        "shake milton", "milton",

        # Terms
        "basketball", "dunk", "slam dunk", "three pointer", "triple double",
    ],
    Sport.BASEBALL: [
        # Leagues
        "mlb", "major league baseball", "minor league",
        # Teams
        "yankees", "red sox", "dodgers", "cubs", "giants", "mets", "cardinals",
        "braves", "astros", "phillies", "padres", "rangers", "mariners", "tigers",
        "orioles", "twins", "white sox", "angels", "athletics", "royals", "reds",

        # ============================================================
        # CURRENT STARS (2020s)
        # ============================================================
        "shohei ohtani", "ohtani",
        "mike trout", "trout",
        "mookie betts", "betts",
        "aaron judge", "judge",
        "juan soto", "soto",
        "ronald acuna jr", "ronald acuna", "acuna jr", "acuna",
        "freddie freeman", "freeman",
        "corey seager", "seager",
        "manny machado", "machado",
        "trea turner", "turner",
        "bryce harper", "harper",
        "nolan arenado", "arenado",
        "pete alonso", "alonso", "polar bear",
        "rafael devers", "devers",
        "marcus semien", "semien",
        "jose ramirez", "j-ram",
        "vladimir guerrero jr", "vlad jr", "vladdy",
        "bo bichette", "bichette",
        "fernando tatis jr", "tatis jr", "tatis",
        "matt olson", "olson",
        "kyle tucker", "tucker",
        "yordan alvarez", "alvarez",
        "jose altuve", "altuve",
        "francisco lindor", "lindor",
        "austin riley", "riley",
        "wander franco", "franco",
        "xander bogaerts", "bogaerts",
        "cody bellinger", "bellinger",
        "kyle schwarber", "schwarber",
        "ozzie albies", "albies",

        # ============================================================
        # YOUNG STARS / ROOKIES
        # ============================================================
        "elly de la cruz", "de la cruz", "elly",
        "gunnar henderson", "henderson",
        "jackson holliday", "holliday",
        "corbin carroll", "carroll",
        "julio rodriguez", "j-rod", "julio",
        "bobby witt jr", "witt jr", "bobby witt",
        "adley rutschman", "rutschman",
        "paul skenes", "skenes",
        "jackson chourio", "chourio",
        "evan carter", "carter",
        "james wood", "wood",
        "marcelo mayer", "mayer",
        "junior caminero", "caminero",
        "jackson merrill", "merrill",
        "wyatt langford", "langford",
        "jasson dominguez", "dominguez", "the martian",
        "anthony volpe", "volpe",
        "jordan walker", "walker",
        "brooks lee", "lee",
        "spencer torkelson", "torkelson",
        "riley greene", "greene",
        "ceddanne rafaela", "rafaela",
        "masyn winn", "winn",
        "colton cowser", "cowser",
        "pete crow-armstrong", "crow-armstrong",
        "francisco alvarez", "f. alvarez",

        # ============================================================
        # PITCHING STARS (CURRENT)
        # ============================================================
        "gerrit cole", "cole",
        "jacob degrom", "degrom",
        "max scherzer", "scherzer", "mad max",
        "justin verlander", "verlander", "jv",
        "zack wheeler", "wheeler",
        "corbin burnes", "burnes",
        "spencer strider", "strider",
        "shane mcclanahan", "mcclanahan",
        "tyler glasnow", "glasnow",
        "zac gallen", "gallen",
        "logan webb", "webb",
        "aaron nola", "nola",
        "pablo lopez", "lopez",
        "yoshinobu yamamoto", "yamamoto",
        "shota imanaga", "imanaga",
        "tarik skubal", "skubal",
        "chris sale", "sale",
        "sandy alcantara", "alcantara",
        "blake snell", "snell",
        "max fried", "fried",
        "clayton kershaw", "kershaw",
        "josh hader", "hader",
        "edwin diaz", "diaz",
        "emmanuel clase", "clase",
        "felix bautista", "bautista",
        "raisel iglesias", "iglesias",
        "devin williams", "williams",

        # ============================================================
        # LEGENDS - PRE-1970 (VINTAGE CARDS)
        # ============================================================
        "babe ruth", "ruth", "the bambino", "sultan of swat",
        "willie mays", "mays", "the say hey kid", "say hey kid",
        "hank aaron", "aaron", "hammerin hank", "hammer",
        "mickey mantle", "mantle", "the mick",
        "ted williams", "williams", "teddy ballgame", "the splendid splinter",
        "lou gehrig", "gehrig", "the iron horse",
        "jackie robinson", "robinson",
        "joe dimaggio", "dimaggio", "joltin joe", "the yankee clipper",
        "roberto clemente", "clemente",
        "sandy koufax", "koufax",
        "bob gibson", "gibson",
        "honus wagner", "wagner",
        "ty cobb", "cobb", "the georgia peach",
        "cy young", "young",
        "walter johnson", "johnson", "the big train",
        "stan musial", "musial", "stan the man",
        "yogi berra", "berra",
        "brooks robinson", "b. robinson",
        "ernie banks", "banks", "mr. cub",
        "warren spahn", "spahn",
        "whitey ford", "ford", "the chairman of the board",
        "duke snider", "snider", "the duke of flatbush",
        "roy campanella", "campanella", "campy",
        "satchel paige", "paige",
        "josh gibson", "j. gibson",
        "cool papa bell", "bell",
        "hank greenberg", "greenberg",
        "jimmie foxx", "foxx", "double x",
        "mel ott", "ott",
        "bill dickey", "dickey",
        "lefty grove", "grove",
        "johnny bench", "bench",
        "harmon killebrew", "killebrew", "killer",
        "al kaline", "kaline", "mr. tiger",
        "frank robinson", "f. robinson",
        "carl yastrzemski", "yaz", "yastrzemski",

        # ============================================================
        # LEGENDS - 1970s-1990s
        # ============================================================
        "nolan ryan", "ryan", "the ryan express",
        "tom seaver", "seaver", "tom terrific",
        "george brett", "brett",
        "mike schmidt", "schmidt",
        "cal ripken jr", "ripken", "the iron man",
        "tony gwynn", "gwynn", "mr. padre",
        "ken griffey jr", "griffey jr", "griffey", "junior", "the kid",
        "barry bonds", "bonds",
        "roger clemens", "clemens", "the rocket",
        "greg maddux", "maddux", "the professor",
        "randy johnson", "r. johnson", "the big unit",
        "pedro martinez", "pedro",
        "wade boggs", "boggs",
        "rickey henderson", "r. henderson", "man of steal",
        "ozzie smith", "o. smith", "the wizard",
        "dave winfield", "winfield",
        "robin yount", "yount",
        "eddie murray", "murray",
        "ryne sandberg", "sandberg", "ryno",
        "kirby puckett", "puckett",
        "paul molitor", "molitor",
        "don mattingly", "mattingly", "donnie baseball",
        "andre dawson", "dawson", "the hawk",
        "gary carter", "carter", "the kid",
        "dennis eckersley", "eckersley", "eck",
        "john smoltz", "smoltz",
        "frank thomas", "thomas", "the big hurt",
        "sammy sosa", "sosa",
        "mark mcgwire", "mcgwire", "big mac",
        "jeff bagwell", "bagwell", "baggy",
        "craig biggio", "biggio",
        "mike piazza", "piazza",
        "ivan rodriguez", "pudge", "i-rod",
        "trevor hoffman", "hoffman",
        "curt schilling", "schilling",

        # ============================================================
        # LEGENDS - 2000s-2010s
        # ============================================================
        "derek jeter", "jeter", "the captain", "dj",
        "alex rodriguez", "rodriguez", "a-rod",
        "albert pujols", "pujols", "the machine",
        "david ortiz", "ortiz", "big papi", "papi",
        "mariano rivera", "rivera", "mo", "sandman",
        "ichiro suzuki", "ichiro",
        "chipper jones", "jones",
        "manny ramirez", "manny", "manny being manny",
        "vladimir guerrero", "guerrero",
        "roy halladay", "halladay", "doc",
        "tim lincecum", "lincecum", "the freak",
        "dustin pedroia", "pedroia", "pedey", "laser show",
        "joe mauer", "mauer",
        "evan longoria", "longoria", "longo",
        "robinson cano", "cano",
        "buster posey", "posey",
        "andrew mccutchen", "mccutchen", "cutch",
        "adrian beltre", "beltre",
        "miguel cabrera", "cabrera", "miggy",
        "joey votto", "votto",
        "ryan howard", "howard", "the big piece",
        "prince fielder", "fielder",
        "david wright", "wright", "captain america",
        "jose reyes", "reyes",
        "troy tulowitzki", "tulowitzki", "tulo",
        "hanley ramirez", "h. ramirez",
        "cc sabathia", "sabathia",
        "felix hernandez", "hernandez", "king felix",
        "madison bumgarner", "bumgarner", "madbum",
        "stephen strasburg", "strasburg",
        "kris bryant", "bryant", "kb",
        "anthony rizzo", "rizzo",
        "javier baez", "baez", "el mago",
        "christian yelich", "yelich", "yeli",
        "giancarlo stanton", "stanton",
        "paul goldschmidt", "goldschmidt", "goldy",
        "jose bautista", "bautista", "joey bats",
        "josh donaldson", "donaldson", "bringer of rain",

        # Terms
        "baseball", "home run", "pitcher", "batting",
    ],
    Sport.FOOTBALL: [
        # Leagues
        "nfl", "ncaa football", "college football", "super bowl",
        # Teams
        "chiefs", "eagles", "cowboys", "49ers", "packers", "patriots", "bills",
        "dolphins", "jets", "ravens", "steelers", "bengals", "browns", "titans",
        "colts", "texans", "jaguars", "broncos", "raiders", "chargers", "seahawks",
        "cardinals", "rams", "saints", "falcons", "panthers", "buccaneers", "bucs",
        "vikings", "bears", "lions", "commanders", "giants",
        # Player names
        "tom brady", "patrick mahomes", "joe montana", "peyton manning", "eli manning",
        "aaron rodgers", "brett favre", "dan marino", "john elway", "johnny unitas",
        "joe burrow", "josh allen", "jalen hurts", "lamar jackson", "dak prescott",
        "justin herbert", "trevor lawrence", "tua tagovailoa", "deshaun watson",
        "jerry rice", "randy moss", "terrell owens", "calvin johnson", "megatron",
        "tyreek hill", "davante adams", "justin jefferson", "ja'marr chase",
        "jordan love", "cj stroud", "c.j. stroud", "brock purdy", "anthony richardson",
        "caleb williams", "jayden daniels", "drake maye", "bo nix", "marvin harrison jr",
        "malik nabers", "rome odunze", "bijan robinson", "breece hall", "jahmyr gibbs",
        "puka nacua", "nico collins", "garrett wilson", "chris olave", "drake london",
        "zay flowers", "flowers", "jonathan taylor", "brock bowers", "bowers",
        "jj mccarthy", "j.j. mccarthy", "mccarthy", "travis etienne", "travis etienne jr", "etienne",
        "de'von achane", "achane", "phidarian mathis", "mathis", "will fuller", "fuller",
        "micah parsons", "tj watt", "t.j. watt", "nick bosa", "myles garrett",
        "sauce gardner", "derek stingley", "ed reed", "troy polamalu",
        "lawrence taylor", "ray lewis", "dick butkus", "brian urlacher",
        "walter payton", "sweetness", "emmitt smith", "barry sanders", "jim brown",
        "adrian peterson", "derrick henry", "christian mccaffrey", "dalvin cook",
        "travis kelce", "tony gonzalez", "rob gronkowski", "gronk",
        "reggie white", "deion sanders", "prime time", "rod woodson",
        "jim thorpe", "deacon jones", "mean joe greene",
        # Terms
        "football", "quarterback", "touchdown", "nfl",
    ],
    Sport.HOCKEY: [
        # Leagues
        "nhl", "national hockey league",
        # Teams
        "bruins", "canadiens", "maple leafs", "rangers", "blackhawks", "red wings",
        "penguins", "flyers", "oilers", "avalanche", "lightning", "panthers",
        "golden knights", "kraken", "flames", "canucks", "jets", "wild", "blues",
        "predators", "stars", "hurricanes", "senators", "sabres", "islanders",
        "devils", "capitals", "blue jackets", "ducks", "kings", "sharks", "coyotes",
        # Player names - Legends (Hall of Famers & All-Time Greats)
        "wayne gretzky", "the great one", "mario lemieux", "super mario", "gordie howe", "mr. hockey",
        "bobby orr", "bobby hull", "the golden jet", "brett hull", "the golden brett",
        "guy lafleur", "the flower", "jean beliveau", "maurice richard", "rocket richard",
        "terry sawchuk", "jacques plante", "ken dryden", "bernie parent",
        "phil esposito", "tony esposito", "marcel dionne", "mike bossy",
        "denis potvin", "ray bourque", "paul coffey", "brian leetch", "chris chelios",
        "mark messier", "the moose", "steve yzerman", "the captain", "joe sakic", "burnaby joe",
        "patrick roy", "saint patrick", "dominik hasek", "the dominator",
        "jaromir jagr", "teemu selanne", "the finnish flash", "peter forsberg", "foppa",
        "pavel bure", "the russian rocket", "sergei fedorov", "nicklas lidstrom", "the perfect human",
        "eric lindros", "the big e", "john leclair", "ron francis", "joe thornton", "jumbo joe",
        "mats sundin", "darryl sittler", "borje salming", "lanny mcdonald",
        "dino ciccarelli", "mike modano", "jeremy roenick", "jj", "pat lafontaine",
        "cam neely", "brendan shanahan", "keith tkachuk", "doug gilmour", "killer",
        "scott stevens", "rod langway", "larry robinson", "serge savard",
        "glenn hall", "mr. goalie", "grant fuhr", "billy smith", "ed belfour", "eddie the eagle",
        "chris pronger", "scott niedermayer", "al macinnis", "rob blake",
        "martin st. louis", "marty st. louis",
        # Player names - Modern Stars (Active/Recent)
        "sidney crosby", "sid the kid", "alex ovechkin", "ovie", "ovi", "the great eight",
        "connor mcdavid", "auston matthews", "nathan mackinnon", "nate the great",
        "nikita kucherov", "kuch", "david pastrnak", "pasta", "leon draisaitl", "drai",
        "cale makar", "patrick kane", "kaner", "jonathan toews", "captain serious",
        "steven stamkos", "stammer", "victor hedman", "andrei vasilevskiy", "vasy",
        "igor shesterkin", "shesty", "connor hellebuyck", "bucky",
        "kirill kaprizov", "the wild thing", "matthew tkachuk", "chucky", "brady tkachuk",
        "mitch marner", "william nylander", "willy styles", "john tavares", "jt",
        "jack eichel", "tage thompson", "jason robertson", "robo", "miro heiskanen",
        "elias pettersson", "petey", "quinn hughes", "jack hughes", "luke hughes",
        "trevor zegras", "zeggy", "mason mctavish", "troy terry",
        "zach werenski", "seth jones", "adam fox", "foxy", "jaccob slavin",
        "anze kopitar", "racoon jesus", "drew doughty", "jonathan quick", "quickie",
        "mark scheifele", "scheif", "kyle connor", "josh morrissey",
        "aleksander barkov", "sasha barkov", "matthew tkachuk", "sam reinhart", "reins",
        "mikko rantanen", "moose", "gabriel landeskog", "landy",
        "j.t. miller", "brock boeser", "the flow",
        "alex debrincat", "the cat", "tim stutzle", "timmy",
        "moritz seider", "mo seider", "dylan larkin", "lucas raymond",
        "sebastien aho", "seabass", "andrei svechnikov", "svech",
        "jake guentzel", "jake the snake", "kris letang", "evgeni malkin", "geno",
        "claude giroux", "g", "travis konecny", "tk",
        "roman josi", "filip forsberg",
        # Player names - Young Stars & Top Prospects
        "connor bedard", "adam fantilli", "leo carlsson", "macklin celebrini", "logan cooley",
        "matvei michkov", "lane hutson", "will smith", "david reinbacher",
        "cutter gauthier", "oliver moore", "gabe perreault", "calum ritchie",
        "brayden yager", "sam dickinson", "carter yakemchuk", "zayne parekh",
        "beckett sennecke", "michael brandsegg-nygard", "cole eiserman",
        "artyom levshunov", "zeev buium", "tij iginla", "cayden lindstrom",
        "dylan guenther", "shane wright", "owen power", "simon nemec",
        "juraj slafkovsky", "logan stankoven", "wyatt johnston", "matthew knies",
        "kirby dach", "cole caufield", "coley", "nick suzuki", "zuke",
        "matty beniers", "seth jarvis", "jarvy", "mason marchment",
        # Terms
        "hockey", "ice hockey", "stanley cup", "hat trick",
    ],
    Sport.SOCCER: [
        # Leagues/Competitions
        "fifa", "world cup", "premier league", "la liga", "bundesliga", "serie a",
        "champions league", "mls", "euro", "copa america", "ligue 1", "eredivisie",
        "fa cup", "carabao cup", "europa league", "conference league",
        # Teams
        "manchester united", "man united", "real madrid", "barcelona", "barca",
        "bayern munich", "liverpool", "chelsea", "arsenal", "manchester city",
        "man city", "psg", "paris saint-germain", "juventus", "inter milan",
        "ac milan", "atletico madrid", "tottenham", "spurs", "borussia dortmund",
        "napoli", "roma", "lazio", "ajax", "benfica", "porto", "sporting cp",
        "celtic", "rangers",
        # Player names - All-Time Legends
        "pele", "o rei", "diego maradona", "el pibe de oro", "johan cruyff",
        "franz beckenbauer", "der kaiser", "alfredo di stefano", "la saeta rubia",
        "george best", "bobby charlton", "bobby moore", "gordon banks",
        "gerd muller", "der bomber", "eusebio", "the black panther", "puskas", "ferenc puskas",
        "lev yashin", "the black spider", "garrincha", "the joy of the people",
        "michel platini", "marco van basten", "ruud gullit", "frank rijkaard",
        "paolo maldini", "franco baresi", "fabio cannavaro", "alessandro nesta",
        "lothar matthaus", "jurgen klinsmann", "rudi voller",
        "roberto baggio", "il divin codino", "gianni rivera", "dino zoff",
        "romario", "bebeto", "socrates", "zico", "falcao", "rivaldo",
        # Player names - Modern Legends (1990s-2010s)
        "zinedine zidane", "zizou", "ronaldinho", "gaucho", "ronaldo nazario", "r9", "il fenomeno",
        "thierry henry", "titi", "patrick vieira", "dennis bergkamp", "the iceman",
        "david beckham", "becks", "ryan giggs", "paul scholes", "roy keane",
        "eric cantona", "king eric", "peter schmeichel",
        "wayne rooney", "wazza", "steven gerrard", "stevie g", "frank lampard", "super frank",
        "john terry", "jt", "ashley cole", "didier drogba", "didi",
        "zlatan ibrahimovic", "ibra", "kaka", "andrea pirlo", "il maestro",
        "gianluigi buffon", "buffon", "iker casillas", "san iker",
        "xavi hernandez", "xavi", "andres iniesta", "el ilusionista", "carles puyol", "puyol",
        "sergio busquets", "busi", "david villa", "el guaje", "fernando torres", "el nino",
        "raul gonzalez", "raul", "sergio ramos", "capi", "marcelo", "dani alves",
        "luka modric", "the maestro", "toni kroos",
        "samuel eto'o", "michael essien", "claude makelele",
        "david silva", "merlin", "sergio aguero", "kun aguero", "yaya toure",
        "eden hazard", "n'golo kante",
        "arjen robben", "franck ribery",
        "philipp lahm", "bastian schweinsteiger", "manuel neuer",
        "jaap stam", "edwin van der sar", "rio ferdinand", "nemanja vidic",
        # Player names - Current Superstars
        "lionel messi", "leo messi", "la pulga", "the goat",
        "cristiano ronaldo", "cr7", "ronaldo",
        "neymar", "neymar jr", "ney",
        "kylian mbappe", "mbappe", "kyky", "donatello",
        "erling haaland", "haaland", "the viking", "the terminator",
        "kevin de bruyne", "kdb", "ginger pele",
        "mohamed salah", "mo salah", "the egyptian king",
        "robert lewandowski", "lewy",
        "karim benzema", "benz", "the cat",
        "harry kane", "hurricane",
        "virgil van dijk", "vvd", "the colossus",
        "sadio mane", "trent alexander-arnold", "taa", "andy robertson", "robbo",
        "marcus rashford", "rashy", "bruno fernandes", "bruno magnifico",
        "casemiro", "case", "raphael varane",
        # Player names - Current Rising Stars
        "jude bellingham", "bellingham",
        "vinicius jr", "vini jr",
        "pedri", "gavi", "lamine yamal", "pau cubarsi",
        "bukayo saka", "starboy", "declan rice",
        "phil foden", "the stockport iniesta", "jack grealish",
        "jadon sancho", "rashford", "marcus rashford",
        "florian wirtz", "jamal musiala", "musi",
        "rodri", "josko gvardiol",
        "khvicha kvaratskhelia", "kvara", "victor osimhen",
        "rafael leao",
        "goncalo ramos", "antonio silva",
        "enzo fernandez", "moises caicedo",
        "julian alvarez", "the spider",
        "darwin nunez", "luis diaz", "lucho",
        "alphonso davies", "phonzy", "joshua kimmich",
        "achraf hakimi", "ousmane dembele", "dembele",
        "federico valverde", "fede", "jude bellingham", "aurelien tchouameni",
        "alejandro garnacho", "garnacho", "kobbie mainoo",
        "warren zaire-emery", "bradley barcola",
        # Player names - American Stars (MLS & USMNT)
        "christian pulisic", "captain america", "pulisic",
        "weston mckennie", "mckennie", "tyler adams",
        "gio reyna", "giovanni reyna", "yunus musah",
        "tim weah", "brenden aaronson", "medford messi",
        "sergino dest", "chris richards", "antonee robinson", "jedi",
        "ricardo pepi", "folarin balogun",
        "matt turner", "ethan horvath", "zack steffen",
        "landon donovan", "ld", "clint dempsey", "deuce",
        "tim howard", "secretary of defense", "brian mcbride",
        "claudio reyna", "tab ramos", "alexi lalas",
        "josef martinez", "hector herrera", "carlos vela",
        "lorenzo insigne", "federico bernardeschi",
        "inter miami", "la galaxy", "lafc",
        # Terms
        "soccer", "futbol", "football club", "fc ", "f.c.",
    ],
    Sport.GOLF: [
        # Tours/Competitions
        "pga", "lpga", "masters", "us open golf", "british open", "the open",
        "ryder cup", "presidents cup", "pga championship", "liv golf",
        "players championship", "tour championship", "memorial tournament",
        # Player names - All-Time Legends
        "tiger woods", "el tigre", "the big cat", "eldrick",
        "jack nicklaus", "the golden bear",
        "arnold palmer", "the king", "arnie",
        "gary player", "the black knight", "mr. fitness",
        "ben hogan", "the hawk", "bantam ben",
        "sam snead", "slammin' sammy", "samuel jackson snead",
        "bobby jones", "emperor jones",
        "byron nelson", "lord byron",
        "gene sarazen", "the squire",
        "walter hagen", "sir walter", "the haig",
        "lee trevino", "super mex", "the merry mex",
        "tom watson", "watson",
        "seve ballesteros", "seve", "el nino",
        "nick faldo", "sir nick",
        "greg norman", "the great white shark", "the shark",
        "raymond floyd", "ray floyd",
        "tom kite", "johnny miller",
        "payne stewart", "hale irwin", "curtis strange",
        "nick price", "bernhard langer",
        "jose maria olazabal", "ollie",
        "fred couples", "boom boom",
        "davis love iii", "vijay singh", "the big fijian",
        "ernie els", "the big easy",
        "david duval", "mark o'meara",
        "john daly", "jd", "wild thing", "long john",
        # Player names - Modern Stars
        "phil mickelson", "lefty", "phil the thrill",
        "rory mcilroy", "rors", "wee mac",
        "jordan spieth", "the golden child", "spieth",
        "justin thomas", "jt",
        "brooks koepka", "brooksie",
        "dustin johnson", "dj",
        "bryson dechambeau", "the scientist", "bryson",
        "scottie scheffler", "scheff",
        "jon rahm", "rahmbo",
        "collin morikawa", "the samurai",
        "xander schauffele", "x", "xman",
        "viktor hovland", "vik", "the norwegian",
        "cameron smith", "cam smith", "mullet man",
        "patrick cantlay", "patty ice",
        "tony finau", "big tone",
        "max homa", "maxhomapga",
        "wyndham clark", "sahith theegala",
        "hideki matsuyama", "deki",
        "tommy fleetwood", "tom fleetwood",
        "shane lowry", "matt fitzpatrick", "fitzy",
        "adam scott", "scotty",
        "jason day", "rickie fowler",
        "sergio garcia", "el nino",
        "francesco molinari", "frankie",
        "webb simpson", "zach johnson", "zj",
        "patrick reed", "captain america",
        "ludvig aberg", "ludde",
        "will zalatoris", "willy z",
        "sam burns", "kurt kitayama", "brian harman",
        "keegan bradley", "corey conners", "russell henley",
        "cameron young", "cam young",
        "tyrrell hatton", "tom kim", "joohyung kim",
        "sungjae im", "si woo kim",
        # Player names - LPGA & Women's Golf
        "annika sorenstam", "annika", "the world's best golfer",
        "nancy lopez", "nance",
        "kathy whitworth", "pat bradley",
        "betsy king", "patty sheehan", "beth daniel",
        "se ri pak", "karrie webb", "lorena ochoa",
        "nelly korda", "jessica korda",
        "lexi thompson", "lydia ko",
        "jin young ko", "ko jin-young",
        "inbee park", "so yeon ryu",
        "minjee lee", "brooke henderson",
        "ariya jutanugarn", "atthaya thitikul",
        "charley hull", "lilia vu",
        "celine boutier", "rose zhang",
        # Terms
        "golf", "golfer", "pga tour", "lpga tour",
    ],
    Sport.BOXING: [
        # Organizations
        "wba", "wbc", "ibf", "wbo", "ufc", "bellator", "pfl", "one championship",
        # Boxing - All-Time Legends
        "muhammad ali", "cassius clay", "the greatest", "the louisville lip",
        "mike tyson", "iron mike", "kid dynamite", "the baddest man on the planet",
        "sugar ray robinson", "pound for pound greatest",
        "sugar ray leonard", "ray leonard",
        "joe louis", "brown bomber", "the detroit bomber",
        "rocky marciano", "the brockton blockbuster", "the rock",
        "jack dempsey", "the manassa mauler",
        "joe frazier", "smokin joe",
        "george foreman", "big george",
        "marvin hagler", "marvelous marvin hagler",
        "thomas hearns", "tommy hearns", "the hitman", "the motor city cobra",
        "roberto duran", "manos de piedra", "hands of stone",
        "julio cesar chavez", "jc superstar", "mr. knockout",
        "jack johnson", "the galveston giant",
        "henry armstrong", "homicide hank",
        "willie pep", "will o' the wisp",
        "archie moore", "the old mongoose",
        "ezzard charles", "the cincinnati cobra",
        "jersey joe walcott", "gene tunney", "the fighting marine",
        "carmen basilio", "emile griffith", "carlos monzon",
        "alexis arguello", "the explosive thin man",
        "salvador sanchez", "wilfredo gomez", "bazooka gomez",
        "aaron pryor", "the hawk",
        "larry holmes", "the easton assassin",
        "michael spinks", "jinx",
        "evander holyfield", "the real deal",
        "riddick bowe", "big daddy",
        "lennox lewis", "the lion",
        "pernell whitaker", "sweet pea",
        "oscar de la hoya", "golden boy",
        "felix trinidad", "tito trinidad",
        "shane mosley", "sugar shane",
        "bernard hopkins", "the executioner", "b-hop", "the alien",
        "roy jones jr", "rjj", "captain hook", "superman",
        "james toney", "lights out",
        # Boxing - Modern Stars
        "floyd mayweather", "money mayweather", "pretty boy floyd", "tbe",
        "manny pacquiao", "pacman", "the fighting pride of the philippines",
        "canelo alvarez", "saul alvarez", "cinnamon",
        "gennady golovkin", "ggg", "triple g",
        "tyson fury", "gypsy king", "the furious one",
        "anthony joshua", "aj",
        "deontay wilder", "the bronze bomber",
        "oleksandr usyk", "the cat", "usyk",
        "terence crawford", "bud crawford", "bud",
        "errol spence jr", "the truth",
        "naoya inoue", "monster", "the japanese monster",
        "vasiliy lomachenko", "loma", "hi-tech", "no mas chenko",
        "juan manuel marquez", "dinamita",
        "miguel cotto", "junito",
        "marcos maidana", "el chino",
        "amir khan", "king khan",
        "andre ward", "son of god", "s.o.g.",
        "sergey kovalev", "krusher",
        "carl froch", "the cobra",
        "joe calzaghe", "pride of wales",
        "wladimir klitschko", "dr. steelhammer",
        "vitali klitschko", "dr. ironfist",
        "jermell charlo", "iron man",
        "jermall charlo", "hitman",
        "david benavidez", "the mexican monster", "el bandera roja",
        "shakur stevenson", "shy",
        "ryan garcia", "kingry", "the flash",
        "gervonta davis", "tank davis", "tank",
        "devin haney", "the dream",
        "artur beterbiev", "lion",
        "dmitry bivol",
        "jake paul", "the problem child",
        "logan paul", "the maverick",
        "claressa shields", "t-rex", "gwoat",
        "katie taylor", "the bray bomber",
        "amanda serrano", "the real deal",
        # MMA - Legends & All-Time Greats
        "conor mcgregor", "the notorious", "mystic mac",
        "khabib nurmagomedov", "the eagle",
        "jon jones", "bones", "jonny bones",
        "anderson silva", "the spider",
        "georges st-pierre", "gsp", "rush",
        "matt hughes", "royce gracie", "rickson gracie",
        "chuck liddell", "the iceman",
        "randy couture", "captain america", "the natural",
        "tito ortiz", "the huntington beach bad boy",
        "bj penn", "the prodigy",
        "fedor emelianenko", "the last emperor",
        "mirko cro cop", "mirko filipovic",
        "dan henderson", "hendo", "dangerous dan",
        "wanderlei silva", "the axe murderer",
        "mauricio rua", "shogun",
        "lyoto machida", "the dragon",
        "vitor belfort", "the phenom",
        "cain velasquez", "junior dos santos", "jds", "cigano",
        "brock lesnar", "the beast incarnate",
        "frank mir", "frank shamrock", "ken shamrock",
        "forrest griffin", "stephan bonnar",
        "nick diaz", "nate diaz", "the diaz brothers",
        "jose aldo", "junior", "the king of rio",
        "demetrious johnson", "mighty mouse", "dj",
        "dominick cruz", "the dominator",
        "urijah faber", "the california kid",
        "daniel cormier", "dc",
        "stipe miocic", "stipe",
        "ronda rousey", "rowdy",
        "holly holm", "the preacher's daughter",
        "joanna jedrzejczyk", "joanna champion",
        "cris cyborg", "cristiane justino",
        "miesha tate", "cupcake",
        "max holloway", "blessed",
        "dustin poirier", "the diamond",
        "tony ferguson", "el cucuy",
        "anthony pettis", "showtime",
        # MMA - Current Stars
        "israel adesanya", "izzy", "the last stylebender",
        "alex pereira", "poatan",
        "islam makhachev", "the blank",
        "leon edwards", "rocky",
        "alex volkanovski", "volk", "alexander the great",
        "sean o'malley", "suga", "suga sean",
        "colby covington", "chaos",
        "jorge masvidal", "gamebred", "street jesus",
        "kamaru usman", "the nigerian nightmare",
        "charles oliveira", "do bronx",
        "francis ngannou", "the predator",
        "tom aspinall", "tommy fury",
        "sean strickland", "tarzan",
        "dricus du plessis", "stillknocks",
        "jiri prochazka", "denisa",
        "jianhui li", "the leech",
        "zhang weili", "magnum",
        "amanda nunes", "the lioness",
        "valentina shevchenko", "bullet",
        "rose namajunas", "thug rose",
        "bo nickal", "dana white",
        # Terms
        "boxing", "boxer", "heavyweight", "knockout", "ko",
        "mma", "mixed martial arts", "ufc", "ultimate fighting",
    ],
    Sport.RACING: [
        # Leagues/Series
        "nascar", "formula 1", "f1", "indycar", "indy 500", "daytona",
        "le mans", "motogp", "drag racing", "nhra", "wrc", "rally",
        "imsa", "formula e", "supercross", "ama motocross",
        # NASCAR - Legends
        "dale earnhardt", "the intimidator", "dale sr", "earnhardt sr",
        "richard petty", "the king",
        "david pearson", "the silver fox",
        "bobby allison", "donnie allison", "davey allison",
        "cale yarborough", "darrell waltrip", "dw", "jaws",
        "jeff gordon", "the rainbow warrior", "wonder boy",
        "jimmie johnson", "seven time", "jj48",
        "rusty wallace", "mark martin", "bill elliott", "awesome bill from dawsonville",
        "terry labonte", "bobby labonte",
        "dale jarrett", "ned jarrett",
        "harry gant", "handsome harry",
        "geoff bodine", "brett bodine", "todd bodine",
        "alan kulwicki", "special k",
        "ricky rudd", "ernie irvan",
        "sterling marlin", "michael waltrip",
        "tony stewart", "smoke",
        # NASCAR - Modern Stars
        "dale earnhardt jr", "dale jr", "junior",
        "kyle busch", "rowdy", "kb18",
        "kevin harvick", "the closer", "happy harvick",
        "chase elliott", "napa know how",
        "joey logano", "sliced bread",
        "denny hamlin", "hamlin",
        "martin truex jr", "mtj",
        "ryan blaney", "blaney",
        "ross chastain", "the melon man",
        "william byron", "willy b",
        "christopher bell", "cbell",
        "tyler reddick", "reddick",
        "bubba wallace", "alex bowman", "bowman",
        "kurt busch", "the outlaw",
        "brad keselowski", "bad brad",
        "kyle larson", "larson", "yung money",
        "ricky stenhouse jr", "aric almirola",
        "austin dillon", "austin cindric",
        "noah gragson", "ty gibbs",
        "sam mayer", "zane smith", "john hunter nemechek",
        # Formula 1 - Legends
        "michael schumacher", "schumacher", "schumi", "the red baron",
        "ayrton senna", "senna", "the master of monaco",
        "alain prost", "the professor",
        "niki lauda", "the rat",
        "juan manuel fangio", "fangio", "el chueco",
        "jim clark", "jackie stewart", "sir jackie", "the flying scot",
        "graham hill", "mr. monaco", "damon hill",
        "stirling moss", "jack brabham",
        "nelson piquet", "nigel mansell", "il leone", "the lion",
        "mika hakkinen", "the flying finn",
        "jacques villeneuve", "gilles villeneuve",
        "james hunt", "hunt the shunt",
        "jochen rindt", "ronnie peterson",
        "emerson fittipaldi", "mario andretti",
        "jody scheckter", "keke rosberg", "nico rosberg",
        "david coulthard", "dc", "rubens barrichello",
        # Formula 1 - Modern Stars
        "lewis hamilton", "hammer time", "sir lewis", "lh44",
        "max verstappen", "mad max", "super max",
        "sebastian vettel", "seb", "baby schumi",
        "fernando alonso", "el nano", "el matador",
        "kimi raikkonen", "iceman", "the iceman",
        "charles leclerc", "sharl", "il predestinato",
        "lando norris", "lando", "last lap lando",
        "george russell", "mr. saturday", "george",
        "carlos sainz", "smooth operator", "carlitos",
        "oscar piastri", "papaya rules",
        "daniel ricciardo", "danny ric", "the honey badger",
        "pierre gasly", "esteban ocon",
        "lance stroll", "sergio perez", "checo",
        "valtteri bottas", "to whom it may concern",
        "kevin magnussen", "k-mag",
        "yuki tsunoda", "zhou guanyu",
        "alexander albon", "alex albon",
        "logan sargeant", "ollie bearman",
        "franco colapinto", "jack doohan",
        "andrea kimi antonelli", "kimi antonelli",
        # IndyCar
        "mario andretti", "andretti", "super mario",
        "aj foyt", "super tex", "anthony joseph foyt",
        "rick mears", "rocket rick",
        "al unser", "big al", "al unser jr", "little al",
        "bobby unser", "johnny rutherford", "lone star jr",
        "emerson fittipaldi", "danny sullivan",
        "michael andretti", "andretti",
        "paul tracy", "pt",
        "scott dixon", "the iceman", "dixie",
        "dario franchitti", "helio castroneves", "spiderman",
        "tony kanaan", "tk",
        "juan pablo montoya", "jpm",
        "will power", "the power",
        "simon pagenaud", "josef newgarden", "newgarden",
        "alexander rossi", "alex palou", "palou",
        "colton herta", "rinus veekay",
        "pato o'ward", "patricio o'ward",
        "marcus ericsson", "ericsson",
        "kyle kirkwood", "christian lundgaard",
        # MotoGP & Motorcycle Racing
        "valentino rossi", "the doctor", "vale",
        "marc marquez", "mm93", "the ant of cervera",
        "giacomo agostini", "ago",
        "mike hailwood", "mike the bike",
        "kenny roberts", "king kenny",
        "eddie lawson", "steady eddie",
        "wayne rainey", "kevin schwantz",
        "mick doohan", "doohan",
        "nicky hayden", "kentucky kid",
        "casey stoner", "stoner",
        "jorge lorenzo", "por fuera", "the hammer",
        "dani pedrosa", "baby samurai",
        "andrea dovizioso", "dovi",
        "maverick vinales", "vinales",
        "fabio quartararo", "el diablo",
        "francesco bagnaia", "pecco",
        "brad binder", "binder",
        "enea bastianini", "the beast",
        "jorge martin", "martinator",
        "marco simoncelli", "sic", "super sic",
        # Drag Racing / NHRA
        "don garlits", "big daddy", "swamp rat",
        "john force", "brute force", "the man",
        "shirley muldowney", "cha cha", "first lady of drag racing",
        "kenny bernstein", "king kenny",
        "tony schumacher", "the sarge", "army",
        "don prudhomme", "the snake",
        "tom mcewen", "the mongoose",
        "bob glidden", "joe amato", "top fuel",
        "warren johnson", "professor",
        "larry dixon", "dixon",
        "brittany force", "ashley force hood",
        "courtney force", "robert hight",
        "matt hagan", "hagan", "ron capps",
        "steve torrence", "torrence",
        "doug kalitta", "connie kalitta",
        "antron brown", "ab", "the sarge",
        "erica enders", "enders",
        "jeg coughlin jr", "jason line",
        "bob tasca iii",
        # Rally / WRC
        "colin mcrae", "if in doubt flat out",
        "richard burns", "burns",
        "marcus gronholm", "gronholm",
        "tommi makinen", "the flying finn",
        "carlos sainz", "el matador",
        "juha kankkunen", "kankkunen",
        "sebastien loeb", "loeb", "le patron",
        "sebastien ogier", "ogier",
        "kalle rovanpera", "rovanpera",
        "ott tanak", "tanak", "thierry neuville",
        "elfyn evans", "evans",
        "ken block", "hoonigan", "block",
        # Terms
        "racing", "race car", "motorsport", "auto racing",
        "checkered flag", "pole position", "pit stop",
    ],
}

# Pre-compile regex patterns for each keyword to improve performance
# This is done once at module load time
_COMPILED_SPORT_PATTERNS: dict[Sport, list[tuple[re.Pattern, int]]] = {}
for _sport, _keywords in SPORT_KEYWORDS.items():
    _COMPILED_SPORT_PATTERNS[_sport] = [
        (re.compile(r'\b' + re.escape(kw.lower()) + r'\b'), len(kw))
        for kw in _keywords
    ]

# Pre-compile non-sports patterns
_COMPILED_NON_SPORTS_PATTERNS: list[tuple[re.Pattern, int]] = [
    (re.compile(r'\b' + re.escape(kw.lower()) + r'\b'), len(kw))
    for kw in NON_SPORTS_KEYWORDS
]


def detect_sport_from_item(
    title: Optional[str],
    description: Optional[str] = None,
    category: Optional[str] = None
) -> Sport:
    """
    Detect the sport category from item title, description, and category.

    Uses multi-layer detection:
    1. First checks for non-sports items (Pokemon, MTG, Star Wars, WWE, etc.)
    2. Year pattern detection (2020-21 = basketball/hockey, 2024 Topps = baseball)
    3. Manufacturer/set name mappings
    4. Player/team/league name matching with scoring

    Args:
        title: Item title (required)
        description: Item description (optional)
        category: Item category (optional)

    Returns:
        Sport enum value
    """
    if not title:
        return Sport.OTHER

    # Combine all text fields for searching
    search_text = title.lower()
    if description:
        search_text += " " + description.lower()
    if category:
        search_text += " " + category.lower()

    # Layer 1: Check for non-sports items FIRST
    # This prevents Pokemon, MTG, Star Wars, WWE, etc. from being miscategorized
    non_sports_score = 0
    for pattern, score in _COMPILED_NON_SPORTS_PATTERNS:
        if pattern.search(search_text):
            non_sports_score += score

    # Layer 2: Year pattern detection
    year_hint_sport = None
    year_hint_score = 0

    # Split-year pattern (2020-21) suggests basketball or hockey
    if SPLIT_YEAR_PATTERN.search(title):
        year_hint_score = 15  # Moderate boost
        # Will be applied to basketball/hockey scores later

    # Topps + year pattern strongly suggests baseball
    if TOPPS_YEAR_PATTERN.search(title):
        year_hint_sport = Sport.BASEBALL
        year_hint_score = 25  # Strong boost for Topps year pattern

    # Layer 3: Manufacturer/set name detection
    manufacturer_hint_sport = None
    manufacturer_hint_score = 0

    # Check specific manufacturer hints
    for hint_phrase, hint_sport in MANUFACTURER_SPORT_HINTS.items():
        if hint_phrase in search_text:
            manufacturer_hint_sport = hint_sport
            manufacturer_hint_score = len(hint_phrase) + 10  # Boost for manufacturer match
            break

    # Check Panini basketball sets
    for set_name in PANINI_BASKETBALL_SETS:
        if set_name in search_text:
            if manufacturer_hint_sport is None or manufacturer_hint_score < len(set_name) + 15:
                manufacturer_hint_sport = Sport.BASKETBALL
                manufacturer_hint_score = len(set_name) + 15

    # Check Panini football sets
    for set_name in PANINI_FOOTBALL_SETS:
        if set_name in search_text:
            if manufacturer_hint_sport is None or manufacturer_hint_score < len(set_name) + 15:
                manufacturer_hint_sport = Sport.FOOTBALL
                manufacturer_hint_score = len(set_name) + 15

    # Check Topps baseball sets
    for set_name in TOPPS_BASEBALL_SETS:
        if set_name in search_text:
            if manufacturer_hint_sport is None or manufacturer_hint_score < len(set_name) + 15:
                manufacturer_hint_sport = Sport.BASEBALL
                manufacturer_hint_score = len(set_name) + 15

    # Check Upper Deck hockey sets
    for set_name in UPPER_DECK_HOCKEY_SETS:
        if set_name in search_text:
            if manufacturer_hint_sport is None or manufacturer_hint_score < len(set_name) + 15:
                manufacturer_hint_sport = Sport.HOCKEY
                manufacturer_hint_score = len(set_name) + 15

    # Check Topps soccer sets
    for set_name in TOPPS_SOCCER_SETS:
        if set_name in search_text:
            if manufacturer_hint_sport is None or manufacturer_hint_score < len(set_name) + 15:
                manufacturer_hint_sport = Sport.SOCCER
                manufacturer_hint_score = len(set_name) + 15

    # Check Panini soccer sets
    for set_name in PANINI_SOCCER_SETS:
        if set_name in search_text:
            if manufacturer_hint_sport is None or manufacturer_hint_score < len(set_name) + 15:
                manufacturer_hint_sport = Sport.SOCCER
                manufacturer_hint_score = len(set_name) + 15

    # Layer 4: Track matches by sport with score (player names, teams, leagues)
    # Higher score = more specific match
    # Uses pre-compiled patterns for performance
    sport_scores: dict[Sport, int] = {sport: 0 for sport in Sport}

    for sport, patterns in _COMPILED_SPORT_PATTERNS.items():
        for pattern, score in patterns:
            # Use word boundary matching to prevent false positives
            # e.g., "russ" should not match "Donruss", "kings" should match as whole word
            if pattern.search(search_text):
                sport_scores[sport] += score

    # Find best sport from keyword matching BEFORE applying any hints
    # This prevents hints from overriding clear player name matches
    best_keyword_sport = Sport.OTHER
    best_keyword_score = 0
    for sport, score in sport_scores.items():
        if score > best_keyword_score:
            best_keyword_score = score
            best_keyword_sport = sport

    # Apply year hint boost ONLY if there's no strong keyword match
    # This prevents "2025 Topps" from overriding "Cooper Flagg" (basketball player)
    # and "2020-21" from overriding "Lionel Messi" (soccer player)
    # Threshold of 8 covers most player names (e.g., "tom brady" = 9 chars)
    if best_keyword_score < 8:
        if year_hint_score > 0 and year_hint_sport is None:
            # Split-year pattern - boost basketball and hockey
            sport_scores[Sport.BASKETBALL] += year_hint_score
            sport_scores[Sport.HOCKEY] += year_hint_score
        elif year_hint_sport:
            # Specific year pattern (e.g., Topps year = baseball)
            sport_scores[year_hint_sport] += year_hint_score

    # Apply manufacturer hint ONLY if:
    # 1. There's no strong keyword match (score < 8), OR
    # 2. The manufacturer hint matches the best keyword sport
    # This prevents "SP Authentic" (hockey set) from overriding "Tom Brady" (football player)
    if manufacturer_hint_sport:
        if best_keyword_score < 8 or manufacturer_hint_sport == best_keyword_sport:
            sport_scores[manufacturer_hint_sport] += manufacturer_hint_score

    # Find the sport with the highest score
    best_sport = Sport.OTHER
    best_score = 0

    for sport, score in sport_scores.items():
        if score > best_score:
            best_score = score
            best_sport = sport

    # If non-sports score is significant and higher than best sport score,
    # classify as OTHER (non-sports collectible)
    # Use a threshold to prevent false positives from short common words
    if non_sports_score > 10 and non_sports_score > best_score:
        return Sport.OTHER

    return best_sport


def get_all_sports() -> list[str]:
    """Return list of all sport values for API use"""
    return [sport.value for sport in Sport]
