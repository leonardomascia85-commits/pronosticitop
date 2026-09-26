"""Calibrazione dei mercati: confronta le probabilita' stimate nei pronostici
con gli esiti reali gia' verificati (stato "finale"), per capire dove il
modello sovrastima o sottostima le probabilita' e affinare le stime future.

Analizza TUTTE le partite con risultato finale in tutti i file
data/pronostici-*.json (compreso lo schema nidificato delle coppe europee),
per ciascuno dei 5 mercati (1X2, DC, OU25, OU35, GGNG) quando presente come
pick esplicito nel file.

Uso: python3 scripts/calibrazione_mercati.py
Sola lettura: non modifica alcun file.
"""
import json, os, glob, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")

PICK_FIELDS = {
    'pick_1x2': '1X2',
    'pick_dc': 'DC',
    'pick_uo': 'OU25',
    'pick_uo35': 'OU35',
    'pick_gg': 'GGNG',
}


def actual_esiti(punteggio):
    if not punteggio:
        return None
    parts = punteggio.split('-')
    if len(parts) != 2:
        return None
    try:
        home, away = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    return {
        '1X2': '1' if home > away else ('2' if home < away else 'X'),
        'OU25': 'over' if (home + away) > 2.5 else 'under',
        'OU35': 'over' if (home + away) > 3.5 else 'under',
        'GGNG': 'gol' if (home > 0 and away > 0) else 'nogol',
    }


def bucket(p):
    if p < 0.55: return '0.50-0.54'
    if p < 0.60: return '0.55-0.59'
    if p < 0.65: return '0.60-0.64'
    if p < 0.70: return '0.65-0.69'
    if p < 0.75: return '0.70-0.74'
    return '0.75+'


def collect_matches():
    matches = []
    for path in sorted(glob.glob(os.path.join(DATA_DIR, 'pronostici-*.json'))):
        d = json.load(open(path, encoding='utf-8'))
        if 'competizioni' in d:
            for comp in d['competizioni']:
                matches.extend(comp.get('partite', []))
        else:
            matches.extend(d.get('partite', []))
    return matches


def main():
    matches = collect_matches()
    per_mercato = collections.defaultdict(list)  # mercato -> [(prob, hit)]

    for m in matches:
        ris = m.get('risultato') or {}
        if ris.get('stato') != 'finale':
            continue
        actual = actual_esiti(ris.get('punteggio'))
        if not actual:
            continue
        for field, mercato in PICK_FIELDS.items():
            pick = m.get(field)
            if not pick:
                continue
            esito_pick = pick.get('esito')
            prob = pick.get('probabilita')
            if esito_pick is None or prob is None:
                continue
            if mercato == 'DC':
                hit = actual['1X2'] in esito_pick
            else:
                hit = actual.get(mercato) == esito_pick
            per_mercato[mercato].append((prob, hit))

    print(f"Partite concluse analizzate: {sum(1 for m in matches if (m.get('risultato') or {}).get('stato') == 'finale')}")
    print()

    tot_n, tot_hit, tot_prob = 0, 0, 0.0
    for mercato in ['1X2', 'DC', 'OU25', 'OU35', 'GGNG']:
        rows = per_mercato.get(mercato, [])
        if not rows:
            continue
        n = len(rows)
        hits = sum(1 for _, h in rows if h)
        avg_prob = sum(p for p, _ in rows) / n
        acc = hits / n
        scarto = acc - avg_prob
        print(f"{mercato:5s}  n={n:3d}  prob.media_stimata={avg_prob:.2%}  accuratezza_reale={acc:.2%}  scarto={scarto:+.2%}")
        tot_n += n
        tot_hit += hits
        tot_prob += avg_prob * n

    print()
    if tot_n:
        print(f"TOTALE  n={tot_n}  prob.media_stimata={tot_prob/tot_n:.2%}  accuratezza_reale={tot_hit/tot_n:.2%}  scarto={(tot_hit/tot_n)-(tot_prob/tot_n):+.2%}")

    print()
    print("Calibrazione per fascia di probabilita' stimata (tutti i mercati insieme):")
    buckets = collections.defaultdict(lambda: [0, 0])  # bucket -> [n, hit]
    for rows in per_mercato.values():
        for prob, hit in rows:
            b = bucket(prob)
            buckets[b][0] += 1
            if hit:
                buckets[b][1] += 1
    for b in ['0.50-0.54', '0.55-0.59', '0.60-0.64', '0.65-0.69', '0.70-0.74', '0.75+']:
        n, hit = buckets.get(b, [0, 0])
        if n == 0:
            continue
        print(f"  {b}: n={n:3d}  accuratezza_reale={hit/n:.2%}")

    if tot_n < 30:
        print()
        print("Nota: campione ancora piccolo (<30 pronostici valutati). Le stime di")
        print("scarto/calibrazione andranno rilette man mano che si accumulano piu'")
        print("partite concluse: usarle come indicazione di tendenza, non come")
        print("correzione statistica definitiva.")


if __name__ == '__main__':
    main()
