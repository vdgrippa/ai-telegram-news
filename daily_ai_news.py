
#!/usr/bin/env python3
"""
daily_ai_news.py  –  raccoglie le novità sull’AI e le pubblica su Telegram.
Da schedulare ogni giorno alle 09:00 Europe/Rome via GitHub Actions.
"""

import os
import datetime
import feedparser
import requests
from textwrap import shorten
import openai

# Carica eventuale .env per i test locali (non fa nulla se il file manca)
from dotenv import load_dotenv
load_dotenv()

# --- credenziali ----------------------------------------------------------------
TG_TOKEN       = os.getenv("TG_TOKEN")          # token BotFather
TG_CHAT_ID     = os.getenv("TG_CHAT_ID")        # id canale (es. -1001234567890)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")    # chiave OpenAI

if not all((TG_TOKEN, TG_CHAT_ID, OPENAI_API_KEY)):
    raise RuntimeError("Variabili d’ambiente mancanti: TG_TOKEN, TG_CHAT_ID, OPENAI_API_KEY")

openai.api_key = OPENAI_API_KEY

# --- parametri ------------------------------------------------------------------
FEED_URLS = [
    # Italiano
    "https://news.google.com/rss/search?q=intelligenza+artificiale&hl=it&gl=IT&ceid=IT:it",
    # Inglese
    "https://news.google.com/rss/search?q=artificial+intelligence&hl=en&gl=US&ceid=US:en",
]
MAX_ARTICLES       = 8      # quante notizie spedire
MAX_TOKENS_OUTPUT  = 40     # lunghezza sintesi GPT
TEMPERATURE        = 0.5    # “creatività” del modello

# --- funzioni -------------------------------------------------------------------
def fetch_articles():
    """Scarica gli RSS, li unisce, ordina per data e rimuove i duplicati."""
    entries = []
    for url in FEED_URLS:
        entries.extend(feedparser.parse(url).entries)

    # ordina per data pubblicazione
    entries.sort(key=lambda e: getattr(e, "published_parsed", None) or getattr(e, "updated_parsed", None), reverse=True)

    # deduplica per link
    seen, unique = set(), []
    for e in entries:
        if e.link not in seen and len(unique) < MAX_ARTICLES:
            seen.add(e.link)
            unique.append(e)
    return unique


def summarize(title: str, snippet: str) -> str:
    """Sintetizza titolo+snippet in max 20 parole usando GPT-3.5-Turbo."""
    prompt = (
        "Riassumi in italiano in massimo 20 parole:\n"
        f"Titolo: {title}\n"
        f"Snippet: {snippet}"
    )
    resp = openai.ChatCompletion.create(
        model="gpt-3.5-turbo-0125",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=MAX_TOKENS_OUTPUT,
        temperature=TEMPERATURE,
    )
    return resp.choices[0].message.content.strip()


def build_message() -> str:
    bullets = []
    for entry in fetch_articles():
        title   = entry.title
        snippet = shorten(getattr(entry, "summary", "") or getattr(entry, "description", ""), width=200, placeholder="…")
        brief   = summarize(title, snippet)
        source  = getattr(entry, "source", {}).get("title") or getattr(entry, "source_title", "")
        url     = entry.link
        bullets.append(f"• **{title}** — {brief} ([{source}]({url}))")

    today  = datetime.date.today().strftime("%d %b %Y")
    header = f"📰 *Rassegna AI – {today}*"
    return "\n".join([header, "", *bullets])


def send_telegram(text: str):
    api_url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False,
    }
    resp = requests.post(api_url, json=payload, timeout=20)
    resp.raise_for_status()


def main():
    message = build_message()
    send_telegram(message)


if __name__ == "__main__":
    main()
