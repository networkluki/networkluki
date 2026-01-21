## Analyzer (JS-aware site crawler)

### Features
- Crawls same-site pages (BFS)
- JavaScript-rendered content via headless
- Word count per page
- Exact keyword matching (word-boundary aware)
- Safe defaults (page limits, timeouts)

Minimal Python-based site analyzer for inspecting rendered content on modern web applications (SPA).

Usage:

Command: python3 analyzer.py https://domian.com --terms "privacy,security,data" --max-pages 10

Output: 

{'url': 'https://example.com', 'word_count': 512, 'matches': {'privacy': 3, 'security': 1, 'data': 7}}

