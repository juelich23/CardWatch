"""Scrapers for different auction houses"""
from app.scrapers.goldin_httpx import GoldinHTTPScraper
from app.scrapers.fanatics import FanaticsScraper
from app.scrapers.heritage import HeritageScraper
from app.scrapers.pristine import PristineScraper
from app.scrapers.rea import REAScraper
from app.scrapers.lelands import LelandsScraper
from app.scrapers.classic_auctions import ClassicAuctionsScraper
from app.scrapers.memorylane import MemoryLaneScraper
from app.scrapers.milehigh import MileHighScraper
from app.scrapers.cleansweep import CleanSweepScraper
from app.scrapers.rr_auction import RRAuctionScraper
from app.scrapers.auction_of_champions import AuctionOfChampionsScraper
from app.scrapers.sirius import SiriusScraper
from app.scrapers.gregmorris import GregMorrisScraper
from app.scrapers.queencity import QueenCityScraper
from app.scrapers.detroitcity import DetroitCityScraper
from app.scrapers.vsa import VSAScraper
from app.scrapers.hunt import HuntAuctionsScraper
from app.scrapers.loveofthegame import LoveOfTheGameScraper
from app.scrapers.cardhobby import CardHobbyScraper

__all__ = [
    'GoldinHTTPScraper',
    'FanaticsScraper',
    'HeritageScraper',
    'PristineScraper',
    'REAScraper',
    'LelandsScraper',
    'ClassicAuctionsScraper',
    'MemoryLaneScraper',
    'MileHighScraper',
    'CleanSweepScraper',
    'RRAuctionScraper',
    'AuctionOfChampionsScraper',
    'SiriusScraper',
    'GregMorrisScraper',
    'QueenCityScraper',
    'DetroitCityScraper',
    'VSAScraper',
    'HuntAuctionsScraper',
    'LoveOfTheGameScraper',
    'CardHobbyScraper',
]
