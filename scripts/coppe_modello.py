"""Pronostici delle coppe europee a partire dalle statistiche dei campionati nazionali.

Una partita di coppa entra in pagina solo se entrambe le squadre hanno le
statistiche nelle nostre pagine di campionato (Serie A, Premier League, La Liga,
Bundesliga, Ligue 1, Liga Portugal, Eredivisie, Süper Lig): gol fatti e subiti
in campionato, avvicinati alla media dal modello v2 (modello_gol.py). I
campionati non sono confrontabili tra loro, quindi la confidenza resta MEDIA.

- costruisci(...)  crea la partita con forma, 5 mercati e nota;
- ricalcola_non_iniziate(d)  riporta forma, mercati e nota delle partite non
  ancora iniziate alle statistiche piu' recenti dei campionati (serve perche'
  tra l'inserimento e la partita passano anche due turni di campionato).
"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import modello_gol
import inserisci_turno as it

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
LEGHE = {'Serie A': 'serie-a', 'Premier League': 'premier-league', 'La Liga': 'la-liga', 'Bundesliga': 'bundesliga',
         'Ligue 1': 'ligue-1', 'Liga Portugal': 'liga-portugal', 'Eredivisie': 'eredivisie', 'Süper Lig': 'super-lig'}
PAT = re.compile(r'(\d+)° posto, (\d+) pt in (\d+) gare \((\d+)V-(\d+)N-(\d+)P\), (\d+)-(\d+)')
_CACHE = None


def _squadre():
    """{(lega, nome): stats} dalle forme dei file dei campionati."""
    global _CACHE
    if _CACHE is None:
        _CACHE = {}
        for lega, f in LEGHE.items():
            d = json.load(open(os.path.join(DATA_DIR, f'pronostici-{f}.json'), encoding='utf-8'))
            for p in d['partite']:
                for nome, fm in ((p['casa'], p['forma_casa']), (p['trasferta'], p['forma_trasferta'])):
                    m = PAT.search(fm)
                    if m:
                        pos, pt, g, v, n, pp, gf, ga = map(int, m.groups())
                        _CACHE[(lega, nome)] = dict(pos=pos, pt=pt, g=g, v=v, n=n, p=pp, gf=gf, ga=ga)
    return _CACHE


def trova(nome_coppa, lega=None, alias=None):
    """(lega, nome nel file del campionato) di una squadra, o None."""
    s = _squadre()
    cand = (alias or {}).get(nome_coppa, nome_coppa)
    for (l, n) in s:
        if lega and l != lega:
            continue
        if n.lower() == cand.lower():
            return l, n
    for (l, n) in s:
        if lega and l != lega:
            continue
        a, b = n.lower(), cand.lower()
        if a in b or b in a:
            return l, n
    return None


def _forma(lega, st):
    return f"{st['pos']}° posto, {st['pt']} pt in {st['g']} gare ({st['v']}V-{st['n']}N-{st['p']}P), {st['gf']}-{st['ga']} in {lega}"


def calcola(p, src_c, src_t):
    """Aggiorna forma, mercati e nota di una partita dai dati correnti."""
    h, a = _squadre()[src_c], _squadre()[src_t]
    eh, ea, boost = modello_gol.gol_attesi(h, a)
    p['forma_casa'], p['forma_trasferta'] = _forma(src_c[0], h), _forma(src_t[0], a)
    for k, v in it.picks(eh, ea, p['casa'], p['trasferta']).items():
        p[k] = dict(v, modello=modello_gol.MODELLO_VERSIONE)
    p['nota'] = (f"Modello a gol attesi (con vantaggio casa): {p['casa']} {eh:.2f} gol attesi ({h['gf']} gol fatti e {h['ga']} subiti in "
                 f"{h['g']} gare di {src_c[0]}), {p['trasferta']} {ea:.2f} ({a['gf']} fatti e {a['ga']} subiti in {a['g']} gare di {src_t[0]}). "
                 f"Somma attesa {eh + ea:.2f} gol. Le statistiche sono quelle dei campionati nazionali su campioni ancora piccoli e vengono "
                 f"avvicinate alla media di 1,4 gol a gara; i campionati non sono confrontabili tra loro, quindi la confidenza e' media."
                 + (' Correzione per squadra molto offensiva applicata.' if boost else ''))
    p['confidenza_dati'] = 'MEDIA'
    p['fonte_stat'] = {'casa': list(src_c), 'trasferta': list(src_t)}


def costruisci(casa, trasf, src_c, src_t, data, da_confermare=False):
    p = {'casa': casa, 'trasferta': trasf, 'data': data}
    calcola(p, src_c, src_t)
    if da_confermare:
        p['nota'] += ' Orario da confermare.'
    p['risultato'] = {'stato': 'non_iniziata', 'punteggio': None, 'aggiornato': None}
    return p


def ricalcola_non_iniziate(d):
    """Ricalcola le partite non iniziate che hanno 'fonte_stat'. True se cambia qualcosa."""
    mod = False
    for c in d.get('competizioni', []):
        for p in c['partite']:
            fs = p.get('fonte_stat')
            if p.get('risultato', {}).get('stato') != 'non_iniziata' or not fs:
                continue
            try:
                calcola(p, tuple(fs['casa']), tuple(fs['trasferta']))
                mod = True
            except KeyError:
                pass
    return mod
