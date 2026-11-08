#!/usr/bin/env python3
"""Checks a configured public feed for wild costumed Pikachu and sends ntfy alerts."""
import json, os, sys, urllib.request
from pathlib import Path

feed_url = os.environ.get('PIKACHU_FEED_URL', '').strip()
topic = os.environ.get('NTFY_TOPIC', '').strip()
if not feed_url:
    print('Falta configurar el secreto PIKACHU_FEED_URL. No existe una API oficial pública de Pokémon GO para leer apariciones salvajes de una cuenta.')
    sys.exit(0)

req = urllib.request.Request(feed_url, headers={'User-Agent': 'PikachuHunter/1.0'})
with urllib.request.urlopen(req, timeout=25) as response:
    payload = json.load(response)
items = payload if isinstance(payload, list) else payload.get('appearances', [])

# Feed esperado: [{"id":"...", "name":"Pikachu", "costume":"...", "wild":true, "source_url":"https://..."}]
found = []
for item in items:
    if not isinstance(item, dict):
        continue
    if item.get('wild') is True and item.get('costume') and item.get('name', '').lower().startswith('pikachu'):
        found.append(item)

state_path = Path('data/notified.json')
state_path.parent.mkdir(exist_ok=True)
try:
    notified = set(json.loads(state_path.read_text(encoding='utf-8')))
except (FileNotFoundError, json.JSONDecodeError):
    notified = set()
new_items = []
for item in found:
    key = str(item.get('id') or f"{item.get('name')}|{item.get('costume')}")
    if key not in notified:
        new_items.append(item)
        notified.add(key)

if new_items and topic:
    for item in new_items:
        title = f"{item.get('name', 'Pikachu')} disfrazado salvaje"
        message = f"Disfraz: {item.get('costume')}"
        if item.get('source_url'):
            message += f"\nFuente: {item['source_url']}"
        request = urllib.request.Request(
            f"https://ntfy.sh/{topic}", data=message.encode('utf-8'),
            headers={'Title': title.encode('utf-8'), 'Priority': 'high', 'Tags': 'zap'}, method='POST'
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            print('Notificación enviada:', response.status, title)
elif new_items:
    print('Hay novedades, pero falta configurar NTFY_TOPIC para enviar notificaciones.')
else:
    print('Sin Pikachu disfrazados salvajes nuevos en el feed.')

state_path.write_text(json.dumps(sorted(notified), ensure_ascii=False, indent=2), encoding='utf-8')
