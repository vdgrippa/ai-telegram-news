#!/usr/bin/env python3
"""
daily_ai_news.py – raccoglie le novità sull’AI e le pubblica su Telegram.
Da schedulare ogni giorno alle 09:00 Europe/Rome via GitHub Actions.
"""

import os
import datetime
from textwrap import shorten

import feedparser
import requests
from dotenv import load_dotenv
from openai import OpenAI

# --------------------------------------------------------------------------- #
# 1. CREDENZIALI (prese da variabili d’ambiente o da .env in locale)
# --------------------------------------------------------------------------- #
load_dotenv()  # se il file .env non c’è, non solleva errori

TG_TOKEN       = os.getenv("TG_TOKEN")          # token BotFather
TG_CHAT_ID     = os.getenv("TG_CHAT_ID")        # id canale (–100…)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")    # chiave OpenAI

if not all((TG_TOKEN, TG_CHAT_ID, OPENAI_API_KEY)):
    raise RuntimeError(
        "Variabili d’ambiente mancanti: TG_TOKEN, TG_CHAT_ID, OPENAI_API_KEY"
    )

client = OpenAI(api_key=OPENAI_API_KEY)

# --------------------------------------------------------------------------- #
# 2. PARAMETRI CONFIGURABILI
# --------------------------------------------------------------------------- #
FEED_URLS = [
    # Italiano
    "https://news.google.com/rss/search?q=intelligenza+artificiale&hl=it&gl=IT&ceid=IT:it",
    # Inglese
    "https://news.google.com/rss/search?q=artificial+intelligence&hl=en&gl=US&ceid=US:en",
]
MAX_ARTICLES      = 8     # quante notizie includere
MAX_TOKENS_OUTPUT = 40    # lunghezza sintesi GPT
TEMPERATURE       = 0.5   # “creatività” del modello

# --------------------------------------------------------------------------- #
# 3. FUNZIONI
# --------------------------------------------------------------------------- #
def fetch_articles():
    """Scarica gli RSS, ordina per data e rimuove i duplicati."""
    entries = []
    for url in FEED_URLS:
        entries.extend(feedparser.parse(url).entries)

    # ordina per data pubblicazione (più recente in cima)
    entries.sort(
        key=lambda e: getattr(e, "published_parsed", None)
        or getattr(e, "updated_parsed", None),
        reverse=True,
    )

    # deduplica per link
    seen, unique = set(), []
    for e in entries:
        if e.link not in seen and len(unique) < MAX_ARTICLES:
            seen.add(e.link)
            unique.append(e)
    return unique


def summarize(title: str, snippet: str) -> str:
    """Sintetizza titolo+snippet in max 20 parole usando gpt-4.1-mini-2025-04-14."""
    prompt = (
        "Riassumi in italiano in massimo 20 parole:\n"
        f"Titolo: {title}\n"
        f"Snippet: {snippet}"
    )
    resp = client.chat.completions.create(
        model="gpt-4.1-mini-2025-04-14",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=MAX_TOKENS_OUTPUT,
        temperature=TEMPERATURE,
    )
    return resp.choices[0].message.content.strip()


def build_message() -> str:
    bullets = []
    for entry in fetch_articles():
        title   = entry.title
        snippet = shorten(
            getattr(entry, "summary", "") or getattr(entry, "description", ""),
            width=200,
            placeholder="…",
        )
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


# --------------------------------------------------------------------------- #
# 4. MAIN
# --------------------------------------------------------------------------- #
def main():
    message = build_message()
    send_telegram(message)


if __name__ == "__main__":
    main()
