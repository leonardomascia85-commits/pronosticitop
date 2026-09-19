"""Ricalcola pick_1x2/pick_uo/pick_gg per le partite non ancora iniziate, con un
modello esplicito a gol attesi (media tra gol fatti/gara della squadra e gol
subiti/gara dell'avversaria, +8%/-8% per il fattore campo). Richiede che
forma_casa/forma_trasferta siano nel formato "X pt in Y gare (VV-NN-PP), GF-GA".

Se il forma_casa/forma_trasferta di una partita e' ancora nel formato
semplificato "W-D-L (ultime 3)" senza gol (capitava per Serie A/B prima del
19/9/2026), va prima riportato al formato pieno "X pt in Y gare (VV-NN-PP),
GF-GA" con i gol fatti/subiti reali (es. dalla classifica ufficiale) — occhio
a non usare classifiche "contaminate" da una partita che in realta' e'
proprio quella da pronosticare (capita quando la partita e' gia' in corso o
appena finita nelle fonti web ma il sito la segna ancora non_iniziata): in
quel caso vanno usati i dati PRE-partita delle due squadre, non quelli
aggiornati con questo stesso match.

Uso: python3 scripts/recompute_picks.py dalla root del repo.
"""
import json, re, os

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
FILES = [
    "pronostici-serie-a.json", "pronostici-serie-b.json", "pronostici-serie-c.json",
    "pronostici-premier-league.json", "pronostici-la-liga.json",
    "pronostici-bundesliga.json", "pronostici-ligue-1.json", "pronostici-liga-portugal.json",
    "pronostici-eredivisie.json", "pronostici-brasileirao.json",
]

PATTERN = re.compile(r'(\d+)\s*pt in (\d+)\s*gare\s*\((\d+)V-(\d+)N-(\d+)P\),\s*(\d+)-(\d+)')

def parse_forma(s):
    m = PATTERN.search(s)
    if not m: return None
    pt, games, v, n, p, gf, ga = map(int, m.groups())
    if games == 0: return None
    return {'games': games, 'gf_pg': gf/games, 'ga_pg': ga/games}

def clamp(x, lo, hi): return max(lo, min(hi, x))

def compute_picks(casa, trasferta, forma_casa, forma_trasferta):
    fc = parse_forma(forma_casa)
    ft = parse_forma(forma_trasferta)
    if not fc or not ft: return None

    exp_home = (fc['gf_pg'] + ft['ga_pg']) / 2 * 1.08  # vantaggio-casa (~8% gol attesi in piu')
    exp_away = (ft['gf_pg'] + fc['ga_pg']) / 2 * 0.92  # svantaggio-trasferta
    diff = exp_home - exp_away
    total = exp_home + exp_away

    # 1X2
    if diff >= 0:
        esito_1x2, team_1x2 = '1', casa
        prob_1x2 = clamp(0.50 + diff*0.12, 0.50, 0.68)
    else:
        esito_1x2, team_1x2 = '2', trasferta
        prob_1x2 = clamp(0.50 + (-diff)*0.12, 0.50, 0.68)

    # Under/Over 2.5
    prob_over_raw = 0.50 + (total-2.5)*0.10
    if prob_over_raw >= 0.50:
        esito_uo, prob_uo = 'over', clamp(prob_over_raw, 0.50, 0.66)
        etich_uo = 'Over 2.5'
    else:
        esito_uo, prob_uo = 'under', clamp(1-prob_over_raw, 0.50, 0.66)
        etich_uo = 'Under 2.5'

    # Gol/No Gol
    min_exp = min(exp_home, exp_away)
    prob_gol_raw = 0.42 + min_exp*0.15
    if prob_gol_raw >= 0.50:
        esito_gg, prob_gg = 'gol', clamp(prob_gol_raw, 0.50, 0.66)
        etich_gg = 'Gol'
    else:
        esito_gg, prob_gg = 'nogol', clamp(1-prob_gol_raw, 0.50, 0.66)
        etich_gg = 'No Gol'

    return {
        'pick_1x2': {'esito': esito_1x2, 'etichetta': f'Vittoria {team_1x2}', 'probabilita': round(prob_1x2, 2)},
        'pick_uo': {'esito': esito_uo, 'etichetta': etich_uo, 'probabilita': round(prob_uo, 2)},
        'pick_gg': {'esito': esito_gg, 'etichetta': etich_gg, 'probabilita': round(prob_gg, 2)},
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
        p['pick_uo'] = new['pick_uo']
        p['pick_gg'] = new['pick_gg']
        changed = True
        total_updated += 1
    if changed:
        json.dump(d, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

print(f"\nAggiornate: {total_updated}, saltate (dati insufficienti): {total_skipped}, esito ribaltato: {total_flipped}")
