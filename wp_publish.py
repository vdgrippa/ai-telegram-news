# wp_publish.py  ───────────────────────────────────────────────────────────
"""
Legge la lista 'extracts' (titolo, riassunto, link) prodotta in memoria
e crea i post WordPress nella categoria 'Bacheca-AI'.
Deve girare dentro GitHub Actions: WP_URL_BASE, WP_USER, WP_APP_PASS,
WP_CAT_ID sono già presenti come variabili d’ambiente.
"""

import os, base64, requests, sys, json

WP_URL      = os.getenv("WP_URL_BASE").rstrip("/")
WP_USER     = os.getenv("WP_USER")
WP_APP_PASS = os.getenv("WP_APP_PASS")         # application-password (24 char)
WP_CAT_ID   = os.getenv("WP_CAT_ID")           # es. "123"

if not all((WP_URL, WP_USER, WP_APP_PASS, WP_CAT_ID)):
    sys.exit("❌  Variabili WP mancanti")

auth_header = {
    "Authorization":
        "Basic " + base64.b64encode(f"{WP_USER}:{WP_APP_PASS}".encode()).decode()
}

def create_post(title: str, body: str):
    payload = {
        "title": title,
        "content": body,
        "status": "publish",           # usa "draft" se vuoi review
        "categories": [int(WP_CAT_ID)]
    }
    r = requests.post(f"{WP_URL}/wp-json/wp/v2/posts",
                      headers=auth_header, json=payload, timeout=30)
    r.raise_for_status()
    post_id = r.json()["id"]
    print(f"✅  Pubblicato post ID {post_id}: {title}")

# -----------------------------------------------------------------
# Qui simuliamo l’array 'extracts'  prodotto dal tuo script Telegram
# Estratto = dict(title, summary, link, source)
extracts = json.loads(os.getenv("EXTRACTS_JSON", "[]"))  # passato dal job

for ext in extracts[:5]:          # garantisce max 5
    title  = f"{ext['title']} – {ext['source']}"
    body   = f"{ext['summary']} ([{ext['source']}]({ext['link']}))"
    create_post(title, body)
