import logging
from bs4 import BeautifulSoup

def remove_honeypot_links(soup: BeautifulSoup) -> BeautifulSoup:
    """
    Removes invisible "honeypot" links from a BeautifulSoup object.

    This function targets links that are likely to be scraper traps by checking
    for common CSS styles used to hide elements from view.

    Args:
        soup: A BeautifulSoup object containing the parsed HTML.

    Returns:
        A BeautifulSoup object with the honeypot links removed.
    """
    honeypot_selectors = [
        'a[style*="display: none"]',
        'a[style*="visibility: hidden"]',
    ]

    for selector in honeypot_selectors:
        honeypots = soup.select(selector)
        for honeypot in honeypots:
            logging.info(f"Removing potential honeypot link: {honeypot.get('href', 'No href found')}")
            honeypot.decompose()

    return soup
