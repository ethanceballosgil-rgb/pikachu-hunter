#!/usr/bin/env python3
"""Monitor official Pokémon GO news pages for Pikachu-related announcements."""
import json, os, re, sys, time
from pathlib import Path
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

BASE = 'https://pokemongolive.com'
INDEX = BASE + '/news/?hl=es'
HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; PikachuHunter/2.0; +https://pokemongolive.com/)'}
DATA = Path('data')
NEWS_FILE = DATA / 'pikachu-news.json'
STATE_FILE = DATA / 'notified-news.json'
TOPIC = os.environ.get('NTFY_TOPIC', '').strip()


def get(url):
    r = requests.get(url, headers=HEADERS, timeout=25)
    r.raise_for_status()
    return r.text


def article_links(html):
    soup = BeautifulSoup(html, 'html.parser')
    links = []
    for a in soup.select('a[href]'):
        href = urljoin(BASE, a.get('href', '').strip())
        p = urlparse(href)
        if p.netloc.endswith('pokemongolive.com') and ('/post/' in p.path or '/news/' in p.path) and p.path.rstrip('/') != '/news':
            clean = p.scheme + '://' + p.netloc + p.path
            if clean not in links:
                links.append(clean)
    return links[:45]


def extract_article(url):
    soup = BeautifulSoup(get(url), 'html.parser')
    title = ''
    for sel in ['meta[property="og:title"]', 'meta[name="twitter:title"]']:
        tag = soup.select_one(sel)
        if tag and tag.get('content'):
            title = tag['content'].strip(); break
    if not title:
        h = soup.find('h1'); title = h.get_text(' ', strip=True) if h else url
    date = ''
    for sel, attr in [('meta[property="article:published_time"]','content'), ('meta[property="og:published_time"]','content'), ('time[datetime]','datetime')]:
        tag = soup.select_one(sel)
        if tag and tag.get(attr):
            date = tag.get(attr).strip(); break
    main = soup.find('article') or soup.find('main') or soup.body or soup
    text = re.sub(r'\s+', ' ', main.get_text(' ', strip=True))
    if 'pikachu' not in text.casefold():
        return None
    # Keep only sentences that explicitly mention Pikachu to avoid unrelated coverage.
    sentences = re.split(r'(?<=[.!?])\s+', text)
    relevant = [s.strip() for s in sentences if 'pikachu' in s.casefold()]
    excerpt = ' '.join(relevant[:4])[:900]
    return {'id': url, 'title': title[:220], 'date': date, 'excerpt': excerpt, 'url': url,
            'region_note': 'Consulta el anuncio para confirmar si incluye España.'}


def send_notification(item):
    if not TOPIC:
        print('NTFY_TOPIC no configurado: el hallazgo se guardará en el panel, pero no se enviará al móvil.')
        return
    message = (item['title'] + '\n' + item['excerpt'][:650] + '\n' + item['url']).encode('utf-8')
    req = requests.post('https://ntfy.sh/' + TOPIC, data=message,
                        headers={'Title': 'Pikachu Hunter: noticia oficial', 'Priority': 'high', 'Tags': 'zap'}, timeout=20)
    req.raise_for_status()


def main():
    DATA.mkdir(exist_ok=True)
    try:
        old_state = json.loads(STATE_FILE.read_text(encoding='utf-8'))
    except (FileNotFoundError, json.JSONDecodeError):
        old_state = []
    seen = set(old_state)
    found = []
    for url in article_links(get(INDEX)):
        try:
            item = extract_article(url)
            if item:
                found.append(item)
                if url not in seen:
                    send_notification(item)
                    seen.add(url)
            time.sleep(0.25)
        except Exception as exc:
            print(f'No se pudo revisar {url}: {exc}', file=sys.stderr)
    found.sort(key=lambda x: x.get('date', ''), reverse=True)
    NEWS_FILE.write_text(json.dumps({'checked_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'source': INDEX, 'items': found[:30]}, ensure_ascii=False, indent=2), encoding='utf-8')
    STATE_FILE.write_text(json.dumps(sorted(seen), ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Noticias oficiales de Pikachu encontradas: {len(found)}')

if __name__ == '__main__':
    main()
  
