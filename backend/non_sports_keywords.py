"""
Non-Sports Keywords for Trading Card Categorization System
These keywords identify items that should NOT be categorized as sports cards.
"""

NON_SPORTS_KEYWORDS = [
    # ============================================
    # TRADING CARD GAMES (TCG)
    # ============================================

    # Pokemon
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
    "pharaoh", "kaiba", "joey wheeler", "yugi muto", "seto kaiba",

    # Other TCGs
    "flesh and blood", "fab tcg", "disney lorcana", "lorcana", "one piece card game",
    "one piece tcg", "optcg", "digimon card game", "digimon tcg", "cardfight vanguard",
    "vanguard tcg", "weiss schwarz", "force of will", "final fantasy tcg", "fftcg",
    "dragon ball super card game", "dbs card game", "metazoo", "sorcery contested realm",
    "grand archive", "altered tcg", "star wars unlimited", "union arena",
    "battle spirits", "buddyfight", "keyforge", "netrunner", "legend of the five rings",
    "l5r", "arkham horror lcg", "lord of the rings lcg", "marvel champions lcg",

    # ============================================
    # ENTERTAINMENT / MEDIA
    # ============================================

    # Star Wars
    "star wars", "starwars", "darth vader", "luke skywalker", "han solo", "yoda",
    "princess leia", "leia organa", "chewbacca", "chewie", "obi-wan kenobi", "obi wan",
    "anakin skywalker", "padme amidala", "mace windu", "qui-gon jinn", "count dooku",
    "emperor palpatine", "darth sidious", "darth maul", "kylo ren", "rey skywalker",
    "finn star wars", "poe dameron", "bb-8", "bb8", "r2-d2", "r2d2", "c-3po", "c3po",
    "mandalorian", "mando", "grogu", "baby yoda", "boba fett", "jango fett",
    "din djarin", "ahsoka tano", "ahsoka", "clone trooper", "stormtrooper",
    "death star", "millennium falcon", "lightsaber", "jedi", "sith", "galactic empire",
    "rebel alliance", "first order", "resistance", "clone wars", "bad batch",
    "andor", "rogue one", "book of boba fett", "obi-wan series", "acolyte",
    "topps star wars", "star wars galaxy", "masterwork star wars",

    # Marvel
    "marvel", "marvel comics", "spider-man", "spiderman", "spider man", "peter parker",
    "miles morales", "iron man", "tony stark", "captain america", "steve rogers",
    "thor", "hulk", "bruce banner", "black widow", "natasha romanoff", "hawkeye",
    "clint barton", "avengers", "x-men", "xmen", "wolverine", "logan", "cyclops",
    "jean grey", "storm", "magneto", "professor x", "charles xavier", "beast",
    "rogue", "gambit", "nightcrawler", "colossus", "iceman", "angel", "psylocke",
    "deadpool", "wade wilson", "venom", "carnage", "thanos", "loki", "doctor strange",
    "scarlet witch", "wanda maximoff", "vision", "black panther", "tchalla",
    "captain marvel", "carol danvers", "ant-man", "wasp", "falcon", "sam wilson",
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
    "batgirl", "barbara gordon", "alfred pennyworth", "commissioner gordon",
    "supergirl", "kara zor-el", "superboy", "shazam", "captain marvel dc", "billy batson",
    "blue beetle", "booster gold", "firestorm", "atom", "plastic man",
    "gotham", "metropolis", "themyscira", "atlantis", "arkham asylum", "wayne manor",
    "batcave", "fortress of solitude", "hall of justice", "watchtower",

    # Disney (non-Lorcana general)
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

    # Harry Potter / Wizarding World
    "harry potter", "hogwarts", "hermione granger", "ron weasley", "albus dumbledore",
    "severus snape", "voldemort", "he who must not be named", "tom riddle",
    "draco malfoy", "hagrid", "sirius black", "remus lupin", "neville longbottom",
    "luna lovegood", "ginny weasley", "fred and george", "dobby", "hedwig",
    "gryffindor", "slytherin", "hufflepuff", "ravenclaw", "quidditch", "golden snitch",
    "deathly hallows", "horcrux", "patronus", "expecto patronum", "avada kedavra",
    "elder wand", "invisibility cloak", "marauders map", "sorting hat",
    "diagon alley", "hogsmeade", "azkaban", "ministry of magic", "platform 9 3/4",
    "wizarding world", "fantastic beasts", "newt scamander",

    # Lord of the Rings / Middle Earth
    "lord of the rings", "lotr", "middle earth", "middle-earth", "tolkien",
    "frodo baggins", "frodo", "samwise gamgee", "sam gamgee", "gandalf", "aragorn",
    "legolas", "gimli", "boromir", "merry", "pippin", "bilbo baggins", "bilbo",
    "gollum", "smeagol", "sauron", "saruman", "nazgul", "ringwraith", "balrog",
    "shire", "rivendell", "mordor", "gondor", "rohan", "minas tirith", "mount doom",
    "one ring", "fellowship of the ring", "two towers", "return of the king",
    "hobbit", "silmarillion", "rings of power",

    # Transformers
    "transformers", "optimus prime", "megatron", "bumblebee", "starscream",
    "soundwave", "shockwave", "grimlock", "jazz", "ironhide", "ratchet",
    "autobots", "decepticons", "cybertron", "energon", "all spark",
    "hasbro transformers",

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

    # ============================================
    # WRESTLING
    # ============================================

    # WWE / WWF
    "wwe", "wwf", "wrestling", "pro wrestling", "professional wrestling",
    "world wrestling", "world wrestling entertainment", "world wrestling federation",
    "hulk hogan", "hulkamania", "the rock", "dwayne johnson", "stone cold",
    "steve austin", "stone cold steve austin", "john cena", "undertaker",
    "the undertaker", "deadman", "shawn michaels", "hbk", "heartbreak kid",
    "bret hart", "hitman", "ric flair", "nature boy", "wooo", "randy savage",
    "macho man", "ultimate warrior", "andre the giant", "rowdy roddy piper",
    "triple h", "hhh", "randy orton", "rko", "edge", "rated r superstar",
    "batista", "rey mysterio", "619", "eddie guerrero", "chris jericho", "y2j",
    "big show", "kane", "mick foley", "mankind", "cactus jack", "dude love",
    "kurt angle", "goldberg", "brock lesnar", "roman reigns", "tribal chief",
    "seth rollins", "dean ambrose", "the shield", "becky lynch", "the man",
    "charlotte flair", "sasha banks", "bayley", "asuka", "bianca belair",
    "kofi kingston", "new day", "kevin owens", "aj styles", "phenomenal one",
    "drew mcintyre", "braun strowman", "fiend", "bray wyatt", "cody rhodes",
    "dusty rhodes", "american dream", "goldust", "booker t", "cm punk",
    "daniel bryan", "yes movement", "miz", "dolph ziggler", "sheamus",
    "wrestlemania", "royal rumble", "summerslam", "survivor series",
    "raw", "smackdown", "nxt", "monday night raw", "friday night smackdown",
    "wwe championship", "universal championship", "intercontinental", "us championship",
    "tag team championship", "women's championship", "divas championship",

    # AEW
    "aew", "all elite wrestling", "tony khan aew", "kenny omega", "young bucks",
    "chris jericho aew", "jon moxley", "hangman adam page", "mjf", "maxwell jacob friedman",
    "jade cargill", "britt baker", "aew dynamite", "aew rampage", "aew collision",
    "aew world championship", "tnt championship", "tbs championship",

    # Other Wrestling
    "wcw", "world championship wrestling", "nwo", "new world order",
    "ecw", "extreme championship wrestling", "tna", "impact wrestling",
    "njpw", "new japan pro wrestling", "roh", "ring of honor",
    "lucha libre", "luchador", "aaa wrestling", "cmll",

    # ============================================
    # OTHER NON-SPORT COLLECTIBLES
    # ============================================

    # Garbage Pail Kids
    "garbage pail kids", "gpk", "adam bomb", "nasty nick", "topps gpk",
    "garbage pail", "gross sticker", "cabbage patch parody",

    # Non-Sport Topps
    "topps non-sport", "non-sport", "nonsport", "non sport",
    "topps heritage non-sport", "topps chrome non-sport",
    "wacky packages", "mars attacks", "mars attacks topps",

    # Movie/TV Cards
    "movie cards", "movie trading cards", "tv cards", "tv trading cards",
    "film cards", "cinema cards", "horror cards", "sci-fi cards",
    "topps movie", "fleer movie", "skybox movie", "upper deck movie",

    # Video Game Cards
    "video game cards", "nintendo cards", "sega cards", "playstation cards",
    "xbox cards", "fortnite cards", "minecraft cards", "roblox cards",
    "call of duty cards", "halo cards", "zelda cards", "mario cards",
    "sonic cards", "street fighter cards", "mortal kombat cards",
    "world of warcraft tcg", "wow tcg", "hearthstone physical",

    # Music Cards
    "music cards", "musician cards", "band cards", "rock cards",
    "beatles cards", "elvis cards", "elvis presley", "michael jackson cards",
    "kiss cards", "rolling stones cards",

    # Historical/Educational
    "civil war cards", "world war cards", "historical cards", "president cards",
    "americana cards", "heritage cards non-sport", "historical figures",

    # Adult/Mature
    "adult cards", "pin-up cards", "bench warmer", "benchwarmer",

    # Miscellaneous Non-Sport
    "comic cards", "comic book cards", "art cards", "artist cards",
    "promo card", "promotional card", "chase card", "insert card",
    "parallel card", "refractor", "auto card", "autograph card",
    "relic card", "memorabilia card", "patch card", "sketch card",
    "trading card game", "tcg", "ccg", "collectible card game",
]

# Create category-specific lists for more granular filtering if needed
POKEMON_KEYWORDS = [kw for kw in NON_SPORTS_KEYWORDS if any(p in kw.lower() for p in
    ["pokemon", "pokémon", "pikachu", "charizard", "mewtwo", "blastoise", "venusaur",
     "bulbasaur", "squirtle", "charmander", "eevee", "jigglypuff", "snorlax", "gengar",
     "dragonite", "mew", "lugia", "ho-oh", "rayquaza", "gyarados", "alakazam", "machamp",
     "arcanine", "lapras", "vaporeon", "jolteon", "flareon", "espeon", "umbreon",
     "tyranitar", "salamence", "metagross", "garchomp", "lucario", "greninja", "mimikyu",
     "sylveon", "gardevoir", "darkrai", "dialga", "palkia", "giratina", "arceus",
     "reshiram", "zekrom", "kyurem", "xerneas", "yveltal", "zygarde", "solgaleo",
     "lunala", "necrozma", "zacian", "zamazenta", "eternatus", "calyrex",
     "shadowless", "base set", "jungle", "fossil", "team rocket", "gym heroes",
     "gym challenge", "neo genesis", "neo discovery", "scarlet violet", "paldea",
     "obsidian flames", "crown zenith", "silver tempest"])]

MTG_KEYWORDS = [
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
]

YUGIOH_KEYWORDS = [
    "yu-gi-oh", "yugioh", "yu gi oh", "ygo", "blue-eyes white dragon", "blue eyes white dragon",
    "dark magician", "exodia", "red-eyes black dragon", "red eyes black dragon",
    "black luster soldier", "dark magician girl", "kuriboh", "summoned skull",
    "celtic guardian", "flame swordsman", "gaia the fierce knight", "curse of dragon",
    "time wizard", "baby dragon", "thousand dragon", "blue-eyes ultimate dragon",
    "slifer the sky dragon", "obelisk the tormentor", "winged dragon of ra",
    "egyptian god card", "millennium puzzle", "duel monsters", "konami yugioh",
    "synchro", "xyz monster", "pendulum", "link monster", "fusion monster",
    "pharaoh", "kaiba", "joey wheeler", "yugi muto", "seto kaiba",
]

WRESTLING_KEYWORDS = [
    "wwe", "wwf", "wrestling", "pro wrestling", "professional wrestling",
    "world wrestling", "world wrestling entertainment", "world wrestling federation",
    "hulk hogan", "hulkamania", "the rock", "dwayne johnson", "stone cold",
    "steve austin", "stone cold steve austin", "john cena", "undertaker",
    "the undertaker", "deadman", "shawn michaels", "hbk", "heartbreak kid",
    "bret hart", "hitman", "ric flair", "nature boy", "randy savage",
    "macho man", "ultimate warrior", "andre the giant", "rowdy roddy piper",
    "triple h", "hhh", "randy orton", "rko", "edge", "rated r superstar",
    "batista", "rey mysterio", "619", "eddie guerrero", "chris jericho", "y2j",
    "big show", "kane", "mick foley", "mankind", "cactus jack", "dude love",
    "kurt angle", "goldberg", "brock lesnar", "roman reigns", "tribal chief",
    "seth rollins", "dean ambrose", "the shield", "becky lynch", "the man",
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
]

STAR_WARS_KEYWORDS = [
    "star wars", "starwars", "darth vader", "luke skywalker", "han solo", "yoda",
    "princess leia", "leia organa", "chewbacca", "chewie", "obi-wan kenobi", "obi wan",
    "anakin skywalker", "padme amidala", "mace windu", "qui-gon jinn", "count dooku",
    "emperor palpatine", "darth sidious", "darth maul", "kylo ren", "rey skywalker",
    "finn star wars", "poe dameron", "bb-8", "bb8", "r2-d2", "r2d2", "c-3po", "c3po",
    "mandalorian", "mando", "grogu", "baby yoda", "boba fett", "jango fett",
    "din djarin", "ahsoka tano", "ahsoka", "clone trooper", "stormtrooper",
    "death star", "millennium falcon", "lightsaber", "jedi", "sith", "galactic empire",
    "rebel alliance", "first order", "resistance", "clone wars", "bad batch",
    "andor", "rogue one", "book of boba fett", "acolyte",
]

MARVEL_KEYWORDS = [
    "marvel", "marvel comics", "spider-man", "spiderman", "spider man", "peter parker",
    "miles morales", "iron man", "tony stark", "captain america", "steve rogers",
    "thor", "hulk", "bruce banner", "black widow", "natasha romanoff", "hawkeye",
    "clint barton", "avengers", "x-men", "xmen", "wolverine", "logan", "cyclops",
    "jean grey", "storm", "magneto", "professor x", "charles xavier", "beast",
    "rogue", "gambit", "nightcrawler", "colossus", "iceman", "angel", "psylocke",
    "deadpool", "wade wilson", "venom", "carnage", "thanos", "loki", "doctor strange",
    "scarlet witch", "wanda maximoff", "vision", "black panther", "tchalla",
    "captain marvel", "carol danvers", "ant-man", "wasp", "falcon", "sam wilson",
    "winter soldier", "bucky barnes", "guardians of the galaxy", "star-lord",
    "groot", "rocket raccoon", "gamora", "drax", "nebula", "nick fury", "shield",
    "fantastic four", "mister fantastic", "invisible woman", "human torch", "thing",
    "silver surfer", "galactus", "doctor doom", "daredevil", "punisher", "elektra",
    "ghost rider", "moon knight", "ms marvel", "kamala khan", "she-hulk",
    "eternals", "shang-chi", "blade", "morbius", "kang", "modok",
]

DC_KEYWORDS = [
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
]

# Total keyword count for verification
TOTAL_KEYWORDS = len(NON_SPORTS_KEYWORDS)

if __name__ == "__main__":
    print(f"Total NON_SPORTS_KEYWORDS: {TOTAL_KEYWORDS}")
    print(f"\nCategories breakdown:")
    print(f"  Pokemon-related: ~55 keywords")
    print(f"  MTG-related: ~40 keywords")
    print(f"  Yu-Gi-Oh-related: ~35 keywords")
    print(f"  Other TCGs: ~35 keywords")
    print(f"  Star Wars: ~50 keywords")
    print(f"  Marvel: ~75 keywords")
    print(f"  DC Comics: ~65 keywords")
    print(f"  Disney: ~50 keywords")
    print(f"  Harry Potter: ~40 keywords")
    print(f"  Lord of the Rings: ~35 keywords")
    print(f"  Wrestling: ~100+ keywords")
    print(f"  Other Entertainment: ~60+ keywords")
    print(f"  Other Collectibles: ~50+ keywords")
