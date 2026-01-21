#!/usr/bin/env python3
# Compatible with Python 3.8+

import re
import sys
import argparse
from typing import Optional, Set, List, Dict, Any, Tuple
from urllib.parse import urljoin, urlparse, urldefrag

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "NetworkLuki-analyzer/1.0",
    "Accept": "text/html,application/xhtml+xml",
}

TIMEOUT = 8
MAX_PAGES_DEFAULT = 10
MAX_BYTES = 2_000_000  # 2MB safety cap

def normalize_netloc(netloc: str) -> str:
    # Normalize host matching: treat www.example.com and example.com as same
    netloc = netloc.lower().strip()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc

def normalize_url(url: str) -> str:
    """
    Normalize URLs for dedupe:
    - remove fragment (#...)
    - strip trailing slash (except domain root)
    """
    url, _frag = urldefrag(url)
    parsed = urlparse(url)

    # normalize scheme/host case
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()

    rebuilt = parsed._replace(scheme=scheme, netloc=netloc).geturl()

    # strip trailing slash for non-root paths
    p2 = urlparse(rebuilt)
    if p2.path not in ("", "/") and rebuilt.endswith("/"):
        rebuilt = rebuilt[:-1]

    return rebuilt

def fetch_page(url: str) -> Optional[str]:
    try:
        with requests.get(url, headers=HEADERS, timeout=TIMEOUT, stream=True) as r:
            r.raise_for_status()

            ctype = (r.headers.get("Content-Type") or "").lower()
            if ("text/html" not in ctype) and ("application/xhtml+xml" not in ctype):
                print(f"[SKIP] Non-HTML content {url} ({ctype})")
                return None

            # Basic size cap (prevents downloading huge pages)
            content = b""
            for chunk in r.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    break
                content += chunk
                if len(content) > MAX_BYTES:
                    print(f"[SKIP] Too large (> {MAX_BYTES} bytes): {url}")
                    return None

            # requests will guess encoding; fall back to utf-8
            encoding = r.encoding or "utf-8"
            try:
                return content.decode(encoding, errors="replace")
            except LookupError:
                return content.decode("utf-8", errors="replace")

    except requests.RequestException as e:
        print(f"[ERROR] Fetch failed {url}: {e}")
        return None

def is_probably_web_link(href: str) -> bool:
    href_l = href.lower().strip()
    if not href_l:
        return False
    if href_l.startswith(("#", "mailto:", "tel:", "javascript:", "data:")):
        return False
    return True

def same_site(netloc_a: str, netloc_b: str) -> bool:
    a = netloc_a.lower()
    b = netloc_b.lower()
    a = a[4:] if a.startswith("www.") else a
    b = b[4:] if b.startswith("www.") else b
    return a == b or a.endswith("." + b) or b.endswith("." + a)

def extract_links(html: str, base_url: str, allowed_netloc: str) -> Set[str]:
    soup = BeautifulSoup(html, "html.parser")
    links: Set[str] = set()

    a_tags = soup.find_all("a", href=True)
    print(f"[DEBUG] Found <a> tags: {len(a_tags)} on {base_url}")

    skipped = 0
    offsite = 0
    nonhttp = 0

    for tag in a_tags:
        href = (tag.get("href") or "").strip()
        if not is_probably_web_link(href):
            skipped += 1
            continue

        full_url = normalize_url(urljoin(base_url, href))
        parsed = urlparse(full_url)

        if parsed.scheme not in ("http", "https"):
            nonhttp += 1
            continue

        if same_site(parsed.netloc, allowed_netloc):
            links.add(full_url)
        else:
            offsite += 1

    print(
        f"[DEBUG] links_kept={len(links)} skipped={skipped} nonhttp={nonhttp} offsite={offsite} allowed_netloc={allowed_netloc}"
    )

    # show a few examples
    for i, u in enumerate(sorted(list(links))[:10]):
        print(f"[DEBUG] kept[{i}] {u}")

    return links

def analyze_content(html: str, search_terms: List[str]) -> Dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")

    for t in soup(["script", "style", "noscript"]):
        t.decompose()

    text = soup.get_text(separator=" ", strip=True).lower()
    word_count = len(text.split())

    matches: Dict[str, int] = {}
    for term in search_terms:
        term_l = term.lower()
        pattern = rf"\b{re.escape(term_l)}\b"
        matches[term] = len(re.findall(pattern, text))

    return {"word_count": word_count, "matches": matches}

def crawl(start_url: str, search_terms: List[str], max_pages: int) -> List[Dict[str, Any]]:
    start_url = normalize_url(start_url)
    start_parsed = urlparse(start_url)

    if start_parsed.scheme not in ("http", "https") or not start_parsed.netloc:
        raise ValueError(f"Invalid start_url: {start_url}")

    allowed_netloc = start_parsed.netloc

    visited: Set[str] = set()
    queue: List[str] = [start_url]
    results: List[Dict[str, Any]] = []

    while queue and len(visited) < max_pages:
        url = normalize_url(queue.pop(0))

        if url in visited:
            continue

        visited.add(url)
        print(f"[INFO] Crawling {url}")

        html = fetch_page(url)
        if not html:
            continue

        analysis = analyze_content(html, search_terms)
        results.append({"url": url, **analysis})

        for link in extract_links(html, url, allowed_netloc):
            if link not in visited and link not in queue:
                queue.append(link)

    return results

def parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Simple site crawler + keyword analyzer")
    p.add_argument("url", help="Start URL, e.g. https://networkluki.com")
    p.add_argument(
        "--terms",
        default="privacy,security,data",
        help="Comma-separated search terms (default: privacy,security,data)",
    )
    p.add_argument(
        "--max-pages",
        type=int,
        default=MAX_PAGES_DEFAULT,
        help=f"Max pages to crawl (default: {MAX_PAGES_DEFAULT})",
    )
    return p.parse_args(argv)

def main(argv: List[str]) -> int:
    args = parse_args(argv)
    terms = [t.strip() for t in args.terms.split(",") if t.strip()]
    if not terms:
        print("[ERROR] No search terms provided.")
        return 2

    report = crawl(args.url, terms, args.max_pages)

    print("\n=== ANALYSIS REPORT ===")
    for page in report:
        print(page)

    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
