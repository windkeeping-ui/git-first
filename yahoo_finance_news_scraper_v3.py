#!/usr/bin/env python3
"""
Yahoo Finance News Scraper V3 - Simplified & Stable

Multi-topic support (latest-news, stock-market, earnings, economies, tech)
with optional neural summarization and strict body extraction.

Usage:
  python yahoo_finance_news_scraper_v3.py --topics latest-news --count 3
  python yahoo_finance_news_scraper_v3.py --topics latest-news stock-market earnings --count 5 --summarizer neural
"""
import argparse
import csv
import json
import re
import time
from datetime import datetime
from typing import List, Dict
from collections import Counter

import requests
from bs4 import BeautifulSoup

try:
    from transformers import pipeline
    HAS_TRANSFORMERS = True
except ImportError:
    HAS_TRANSFORMERS = False

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
}

TOPIC_URLS = {
    "latest-news": "https://finance.yahoo.com/topic/latest-news/",
    "stock-market": "https://finance.yahoo.com/topic/stock-market-news/",
    "earnings": "https://finance.yahoo.com/topic/earnings/",
    "economies": "https://finance.yahoo.com/topic/economic-news/",
    "tech": "https://finance.yahoo.com/topic/tech/",
}


class Summarizer:
    def __init__(self, method: str = "extractive"):
        self.method = method
        self.pipeline = None
        if method == "neural":
            if HAS_TRANSFORMERS:
                try:
                    self.pipeline = pipeline("summarization", model="google/pegasus-xsum")
                    print("✓ Pegasus model loaded for neural summarization\n")
                except Exception as e:
                    print(f"⚠ Pegasus load failed: {e}. Using extractive.\n")
                    self.method = "extractive"
            else:
                print("⚠ transformers not installed; using extractive.\n")
                self.method = "extractive"
    
    def summarize(self, text: str, max_sents: int = 3) -> str:
        if not text or len(text) < 50:
            return text[:200] if text else ""
        
        if self.method == "neural" and self.pipeline:
            try:
                words = text.split()
                if len(words) > 1000:
                    text = " ".join(words[:1000])
                result = self.pipeline(text, max_length=100, min_length=30, do_sample=False)
                return result[0]["summary_text"] if result else self._extractive(text, max_sents)
            except:
                return self._extractive(text, max_sents)
        return self._extractive(text, max_sents)
    
    def _extractive(self, text: str, max_sents: int = 3) -> str:
        sentences = re.split(r'(?<=[.!?])\s+', text)
        if len(sentences) <= max_sents:
            return text.strip()
        
        stopwords = {'the','and','a','to','of','in','is','for','on','that','with','as','by','at','it','from','be'}
        words = [w.lower() for w in re.findall(r"\w+", text) if w.lower() not in stopwords and len(w) > 2]
        if not words:
            return " ".join(sentences[:max_sents])
        
        freqs = Counter(words)
        scores = []
        for s in sentences:
            if s.strip():
                sw = [w.lower() for w in re.findall(r"\w+", s)]
                score = sum(freqs.get(w, 0) for w in sw) / max(len(sw), 1)
                scores.append((s, score))
            else:
                scores.append((s, 0))
        
        top = sorted(scores, key=lambda x: x[1], reverse=True)[:max_sents]
        top_idx = {scores.index(t) for t in top}
        return " ".join(s for i, (s, _) in enumerate(scores) if i in top_idx).strip()


def get_listing(url: str, max_pages: int = None) -> List[str]:
    """Fetch ALL article links from topic page with unlimited pagination."""
    links = []
    seen = set()
    page = 0
    max_attempts = max_pages if max_pages else 100  # Unlimited with safety limit
    
    while page < max_attempts:
        try:
            # Pagination: first page has no offset, subsequent pages use offset
            page_url = f"{url}?count=100&offset={page * 100}" if page > 0 else url
            print(f"  Fetching page {page + 1}...")
            
            resp = requests.get(page_url, headers=HEADERS, timeout=15, verify=False)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            
            page_links = []
            for a in soup.find_all("a", href=True):
                href = a["href"]
                # Look for news article links
                if "/news/" not in href or any(x in href for x in ["#", "javascript:", "subscribe"]):
                    continue
                
                # Clean up URL
                if href.startswith("/"):
                    full = requests.compat.urljoin(url, href)
                elif href.startswith("http"):
                    full = href
                else:
                    continue
                
                # Ensure it's a valid finance.yahoo.com article
                if full and full not in seen and "finance.yahoo.com" in full:
                    seen.add(full)
                    page_links.append(full)
            
            # If no new links found on this page, stop pagination
            if not page_links:
                print(f"  No new links on page {page + 1}. Pagination complete.")
                break
            
            links.extend(page_links)
            print(f"  Found {len(page_links)} links on page {page + 1} (total so far: {len(links)})")
            
            page += 1
            time.sleep(0.5)  # Be polite between pages
        
        except Exception as e:
            print(f"  Error fetching page {page + 1}: {e}")
            break
    
    print(f"  Total links collected: {len(links)}")
    return links


def extract_body(soup: BeautifulSoup) -> str:
    """Strict article body extraction"""
    # Try main article containers
    for selector in [("article", {}), ("div", {"class": re.compile(r"caas-body")}), ("div", {"role": "main"})]:
        try:
            node = soup.find(selector[0], selector[1] if selector[1] else None)
            if not node:
                continue
            for tag in node.find_all(["script", "style", "nav"]):
                tag.decompose()
            ps = node.find_all("p")
            if ps:
                parts = [p.get_text(strip=True) for p in ps if len(p.get_text(strip=True)) > 20]
                if parts and len("\n\n".join(parts)) > 200:
                    return "\n\n".join(parts)
        except:
            continue
    
    # Fallback: all paragraphs with filtering
    ps = soup.find_all("p")
    parts = [p.get_text(strip=True) for p in ps if len(p.get_text(strip=True)) > 20]
    return "\n\n".join(parts[:20]) if parts and len("\n\n".join(parts[:20])) > 200 else None


def fetch_article(url: str, summarizer: Summarizer) -> Dict:
    out = {
        "url": url, "title": None, "description": None, "published": None,
        "content": None, "summary": None, "scraped_at": datetime.now().isoformat()
    }
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15, verify=False)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        
        h1 = soup.find("h1")
        out["title"] = h1.get_text(strip=True) if h1 else None
        if not out["title"]:
            og = soup.find("meta", property="og:title")
            out["title"] = og.get("content", "").strip() if og else None
        
        desc = soup.find("meta", attrs={"name": "description"})
        out["description"] = desc.get("content", "").strip() if desc else None
        
        time_tag = soup.find("time")
        out["published"] = time_tag.get("datetime") if time_tag else None
        
        body = extract_body(soup)
        if body:
            out["content"] = body
            out["summary"] = summarizer.summarize(body)
    except Exception as e:
        out["error"] = str(e)
    return out


def save_json(items: List[Dict], path: str):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)


def save_csv(items: List[Dict], path: str):
    if not items:
        open(path, "w").close()
        return
    with open(path, "w", newline='', encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["url", "title", "description", "published", "content", "summary", "scraped_at", "error"])
        writer.writeheader()
        for item in items:
            writer.writerow({k: item.get(k, "") for k in writer.fieldnames})


def main():
    parser = argparse.ArgumentParser(description="Yahoo Finance News Scraper V3 - Fetch ALL news from topics")
    parser.add_argument("--topics", nargs="+", default=["latest-news"], choices=list(TOPIC_URLS.keys()))
    parser.add_argument("--count", type=int, default=None, help="Max articles per topic (None = fetch all)")
    parser.add_argument("--output", type=str, default="news.json")
    parser.add_argument("--format", choices=["json", "csv"], default="json")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between article fetches (seconds)")
    parser.add_argument("--summarizer", choices=["extractive", "neural"], default="extractive")
    parser.add_argument("--max-pages", type=int, default=None, help="Max pages to scrape per topic (None = unlimited)")
    args = parser.parse_args()
    
    summarizer = Summarizer(args.summarizer)
    all_items = []
    
    for topic in args.topics:
        url = TOPIC_URLS[topic]
        print(f"\n[{topic.upper()}] {url}")
        links = get_listing(url, max_pages=args.max_pages)
        
        # Limit articles if count is specified
        articles_to_fetch = links if args.count is None else links[:args.count]
        print(f"  Fetching {len(articles_to_fetch)} articles out of {len(links)} found\n")
        
        for i, link in enumerate(articles_to_fetch, 1):
            print(f"  [{i}/{len(articles_to_fetch)}] {link[:80]}...")
            item = fetch_article(link, summarizer)
            all_items.append(item)
            time.sleep(args.delay)
    
    if args.format == "json":
        save_json(all_items, args.output)
    else:
        save_csv(all_items, args.output)
    print(f"\nSaved {len(all_items)} items to {args.output}")


if __name__ == "__main__":
    main()
