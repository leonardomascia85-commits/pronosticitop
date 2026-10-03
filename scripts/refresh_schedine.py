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

# Soglie ricalibrate su un pool che esclude doppia chance e Under 3.5 dal
# ruolo di mercato "migliore" (pick_best_market): senza il loro gonfiamento
# artificiale della probabilita', il grosso degli eventi sta nella fascia
# 0.52-0.62 invece che 0.55-0.90, quindi le vecchie soglie (fino a 0.70 per
# il livello piu' basso) non trovavano piu' abbastanza eventi eleggibili.
THRESHOLDS = {4: (0.60, 0.56), 5: (0.56, 0.53), 6: (0.53, 0.51), 7: (0.51, 0.50)}


def confidenza(prob):
    if prob >= 0.62: return 'ALTA'
    if prob >= 0.56: return 'MEDIA-ALTA'
    if prob >= 0.52: return 'MEDIA'
    return 'BASSA'


# Doppia chance e Under/Over 3.5 coprono piu' esiti possibili e quindi hanno
# quasi sempre la probabilita' stimata piu' alta, a prescindere dai dati
# specifici della partita: se li lasciamo competere sulla sola probabilita'
# finiscono per essere scelti in quasi tutte le partite, schiacciando Esito
# secco, Under/Over 2.5 e Gol/No Gol (che restano piu' informativi sulla
# partita, anche se numericamente un po' piu' bassi). Per questo li usiamo
# come pronostico "di riserva": solo se nessuno degli altri tre mercati
# raggiunge almeno il 50% di probabilita' (partita davvero equilibrata),
# torniamo al piu' probabile in assoluto.
MERCATI_RISERVA = ('DC', 'OU35')
SOGLIA_MERCATI_PRIMARI = 0.50

def pick_best_market(markets):
    primari = [m for m in markets if m[0] not in MERCATI_RISERVA and m[1]['probabilita'] >= SOGLIA_MERCATI_PRIMARI]
    if primari:
        return max(primari, key=lambda m: m[1]['probabilita'])
    return max(markets, key=lambda m: m[1]['probabilita'])


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


CORNER_LINE = 9.5  # linea fissa usata da pick_corner (vedi build_pool/aggiunta mercato corner)


def actual_esiti(punteggio, corner=None):
    if not punteggio:
        return None
    parts = punteggio.split('-')
    if len(parts) != 2:
        return None
    try:
        home, away = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    esiti = {
        '1X2': '1' if home > away else ('2' if home < away else 'X'),
        'OU25': 'over' if (home + away) > 2.5 else 'under',
        'OU35': 'over' if (home + away) > 3.5 else 'under',
        'GGNG': 'gol' if (home > 0 and away > 0) else 'nogol',
    }
    if corner:
        cparts = corner.split('-')
        if len(cparts) == 2:
            try:
                c_home, c_away = int(cparts[0]), int(cparts[1])
                esiti['CORNER'] = 'over' if (c_home + c_away) > CORNER_LINE else 'under'
            except ValueError:
                pass
    return esiti


MERCATO_ALIAS = {
    '1X2': '1X2', 'DC': 'DC', 'Doppia chance': 'DC',
    'OU25': 'OU25', 'Under/Over 2.5': 'OU25',
    'OU35': 'OU35', 'Under/Over 3.5': 'OU35',
    'GGNG': 'GGNG', 'Gol/No Gol': 'GGNG',
    'CORNER': 'CORNER',
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
    if mercato in ('OU25', 'OU35', 'CORNER'):
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
    """Ritorna (esito, punteggio). esito e' None se la partita non e' ancora
    finale, o se il mercato e' CORNER ma il conteggio corner reale non e'
    ancora stato raccolto (il punteggio gol da solo non basta a risolverlo)."""
    ris = lookup.get(ev['campionato'] + '||' + ev['partita'])
    if not ris or ris.get('stato') != 'finale':
        return None, None
    mercato, esito_pick = resolve_pick(ev)
    if not esito_pick:
        return None, None
    if mercato == 'CORNER' and not ris.get('corner'):
        return None, None  # finale ma corner non ancora raccolto: ritenta al prossimo giro
    actual = actual_esiti(ris.get('punteggio'), ris.get('corner'))
    if not actual:
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
            best = pick_best_market(markets)
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


# Leghe con il campo pick_corner (vedi 'Aggiunge mercato corner...'): solo
# queste alimentano il pool "solo corner", le altre non hanno il dato.
CORNER_LEAGUES = {
    'pronostici-serie-a.json': 'Serie A',
    'pronostici-premier-league.json': 'Premier League',
    'pronostici-la-liga.json': 'La Liga',
    'pronostici-bundesliga.json': 'Bundesliga',
    'pronostici-ligue-1.json': 'Ligue 1',
}

# Le 3 sezioni tematiche a mercato singolo: campo pick_* sorgente, codice
# mercato canonico, e il sottoinsieme di file campionato da cui pescare.
SEZIONI_TEMATICHE = {
    'solo_gol': ('pick_gg', 'GGNG', LEAGUES),
    'solo_under': ('pick_uo', 'OU25', LEAGUES),
    'solo_corner': ('pick_corner', 'CORNER', CORNER_LEAGUES),
}


def build_pool_single_market(pick_field, mercato_code, league_files):
    """Pool di una sezione tematica a mercato singolo: un solo evento per
    partita, preso sempre dallo stesso campo pick_* (nessuna scelta tra
    mercati diversi, a differenza di build_pool())."""
    pool = []
    for fn, name in league_files.items():
        path = os.path.join(DATA_DIR, fn)
        if not os.path.exists(path):
            continue
        d = json.load(open(path, encoding='utf-8'))
        for p in d.get('partite', []):
            if p.get('risultato', {}).get('stato') != 'non_iniziata':
                continue
            pick = p.get(pick_field)
            if not pick:
                continue
            try:
                kickoff = datetime.datetime.fromisoformat(p['data'])
            except Exception:
                continue
            if kickoff <= NOW:
                continue
            pool.append({
                'partita': f"{p['casa']} - {p['trasferta']}",
                'campionato': name,
                'data': p['data'],
                'mercato': mercato_code,
                'pronostico': pick['etichetta'],
                'esito_pick': pick['esito'],
                'probabilita_stimata': round(pick['probabilita'], 2),
                'quota_stimata': round(1 / pick['probabilita'], 2),
                'confidenza_dati': confidenza(pick['probabilita']),
                'motivazione': p['nota'],
                'esito': None,
                'risultato_reale': None,
            })
    pool.sort(key=lambda x: -x['probabilita_stimata'])
    return pool


def build_single_market_levels(pool, levels=(4, 5, 6, 7)):
    """pool: eventi di build_pool_single_market(), gia' ordinati per
    probabilita' decrescente (un solo evento per partita, nessun mercato di
    riserva a cui attingere). Quando il pool e' abbastanza grande da coprire
    tutti e 4 i livelli senza ripetizioni (>= 4+5+6+7=22 partite) li riempie
    con gruppi di partite completamente disgiunti, dalle piu' probabili (per
    il livello piu' basso) alle meno probabili; quando e' piccolo, riusa le
    stesse partite tra livelli solo se non bastano quelle ancora inedite. Il
    risultato e' sempre riordinato per rischio crescente, come
    build_nazionali_levels()."""
    if not pool:
        return []
    totale = sum(levels)
    grezze = []
    if len(pool) >= totale:
        cursore = 0
        for n in levels:
            grezze.append(pool[cursore:cursore + n])
            cursore += n
    else:
        usate = set()
        for n in levels:
            eventi = [e for e in pool if e['partita'] not in usate][:n]
            if len(eventi) < n:
                extra = [e for e in pool if e not in eventi][:n - len(eventi)]
                eventi = eventi + extra
            for e in eventi:
                usate.add(e['partita'])
            if eventi:
                grezze.append(eventi)
    grezze.sort(key=lambda eventi: -combo_prob(eventi))
    schedine = []
    for level, eventi in zip(levels, grezze):
        pc = combo_prob(eventi)
        schedine.append({
            'livello_rischio': level,
            'quota_combinata': round(1 / pc, 2),
            'probabilita_combinata': round(pc, 3),
            'eventi': eventi,
        })
    return schedine


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
        best = pick_best_market(markets)
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


def build_matches_nazionali():
    """Come build_pool_nazionali, ma tiene TUTTI e 5 i mercati di ogni partita
    (non solo il migliore): serve a build_nazionali_levels per costruire le
    schedine dei 4 livelli di rischio con mercati diversi quando una partita
    deve ricomparire in piu' livelli."""
    path = os.path.join(DATA_DIR, 'pronostici-nazionali.json')
    if not os.path.exists(path):
        return []
    d = json.load(open(path, encoding='utf-8'))
    matches = []
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
        markets.sort(key=lambda m: -m[1]['probabilita'])
        matches.append((p, markets))
    return matches


LIVELLI_NAZIONALI = (4, 5, 6, 7)  # basso, medio-basso, medio-alto, alto: eventi crescenti


def combo_prob(events):
    p = 1.0
    for e in events:
        p *= e['probabilita_stimata']
    return p


def _evento_nazionale(p, mkt_code, pick):
    return {
        'partita': f"{p['casa']} - {p['trasferta']}",
        'campionato': 'Nazionali',
        'girone': p.get('girone'),
        'data': p['data'],
        'mercato': mkt_code,
        'pronostico': pick['etichetta'],
        'esito_pick': pick['esito'],
        'probabilita_stimata': round(pick['probabilita'], 2),
        'quota_stimata': round(1 / pick['probabilita'], 2),
        'confidenza_dati': confidenza(pick['probabilita']),
        'motivazione': p['nota'],
        'esito': None,
        'risultato_reale': None,
    }


def build_nazionali_levels(matches):
    """matches: output di build_matches_nazionali() (partite con tutti e 5 i
    mercati, ordinati per probabilita' decrescente). Costruisce fino a 4
    schedine (livelli 4/5/6/7 = basso/medio-basso/medio-alto/alto, con un
    numero di eventi via via crescente).

    Per ogni partita, la prima volta che viene usata si sceglie con
    pick_best_market() (doppia chance e Under 3.5 restano di riserva, per
    non far dominare un solo mercato all'interno della stessa schedina); le
    volte successive, se la stessa partita deve ricomparire in un livello
    piu' alto perche' il pool e' piccolo, si passa al miglior mercato REALE
    tra quelli non ancora mostrati per quella partita (mai lo stesso). Ad
    ogni passo si sceglie comunque, tra le partite non ancora usate nel
    livello corrente, quella con l'offerta disponibile piu' alta: quando il
    pool e' ampio le partite mai usate vincono quasi sempre, quindi la
    diversificazione tra le quattro schedine emerge da sola; il riutilizzo
    di una partita scatta solo quando serve davvero.

    Alla fine le schedine costruite vengono riordinate per probabilita'
    combinata decrescente e rietichettate sui livelli 4/5/6/7, cosi' che il
    risultato finale sia sempre "crescente" in rischio dalla piu' sicura
    alla piu' rischiosa, indipendentemente da eventuali partite ripetute con
    un mercato via via meno prevedibile."""
    if not matches:
        return []
    stato = []
    for p, markets in matches:
        key = p['casa'] + ' - ' + p['trasferta']
        primo_codice, primo_pick = pick_best_market(markets)
        resto = [m for m in markets if m[0] != primo_codice]
        offerte = [(primo_codice, primo_pick)] + resto
        stato.append({'p': p, 'markets': offerte, 'idx': 0, 'key': key})

    grezze = []
    for n in (4, 5, 6, 7):
        eventi = []
        used_this_level = set()
        while len(eventi) < n:
            migliore = None
            for s in stato:
                if s['key'] in used_this_level or s['idx'] >= len(s['markets']):
                    continue
                mkt_code, pick = s['markets'][s['idx']]
                if migliore is None or pick['probabilita'] > migliore[1]['probabilita']:
                    migliore = (mkt_code, pick, s)
            if migliore is None:
                break  # nessuna offerta rimasta per nessuna partita
            mkt_code, pick, s = migliore
            eventi.append(_evento_nazionale(s['p'], mkt_code, pick))
            used_this_level.add(s['key'])
            s['idx'] += 1
        if eventi:
            grezze.append(eventi)

    # Riordina per rischio reale (probabilita' combinata decrescente) e
    # rietichetta sui livelli 4/5/6/7: garantisce che il risultato pubblicato
    # sia sempre crescente in rischio, anche nei rari casi limite in cui una
    # partita ripetuta con un mercato meno probabile in assoluto (ma comunque
    # alto per quella specifica partita) alterasse l'ordine "naturale".
    grezze.sort(key=lambda eventi: -combo_prob(eventi))
    schedine = []
    for level, eventi in zip(LIVELLI_NAZIONALI, grezze):
        pc = combo_prob(eventi)
        schedine.append({
            'livello_rischio': level,
            'quota_combinata': round(1 / pc, 2),
            'probabilita_combinata': round(pc, 3),
            'eventi': eventi,
        })
    return schedine


def pick_combo_nazionali(pool, n):
    """Pool delle Nazionali sempre piccolo (una sola finestra alla volta). Per il
    livello piu' basso prende i migliori n eventi (la combo piu' sicura); per i
    livelli successivi, se non deve necessariamente includere tutto il pool,
    prende invece gli ultimi n per evitare che gli stessi eventi piu' quotati
    finiscano in ogni schedina (altrimenti un solo risultato a sorpresa fa
    perdere tutte le schedine contemporaneamente)."""
    if len(pool) < n:
        return None
    if n >= len(pool) or n <= 4:
        return pool[:n]
    return pool[-n:]


def is_nazionali_schedina(sch):
    eventi = sch.get('eventi') or []
    return bool(eventi) and all(e.get('campionato') == 'Nazionali' for e in eventi)


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

    # Eventi gia' usati in schedine ATTIVE (non archiviate) esistenti prima di
    # questa esecuzione: build_pool()/build_pool_nazionali() includono tutte
    # le partite non_iniziata future, comprese quelle di una schedina attiva
    # rimasta invariata in questo giro (es. L4-3 non tocca nulla se nessuno
    # dei suoi eventi e' ancora finale). Senza escluderle, una NUOVA sostituta
    # (es. L4-4 al posto di L4-2 archiviata) può finire per riproporre gli
    # stessi identici eventi di una schedina gia' pubblicata (es. L4-3),
    # mostrando due schedine duplicate sul sito.
    eventi_attivi_club, eventi_attivi_naz = set(), set()
    for w in settimane.get('settimane', []):
        path = os.path.join(DATA_DIR, w['file'])
        if not os.path.exists(path):
            continue
        d = json.load(open(path, encoding='utf-8'))
        for sch in d.get('schedine', []):
            if sch.get('stato') == 'archiviata':
                continue
            target = eventi_attivi_naz if is_nazionali_schedina(sch) else eventi_attivi_club
            for e in sch.get('eventi', []):
                target.add(e['partita'])

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
                    pool_naz = [e for e in pool_naz if e['partita'] not in eventi_attivi_naz]
                combo = pick_combo_nazionali(pool_naz, n)
            else:
                if pool is None:
                    pool = build_pool()
                    pool = [e for e in pool if e['partita'] not in eventi_attivi_club]
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

    # Sezioni tematiche a mercato singolo (Solo Gol/No Gol, Solo Under/Over,
    # Solo Corner): file perpetui a parte, non elencati in settimane.json
    # (non sono un "turno" ma schede fisse della pagina schedine), con la
    # stessa logica archivia-e-sostituisci delle altre, una sezione alla
    # volta con il proprio pool a mercato singolo.
    SEZIONI_FILES = {
        'solo_gol': 'schedine-solo-gol.json',
        'solo_under': 'schedine-solo-under.json',
        'solo_corner': 'schedine-solo-corner.json',
    }
    for kind, fn in SEZIONI_FILES.items():
        path = os.path.join(DATA_DIR, fn)
        if not os.path.exists(path):
            continue
        data = json.load(open(path, encoding='utf-8'))
        file_changed = False
        pick_field, mercato_code, league_files = SEZIONI_TEMATICHE[kind]

        eventi_attivi = set()
        for sch in data.get('schedine', []):
            if sch.get('stato') != 'archiviata':
                for e in sch.get('eventi', []):
                    eventi_attivi.add(e['partita'])

        pool_sezione = None
        for sch in data.get('schedine', []):
            if sch.get('stato') == 'archiviata':
                continue
            outcomes = [event_outcome(ev, lookup) for ev in sch['eventi']]
            if any(esito is None for esito, _ in outcomes):
                continue

            for ev, (esito, punteggio) in zip(sch['eventi'], outcomes):
                ev['esito'] = esito
                ev['risultato_reale'] = punteggio
            sch['stato'] = 'archiviata'
            sch['esito_finale'] = 'vinta' if all(e == 'vinto' for e, _ in outcomes) else 'persa'
            sch['archiviata_il'] = NOW.isoformat()
            file_changed = True
            summary.append(f"{fn}: {sch['id']} archiviata ({sch['esito_finale']})")

            if pool_sezione is None:
                pool_sezione = build_pool_single_market(pick_field, mercato_code, league_files)
                pool_sezione = [e for e in pool_sezione if e['partita'] not in eventi_attivi]

            n = len(sch['eventi'])
            level = sch['livello_rischio']
            combo = pool_sezione[:n] if len(pool_sezione) >= n else None

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
                eventi_attivi |= used
                pool_sezione = [e for e in pool_sezione if e['partita'] not in used]
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
