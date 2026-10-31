#!/usr/bin/env python3
"""Aggiorna in automatico il mercato corner (Over/Under 9.5) delle partite non ancora iniziate.

1. Scarica da Betaminic le medie corner a favore/contro per squadra (Serie A, Premier League,
   La Liga, Bundesliga, Ligue 1) e le salva in data/stats-corner.json (al massimo ogni
   STATS_MAX_ETA_ORE ore; se il download fallisce restano valide le ultime statistiche).
2. Per ogni partita 'non_iniziata' dei 5 campionati calcola pick_corner con il modello corretto:
   - totale atteso = media tra (corner a favore casa, subiti trasferta) e (a favore trasferta,
     subiti casa), poi accostato alla media del campionato (le medie su 8-10 gare sono rumorose:
     peso della squadra g/(g+5), al massimo 0.8);
   - distribuzione binomiale negativa invece di Poisson: i corner totali variano piu' di una
     Poisson (deviazione standard ~3.7 con media ~10.3): le probabilita' estreme (0.80+) non sono credibili.
Non usa Claude: si lancia da solo (e viene chiamato da refresh_schedine.py a ogni giro).
"""
import datetime
import json
import math
import os
import re
import ssl
import sys
import unicodedata
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
STATS_FILE = os.path.join(DATA, 'stats-corner.json')
STATS_MAX_ETA_ORE = 10
CORNER_LINE = 9.5
NB_R = 40.0          # sovradispersione: var = m + m^2/R (sd ~3.7 con media 10.3)
PESO_MAX = 0.8       # peso massimo delle medie della squadra rispetto alla media del campionato
PESO_K = 5.0         # peso = g/(g+K): con 9 gare circa 0.64

LEGHE = {
    'pronostici-serie-a.json': ('serie-a', 'Serie A'),
    'pronostici-premier-league.json': ('premier-league', 'Premier League'),
    'pronostici-la-liga.json': ('la-liga', 'La Liga'),
    'pronostici-bundesliga.json': ('bundesliga', 'Bundesliga'),
    'pronostici-ligue-1.json': ('ligue-1', 'Ligue 1'),
}

# nome Betaminic -> nome usato nei nostri file (normalizzato, vedi _norm)
ALIAS = {
    'inter milan': 'inter', 'ac milan': 'milan', 'man utd': 'manchester united', 'man city': 'manchester city',
    'nottm forest': 'nottingham forest', 'ipswich': 'ipswich town', 'coventry': 'coventry city', 'hull': 'hull city',
    'brighton': 'brighton & hove albion', 'newcastle': 'newcastle united', 'tottenham': 'tottenham hotspur',
    'bournemouth': 'afc bournemouth', 'leeds': 'leeds united', 'leeds utd': 'leeds united',
    'cd alaves': 'deportivo alaves', 'athletic bilbao': 'athletic club', 'celta vigo': 'celta de vigo',
    'racing santander': 'racing de santander', 'deportivo la coruna': 'deportivo de la coruna',
    'atletico madrid': 'atletico madrid', 'barcelona': 'fc barcelona', 'malaga': 'malaga',
    'bayern munich': 'fc bayern munchen', 'mainz': '1. fsv mainz 05', 'cologne': '1. fc koln',
    'union berlin': '1. fc union berlin', 'elversberg': 'sv elversberg', "borussia m'gladbach": 'borussia monchengladbach',
    'paderborn': 'sc paderborn 07', 'hamburg': 'hamburger sv', 'augsburg': 'fc augsburg', 'werder bremen': 'sv werder bremen',
    'schalke': 'fc schalke 04', 'bayer leverkusen': 'bayer 04 leverkusen',
    'marseille': 'olympique de marseille', 'toulouse': 'toulouse fc', 'le mans': 'le mans fc', 'brest': 'stade brestois 29',
    'lorient': 'fc lorient', 'lyon': 'olympique lyonnais', 'strasbourg': 'rc strasbourg alsace', 'lens': 'rc lens',
    'troyes': 'estac troyes', 'nice': 'ogc nice', 'auxerre': 'aj auxerre', 'angers': 'angers sco', 'le havre': 'le havre ac',
    'rennes': 'stade rennais fc', 'lille': 'losc lille', 'monaco': 'as monaco', 'psg': 'paris saint-germain',
}


def _norm(s):
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower().strip()
    return re.sub(r'\s+', ' ', s)


def _nome_nostro(nome_bm):
    n = _norm(nome_bm)
    return ALIAS.get(n, n)


def scarica_stats():
    """Scarica le 5 pagine Betaminic e restituisce {lega: {squadra: {g, fav, con}}} oppure None."""
    ctx = ssl.create_default_context()
    ca = '/root/.ccr/ca-bundle.crt'
    if os.path.exists(ca):
        ctx = ssl.create_default_context(cafile=ca)
    out = {}
    for _, (slug, lega) in LEGHE.items():
        url = f'https://www.betaminic.com/statistics/corner-stats-{slug}/'
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            html = urllib.request.urlopen(req, timeout=40, context=ctx).read().decode('utf8', 'ignore')
        except Exception as e:  # rete assente o pagina cambiata: si tengono le statistiche precedenti
            print(f'corner: download {lega} non riuscito ({e})')
            return None
        # la pagina ha piu' tabelle (aiuto, tutte le gare, casa, trasferta): si prende la prima
        # che contiene almeno 16 squadre con partite giocate e medie corner (= "All games")
        squadre = {}
        for tid in dict.fromkeys(re.findall(r'id="(table_\d+)_row_0"', html)):
            cand = {}
            for r in re.findall(r'<tr id="%s_row_\d+".*?</tr>' % tid, html, re.S):
                celle = [re.sub(r'<[^>]+>', '', c).strip() for c in re.findall(r'<td[^>]*>(.*?)</td>', r, re.S)]
                if len(celle) < 4:
                    continue
                try:
                    cand[celle[0]] = {'g': int(celle[1]), 'fav': float(celle[2]), 'con': float(celle[3])}
                except ValueError:
                    continue
            if len(cand) >= 16:
                squadre = cand
                break
        if len(squadre) < 16:
            print(f'corner: tabella {lega} non trovata o incompleta ({len(squadre)} squadre)')
            return None
        out[lega] = squadre
    return out


def carica_stats(forza=False):
    vecchio = {}
    if os.path.exists(STATS_FILE):
        vecchio = json.load(open(STATS_FILE, encoding='utf-8'))
    now = datetime.datetime.now(datetime.timezone.utc)
    if not forza and vecchio.get('aggiornato'):
        eta = now - datetime.datetime.fromisoformat(vecchio['aggiornato'])
        if eta < datetime.timedelta(hours=STATS_MAX_ETA_ORE):
            return vecchio
    nuove = scarica_stats()
    if not nuove:
        return vecchio
    nuove['aggiornato'] = now.isoformat(timespec='seconds')
    nuove['fonte'] = 'betaminic.com (corner a favore/contro per gara, tutte le partite)'
    with open(STATS_FILE, 'w', encoding='utf-8') as f:
        json.dump(nuove, f, ensure_ascii=False, indent=1)
    return nuove


def nb_pmf(k, mean, r=NB_R):
    p = r / (r + mean)
    return math.exp(math.lgamma(k + r) - math.lgamma(r) - math.lgamma(k + 1)) * (p ** r) * ((1 - p) ** k)


def prob_over(mean):
    return 1 - sum(nb_pmf(k, mean) for k in range(int(CORNER_LINE) + 1))


def totale_atteso(sq, casa, trasf, media_lega):
    a, b = sq[casa], sq[trasf]
    tot = (a['fav'] + b['con']) / 2 + (b['fav'] + a['con']) / 2
    w = min(PESO_MAX, min(a['g'], b['g']) / (min(a['g'], b['g']) + PESO_K))
    return w * tot + (1 - w) * media_lega, tot


def aggiorna_partite(stats):
    modificati = []
    for fn, (_, lega) in LEGHE.items():
        path = os.path.join(DATA, fn)
        if not os.path.exists(path) or lega not in stats:
            continue
        sq = {_nome_nostro(k): v for k, v in stats[lega].items()}
        media_lega = 2 * sum(v['fav'] for v in sq.values()) / len(sq)
        raw = open(path, encoding='utf-8').read()
        d = json.loads(raw)
        cambiato = False
        for p in d.get('partite', []):
            if p.get('risultato', {}).get('stato') != 'non_iniziata':
                continue
            a, b = _norm(p['casa']), _norm(p['trasferta'])
            if a not in sq or b not in sq:
                continue
            tot, grezzo = totale_atteso(sq, a, b, media_lega)
            over = prob_over(tot)
            pick = ({'esito': 'over', 'etichetta': 'Over 9.5 corner', 'probabilita': round(over, 2)} if over >= 0.5
                    else {'esito': 'under', 'etichetta': 'Under 9.5 corner', 'probabilita': round(1 - over, 2)})
            pick['corner_attesi_totali'] = round(tot, 1)
            pick['modello'] = 'corner-v2'
            if p.get('pick_corner') != pick:
                p['pick_corner'] = pick
                cambiato = True
        if cambiato:
            ind = 1 if raw.startswith('{\n "') else 2
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(d, f, ensure_ascii=False, indent=ind)
            modificati.append(fn)
    return modificati


def main():
    stats = carica_stats(forza='--forza' in sys.argv)
    if not stats or not any(l in stats for _, l in LEGHE.values()):
        print('corner: nessuna statistica disponibile')
        return []
    mod = aggiorna_partite(stats)
    if mod:
        print('corner: pick_corner aggiornati in', ', '.join(mod))
    return mod


if __name__ == '__main__':
    main()
