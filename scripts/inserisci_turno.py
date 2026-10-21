"""Inserisce il turno successivo di un campionato in data/pronostici-<lega>.json.

Sostituisce l'array "partite" con le partite del nuovo turno e calcola i 5
mercati (1X2, Doppia chance, Under/Over 2.5, Under/Over 3.5, Gol/No Gol) con
lo stesso modello a gol attesi di recompute_picks.py (media tra gol fatti a
gara e gol subiti a gara dell'avversaria, +8% / -8% fattore campo, Poisson con
correzione Dixon-Coles). Tutti i dati in ingresso (calendario, classifica con
gol fatti e subiti) devono essere reali e verificati: lo script non inventa
nulla, calcola soltanto.

Uso: python3 scripts/inserisci_turno.py spec.json
spec.json = {
  "file": "pronostici-serie-a.json", "giornata": "7ª giornata", "periodo": "16-19 ottobre 2026",
  "tabella": {"Squadra": {"pos": 1, "g": 6, "v": 5, "n": 1, "p": 0, "gf": 18, "ga": 8, "pt": 16}, ...},
  "partite": [{"casa": "...", "trasferta": "...", "data": "2026-10-17T15:00:00+02:00", "da_confermare": false}],
  "corner": {"Squadra": {"fav": 5.1, "con": 4.8}, ...}   # opzionale: corner a favore/contro a partita
}
Campo opzionale "prev" per squadra nella tabella: {"g": 38, "gf": 70, "ga": 40} = stagione
PRECEDENTE (stessa lega). Se presente, i gol fatti/subiti a gara della squadra non sono piu'
il solo campione delle prime giornate (4-8 gare, molto rumoroso: nel caso PSG-Manchester City
del 14/10/2026 il PSG aveva 6 gol in 4 gare e 0.92 gol attesi) ma una media pesata tra la
stagione in corso e un prior (60% stagione precedente, 40% media del campionato) che pesa
quanto K_PRIOR partite. Senza "prev" il calcolo resta quello storico (campione grezzo).
"""
import json, math, os, sys, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import modello_gol

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
MAX_GOALS = 9
RHO = -0.10
CAP = 0.90
CORNER_LINE = 9.5
K_PRIOR = 6  # peso (in partite) del prior stagione precedente / media campionato


def pois(k, lam):
    return math.exp(-lam) * lam ** k / math.factorial(k)


def grid(eh, ea):
    ph = [pois(h, eh) for h in range(MAX_GOALS)]
    pa = [pois(a, ea) for a in range(MAX_GOALS)]
    g = [[ph[h] * pa[a] for a in range(MAX_GOALS)] for h in range(MAX_GOALS)]
    g[0][0] *= 1 - eh * ea * RHO
    g[0][1] *= 1 + eh * RHO
    g[1][0] *= 1 + ea * RHO
    g[1][1] *= 1 - RHO
    t = sum(map(sum, g))
    return [[c / t for c in r] for r in g]


def clamp(x):
    return max(0, min(CAP, x))


def picks(eh, ea, casa, trasf):
    g = grid(eh, ea)
    R = range(MAX_GOALS)
    p1 = sum(g[h][a] for h in R for a in R if h > a)
    px = sum(g[h][a] for h in R for a in R if h == a)
    p2 = sum(g[h][a] for h in R for a in R if h < a)
    o25 = sum(g[h][a] for h in R for a in R if h + a >= 3)
    o35 = sum(g[h][a] for h in R for a in R if h + a >= 4)
    gg = sum(g[h][a] for h in range(1, MAX_GOALS) for a in range(1, MAX_GOALS))
    e, t, pr = max([('1', f'Vittoria {casa}', p1), ('X', 'Pareggio', px), ('2', f'Vittoria {trasf}', p2)], key=lambda x: x[2])
    out = {'pick_1x2': {'esito': e, 'etichetta': t, 'probabilita': round(clamp(pr), 2)}}
    e, t, pr = max([('1X', f'{casa} o pareggio', p1 + px), ('12', f'{casa} o {trasf}', p1 + p2),
                    ('X2', f'Pareggio o {trasf}', px + p2)], key=lambda x: x[2])
    out['pick_dc'] = {'esito': e, 'etichetta': t, 'probabilita': round(clamp(pr), 2)}
    out['pick_uo'] = ({'esito': 'over', 'etichetta': 'Over 2.5', 'probabilita': round(clamp(o25), 2)} if o25 >= .5 else
                      {'esito': 'under', 'etichetta': 'Under 2.5', 'probabilita': round(clamp(1 - o25), 2)})
    out['pick_uo35'] = ({'esito': 'over', 'etichetta': 'Over 3.5', 'probabilita': round(clamp(o35), 2)} if o35 >= .5 else
                        {'esito': 'under', 'etichetta': 'Under 3.5', 'probabilita': round(clamp(1 - o35), 2)})
    out['pick_gg'] = ({'esito': 'gol', 'etichetta': 'Gol', 'probabilita': round(clamp(gg), 2)} if gg >= .5 else
                      {'esito': 'nogol', 'etichetta': 'No Gol', 'probabilita': round(clamp(1 - gg), 2)})
    return out


def conf(prob_dati_ok):
    return 'ALTA' if prob_dati_ok else 'MEDIA'


def forma(t, s):
    vnp = f" ({s['v']}V-{s['n']}N-{s['p']}P)" if all(k in s for k in 'vnp') else ''
    return f"{s['pos']}° posto, {s['pt']} pt in {s['g']} gare{vnp}, {s['gf']}-{s['ga']}"


def corner_pick(c, casa, trasf):
    a, b = c.get(casa), c.get(trasf)
    if not a or not b:
        return None
    tot = (a['fav'] + b['con']) / 2 + (b['fav'] + a['con']) / 2
    over = 1 - sum(pois(k, tot) for k in range(int(CORNER_LINE) + 1))
    if over >= .5:
        return {'esito': 'over', 'etichetta': 'Over 9.5 corner', 'probabilita': round(clamp(over), 2), 'corner_attesi_totali': round(tot, 1)}
    return {'esito': 'under', 'etichetta': 'Under 9.5 corner', 'probabilita': round(clamp(1 - over), 2), 'corner_attesi_totali': round(tot, 1)}


def medie_campionato(tab):
    g = sum(t['g'] for t in tab.values())
    return sum(t['gf'] for t in tab.values()) / g if g else 1.4


def tassi(t, media):
    """Gol fatti e subiti a gara della squadra, stabilizzati con il prior
    della stagione precedente quando disponibile (vedi docstring)."""
    gf, ga = t['gf'] / t['g'], t['ga'] / t['g']
    prev = t.get('prev')
    if not prev or not prev.get('g'):
        return gf, ga
    pf = 0.6 * prev['gf'] / prev['g'] + 0.4 * media
    pa = 0.6 * prev['ga'] / prev['g'] + 0.4 * media
    n = t['g']
    return (gf * n + pf * K_PRIOR) / (n + K_PRIOR), (ga * n + pa * K_PRIOR) / (n + K_PRIOR)


def main(spec_path):
    spec = json.load(open(spec_path, encoding='utf-8'))
    path = os.path.join(DATA_DIR, spec['file'])
    d = json.load(open(path, encoding='utf-8'))
    tab = spec['tabella']
    medie = medie_campionato(tab)
    nuove = []
    for m in spec['partite']:
        h, a = tab[m['casa']], tab[m['trasferta']]
        eh, ea, boost = modello_gol.gol_attesi(h, a)
        p = {'casa': m['casa'], 'trasferta': m['trasferta'], 'data': m['data'],
             'forma_casa': forma(m['casa'], h), 'forma_trasferta': forma(m['trasferta'], a)}
        if m.get('girone'):
            p = dict({'girone': m['girone']}, **p)
        p.update(picks(eh, ea, m['casa'], m['trasferta']))
        for _k in ('pick_1x2', 'pick_dc', 'pick_uo', 'pick_uo35', 'pick_gg'):
            p[_k]['modello'] = modello_gol.MODELLO_VERSIONE
        nota = (f"Modello a gol attesi (con vantaggio casa): {m['casa']} {eh:.2f} gol attesi "
                f"({h['pos']}° con {h['pt']} punti, {h['gf']} gol fatti e {h['ga']} subiti in {h['g']} gare), "
                f"{m['trasferta']} {ea:.2f} ({a['pos']}° con {a['pt']} punti, {a['gf']} fatti e {a['ga']} subiti in {a['g']} gare). "
                f"Somma attesa {eh + ea:.2f} gol.")
        if boost:
            nota += ' Correzione per squadra molto offensiva applicata.'
        if m.get('da_confermare'):
            nota += ' Orario da confermare.'
        p['nota'] = nota
        p['confidenza_dati'] = 'ALTA' if min(h['g'], a['g']) >= 5 else 'MEDIA'
        p['risultato'] = {'stato': 'non_iniziata', 'punteggio': None, 'aggiornato': None}
        if spec.get('corner'):
            cp = corner_pick(spec['corner'], m['casa'], m['trasferta'])
            if cp:
                p['pick_corner'] = cp
        nuove.append(p)
    nuove.sort(key=lambda x: x['data'])
    # Le partite concluse del turno che viene sostituito non si perdono: restano in
    # data/storico-partite.json (serve alla calibrazione e a rivedere i risultati).
    concluse = [dict(p, campionato=d.get('campionato'), giornata=d.get('giornata')) for p in d.get('partite', [])
                if p.get('risultato', {}).get('stato') in ('finale', 'sospesa')]
    storico_path = os.path.join(DATA_DIR, 'storico-partite.json')
    storico = json.load(open(storico_path, encoding='utf-8')) if os.path.exists(storico_path) else {'partite': []}
    gia = {(x.get('campionato'), x['casa'], x['trasferta'], x['data']) for x in storico['partite']}
    storico['partite'] += [x for x in concluse if (x['campionato'], x['casa'], x['trasferta'], x['data']) not in gia]
    with open(storico_path, 'w', encoding='utf-8') as f:
        json.dump(storico, f, ensure_ascii=False, indent=1)
    d['partite'] = nuove
    d['giornata'] = spec['giornata']
    d['periodo'] = spec['periodo']
    d['aggiornato'] = datetime.date.today().isoformat()
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    print(f"{spec['file']}: {len(nuove)} partite inserite ({spec['giornata']})")


if __name__ == '__main__':
    main(sys.argv[1])
