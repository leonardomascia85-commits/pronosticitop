"""Genera le schedine della sezione Nazionali (data/pronostici-nazionali.json),
con la stessa logica di calcolo di scripts/gen_schedine.py: per ogni partita si
sceglie il mercato con la probabilita' stimata piu' alta, poi si combinano gli
eventi piu' affidabili (probabilita' piu' alta) in schedine di 4, 5 e 6-8 eventi.
Scrive data/nazionali-schedine.json.
"""
import json, datetime, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")

def confidenza(prob):
    if prob >= 0.62: return 'ALTA'
    if prob >= 0.56: return 'MEDIA-ALTA'
    if prob >= 0.52: return 'MEDIA'
    return 'BASSA'

NOW = datetime.datetime.now(datetime.timezone.utc)

d = json.load(open(os.path.join(DATA_DIR, "pronostici-nazionali.json"), encoding="utf-8"))

pool = []
for p in d['partite']:
    if p.get('risultato', {}).get('stato') != 'non_iniziata':
        continue
    kickoff = datetime.datetime.fromisoformat(p['data'])
    if kickoff <= NOW:
        continue
    markets = []
    if p.get('pick_1x2'): markets.append(('1X2', p['pick_1x2']))
    if p.get('pick_dc'): markets.append(('DC', p['pick_dc']))
    if p.get('pick_uo'): markets.append(('OU25', p['pick_uo']))
    if p.get('pick_uo35'): markets.append(('OU35', p['pick_uo35']))
    if p.get('pick_gg'): markets.append(('GGNG', p['pick_gg']))
    best = max(markets, key=lambda m: m[1]['probabilita'])
    pool.append({
        'partita': f"{p['casa']} - {p['trasferta']}",
        'campionato': 'Nazionali',
        'girone': p.get('girone'),
        'data': p['data'],
        'mercato': best[0],
        'pronostico': best[1]['etichetta'],
        'esito_pick': best[1]['esito'],
        'probabilita_stimata': round(best[1]['probabilita'], 2),
        'quota_stimata': round(1 / best[1]['probabilita'], 2),
        'confidenza_dati': confidenza(best[1]['probabilita']),
        'motivazione': p['nota'],
        'esito': None,
        'risultato_reale': None,
    })

pool.sort(key=lambda x: -x['probabilita_stimata'])
print(f"Pool nazionali disponibile: {len(pool)} eventi")


def combo_prob(events):
    p = 1.0
    for e in events:
        p *= e['probabilita_stimata']
    return p


def build_level(level, n_events):
    n = min(n_events, len(pool))
    combo = pool[:n]
    pc = combo_prob(combo)
    return {
        'id': f'L{level}-1',
        'livello_rischio': level,
        'quota_combinata': round(1 / pc, 2),
        'probabilita_combinata': round(pc, 3),
        'eventi': combo,
    }


schedine = []
if len(pool) >= 4:
    schedine.append(build_level(4, 4))
if len(pool) >= 5:
    schedine.append(build_level(5, 5))
if len(pool) >= 6:
    schedine.append(build_level(8, min(8, len(pool))))

today = NOW.date().isoformat()
out = {
    "id": "nazionali-" + today,
    "titolo": "Nazionali — " + d.get("giornata", ""),
    "periodo": d.get("periodo", ""),
    "generato_il": today,
    "aggiornato_il": today,
    "stato": "pubblicata",
    "nota_dati": "Schedine costruite sugli eventi reali della finestra nazionali in corso (stessi dati pubblicati in /nazionali.html: ranking, forma recente, gol fatti/subiti). Ogni evento usa il mercato (1X2, doppia chance, Under/Over, Gol/No Gol) con la probabilita' stimata piu' alta per quella partita. Le schedine combinano sempre gli eventi con la probabilita' stimata piu' alta disponibile nel turno.",
    "schedine": schedine,
}

out_path = os.path.join(DATA_DIR, "nazionali-schedine.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)

print("Scritte", len(schedine), "schedine in", out_path)
for s in schedine:
    print(f"  {s['id']}: {len(s['eventi'])} eventi, prob_comb={s['probabilita_combinata']:.3f}  quota={s['quota_combinata']:.2f}")
