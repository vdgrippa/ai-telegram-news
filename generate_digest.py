# generate_digest.py
import json
from daily_ai_news import fetch_articles, safe_summary   # funzioni già esistenti

digest = []
for entry in fetch_articles()[:5]:       # i 5 estratti che andranno su WP
    digest.append({
        "title":   entry.title,
        "summary": safe_summary(
                       entry.title,
                       getattr(entry, "summary", "") or getattr(entry, "description", "")
                   ),
        "link":    entry.link,
        "source":  getattr(entry, "source", {}).get("title")
                   or getattr(entry, "source_title", ""),
    })

print(json.dumps(digest, ensure_ascii=False))
