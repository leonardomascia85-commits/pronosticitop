"""Archivia le schedine (sia quelle principali multi-campionato sia quelle della
sezione Nazionali) i cui eventi sono TUTTI terminati, registrando il risultato
reale di ciascun evento, e pubblica al loro posto una nuova schedina allo
stesso livello di rischio pescando dagli eventi non ancora iniziati
attualmente disponibili. Se in quel momento non ci sono abbastanza partite
future per un livello, la schedina viene comunque archiviata ma non sostituita
in questa esecuzione (verra' ritentata alla prossima).

Uso: python3 scripts/refresh_schedine.py dalla root del repo.
Dopo l'esecuzione: validare con python3 -m json.tool sui file segnalati come
modificati, poi commit + push.
"""
import json, datetime, os, random, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")

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

NOW = datetime.datetime.now(datetime.timezone.utc)

THRESHOLDS = {4: (0.70, 0.65), 5: (0.65, 0.60), 6: (0.58, 0.55), 7: (0.55, 0.52)}


def confidenza(prob):
    if prob >= 0.62: return 'ALTA'
    if prob >= 0.56: return 'MEDIA-ALTA'
    if prob >= 0.52: return 'MEDIA'
    return 'BASSA'


def load_results():
    lookup = {}
    for fn, name in LEAGUES.items():
        path = os.path.join(DATA_DIR, fn)
        if not os.path.exists(path):
            continue
        d = json.load(open(path, encoding='utf-8'))
        for p in d.get('partite', []):
            lookup[name + '||' + p['casa'] + ' - ' + p['trasferta']] = p.get('risultato', {})

    naz_path = os.path.join(DATA_DIR, 'pronostici-nazionali.json')
    if os.path.exists(naz_path):
        d = json.load(open(naz_path, encoding='utf-8'))
        for p in d.get('partite', []):
            lookup['Nazionali||' + p['casa'] + ' - ' + p['trasferta']] = p.get('risultato', {})
    return lookup


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


MERCATO_ALIAS = {
    '1X2': '1X2', 'DC': 'DC', 'Doppia chance': 'DC',
    'OU25': 'OU25', 'Under/Over 2.5': 'OU25',
    'OU35': 'OU35', 'Under/Over 3.5': 'OU35',
    'GGNG': 'GGNG', 'Gol/No Gol': 'GGNG',
}


def resolve_pick(ev):
    """Ritorna (mercato_canonico, esito_pick), derivandoli dal testo del
    pronostico per gli eventi di schema piu' vecchio che non hanno gia' un
    campo 'esito_pick' esplicito."""
    mercato = MERCATO_ALIAS.get(ev.get('mercato'), ev.get('mercato'))
    if ev.get('esito_pick'):
        return mercato, ev['esito_pick']
    testo = (ev.get('pronostico') or '').strip()
    if mercato in ('1X2', 'DC'):
        token = testo.split(' ', 1)[0].split('(', 1)[0].strip()
        return mercato, token or None
    if mercato == 'OU25' or mercato == 'OU35':
        low = testo.lower()
        if low.startswith('over'): return mercato, 'over'
        if low.startswith('under'): return mercato, 'under'
        return mercato, None
    if mercato == 'GGNG':
        low = testo.lower()
        if low.startswith('gg'): return mercato, 'gol'
        if low.startswith('ng'): return mercato, 'nogol'
        return mercato, None
    return mercato, None


def event_outcome(ev, lookup):
    """Ritorna (esito, punteggio). esito e' None se la partita non e' ancora finale."""
    ris = lookup.get(ev['campionato'] + '||' + ev['partita'])
    if not ris or ris.get('stato') != 'finale':
        return None, None
    actual = actual_esiti(ris.get('punteggio'))
    if not actual:
        return None, None
    mercato, esito_pick = resolve_pick(ev)
    if not esito_pick:
        return None, None
    if mercato == 'DC':
        won = actual['1X2'] in esito_pick
    else:
        won = actual.get(mercato) == esito_pick
    return ('vinto' if won else 'perso'), ris.get('punteggio')


def build_pool():
    pool = []
    for fn, name in LEAGUES.items():
        path = os.path.join(DATA_DIR, fn)
        if not os.path.exists(path):
            continue
        d = json.load(open(path, encoding='utf-8'))
        for p in d.get('partite', []):
            if p.get('risultato', {}).get('stato') != 'non_iniziata':
                continue
            try:
                kickoff = datetime.datetime.fromisoformat(p['data'])
            except Exception:
                continue
            if kickoff <= NOW:
                continue
            markets = []
            if p.get('pick_1x2'): markets.append(('1X2', p['pick_1x2']))
            if p.get('pick_dc'): markets.append(('DC', p['pick_dc']))
            if p.get('pick_uo'): markets.append(('OU25', p['pick_uo']))
            if p.get('pick_uo35'): markets.append(('OU35', p['pick_uo35']))
            if p.get('pick_gg'): markets.append(('GGNG', p['pick_gg']))
            if not markets:
                continue
            best = max(markets, key=lambda m: m[1]['probabilita'])
            pool.append({
                'partita': f"{p['casa']} - {p['trasferta']}",
                'campionato': name,
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
    return pool


def build_pool_nazionali():
    path = os.path.join(DATA_DIR, 'pronostici-nazionali.json')
    if not os.path.exists(path):
        return []
    d = json.load(open(path, encoding='utf-8'))
    pool = []
    for p in d.get('partite', []):
        if p.get('risultato', {}).get('stato') != 'non_iniziata':
            continue
        try:
            kickoff = datetime.datetime.fromisoformat(p['data'])
        except Exception:
            continue
        if kickoff <= NOW:
            continue
        markets = []
        if p.get('pick_1x2'): markets.append(('1X2', p['pick_1x2']))
        if p.get('pick_dc'): markets.append(('DC', p['pick_dc']))
        if p.get('pick_uo'): markets.append(('OU25', p['pick_uo']))
        if p.get('pick_uo35'): markets.append(('OU35', p['pick_uo35']))
        if p.get('pick_gg'): markets.append(('GGNG', p['pick_gg']))
        if not markets:
            continue
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
    return pool


def pick_combo_nazionali(pool, n):
    """Pool delle Nazionali sempre piccolo (una sola finestra alla volta):
    prende semplicemente i migliori n eventi per probabilita' stimata."""
    if len(pool) < n:
        return None
    return pool[:n]


def is_nazionali_schedina(sch):
    eventi = sch.get('eventi') or []
    return bool(eventi) and all(e.get('campionato') == 'Nazionali' for e in eventi)


def combo_prob(events):
    p = 1.0
    for e in events:
        p *= e['probabilita_stimata']
    return p


def pick_combo(pool, n, level):
    elig_threshold, min_threshold = THRESHOLDS.get(level, (0.55, 0.50))
    threshold = elig_threshold
    candidates = []
    while True:
        candidates = [e for e in pool if e['probabilita_stimata'] >= threshold]
        if len(candidates) >= n or threshold <= min_threshold:
            break
        threshold = round(max(min_threshold, threshold - 0.03), 2)
    if len(candidates) < n:
        return None

    by_league = collections.defaultdict(list)
    for e in candidates:
        by_league[e['campionato']].append(e)
    leagues_cycle = list(by_league.keys())
    random.shuffle(leagues_cycle)
    chosen, chosen_matches = [], set()
    li, attempts = 0, 0
    while len(chosen) < n and attempts < 300:
        attempts += 1
        lg = leagues_cycle[li % len(leagues_cycle)]
        li += 1
        opts = [e for e in by_league[lg] if e['partita'] not in chosen_matches]
        if opts:
            pick = random.choice(opts)
            chosen.append(pick)
            chosen_matches.add(pick['partita'])
    if len(chosen) < n:
        remaining = [e for e in candidates if e['partita'] not in chosen_matches]
        random.shuffle(remaining)
        chosen += remaining[:n - len(chosen)]
    return chosen if len(chosen) == n else None


def next_id(existing_ids, level):
    prefix = f"L{level}-"
    nums = [int(i[len(prefix):]) for i in existing_ids
            if i.startswith(prefix) and i[len(prefix):].isdigit()]
    return f"{prefix}{(max(nums) + 1) if nums else 1}"


def main():
    settimane_path = os.path.join(DATA_DIR, 'settimane.json')
    settimane = json.load(open(settimane_path, encoding='utf-8'))
    lookup = load_results()
    pool = None
    pool_naz = None
    changed_files = []
    summary = []

    for w in settimane.get('settimane', []):
        fn = w['file']
        path = os.path.join(DATA_DIR, fn)
        if not os.path.exists(path):
            continue
        data = json.load(open(path, encoding='utf-8'))
        file_changed = False

        for sch in data.get('schedine', []):
            if sch.get('stato') == 'archiviata':
                continue
            outcomes = [event_outcome(ev, lookup) for ev in sch['eventi']]
            if any(esito is None for esito, _ in outcomes):
                continue  # almeno una partita non ancora conclusa

            for ev, (esito, punteggio) in zip(sch['eventi'], outcomes):
                ev['esito'] = esito
                ev['risultato_reale'] = punteggio
            sch['stato'] = 'archiviata'
            sch['esito_finale'] = 'vinta' if all(e == 'vinto' for e, _ in outcomes) else 'persa'
            sch['archiviata_il'] = NOW.isoformat()
            file_changed = True
            summary.append(f"{fn}: {sch['id']} archiviata ({sch['esito_finale']})")

            n = len(sch['eventi'])
            level = sch['livello_rischio']
            nazionale = is_nazionali_schedina(sch)
            if nazionale:
                if pool_naz is None:
                    pool_naz = build_pool_nazionali()
                combo = pick_combo_nazionali(pool_naz, n)
            else:
                if pool is None:
                    pool = build_pool()
                combo = pick_combo(pool, n, level)

            if combo:
                pc = combo_prob(combo)
                new_id = next_id([s['id'] for s in data['schedine']], level)
                data['schedine'].append({
                    'id': new_id,
                    'livello_rischio': level,
                    'quota_combinata': round(1 / pc, 2),
                    'probabilita_combinata': round(pc, 3),
                    'stato': 'pubblicata',
                    'eventi': combo,
                })
                used = {e['partita'] for e in combo}
                if nazionale:
                    pool_naz = [e for e in pool_naz if e['partita'] not in used]
                else:
                    pool = [e for e in pool if e['partita'] not in used]
                summary.append(f"{fn}: nuova schedina {new_id} pubblicata ({n} eventi, prob {pc:.3f})")
            else:
                summary.append(f"{fn}: nessuna sostituta pubblicata per livello {level} "
                                f"(eventi futuri disponibili insufficienti)")

        if file_changed:
            data['aggiornato_il'] = NOW.date().isoformat()
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            changed_files.append(fn)

    print('\n'.join(summary) if summary else 'Nessuna schedina da archiviare in questo momento.')
    print('File modificati:', changed_files)


if __name__ == '__main__':
    main()
