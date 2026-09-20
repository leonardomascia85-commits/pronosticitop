"""Genera le schedine multi-campionato del weekend, incrociando i pick gia'
pubblicati nei file data/pronostici-<lega>.json. Uso: python3 scripts/gen_schedine.py
dalla root del repo. Dopo la generazione:
  1. Rifinire a mano "titolo" e "periodo" nel file data/<data>.json con le date reali del weekend.
  2. Aggiungere la nuova voce in cima a data/settimane.json.
  3. Validare con `python3 -m json.tool data/<data>.json`.
"""
import json, random, collections, os

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

LEAGUES = {
  'pronostici-serie-a.json': 'Serie A',
  'pronostici-serie-b.json': 'Serie B',
  'pronostici-serie-c.json': 'Serie C',
  'pronostici-premier-league.json': 'Premier League',
  'pronostici-la-liga.json': 'La Liga',
  'pronostici-bundesliga.json': 'Bundesliga',
  'pronostici-ligue-1.json': 'Ligue 1',
  'pronostici-liga-portugal.json': 'Liga Portugal',
  'pronostici-eredivisie.json': 'Eredivisie',
  'pronostici-brasileirao.json': 'Brasileirão',
}

def confidenza(prob):
    if prob >= 0.62: return 'ALTA'
    if prob >= 0.56: return 'MEDIA-ALTA'
    if prob >= 0.52: return 'MEDIA'
    return 'BASSA'

import datetime
NOW = datetime.datetime.now(datetime.timezone.utc)

pool = []
for fn, name in LEAGUES.items():
    d = json.load(open(f"{DATA_DIR}/{fn}"))
    for p in d.get('partite', []):
        if p.get('risultato', {}).get('stato') != 'non_iniziata':
            continue
        kickoff = datetime.datetime.fromisoformat(p['data'])
        if kickoff <= NOW:
            continue  # stato non ancora aggiornato ma partita gia' iniziata/finita: escludi comunque
        markets = []
        if p.get('pick_1x2'): markets.append(('1X2', p['pick_1x2']))
        if p.get('pick_dc'): markets.append(('DC', p['pick_dc']))
        if p.get('pick_uo'): markets.append(('OU25', p['pick_uo']))
        if p.get('pick_uo35'): markets.append(('OU35', p['pick_uo35']))
        if p.get('pick_gg'): markets.append(('GGNG', p['pick_gg']))
        best = max(markets, key=lambda m: m[1]['probabilita'])
        pool.append({
            'partita': f"{p['casa']} - {p['trasferta']}",
            'campionato': name,
            'data': p['data'],
            'mercato': best[0],
            'pronostico': best[1]['etichetta'],
            'esito_pick': best[1]['esito'],
            'probabilita_stimata': round(best[1]['probabilita'], 2),
            'quota_stimata': round(1/best[1]['probabilita'], 2),
            'confidenza_dati': confidenza(best[1]['probabilita']),
            'motivazione': p['nota'],
            'esito': None,
            'risultato_reale': None,
        })

pool.sort(key=lambda x: -x['probabilita_stimata'])
print(f"Pool size: {len(pool)}")

random.seed(7)

def diverse_pick(eligible, n):
    by_league = collections.defaultdict(list)
    for e in eligible:
        by_league[e['campionato']].append(e)
    leagues_cycle = list(by_league.keys())
    random.shuffle(leagues_cycle)
    chosen, chosen_matches = [], set()
    li, attempts = 0, 0
    while len(chosen) < n and attempts < 500:
        attempts += 1
        lg = leagues_cycle[li % len(leagues_cycle)]
        li += 1
        candidates = [e for e in by_league[lg] if e['partita'] not in chosen_matches]
        if candidates:
            pick = random.choice(candidates[:max(1,len(candidates)//1)])
            by_league[lg].remove(pick)
            chosen.append(pick)
            chosen_matches.add(pick['partita'])
    return chosen if len(chosen) == n else None

def combo_prob(events):
    p = 1.0
    for e in events: p *= e['probabilita_stimata']
    return p

def build_level(level, n_events, n_variants, elig_threshold, min_threshold):
    # Non scendiamo mai sotto min_threshold: se il pool a elig_threshold non basta
    # per costruire n_variants combo diverse, allarghiamo la soglia a piccoli passi
    # (mai sotto il minimo) invece di infilare eventi deboli pur di riempire la schedina.
    threshold = elig_threshold
    candidates = []
    while True:
        eligible = [e for e in pool if e['probabilita_stimata'] >= threshold]
        candidates = []
        seen = set()
        tries = 0
        while len(candidates) < 40 and tries < 400:
            tries += 1
            combo = diverse_pick(eligible, n_events)
            if not combo: continue
            key = frozenset(e['partita'] for e in combo)
            if key in seen: continue
            seen.add(key)
            candidates.append(combo)
        if len(candidates) >= n_variants or threshold <= min_threshold:
            if threshold < elig_threshold:
                print(f"Livello {level}: soglia {elig_threshold} troppo stretta per il pool disponibile, allargata a {threshold:.2f}")
            break
        threshold = round(max(min_threshold, threshold - 0.03), 2)
    # sort candidates by combined probability, descending (safest first)
    candidates.sort(key=lambda c: -combo_prob(c))
    # spread selection across the sorted candidate list from safest to riskiest
    if len(candidates) <= n_variants:
        selected = candidates
    else:
        idxs = [round(i * (len(candidates)-1) / (n_variants-1)) for i in range(n_variants)]
        seen_idx = []
        for i in idxs:
            if i not in seen_idx: seen_idx.append(i)
        selected = [candidates[i] for i in seen_idx]

    schedine = []
    for i, combo in enumerate(selected):
        pc = combo_prob(combo)
        schedine.append({
            'id': f'L{level}-{i+1}',
            'livello_rischio': level,
            'quota_combinata': round(1/pc, 2),
            'probabilita_combinata': round(pc, 3),
            'eventi': combo,
        })
    return schedine

schedine = []
schedine += build_level(4, 4, 4, elig_threshold=0.70, min_threshold=0.65)
schedine += build_level(5, 5, 4, elig_threshold=0.65, min_threshold=0.60)
schedine += build_level(6, 6, 3, elig_threshold=0.58, min_threshold=0.55)
schedine += build_level(7, 7, 3, elig_threshold=0.55, min_threshold=0.52)

today = NOW.date().isoformat()
out = {
    "id": today,
    "titolo": "Weekend del " + today,  # da rifinire a mano con le date esatte venerdi-domenica
    "generato_il": today,
    "aggiornato_il": today,
    "stato": "pubblicata",
    "campionati_coperti": sorted(set(e['campionato'] for e in pool)),
    "nota_dati": "Schedine costruite incrociando eventi reali dai turni in corso di Serie A, Serie B, Serie C, Premier League, La Liga, Bundesliga, Ligue 1, Liga Portugal, Eredivisie e Brasileirão (stessi dati statistici verificati pubblicati nelle pagine di ogni campionato: forma, gol fatti/subiti, classifica). Champions League non presente in questo turno (pausa del calendario). Ogni evento usa il mercato (1X2, Under/Over 2.5, Gol/No Gol) con la probabilita' stimata piu' alta per quella partita. Le partite gia' disputate al momento della pubblicazione sono escluse. All'interno di ogni livello di rischio (stesso numero di eventi), le schedine sono ordinate dalla piu' sicura (probabilita' combinata piu' alta, #1) alla piu' rischiosa (probabilita' combinata piu' bassa, ultima).",
    "schedine": schedine,
}

with open(f"{DATA_DIR}/{today}.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)

print("Scritte", len(schedine), "schedine\n")
by_level = collections.defaultdict(list)
for s in schedine: by_level[s['livello_rischio']].append(s)
for level, group in sorted(by_level.items()):
    print(f"--- Livello {level} ---")
    for s in group:
        print(f"  {s['id']}: prob_comb={s['probabilita_combinata']:.3f}  quota={s['quota_combinata']:.2f}  leghe={[e['campionato'] for e in s['eventi']]}")
