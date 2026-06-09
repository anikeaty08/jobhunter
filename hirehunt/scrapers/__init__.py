"""Built-in source scrapers."""

from hirehunt.scrapers.faang import (
    AmazonJobsScraper,
    AppleJobsScraper,
    GoogleCareersScraper,
    MetaCareersScraper,
    MicrosoftCareersScraper,
    NetflixJobsScraper,
)
from hirehunt.scrapers.indeed import IndeedScraper
from hirehunt.scrapers.internshala import InternshalaScraper
from hirehunt.scrapers.linkedin import LinkedInScraper
from hirehunt.scrapers.naukri import NaukriScraper
from hirehunt.scrapers.shine import ShineScraper
from hirehunt.scrapers.unstop import UnstopScraper

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
