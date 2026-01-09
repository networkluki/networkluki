import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re

HEADERS = {
    "User-Agent": "NetworkLuki-analyzer/1.0",
    "Accept": "text/html"
}

TIMEOUT = 5
MAX_PAGES = 10

def fetch_page(url: str) -> str | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        return r.text
    except requests.RequestException as e:
        print(f"[ERROR] Fetch failed {url}: {e}")
        return None

def extract_links(html: str, base_url: str) -> set[str]:
    soup = BeautifulSoup(html, "html.parser")
    links = set()

    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        full_url = urljoin(base_url, href)

        parsed = urlparse(full_url)
        if parsed.scheme in ("http", "https"):
            links.add(full_url)

    return links

def analyze_content(html: str, search_terms: list[str]) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    text = soup.get_text(separator=" ", strip=True).lower()

    word_count = len(text.split())
    matches = {}

    for term in search_terms:
        matches[term] = len(re.findall(rf"\b{re.escape(term.lower())}\b", text))

    return {
        "word_count": word_count,
        "matches": matches
    }

def crawl(start_url: str, search_terms: list[str]) -> list[dict]:
    visited = set()
    queue = [start_url]
    results = []

    while queue and len(visited) < MAX_PAGES:
        url = queue.pop(0)
        if url in visited:
            continue

        visited.add(url)
        print(f"[INFO] Crawling {url}")

        html = fetch_page(url)
        if not html:
            continue

        analysis = analyze_content(html, search_terms)
        results.append({
            "url": url,
            **analysis
        })

        for link in extract_links(html, url):
            if link not in visited and link.startswith(start_url):
                queue.append(link)

    return results

if __name__ == "__main__":
    START_URL = "https://domain.com"
    SEARCH_TERMS = ["privacy", "security", "data"]

    report = crawl(START_URL, SEARCH_TERMS)

    print("\n=== ANALYSIS REPORT ===")
    for page in report:
        print(page)
