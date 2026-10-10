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
import json, datetime, os, random, collections, math

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
    'pronostici-super-lig.json': 'Süper Lig',
    'pronostici-brasileirao.json': 'Brasileirão',
}

# La pagina schedine (multi-campionato) non deve mai includere la Serie C
# (troppo imprevedibile) e deve restare sempre dentro un singolo weekend:
# questo e' il pool usato SOLO da build_pool() per quella pagina. load_results()
# e le sezioni tematiche (solo_gol/solo_under) restano sul dizionario LEAGUES
# completo sopra, che include ancora la Serie C.
LEAGUES_SCHEDINE_PRINCIPALI = {
    'pronostici-serie-a.json': 'Serie A',
    'pronostici-serie-b.json': 'Serie B',
    'pronostici-premier-league.json': 'Premier League',
    'pronostici-la-liga.json': 'La Liga',
    'pronostici-bundesliga.json': 'Bundesliga',
    'pronostici-ligue-1.json': 'Ligue 1',
    'pronostici-liga-portugal.json': 'Liga Portugal',
    'pronostici-eredivisie.json': 'Eredivisie',
    'pronostici-super-lig.json': 'Süper Lig',
    'pronostici-brasileirao.json': 'Brasileirão',
}

NOW = datetime.datetime.now(datetime.timezone.utc)

# Soglie ricalibrate su un pool che esclude doppia chance e Under 3.5 dal
# ruolo di mercato "migliore" (pick_best_market): senza il loro gonfiamento
# artificiale della probabilita', il grosso degli eventi sta nella fascia
# 0.52-0.62 invece che 0.55-0.90, quindi le vecchie soglie (fino a 0.70 per
# il livello piu' basso) non trovavano piu' abbastanza eventi eleggibili.
THRESHOLDS = {4: (0.60, 0.56), 5: (0.56, 0.53), 6: (0.53, 0.51), 7: (0.51, 0.50)}

# Una schedina deve restare dentro un unico turno/weekend: partite che cadono
# a piu' di SAME_ROUND_WINDOW_DAYS l'una dall'altra (es. una rinviata di
# settimane per la sosta nazionali, o il turno successivo di un'altra lega)
# non vanno mai combinate nella stessa schedina. 4 giorni copre un turno
# tipico (gio/ven-lun) senza poter scavalcare nel weekend successivo.
SAME_ROUND_WINDOW_DAYS = 4


def _filter_same_round(items, get_date):
    """Tiene solo gli elementi entro SAME_ROUND_WINDOW_DAYS dal piu' vicino nel
    tempo, cosi' una partita rinviata di settimane non resta mescolata nello
    stesso pool di partite del turno in corso. get_date(item) -> datetime."""
    if len(items) <= 1:
        return items
    earliest = min(get_date(i) for i in items)
    return [i for i in items if (get_date(i) - earliest).days <= SAME_ROUND_WINDOW_DAYS]


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
        'GOALS': (home, away),
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
    'SEGNA': 'SEGNA',
    'MULTIGOL': 'MULTIGOL',
    'PT': 'PT',
    'AMM': 'AMM',
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


def _somma_coppia(txt):
    if not txt:
        return None
    parts = str(txt).split('-')
    if len(parts) != 2:
        return None
    try:
        return int(parts[0]) + int(parts[1])
    except ValueError:
        return None


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
    elif mercato == 'SEGNA':
        home, away = actual['GOALS']
        won = (home > 0) if esito_pick == 'casa' else (away > 0)
    elif mercato == 'MULTIGOL':
        lo, hi = (int(x) for x in esito_pick.split('-'))
        won = lo <= sum(actual['GOALS']) <= hi
    elif mercato == 'PT':
        tot = _somma_coppia(ris.get('primo_tempo'))
        if tot is None:
            return None, None  # finale ma risultato del primo tempo non ancora raccolto
        won = (tot >= 1) if esito_pick == 'over05' else (tot <= 1)
    elif mercato == 'AMM':
        tot = _somma_coppia(ris.get('ammonizioni'))
        if tot is None:
            return None, None  # finale ma ammonizioni non ancora raccolte
        won = (tot > CARTELLINI_LINE) if esito_pick == 'over' else (tot < CARTELLINI_LINE)
    else:
        won = actual.get(mercato) == esito_pick
    return ('vinto' if won else 'perso'), ris.get('punteggio')


def build_pool():
    pool = []
    for fn, name in LEAGUES_SCHEDINE_PRINCIPALI.items():
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
            if kickoff.weekday() not in (4, 5, 6, 0):  # solo ven-sab-dom-lun (weekend): mai partite infrasettimanali
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


# --- Pagina Schedine (multi-campionato): quattro fasce di rischio per ogni
# livello di eventi, ognuna con una quota massima fissata dall'utente.
# Per 4 eventi: quota massima 3 (rischio basso), 5 (medio), 7 (medio-alto) e
# 9 (alto); per 5 eventi 4/6/8/10; con lo stesso passo proporzionale 5/7/9/11
# per 6 eventi e 6/8/10/12 per 7 eventi. Ogni schedina deve cadere nella
# propria fascia, cioe' tra la quota massima della fascia precedente e la
# propria, cosi' le quattro schedine di un livello hanno rischi davvero diversi.
QUOTE_MAX_FASCE = {4: (3, 5, 7, 9), 5: (4, 6, 8, 10), 6: (5, 7, 9, 11), 7: (6, 8, 10, 12)}
RISCHIO_FASCE = ('Rischio basso', 'Rischio medio', 'Rischio medio-alto', 'Rischio alto')
MERCATI_PICK = (('1X2', 'pick_1x2'), ('DC', 'pick_dc'), ('OU25', 'pick_uo'),
                ('OU35', 'pick_uo35'), ('GGNG', 'pick_gg'))


def build_pool_tutti_mercati():
    """Come build_pool() (stessi campionati, solo weekend, solo partite future)
    ma con TUTTI i mercati di ogni partita con probabilita' almeno del 50%:
    servono per costruire schedine dentro una fascia di quota precisa."""
    partite = []
    for fn, name in LEAGUES_SCHEDINE_PRINCIPALI.items():
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
            if kickoff <= NOW or kickoff.weekday() not in (4, 5, 6, 0):
                continue
            eventi = []
            for code, field in MERCATI_PICK:
                pick = p.get(field)
                if not pick or pick['probabilita'] < 0.5:
                    continue
                eventi.append({
                    'partita': f"{p['casa']} - {p['trasferta']}",
                    'campionato': name,
                    'data': p['data'],
                    'mercato': code,
                    'pronostico': pick['etichetta'],
                    'esito_pick': pick['esito'],
                    'probabilita_stimata': round(pick['probabilita'], 2),
                    'quota_stimata': round(1 / pick['probabilita'], 2),
                    'confidenza_dati': confidenza(pick['probabilita']),
                    'motivazione': p['nota'],
                    'esito': None,
                    'risultato_reale': None,
                })
            if eventi:
                partite.append(eventi)
    partite = _filter_same_round(partite, lambda m: datetime.datetime.fromisoformat(m[0]['data']))
    return partite


def fascia_da_quota(level, quota):
    for i, qmax in enumerate(QUOTE_MAX_FASCE[level]):
        if quota <= qmax:
            return i + 1
    return len(QUOTE_MAX_FASCE[level])


def build_schedina_fascia(partite, level, fascia, gia_usate_livello=(), gia_usate=(), seed=0, tentativi=12000):
    """Ricerca casuale (riproducibile) della combinazione di `level` partite
    diverse, un mercato per partita, con quota combinata nella fascia
    (quota massima fascia precedente, quota massima fascia]. Tra le valide
    preferisce: meno partite in comune con le altre schedine dello stesso
    livello, piu' mercati "primari" (esito, Under/Over 2.5, Gol/No Gol),
    meno partite in comune con il resto della pagina, quota piu' vicina al
    tetto. Restituisce None se nessuna combinazione rientra nella fascia."""
    import random
    caps = QUOTE_MAX_FASCE[level]
    hi = caps[fascia - 1]
    lo = caps[fascia - 2] if fascia > 1 else 1.0
    if len(partite) < level:
        return None
    rng = random.Random(f"{seed}-{level}-{fascia}")
    # per le fasce basse servono partite con almeno un mercato molto
    # probabile: meta' dei tentativi pesca solo tra le partite migliori
    migliori = sorted(partite, key=lambda m: -max(e['probabilita_stimata'] for e in m))[:2 * level + 6]
    best, best_key = None, None
    for t in range(tentativi):
        base = migliori if (t % 2 and len(migliori) >= level) else partite
        scelta = rng.sample(base, level)
        mercati = [sorted(m, key=lambda e: -e['probabilita_stimata']) for m in scelta]
        idx = [rng.randrange(len(m)) for m in mercati]
        # riparazione: sposta un evento alla volta su un mercato piu' (o meno)
        # probabile della stessa partita finche' la quota entra nella fascia
        for _ in range(3 * level):
            q = 1 / combo_prob([m[i] for m, i in zip(mercati, idx)])
            if q > hi:
                mobili = [k for k, i in enumerate(idx) if i > 0]
                if not mobili:
                    break
                k = rng.choice(mobili); idx[k] -= 1
            elif q <= lo:
                mobili = [k for k, i in enumerate(idx) if i < len(mercati[k]) - 1]
                if not mobili:
                    break
                k = rng.choice(mobili); idx[k] += 1
            else:
                break
        eventi = [m[i] for m, i in zip(mercati, idx)]
        dates = [datetime.datetime.fromisoformat(e['data']) for e in eventi]
        if (max(dates) - min(dates)).days > SAME_ROUND_WINDOW_DAYS:
            continue
        q = 1 / combo_prob(eventi)
        if not (lo < q <= hi):
            continue
        nomi = {e['partita'] for e in eventi}
        key = (-len(nomi & set(gia_usate_livello)),
               sum(e['mercato'] not in MERCATI_RISERVA for e in eventi),
               -len(nomi & set(gia_usate)),
               q)
        if best_key is None or key > best_key:
            best, best_key = eventi, key
    if not best:
        return None
    best = sorted(best, key=lambda e: e['data'])
    pc = combo_prob(best)
    return {
        'livello_rischio': level,
        'fascia': fascia,
        'rischio': RISCHIO_FASCE[fascia - 1],
        'quota_max': hi,
        'quota_combinata': round(1 / pc, 2),
        'probabilita_combinata': round(pc, 3),
        'stato': 'pubblicata',
        'eventi': best,
    }


def riempi_fasce(schedine, partite=None, seed=0):
    """Aggiunge a `schedine` (lista del turno, modificata sul posto) le
    schedine mancanti: per ogni livello 4-7 deve esserci una schedina attiva
    per ciascuna delle 4 fasce. Le schedine attive senza campo 'fascia'
    (create prima di questo schema) occupano la fascia corrispondente alla
    loro quota finche' non si concludono. Restituisce gli id aggiunti."""
    if partite is None:
        partite = build_pool_tutti_mercati()
    aggiunte = []
    for level in sorted(QUOTE_MAX_FASCE):
        attive = [x for x in schedine if x.get('stato') != 'archiviata' and x['livello_rischio'] == level]
        occupate = {x.get('fascia') or fascia_da_quota(level, x['quota_combinata']) for x in attive}
        for fascia in range(1, len(QUOTE_MAX_FASCE[level]) + 1):
            if fascia in occupate:
                continue
            usate_livello = {e['partita'] for x in schedine if x.get('stato') != 'archiviata'
                             and x['livello_rischio'] == level for e in x['eventi']}
            usate = {e['partita'] for x in schedine if x.get('stato') != 'archiviata' for e in x['eventi']}
            nuova = build_schedina_fascia(partite, level, fascia, usate_livello, usate, seed=seed)
            if not nuova:
                continue
            nuova = {'id': next_id([x['id'] for x in schedine], level), **nuova}
            schedine.append(nuova)
            aggiunte.append(nuova['id'])
    return aggiunte


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
    'solo_segna': ('derived_segna', 'SEGNA', LEAGUES),
    'solo_multigol': ('derived_multigol', 'MULTIGOL', LEAGUES),
    'solo_primotempo': ('derived_primotempo', 'PT', LEAGUES),
    'solo_ammonizioni': ('derived_ammonizioni', 'AMM', CORNER_LEAGUES),
}


# --- Mercati derivati (nessun dato aggiuntivo): "Squadra X segna" e "Multigol".
# Si ricavano dalle stesse probabilita' gia' pubblicate (1X2, doppia chance,
# Under/Over 2.5 e 3.5, Gol/No Gol) stimando i gol attesi delle due squadre con
# una Poisson indipendente: vengono scelti i due valori che meglio riproducono
# le probabilita' dei pick esistenti, da cui si calcolano i nuovi mercati.
def _pmf(lam, n=12):
    out, term = [], math.exp(-lam)
    for k in range(n):
        out.append(term)
        term *= lam / (k + 1)
    return out


def _model_probs(lh, la):
    ph, pa = _pmf(lh), _pmf(la)
    p1 = px = p2 = o25 = o35 = gg = 0.0
    for i, a in enumerate(ph):
        for j, b in enumerate(pa):
            q = a * b
            if i > j: p1 += q
            elif i == j: px += q
            else: p2 += q
            if i + j > 2: o25 += q
            if i + j > 3: o35 += q
            if i > 0 and j > 0: gg += q
    return {'1': p1, 'X': px, '2': p2, '1X': p1 + px, 'X2': px + p2, '12': p1 + p2,
            'o25': o25, 'o35': o35, 'gg': gg}


def _targets(p):
    t = []
    if p.get('pick_1x2'): t.append((p['pick_1x2']['esito'], p['pick_1x2']['probabilita']))
    if p.get('pick_dc'): t.append((p['pick_dc']['esito'], p['pick_dc']['probabilita']))
    if p.get('pick_uo'): t.append(('o25' if p['pick_uo']['esito'] == 'over' else 'u25', p['pick_uo']['probabilita']))
    if p.get('pick_uo35'): t.append(('o35' if p['pick_uo35']['esito'] == 'over' else 'u35', p['pick_uo35']['probabilita']))
    if p.get('pick_gg'): t.append(('gg' if p_gg_is_gol(p) else 'ng', p['pick_gg']['probabilita']))
    return t


def p_gg_is_gol(p):
    return p['pick_gg']['esito'] == 'gol'


def fit_lambdas(p):
    t = _targets(p)
    if len(t) < 3:
        return None

    def loss(lh, la):
        m = _model_probs(lh, la)
        m.update({'u25': 1 - m['o25'], 'u35': 1 - m['o35'], 'ng': 1 - m['gg']})
        return sum((m[k] - v) ** 2 for k, v in t)

    lh, la, step = 1.4, 1.1, 0.5
    best = loss(lh, la)
    while step > 0.01:
        moved = False
        for dh, da in ((step, 0), (-step, 0), (0, step), (0, -step)):
            nh, na = min(4.0, max(0.15, lh + dh)), min(4.0, max(0.15, la + da))
            v = loss(nh, na)
            if v < best - 1e-12:
                lh, la, best, moved = nh, na, v, True
        if not moved:
            step /= 2
    return lh, la


# Primo tempo: quota di gol attesi nel primo tempo rispetto al totale della
# partita (valore tipico dei campionati europei, circa il 45%); da ricalibrare
# con i risultati del primo tempo che raccogliamo a fine partita.
PT_FRACTION = 0.45
# Ammonizioni: linea fissa sul totale dei cartellini gialli della partita.
CARTELLINI_LINE = 4.5
CARTELLINI_PRIOR_GAMES = 6   # peso (in partite) della media di campionato
CARTELLINI_MAX_AGE_DAYS = 21  # oltre questa eta' i dati squadra non si usano
CARTELLINI_DISPERSION = 1.4   # varianza/media dei cartellini (arbitro, partita)
_STATS_FILE_LEAGUE = {
    'pronostici-serie-a.json': 'serie-a', 'pronostici-premier-league.json': 'premier-league',
    'pronostici-la-liga.json': 'la-liga', 'pronostici-bundesliga.json': 'bundesliga',
    'pronostici-ligue-1.json': 'ligue-1',
}
_cards_cache = {}


def _load_cards_stats():
    if 'v' not in _cards_cache:
        v = None
        path = os.path.join(DATA_DIR, 'stats-cartellini.json')
        if os.path.exists(path):
            d = json.load(open(path, encoding='utf-8'))
            try:
                age = (NOW.date() - datetime.date.fromisoformat(d['aggiornato'])).days
            except Exception:
                age = 10 ** 6
            if age <= CARTELLINI_MAX_AGE_DAYS:
                v = d
        _cards_cache['v'] = v
    return _cards_cache['v']


def _nb_pmf(mean, n=25):
    p = 1.0 / CARTELLINI_DISPERSION
    r = mean * p / (1 - p)
    return [math.exp(math.lgamma(k + r) - math.lgamma(r) - math.lgamma(k + 1) + r * math.log(p) + k * math.log(1 - p))
            for k in range(n)]


def _derive_cartellini(p, fn):
    stats = _load_cards_stats()
    lg = _STATS_FILE_LEAGUE.get(fn)
    if not stats or not lg:
        return None
    teams = stats['leghe'].get(lg, {})
    h, a = teams.get(p['casa']), teams.get(p['trasferta'])
    if not h or not a:
        return None
    mean_y = sum(t['yf'] for t in teams.values()) / len(teams)

    def sh(t, k):
        return (t[k] * t['tg'] + mean_y * CARTELLINI_PRIOR_GAMES) / (t['tg'] + CARTELLINI_PRIOR_GAMES)

    total = (sh(h, 'yf') + sh(a, 'ya')) / 2 + (sh(a, 'yf') + sh(h, 'ya')) / 2
    pmf = _nb_pmf(total)
    p_under = sum(pmf[:int(CARTELLINI_LINE) + 1])
    if p_under >= 0.5:
        return {'esito': 'under', 'etichetta': f'Under {CARTELLINI_LINE} ammonizioni', 'probabilita': p_under}
    return {'esito': 'over', 'etichetta': f'Over {CARTELLINI_LINE} ammonizioni', 'probabilita': 1 - p_under}


def derive_pick(p, kind, fn=None):
    if kind == 'derived_ammonizioni':
        return _derive_cartellini(p, fn)
    lam = fit_lambdas(p)
    if not lam:
        return None
    lh, la = lam
    if kind == 'derived_primotempo':
        m = PT_FRACTION * (lh + la)
        p_over = 1 - math.exp(-m)
        p_under15 = math.exp(-m) * (1 + m)
        if p_over >= p_under15:
            return {'esito': 'over05', 'etichetta': 'Almeno un gol nel primo tempo', 'probabilita': p_over}
        return {'esito': 'under15', 'etichetta': 'Al massimo un gol nel primo tempo', 'probabilita': p_under15}
    if kind == 'derived_segna':
        ph, pa = 1 - math.exp(-lh), 1 - math.exp(-la)
        if ph >= pa:
            return {'esito': 'casa', 'etichetta': f"Segna la squadra di casa ({p['casa']})", 'probabilita': ph}
        return {'esito': 'trasferta', 'etichetta': f"Segna la squadra ospite ({p['trasferta']})", 'probabilita': pa}
    if kind == 'derived_multigol':
        tot = _pmf(lh + la, 14)
        opts = [('1-3', sum(tot[1:4])), ('2-4', sum(tot[2:5]))]
        esito, prob = max(opts, key=lambda o: o[1])
        return {'esito': esito, 'etichetta': f'Multigol {esito}', 'probabilita': prob}
    return None


def build_pool_single_market(pick_field, mercato_code, league_files, weekend_only=False):
    """Pool di una sezione tematica a mercato singolo: un solo evento per
    partita, preso sempre dallo stesso campo pick_* (nessuna scelta tra
    mercati diversi, a differenza di build_pool()). weekend_only=True (usato
    da solo_gol/solo_under) esclude le partite infrasettimanali, come per la
    pagina schedine principale; solo_corner resta senza questo vincolo."""
    pool = []
    for fn, name in league_files.items():
        path = os.path.join(DATA_DIR, fn)
        if not os.path.exists(path):
            continue
        d = json.load(open(path, encoding='utf-8'))
        for p in d.get('partite', []):
            if p.get('risultato', {}).get('stato') != 'non_iniziata':
                continue
            pick = derive_pick(p, pick_field, fn) if pick_field.startswith('derived_') else p.get(pick_field)
            if not pick:
                continue
            try:
                kickoff = datetime.datetime.fromisoformat(p['data'])
            except Exception:
                continue
            if kickoff <= NOW:
                continue
            if weekend_only and kickoff.weekday() not in (4, 5, 6, 0):  # ven-sab-dom-lun
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
                'confidenza_dati': 'MEDIA' if mercato_code in ('PT', 'AMM') else confidenza(pick['probabilita']),
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
    pool = _filter_same_round(pool, lambda e: datetime.datetime.fromisoformat(e['data']))
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


# --- Sezioni con due varianti per livello (richiesta dell'utente): per Solo
# Gol/No Gol, Solo Under/Over e Solo Corner ogni livello (4, 5, 6 e 7 eventi)
# ha DUE schedine attive:
#   - 'quota_max': la combinazione piu' probabile possibile, con l'obiettivo di
#     restare entro una quota combinata pari al numero di eventi (4 eventi ->
#     quota massima 4, 5 -> 5, 6 -> 6, 7 -> 7). Se nemmeno gli eventi piu'
#     probabili del turno bastano a restare sotto il tetto, si pubblica
#     comunque la combinazione con la quota piu' bassa possibile e lo si
#     segnala con quota_rispettata=False: le probabilita' non vengono mai
#     gonfiate per rientrare nel tetto.
#   - 'libera': scelta del modello con rischio medio (basso-medio per il
#     livello da 4), costruita con i migliori eventi non gia' usati dalle
#     altre schedine attive della sezione, cosi' le due varianti dello stesso
#     livello non si sovrappongono.
SEZIONI_VARIANTI = ('solo_gol', 'solo_under', 'solo_corner', 'solo_segna',
                    'solo_multigol', 'solo_primotempo', 'solo_ammonizioni')
LIVELLI_VARIANTI = (4, 5, 6, 7)


def _schedina_variante(eventi, level, variante):
    pc = combo_prob(eventi)
    quota = round(1 / pc, 2)
    sch = {
        'livello_rischio': level,
        'variante': variante,
        'quota_combinata': quota,
        'probabilita_combinata': round(pc, 3),
        'stato': 'pubblicata',
        'eventi': eventi,
    }
    if variante == 'quota_max':
        sch['quota_max'] = level
        sch['quota_rispettata'] = quota <= level
    return sch


def build_variante(pool, level, variante, escludi=()):
    """pool ordinato per probabilita' decrescente. 'quota_max' prende sempre i
    migliori n eventi del turno (l'unico modo di avvicinarsi al tetto di
    quota); 'libera' prende i migliori n eventi esclusi quelli della
    'quota_max' dello stesso livello (escludi), cosi' resta a rischio medio
    senza duplicare l'altra schedina del livello."""
    candidati = pool if variante == 'quota_max' else [e for e in pool if e['partita'] not in escludi]
    if len(candidati) < level:
        return None
    return _schedina_variante(list(candidati[:level]), level, variante)


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
    matches = _filter_same_round(matches, lambda m: datetime.datetime.fromisoformat(m[0]['data']))
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

    for _attempt in range(30):
        by_league = collections.defaultdict(list)
        for e in candidates:
            by_league[e['campionato']].append(e)
        leagues_cycle = list(by_league.keys())
        random.shuffle(leagues_cycle)
        chosen, chosen_matches = [], set()
        li, attempts = 0, 0
        # Per le schedine piu' "popolari" (4/5 eventi) puntiamo a vincerle
        # davvero: scegliamo sempre l'evento a probabilita' piu' alta
        # disponibile in ogni lega, non uno a caso. Per i livelli piu'
        # rischiosi (6/7 eventi) manteniamo la scelta casuale, che da' piu'
        # varieta' alle schedine via via meno "da vincere a tutti i costi".
        greedy = n <= 5
        while len(chosen) < n and attempts < 300:
            attempts += 1
            lg = leagues_cycle[li % len(leagues_cycle)]
            li += 1
            opts = [e for e in by_league[lg] if e['partita'] not in chosen_matches]
            if opts:
                pick = max(opts, key=lambda e: e['probabilita_stimata']) if greedy else random.choice(opts)
                chosen.append(pick)
                chosen_matches.add(pick['partita'])
        if len(chosen) < n:
            remaining = [e for e in candidates if e['partita'] not in chosen_matches]
            if greedy:
                remaining.sort(key=lambda e: -e['probabilita_stimata'])
            else:
                random.shuffle(remaining)
            chosen += remaining[:n - len(chosen)]
        if len(chosen) != n:
            continue
        dates = [datetime.datetime.fromisoformat(e['data']) for e in chosen]
        if (max(dates) - min(dates)).days <= SAME_ROUND_WINDOW_DAYS:
            return chosen
    return None


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

    # Il turno multi-campionato piu' recente (il primo in settimane.json che
    # non sia delle Nazionali): e' l'unico in cui riempi_fasce() pubblica le
    # schedine mancanti.
    turno_club_corrente = next((w['file'] for w in settimane.get('settimane', [])
                                if not w['file'].startswith('nazionali')), None)

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
            # una schedina con almeno un evento perso e' gia' persa: si archivia
            # subito e si sostituisce, senza aspettare le partite rimaste
            if any(esito is None for esito, _ in outcomes) and not any(esito == 'perso' for esito, _ in outcomes):
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
                # la sostituta viene creata da riempi_fasce() qui sotto, nella
                # fascia di quota rimasta libera
                continue

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

        if fn == turno_club_corrente:
            aggiunte = riempi_fasce(data['schedine'], seed=NOW.date().isoformat())
            if aggiunte:
                file_changed = True
                summary.append(f"{fn}: nuove schedine a fasce di quota pubblicate: {', '.join(aggiunte)}")

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
        'solo_segna': 'schedine-solo-segna.json',
        'solo_multigol': 'schedine-solo-multigol.json',
        'solo_primotempo': 'schedine-solo-primotempo.json',
        'solo_ammonizioni': 'schedine-solo-ammonizioni.json',
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
            # una schedina con almeno un evento perso e' gia' persa: si archivia
            # subito e si sostituisce, senza aspettare le partite rimaste
            if any(esito is None for esito, _ in outcomes) and not any(esito == 'perso' for esito, _ in outcomes):
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
                pool_sezione = build_pool_single_market(
                    pick_field, mercato_code, league_files,
                    weekend_only=(kind != 'solo_corner'))
                pool_sezione = [e for e in pool_sezione if e['partita'] not in eventi_attivi]
                pool_sezione = _filter_same_round(pool_sezione, lambda e: datetime.datetime.fromisoformat(e['data']))

            n = len(sch['eventi'])
            level = sch['livello_rischio']
            if kind in SEZIONI_VARIANTI:
                # la sostituta viene creata dal riempimento delle varianti qui sotto
                continue
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

        if kind in SEZIONI_VARIANTI:
            # Riempie le varianti mancanti: per ogni livello deve esserci una
            # schedina attiva 'quota_max' e una 'libera'. Le schedine attive
            # senza campo 'variante' (create prima di questo schema) occupano
            # il posto della 'libera' finche' non si concludono.
            attive = [x for x in data.get('schedine', []) if x.get('stato') != 'archiviata']
            mancanti = []
            for level in LIVELLI_VARIANTI:
                del_livello = [x for x in attive if x['livello_rischio'] == level]
                if not any(x.get('variante') == 'quota_max' for x in del_livello):
                    mancanti.append((level, 'quota_max'))
                if not any(x.get('variante', 'libera') == 'libera' for x in del_livello):
                    mancanti.append((level, 'libera'))
            if mancanti:
                pool_v = build_pool_single_market(
                    pick_field, mercato_code, league_files,
                    weekend_only=(kind != 'solo_corner'))
                pool_v = _filter_same_round(pool_v, lambda e: datetime.datetime.fromisoformat(e['data']))
                # prima tutte le quota_max (usano i migliori eventi), poi le libere
                for level, variante in sorted(mancanti, key=lambda m: (m[1] != 'quota_max', m[0])):
                    escludi = {e['partita'] for x in data['schedine']
                               if x.get('stato') != 'archiviata' and x['livello_rischio'] == level
                               and x.get('variante') == 'quota_max' for e in x['eventi']}
                    nuova = build_variante(pool_v, level, variante, escludi)
                    if not nuova:
                        summary.append(f"{fn}: nessuna schedina {variante} pubblicata per livello {level} "
                                       f"(eventi futuri disponibili insufficienti)")
                        continue
                    nuova = {'id': next_id([x['id'] for x in data['schedine']], level), **nuova}
                    data['schedine'].append(nuova)
                    file_changed = True
                    summary.append(f"{fn}: nuova schedina {nuova['id']} ({variante}) pubblicata, "
                                   f"quota {nuova['quota_combinata']}")

        if file_changed:
            data['aggiornato_il'] = NOW.date().isoformat()
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            changed_files.append(fn)

    print('\n'.join(summary) if summary else 'Nessuna schedina da archiviare in questo momento.')
    print('File modificati:', changed_files)


if __name__ == '__main__':
    main()
