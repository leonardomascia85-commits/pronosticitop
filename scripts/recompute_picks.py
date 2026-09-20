"""Ricalcola i pick per le partite non ancora iniziate, con un modello a gol
attesi (media tra gol fatti/gara della squadra e gol subiti/gara
dell'avversaria, +8%/-8% per il fattore campo) e una vera distribuzione di
Poisson sul numero di gol per derivare le probabilita' di ogni mercato:

- 1X2 (esito finale)
- Doppia chance (1X / X2 / 12)
- Under/Over 2.5
- Under/Over 3.5
- Gol/No Gol (entrambe segnano)

Si assume che i gol delle due squadre siano variabili Poisson indipendenti
con media pari al gol atteso stimato (approccio standard nei modelli di
previsione calcistica, es. modello di Poisson indipendente/Dixon-Coles
semplificato). Da qui si costruisce la matrice di probabilita' di ogni
risultato esatto (0-0, 1-0, 0-1, ... fino a 8-8) e si sommano le celle
pertinenti per ciascun mercato — niente piu' formule lineari improvvisate.

Richiede che forma_casa/forma_trasferta siano nel formato "X pt in Y gare
(VV-NN-PP), GF-GA". Se il forma_casa/forma_trasferta di una partita e'
ancora nel formato semplificato "W-D-L (ultime 3)" senza gol, va prima
riportato al formato pieno con i gol fatti/subiti reali (es. dalla
classifica ufficiale) — occhio a non usare classifiche "contaminate" da una
partita che in realta' e' proprio quella da pronosticare: in quel caso
vanno usati i dati PRE-partita delle due squadre.

Tocca SOLO le partite con risultato.stato == "non_iniziata": non modifica
mai risultati gia' giocati o in corso.

Uso: python3 scripts/recompute_picks.py dalla root del repo.
"""
import json, re, os, math

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
FILES = [
    "pronostici-serie-a.json", "pronostici-serie-b.json", "pronostici-serie-c.json",
    "pronostici-premier-league.json", "pronostici-la-liga.json",
    "pronostici-bundesliga.json", "pronostici-ligue-1.json", "pronostici-liga-portugal.json",
    "pronostici-eredivisie.json", "pronostici-brasileirao.json",
]

PATTERN = re.compile(r'(\d+)\s*pt in (\d+)\s*gare\s*\((\d+)V-(\d+)N-(\d+)P\),\s*(\d+)-(\d+)')
MAX_GOALS = 9  # copertura oltre il 99.9% della massa di probabilita' per lambda realistici

def parse_forma(s):
    m = PATTERN.search(s)
    if not m: return None
    pt, games, v, n, p, gf, ga = map(int, m.groups())
    if games == 0: return None
    return {'games': games, 'gf_pg': gf/games, 'ga_pg': ga/games}

def clamp(x, lo, hi): return max(lo, min(hi, x))

def poisson_pmf(k, lam):
    return math.exp(-lam) * lam**k / math.factorial(k)

def score_grid(exp_home, exp_away):
    ph = [poisson_pmf(h, exp_home) for h in range(MAX_GOALS)]
    pa = [poisson_pmf(a, exp_away) for a in range(MAX_GOALS)]
    return [[ph[h]*pa[a] for a in range(MAX_GOALS)] for h in range(MAX_GOALS)]

def compute_picks(casa, trasferta, forma_casa, forma_trasferta):
    fc = parse_forma(forma_casa)
    ft = parse_forma(forma_trasferta)
    if not fc or not ft: return None

    exp_home = (fc['gf_pg'] + ft['ga_pg']) / 2 * 1.08  # vantaggio-casa (~8% gol attesi in piu')
    exp_away = (ft['gf_pg'] + fc['ga_pg']) / 2 * 0.92  # svantaggio-trasferta

    grid = score_grid(exp_home, exp_away)
    p1 = sum(grid[h][a] for h in range(MAX_GOALS) for a in range(MAX_GOALS) if h > a)
    px = sum(grid[h][a] for h in range(MAX_GOALS) for a in range(MAX_GOALS) if h == a)
    p2 = sum(grid[h][a] for h in range(MAX_GOALS) for a in range(MAX_GOALS) if h < a)
    p_over25 = sum(grid[h][a] for h in range(MAX_GOALS) for a in range(MAX_GOALS) if h+a >= 3)
    p_over35 = sum(grid[h][a] for h in range(MAX_GOALS) for a in range(MAX_GOALS) if h+a >= 4)
    p_gg = sum(grid[h][a] for h in range(1, MAX_GOALS) for a in range(1, MAX_GOALS))

    # 1X2
    esiti_1x2 = [('1', casa, p1), ('X', 'pareggio', px), ('2', trasferta, p2)]
    esito_1x2, team_1x2, prob_1x2 = max(esiti_1x2, key=lambda t: t[2])
    etich_1x2 = f'Vittoria {team_1x2}' if esito_1x2 != 'X' else 'Pareggio'

    # Doppia chance: la combinazione piu' probabile tra 1X/X2/12
    dc_opts = [('1X', f'{casa} o pareggio', p1+px), ('12', f'{casa} o {trasferta}', p1+p2), ('X2', f'pareggio o {trasferta}', px+p2)]
    esito_dc, etich_dc, prob_dc = max(dc_opts, key=lambda t: t[2])

    # Under/Over 2.5 e 3.5
    if p_over25 >= 0.5:
        esito_uo, prob_uo, etich_uo = 'over', p_over25, 'Over 2.5'
    else:
        esito_uo, prob_uo, etich_uo = 'under', 1-p_over25, 'Under 2.5'
    if p_over35 >= 0.5:
        esito_uo35, prob_uo35, etich_uo35 = 'over', p_over35, 'Over 3.5'
    else:
        esito_uo35, prob_uo35, etich_uo35 = 'under', 1-p_over35, 'Under 3.5'

    # Gol/No Gol
    if p_gg >= 0.5:
        esito_gg, prob_gg, etich_gg = 'gol', p_gg, 'Gol'
    else:
        esito_gg, prob_gg, etich_gg = 'nogol', 1-p_gg, 'No Gol'

    CAP = 0.90  # tetto di prudenza: mai mostrare probabilita' che sembrino una certezza
    return {
        'pick_1x2': {'esito': esito_1x2, 'etichetta': etich_1x2, 'probabilita': round(clamp(prob_1x2, 0, CAP), 2)},
        'pick_dc': {'esito': esito_dc, 'etichetta': etich_dc, 'probabilita': round(clamp(prob_dc, 0, CAP), 2)},
        'pick_uo': {'esito': esito_uo, 'etichetta': etich_uo, 'probabilita': round(clamp(prob_uo, 0, CAP), 2)},
        'pick_uo35': {'esito': esito_uo35, 'etichetta': etich_uo35, 'probabilita': round(clamp(prob_uo35, 0, CAP), 2)},
        'pick_gg': {'esito': esito_gg, 'etichetta': etich_gg, 'probabilita': round(clamp(prob_gg, 0, CAP), 2)},
        'exp_home': round(exp_home,2), 'exp_away': round(exp_away,2),
    }

total_updated = 0
total_skipped = 0
total_flipped = 0
for fn in FILES:
    path = f"{DATA_DIR}/{fn}"
    d = json.load(open(path))
    changed = False
    for p in d.get('partite', []):
        if p.get('risultato', {}).get('stato') != 'non_iniziata':
            continue
        new = compute_picks(p['casa'], p['trasferta'], p['forma_casa'], p['forma_trasferta'])
        if not new:
            total_skipped += 1
            continue
        old_esito = p['pick_1x2']['esito']
        if old_esito != new['pick_1x2']['esito']:
            total_flipped += 1
            print(f"FLIP [{fn}] {p['casa']}-{p['trasferta']}: {p['pick_1x2']['etichetta']} ({p['pick_1x2']['probabilita']}) -> {new['pick_1x2']['etichetta']} ({new['pick_1x2']['probabilita']})")
        p['pick_1x2'] = new['pick_1x2']
        p['pick_dc'] = new['pick_dc']
        p['pick_uo'] = new['pick_uo']
        p['pick_uo35'] = new['pick_uo35']
        p['pick_gg'] = new['pick_gg']
        changed = True
        total_updated += 1
    if changed:
        json.dump(d, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

print(f"\nAggiornate: {total_updated}, saltate (dati insufficienti): {total_skipped}, esito 1X2 ribaltato: {total_flipped}")
