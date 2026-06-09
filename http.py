"""
utils/http.py — Shared HTTP session with rotating user agents and retry logic
"""

import requests
import time
import random
import logging
from typing import Optional
from urllib.parse import urlencode, quote

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
]


def get_session(proxies: Optional[list] = None) -> requests.Session:
    """Create a requests session with random user agent."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    })
    if proxies:
        proxy = random.choice(proxies)
        session.proxies.update({"http": proxy, "https": proxy})
    return session


def safe_get(
    session: requests.Session,
    url: str,
    headers: Optional[dict] = None,
    params: Optional[dict] = None,
    retries: int = 3,
    delay: float = 2.0,
    timeout: int = 15,
) -> Optional[requests.Response]:
    """GET with retry + exponential backoff."""
    for attempt in range(retries):
        try:
            resp = session.get(url, headers=headers, params=params, timeout=timeout)
            if resp.status_code == 200:
                return resp
            elif resp.status_code == 429:
                wait = delay * (2 ** attempt) + random.uniform(0, 1)
                logger.warning(f"Rate limited on {url}, waiting {wait:.1f}s")
                time.sleep(wait)
            elif resp.status_code in (403, 406):
                logger.warning(f"Blocked ({resp.status_code}) on {url}")
                return resp  # Return so caller can handle
            else:
                logger.warning(f"HTTP {resp.status_code} on {url}")
                return resp
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout on {url} (attempt {attempt+1})")
            time.sleep(delay)
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"Connection error on {url}: {e}")
            time.sleep(delay)
        except Exception as e:
            logger.error(f"Unexpected error on {url}: {e}")
            break
    return None


def polite_delay(min_s: float = 1.0, max_s: float = 3.0):
    """Random delay to be polite to servers."""
    time.sleep(random.uniform(min_s, max_s))