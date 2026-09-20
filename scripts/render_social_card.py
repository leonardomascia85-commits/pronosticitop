"""Renderizza il template social/template-schedina-vincente.html in un PNG
1080x1080 pronto per Instagram/Facebook, a partire dai dati di una schedina
vincente.

Uso:
  python3 scripts/render_social_card.py --livello 4 --quota 5.29 \
      --evento "Inter - Milan|Vittoria Inter|2-1" \
      --evento "Napoli - Roma|Over 2.5|3-1" \
      --out social/output/schedina-vincente-L4-1.png

Oppure, per rigenerare l'ultima schedina promossa in data/schedine-vinte.json:
  python3 scripts/render_social_card.py --ultima
"""
import argparse, json, os, sys, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def render(data, out_path, template_path=None):
    from playwright.sync_api import sync_playwright

    template_path = template_path or os.path.join(ROOT, 'social', 'template-schedina-vincente.html')
    url = 'file://' + template_path + '?d=' + urllib.parse.quote(json.dumps(data, ensure_ascii=False))

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        page = browser.new_page(viewport={'width': 1080, 'height': 1080})
        page.goto(url)
        page.wait_for_timeout(200)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        page.screenshot(path=out_path)
        browser.close()
    print('Salvato:', out_path)


def from_ultima():
    path = os.path.join(ROOT, 'data', 'schedine-vinte.json')
    promosse = json.load(open(path, encoding='utf-8')).get('promosse', [])
    if not promosse:
        print('Nessuna schedina promossa in data/schedine-vinte.json')
        sys.exit(1)
    win = promosse[-1]
    data = {
        'livello': win['livello_rischio'],
        'quota': win.get('quota_combinata'),
        'eventi': [{'partita': e['partita'], 'pronostico': e['pronostico'], 'risultato': e.get('risultato')} for e in win['eventi']],
    }
    out = os.path.join(ROOT, 'social', 'output', 'schedina-vincente-%s-%s.png' % (win['settimana'], win['id']))
    render(data, out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--livello', type=int)
    ap.add_argument('--quota', type=float)
    ap.add_argument('--evento', action='append', default=[], help='partita|pronostico|risultato')
    ap.add_argument('--out')
    ap.add_argument('--ultima', action='store_true')
    args = ap.parse_args()

    if args.ultima:
        from_ultima()
        return

    if not args.evento or not args.out:
        print('Servono almeno --evento e --out (oppure usa --ultima)')
        sys.exit(1)

    eventi = []
    for e in args.evento:
        parts = e.split('|')
        eventi.append({'partita': parts[0], 'pronostico': parts[1] if len(parts) > 1 else '', 'risultato': parts[2] if len(parts) > 2 else ''})

    data = {'livello': args.livello, 'quota': args.quota, 'eventi': eventi}
    render(data, args.out)


if __name__ == '__main__':
    main()
