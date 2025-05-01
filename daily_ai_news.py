#!/usr/bin/env python3
"""
daily_ai_news.py – versione con retry, deduplica avanzata e logging.
"""

import os, time, datetime
from textwrap import shorten
from difflib import SequenceMatcher

import feedparser, requests
from dotenv import load_dotenv
from openai import OpenAI, OpenAIError

# ------------------------- credenziali ------------------------------------- #
load_dotenv()
TG_TOKEN       = os.getenv("TG_TOKEN")
TG_CHAT_ID     = os.getenv("TG_CHAT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not all((TG_TOKEN, TG_CHAT_ID, OPENAI_API_KEY)):
    raise RuntimeError("Variabili d’ambiente mancanti")
client = OpenAI(api_key=OPENAI_API_KEY)

# ------------------------- parametri --------------------------------------- #
FEED_URLS = [
    # Google News – AI in italiano
    "https://news.google.com/rss/search?q=intelligenza+artificiale&hl=it&gl=IT&ceid=IT:it",
    "https://news.google.com/rss/search?q=ai+generativa&hl=it&gl=IT&ceid=IT:it",
    "https://news.google.com/rss/search?q=modelli+linguistici&hl=it&gl=IT&ceid=IT:it",
]

MAX_ARTICLES, MAX_TOKENS_OUTPUT, TEMPERATURE = 5, 40, 0.3
MODEL = "gpt-4o-mini"          # usa l’alias stabile

# ------------------------- helper ------------------------------------------ #
def is_similar(a, b, soglia=0.85):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio() >= soglia

def summarize(title: str, snippet: str) -> str:
    """
    Restituisce un riassunto di **40 parole** nella stessa lingua dell’articolo.
    """
    prompt = (
        "Riassumi in esattamente 40 parole, mantenendo la lingua originale del testo. "
        "Termina con un punto.\n"
        f"Titolo: {title}\n"
        f"Snippet: {snippet}"
    )
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=60,          # 40 parole ≈ 55–60 token
        temperature=TEMPERATURE,
    )
    return resp.choices[0].message.content.strip()


def safe_summary(title, snippet, tries=2, wait=25):
    for i in range(tries):
        try:
            return summarize(title, snippet)
        except OpenAIError as err:
            print(f"[GPT] retry {i+1}/{tries}: {err}")
            time.sleep(wait)
    return "Sintesi non disponibile."

from langdetect import detect, LangDetectException   # ⬅︎ import in testa al file

def is_italian(text: str) -> bool:
    """
    Ritorna True se la lingua rilevata è italiano ('it'), altrimenti False.
    langdetect lavora su poche parole, ma usiamo il titolo che è sempre presente.
    """
    try:
        return detect(text) == "it"
    except LangDetectException:
        # in caso di stringa troppo corta o errore di detection scartiamo l'articolo
        return False


def fetch_articles():
    """Scarica gli RSS, filtra per lingua italiana, rimuove duplicati e ordina per data."""
    # 1) unisci gli entry provenienti dai feed
    entries = [e for url in FEED_URLS for e in feedparser.parse(url).entries]

    # 2) ordina per data pubblicazione (più recente in cima)
    entries.sort(
        key=lambda e: getattr(e, "published_parsed", None)
               or getattr(e, "updated_parsed", None),
        reverse=True,
    )

    # 3) deduplica e filtra SOLO italiano
    seen_links, seen_titles, unique = set(), [], []
    for e in entries:
        if e.link in seen_links:            # link già visto
            continue
        if not is_italian(e.title):         # scarta se il titolo non è in IT
            continue
        if any(is_similar(e.title, t) for t in seen_titles):  # titolo quasi duplicato
            continue

        seen_links.add(e.link)
        seen_titles.append(e.title)
        unique.append(e)

        if len(unique) >= MAX_ARTICLES:     # stop appena raggiunto il limite
            break

    return unique

def build_message() -> str:
    sections = []
    for entry in fetch_articles():
        title   = entry.title.strip()
        source  = (getattr(entry, "source", {}).get("title")
                   or getattr(entry, "source_title", "")).strip()
        url     = entry.link
        # snippet originale per fornire contesto al riassunto
        snippet = shorten(
            getattr(entry, "summary", "") or getattr(entry, "description", ""),
            width=300, placeholder="…",
        )
        brief   = safe_summary(title, snippet)  # 40 parole, stessa lingua

        # ── formato finale ──
        section = (
            f"• {title} - {source}.\n"
            f"{brief} ([{source}]({url}))"
        )
        sections.append(section)

    header = f"📰 *Rassegna AI – {datetime.date.today():%d %b %Y}*"
    return "\n\n".join([header, "", *sections])     # riga bianca fra articoli



def send_telegram(text, tries=2):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {"chat_id": TG_CHAT_ID, "text": text,
               "parse_mode": "Markdown", "disable_web_page_preview": False}
    for i in range(tries):
        r = requests.post(url, json=payload, timeout=20)
        if r.ok and r.json().get("ok"):
            return
        print(f"[TG] errore {r.status_code}: {r.text}")
        if "parse" in r.text and payload["parse_mode"] == "Markdown":
            payload["parse_mode"] = "HTML"
        time.sleep(10)
    raise RuntimeError("Invio Telegram fallito")

def main():
    send_telegram(build_message())

if __name__ == "__main__":
    main()
