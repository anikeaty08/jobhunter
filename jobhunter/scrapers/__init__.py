"""Built-in source scrapers."""

from jobhunter.scrapers.faang import (
    AmazonJobsScraper,
    AppleJobsScraper,
    GoogleCareersScraper,
    MetaCareersScraper,
    MicrosoftCareersScraper,
    NetflixJobsScraper,
)
from jobhunter.scrapers.indeed import IndeedScraper
from jobhunter.scrapers.internshala import InternshalaScraper
from jobhunter.scrapers.linkedin import LinkedInScraper
from jobhunter.scrapers.naukri import NaukriScraper
from jobhunter.scrapers.shine import ShineScraper
from jobhunter.scrapers.unstop import UnstopScraper

BUILTIN_SCRAPERS = [
    # Global
    IndeedScraper,
    LinkedInScraper,
    # India
    InternshalaScraper,
    NaukriScraper,
    ShineScraper,
    UnstopScraper,
    # FAANG / Big Tech
    GoogleCareersScraper,
    AmazonJobsScraper,
    MetaCareersScraper,
    AppleJobsScraper,
    NetflixJobsScraper,
    MicrosoftCareersScraper,
]
