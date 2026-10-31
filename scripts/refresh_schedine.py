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


def _chiave_weekend(d):
    """Venerdi' del weekend (ven-sab-dom-lun) a cui appartiene la data locale d."""
    giorno = d.date()
    return giorno - datetime.timedelta(days=(giorno.weekday() - 4) % 7 if giorno.weekday() >= 4 else 3)


def stesso_turno(dates):
    """True se tutte le date appartengono allo stesso turno. Se sono tutte in
    giorni di weekend (ven-sab-dom-lun) DEVONO essere nello stesso weekend: un
    lunedi' e il venerdi' successivo (4 giorni e poche ore) sono weekend diversi
    e non vanno mai combinati. Per i turni infrasettimanali (coppe, nazionali)
    vale la finestra di SAME_ROUND_WINDOW_DAYS giorni esatti."""
    dates = list(dates)
    if not dates:
        return True
    if all(d.weekday() in (4, 5, 6, 0) for d in dates):
        return len({_chiave_weekend(d) for d in dates}) == 1
    return (max(dates) - min(dates)).total_seconds() <= SAME_ROUND_WINDOW_DAYS * 86400


def _filter_same_round(items, get_date):
    """Tiene solo gli elementi dello stesso turno/weekend del piu' vicino nel
    tempo, cosi' una partita rinviata di settimane o il weekend successivo non
    restano mescolati nello stesso pool. get_date(item) -> datetime."""
    if len(items) <= 1:
        return items
    earliest_item = min(items, key=get_date)
    earliest = get_date(earliest_item)
    return [i for i in items if stesso_turno([earliest, get_date(i)])]


def confidenza(prob):
    if prob >= 0.62: return 'ALTA'
    if prob >= 0.56: return 'MEDIA-ALTA'
    if prob >= 0.52: return 'MEDIA'
    return 'BASSA'


# --- Calibrazione dei mercati (introdotta dopo l'analisi del 16 ottobre 2026) ---
# Il confronto tra probabilita' stimate ed esiti reali su 152 partite concluse
# mostra che il modello sottostima in modo sistematico i mercati "da gol":
# Over 2.5 stimato 55,7% contro 63,8% reale, Gol 56,8% contro 60,5%. Le
# probabilita' usate per scegliere e combinare gli eventi vengono quindi
# corrette con uno scarto per (mercato, esito) calcolato SUGLI STESSI DATI
# reali del sito (partite concluse in tutti i file + storico), ristretto verso
# zero quando il campione e' piccolo (CALIB_K) e limitato a +-CALIB_CAP_LOGIT.
# La probabilita' originale del modello resta nel campo probabilita_modello.
CALIB_K = 40
CALIB_CAP_LOGIT = 0.45   # scarto massimo (scala logit) applicabile a un mercato
PROB_MAX = 0.88          # nessun evento supera l'88%: oltre quel livello il campione non lo sostiene
# Pendenza della calibrazione: il backtest mostra che le probabilita' stimate
# molto alte NON si realizzano piu' delle medie (Doppia chance con stima >= 80%:
# 77% reale; Gol/No Gol: nessun potere discriminante). Per questi mercati si
# comprime lo scarto dal centro del gruppo; per gli altri solo leggermente.
PENDENZA_MERCATO = {'1X2': 0.85, 'DC': 0.55, 'OU25': 0.85, 'OU35': 0.85, 'GGNG': 0.5}
MERCATO_DA_CAMPO = {'pick_1x2': '1X2', 'pick_dc': 'DC', 'pick_uo': 'OU25',
                    'pick_uo35': 'OU35', 'pick_gg': 'GGNG'}
_CALIB_CACHE = None


def _esito_pick_ok(code, esito, h, a):
    t = h + a
    if code == '1X2': return (esito == '1' and h > a) or (esito == 'X' and h == a) or (esito == '2' and h < a)
    if code == 'DC': return (esito == '1X' and h >= a) or (esito == 'X2' and h <= a) or (esito == '12' and h != a)
    if code == 'OU25': return t > 2 if esito == 'over' else t <= 2
    if code == 'OU35': return t > 3 if esito == 'over' else t <= 3
    if code == 'GGNG': return (h > 0 and a > 0) if esito == 'gol' else not (h > 0 and a > 0)
    return None


def _partite_concluse_tutte():
    viste, out = set(), []
    def prendi(p):
        r = p.get('risultato') or {}
        if r.get('stato') != 'finale' or not r.get('punteggio'):
            return
        k = (p.get('casa'), p.get('trasferta'), p.get('data'))
        if k in viste:
            return
        viste.add(k)
        out.append(p)
    for fn in sorted(os.listdir(DATA_DIR)):
        if not (fn.startswith('pronostici-') and fn.endswith('.json')) and fn != 'storico-partite.json':
            continue
        try:
            d = json.load(open(os.path.join(DATA_DIR, fn), encoding='utf-8'))
        except Exception:
            continue
        for p in d.get('partite', []):
            prendi(p)
        for comp in d.get('competizioni', []):
            for p in comp.get('partite', []):
                prendi(p)
    return out


def calibrazione_offsets():
    global _CALIB_CACHE
    if _CALIB_CACHE is not None:
        return _CALIB_CACHE
    acc = collections.defaultdict(lambda: [0, 0, 0.0])
    for p in _partite_concluse_tutte():
        try:
            h, a = map(int, p['risultato']['punteggio'].split('-'))
        except Exception:
            continue
        for campo, code in MERCATO_DA_CAMPO.items():
            pick = p.get(campo)
            if not pick:
                continue
            ok = _esito_pick_ok(code, pick['esito'], h, a)
            if ok is None:
                continue
            x = acc[(pick.get('modello', 'v1'), code, pick['esito'])]
            x[0] += 1; x[1] += ok; x[2] += pick['probabilita']
    off = {}
    for k, (n, w, pr) in acc.items():
        # scarto sulla scala logit (non un +x% piatto): sulle probabilita'
        # alte l'effetto si smorza da solo e non sfora mai il 100%. Si salva
        # anche il centro del gruppo (hit rate reale) attorno a cui si
        # comprime la pendenza (vedi PENDENZA_MERCATO).
        hit = min(max(w / n, 0.02), 0.98)
        est = min(max(pr / n, 0.02), 0.98)
        d = math.log(hit / (1 - hit)) - math.log(est / (1 - est))
        d = max(-CALIB_CAP_LOGIT, min(CALIB_CAP_LOGIT, d * n / (n + CALIB_K)))
        off[k] = (d, math.log(est / (1 - est)) + d)
    _CALIB_CACHE = off
    return off


# Secondo livello di calibrazione, appreso dagli errori delle schedine
# (introdotto il 23 ottobre 2026). La prima calibrazione corregge le stime del
# modello su TUTTE le partite; ma le gambe che finiscono davvero nelle schedine
# sono quelle scelte perche' molto probabili, e su di esse alcuni mercati
# sbagliano ancora in modo sistematico (Under 2.5, No Gol e X2 sovrastimati;
# Over 2.5 sottostimato). Si confronta quindi, per (mercato, esito), la
# probabilita' stimata al momento della schedina con l'esito reale delle gambe
# chiuse, e lo scarto residuo (ristretto con SEL_K, limitato a SEL_CAP) viene
# applicato alle probabilita' usate per scegliere le gambe nuove.
SEL_K = 25
SEL_CAP_LOGIT = 0.5
_SEL_CACHE = None


def residui_selezione():
    global _SEL_CACHE
    if _SEL_CACHE is not None:
        return _SEL_CACHE
    codici = set(MERCATO_DA_CAMPO.values())
    acc, viste = collections.defaultdict(lambda: [0, 0, 0.0]), set()
    for fn in sorted(os.listdir(DATA_DIR)):
        if fn.startswith('pronostici-') or fn in ('storico-partite.json', 'settimane.json'):
            continue
        try:
            d = json.load(open(os.path.join(DATA_DIR, fn), encoding='utf-8'))
        except Exception:
            continue
        stack = [d]
        while stack:
            x = stack.pop()
            if isinstance(x, dict):
                if 'eventi' in x and 'livello_rischio' in x:
                    for e in x['eventi']:
                        if e.get('mercato') not in codici or e.get('esito') not in ('vinto', 'perso'):
                            continue
                        k = (e['partita'], e['mercato'], e.get('esito_pick'))
                        if k in viste or not e.get('probabilita_stimata'):
                            continue
                        viste.add(k)
                        a = acc[(e['mercato'], e.get('esito_pick'))]
                        a[0] += 1; a[1] += e['esito'] == 'vinto'; a[2] += e['probabilita_stimata']
                else:
                    stack.extend(x.values())
            elif isinstance(x, list):
                stack.extend(x)
    off = {}
    for k, (n, w, pr) in acc.items():
        hit = min(max(w / n, 0.02), 0.98)
        est = min(max(pr / n, 0.02), 0.98)
        d = math.log(hit / (1 - hit)) - math.log(est / (1 - est))
        off[k] = max(-SEL_CAP_LOGIT, min(SEL_CAP_LOGIT, d * n / (n + SEL_K)))
    _SEL_CACHE = off
    return off


def pick_calibrato(code, pick):
    """Copia del pick con la probabilita' corretta dallo storico: scarto del
    gruppo (mercato, esito) piu' compressione verso il suo hit rate reale."""
    # Lo scarto si calcola e si applica per versione del modello: i pick v1
    # (senza campo 'modello') avevano la sottostima dei gol che la v2 corregge
    # gia' da se', quindi i loro scarti non vanno applicati ai pick v2.
    d, centro = calibrazione_offsets().get((pick.get('modello', 'v1'), code, pick['esito']), (0.0, None))
    p0 = min(max(pick['probabilita'], 0.02), 0.98)
    lg = math.log(p0 / (1 - p0)) + d
    if centro is not None:
        lg = centro + PENDENZA_MERCATO.get(code, 1.0) * (lg - centro)
    lg += residui_selezione().get((code, pick['esito']), 0.0)
    p = min(PROB_MAX, max(0.05, 1 / (1 + math.exp(-lg))))
    return {**pick, 'probabilita': round(p, 3), 'probabilita_modello': pick['probabilita']}


def mercati_calibrati(p):
    """I 5 mercati di una partita come lista (codice, pick calibrato)."""
    return [(code, pick_calibrato(code, p[campo])) for campo, code in MERCATO_DA_CAMPO.items() if p.get(campo)]


# Selezione del mercato per ogni partita: il piu' probabile in assoluto (dopo
# la calibrazione). Fino al 16/10/2026 Doppia Chance e Under/Over 3.5 erano
# "di riserva" (scelti solo se nessun altro mercato superava il 50%) per
# diversificare i mercati. Il backtest sulle 152 partite concluse mostra che
# quella regola dimezzava la probabilita' di vincita: schedine da 4 eventi
# vinte 13% contro 37-40% scegliendo sempre l'evento piu' probabile.
MERCATI_RISERVA = ()
SOGLIA_MERCATI_PRIMARI = 0.50


# Regola delle Miste (23/10/2026): su 93 Miste chiuse la doppia chance e' l'unico
# mercato la cui stima regge (78% stimato, 80% reale); Gol/No Gol (61% -> 50%)
# e Esito 1X2 (63% -> 50%) escono molto meno di quanto stimato, perche' scegliere
# il massimo tra mercati con stime incerte favorisce gli errori ottimisti. Per
# ogni partita il mercato di base e' la doppia chance; un altro mercato la
# sostituisce solo se la sua probabilita' calibrata la supera di almeno
# MARGINE_DC (10 punti).
MARGINE_DC = 0.10


def mercati_ammessi_miste(markets):
    """markets: lista (codice, pick) con 'probabilita'. Tiene la doppia chance
    e gli altri mercati che la superano di almeno MARGINE_DC (senza doppia
    chance, non filtra)."""
    dc = [m for m in markets if m[0] == 'DC']
    if not dc:
        return list(markets)
    base = dc[0][1]['probabilita']
    return [m for m in markets if m[0] == 'DC' or m[1]['probabilita'] >= base + MARGINE_DC]


def pick_best_market(markets):
    return max(mercati_ammessi_miste(markets), key=lambda m: m[1]['probabilita'])


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

    coppe_path = os.path.join(DATA_DIR, 'pronostici-coppe-europee.json')
    if os.path.exists(coppe_path):
        d = json.load(open(coppe_path, encoding='utf-8'))
        for comp in d.get('competizioni', []):
            for p in comp.get('partite', []):
                lookup[comp.get('nome', '') + '||' + p['casa'] + ' - ' + p['trasferta']] = p.get('risultato', {})

    # partite gia' spostate nello storico: servono ancora per risolvere le schedine aperte
    storico_path = os.path.join(DATA_DIR, 'storico-partite.json')
    if os.path.exists(storico_path):
        d = json.load(open(storico_path, encoding='utf-8'))
        for p in d.get('partite', []):
            if p.get('campionato') and p.get('risultato'):
                lookup.setdefault(p['campionato'] + '||' + p['casa'] + ' - ' + p['trasferta'], p['risultato'])
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
    'MULTIGOL': 'MULTIGOL', 'TOT': 'TOT',
    'PT': 'PT',
    'AMM': 'AMM',
    'COMBO': 'COMBO',
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
    if ris and ris.get('stato') == 'sospesa':
        return 'annullato', 'sospesa'  # partita sospesa: evento annullato, non decide la schedina
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
    elif mercato == 'TOT':
        t = sum(actual['GOALS'])
        won = {'over05': t >= 1, 'over15': t >= 2, 'under35': t <= 3, 'under45': t <= 4, 'under55': t <= 5}[esito_pick]
    elif mercato == 'MULTIGOL':
        lo, hi = (int(x) for x in esito_pick.split('-'))
        won = lo <= sum(actual['GOALS']) <= hi
    elif mercato == 'PT':
        tot = _somma_coppia(ris.get('primo_tempo'))
        if tot is None:
            return None, None  # finale ma risultato del primo tempo non ancora raccolto
        won = (tot >= 1) if esito_pick == 'over05' else (tot <= 1)
    elif mercato == 'COMBO':
        home, away = actual['GOALS']
        fn_combo = COMBO_DEF.get(esito_pick)
        if not fn_combo:
            return None, None
        won = fn_combo[1](home, away)
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
            markets = mercati_calibrati(p)
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
                'probabilita_modello': round(best[1].get('probabilita_modello', best[1]['probabilita']), 2),
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


GIORNI_WEEKEND = (4, 5, 6, 0)   # ven-sab-dom-lun
GIORNI_INFRASETT = (1, 2, 3)    # mar-mer-gio: turno infrasettimanale, a parte


def build_pool_tutti_mercati(giorni=GIORNI_WEEKEND):
    """Come build_pool() (stessi campionati, solo partite future) ma con
    TUTTI i mercati di ogni partita con probabilita' almeno del 50%: servono
    per costruire schedine dentro una fascia di quota precisa. `giorni` sceglie
    il tipo di turno: weekend (ven-lun, default) oppure infrasettimanale
    (mar-gio); i due turni non si mescolano mai nella stessa schedina."""
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
            if kickoff <= NOW or kickoff.weekday() not in giorni:
                continue
            eventi = []
            ammessi = {c for c, _ in mercati_ammessi_miste(mercati_calibrati(p))}
            for code, field in MERCATI_PICK:
                pick = p.get(field)
                if not pick or code not in ammessi:
                    continue
                pick = pick_calibrato(code, pick)
                if pick['probabilita'] < 0.5:
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
                'probabilita_modello': round(pick.get('probabilita_modello', pick['probabilita']), 2),
                    'confidenza_dati': confidenza(pick['probabilita']),
                    'motivazione': p['nota'],
                    'esito': None,
                    'risultato_reale': None,
                })
            # mercati piu' semplici da centrare (backtest su 441 partite: Over 1.5 81%, Under 4.5 83%,
            # Multigol 1-5 84%, Segna 77-83%): stessa regola delle altre, devono battere la doppia chance di MARGINE_DC
            dc = p.get('pick_dc')
            soglia = (pick_calibrato('DC', dc)['probabilita'] + MARGINE_DC) if dc else 0.5
            for kind, code in (('derived_over15', 'TOT'), ('derived_under', 'TOT'), ('derived_multigol', 'MULTIGOL'), ('derived_segna', 'SEGNA')):
                px = derive_pick(p, kind)
                if not px or px['probabilita'] < max(0.5, soglia):
                    continue
                eventi.append({
                    'partita': f"{p['casa']} - {p['trasferta']}", 'campionato': name, 'data': p['data'],
                    'mercato': code, 'pronostico': px['etichetta'], 'esito_pick': px['esito'],
                    'probabilita_stimata': round(px['probabilita'], 2), 'quota_stimata': round(1 / px['probabilita'], 2),
                    'probabilita_modello': round(px['probabilita'], 2), 'confidenza_dati': confidenza(px['probabilita']),
                    'motivazione': p['nota'], 'esito': None, 'risultato_reale': None,
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
    preferisce la piu' probabile (quota piu' bassa), con una piccola penalita'
    per le partite in comune con le altre schedine. Restituisce None se
    nessuna combinazione rientra nella fascia."""
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
        if not stesso_turno(dates):
            continue
        q = 1 / combo_prob(eventi)
        if not (lo < q <= hi) or not _rispetta_limiti(eventi):
            continue
        nomi = {e['partita'] for e in eventi}
        # Dentro la fascia si cerca la combinazione PIU' PROBABILE (quota piu'
        # bassa tra quelle ammesse), non quella piu' vicina al tetto: la
        # fascia fissa solo il rischio massimo, non quello minimo. Le
        # sovrapposizioni con le altre schedine costano una piccola penalita'
        # (un errore su una partita condivisa affonda piu' schedine insieme).
        pcomb = 1 / q
        key = (pcomb - 0.02 * len(nomi & set(gia_usate_livello)) - 0.004 * len(nomi & set(gia_usate)),)
        if best_key is None or key > best_key:
            best, best_key = eventi, key
    if not best:
        return None

    # Rifinitura a scalata: dalla migliore trovata a caso prova tutte le
    # sostituzioni di un singolo evento (altra partita o altro mercato della
    # stessa partita) e tiene quelle che aumentano la probabilita' restando
    # dentro la fascia e dentro le regole (finestra del turno, limiti).
    def punteggio(ev):
        nomi_ = {e['partita'] for e in ev}
        return combo_prob(ev) - 0.02 * len(nomi_ & set(gia_usate_livello)) - 0.004 * len(nomi_ & set(gia_usate))

    def valida(ev):
        if len({e['partita'] for e in ev}) != len(ev) or not _rispetta_limiti(ev):
            return False
        ds = [datetime.datetime.fromisoformat(e['data']) for e in ev]
        if not stesso_turno(ds):
            return False
        qq = 1 / combo_prob(ev)
        return lo < qq <= hi

    tutti = [e for m in partite for e in m]
    migliorato = True
    giri = 0
    while migliorato and giri < 40:
        migliorato = False
        giri += 1
        base = punteggio(best)
        for i in range(len(best)):
            for cand in tutti:
                prova = best[:i] + [cand] + best[i + 1:]
                if cand is best[i] or not valida(prova):
                    continue
                sc = punteggio(prova)
                if sc > base + 1e-9:
                    best, base, migliorato = prova, sc, True
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
            disponibili = [m for m in partite if m[0]['partita'] not in usate_livello]
            nuova = build_schedina_fascia(disponibili, level, fascia, usate_livello, usate, seed=seed)
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
    'solo_gol': ('derived_over15', 'TOT', LEAGUES),
    'solo_under': ('derived_under', 'TOT', LEAGUES),
    'solo_corner': ('pick_corner', 'CORNER', CORNER_LEAGUES),
    'solo_segna': ('derived_segna', 'SEGNA', LEAGUES),
    'solo_multigol': ('derived_multigol', 'MULTIGOL', LEAGUES),
    'solo_primotempo': ('derived_primotempo', 'PT', LEAGUES),
    'solo_ammonizioni': ('derived_ammonizioni', 'AMM', CORNER_LEAGUES),
    'solo_combo': ('derived_combo', 'COMBO', LEAGUES),
    'solo_sicure': ('derived_sicuro', 'TOT', LEAGUES),
}


SEGNA_OSPITE_MAX = 0.84

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


# --- Combo: due mercati sulla stessa partita (es. Gol + Over 2.5). La
# probabilita' congiunta si calcola sulla distribuzione dei punteggi (Poisson
# con i gol attesi ricavati dai pick), non moltiplicando le due probabilita':
# i mercati sono legati tra loro e il prodotto sbaglierebbe. Per ogni partita
# si sceglie la combo piu' probabile tra quelle con quota stimata >= 1.45.
COMBO_QUOTA_MIN = 1.45
COMBO_PROB_MIN = 0.45
COMBO_DEF = {
    'gol_o25': ('Gol + Over 2.5', lambda h, a: h > 0 and a > 0 and h + a > 2),
    'gol_u35': ('Gol + Under 3.5', lambda h, a: h > 0 and a > 0 and h + a < 4),
    '1x_u35': ('{c} o pareggio + Under 3.5', lambda h, a: h >= a and h + a < 4),
    'x2_u35': ('Pareggio o {t} + Under 3.5', lambda h, a: h <= a and h + a < 4),
    '1x_o15': ('{c} o pareggio + Over 1.5', lambda h, a: h >= a and h + a > 1),
    'x2_o15': ('Pareggio o {t} + Over 1.5', lambda h, a: h <= a and h + a > 1),
    '12_o15': ('Nessun pareggio + Over 1.5', lambda h, a: h != a and h + a > 1),
    '1_o15': ('{c} vince + Over 1.5', lambda h, a: h > a and h + a > 1),
    '2_o15': ('{t} vince + Over 1.5', lambda h, a: a > h and h + a > 1),
}


def _prob_combo(lh, la, fn):
    ph, pa = _pmf(lh), _pmf(la)
    return sum(x * y for i, x in enumerate(ph) for j, y in enumerate(pa) if fn(i, j))


def derive_combo(p):
    lam = fit_lambdas(p)
    if not lam:
        return None
    lh, la = lam
    best = None
    for key, (etichetta, fn) in COMBO_DEF.items():
        pr = _prob_combo(lh, la, fn)
        if pr < COMBO_PROB_MIN or 1 / pr < COMBO_QUOTA_MIN:
            continue
        if best is None or pr > best[1]:
            best = (key, pr, etichetta)
    if not best:
        return None
    key, pr, etichetta = best
    return {'esito': key, 'etichetta': etichetta.format(c=p['casa'], t=p['trasferta']), 'probabilita': pr}


def derive_pick(p, kind, fn=None):
    if kind == 'derived_combo':
        return derive_combo(p)
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
        # backtest su 441 partite concluse: quando il modello da' all'ospite 87%+ di segnare,
        # segna solo il 68% delle volte (13/19; Solo Segna ospite 25/32). Si limita al 84%.
        pa = min(pa, SEGNA_OSPITE_MAX)
        if ph >= pa:
            return {'esito': 'casa', 'etichetta': f"Segna la squadra di casa ({p['casa']})", 'probabilita': ph}
        return {'esito': 'trasferta', 'etichetta': f"Segna la squadra ospite ({p['trasferta']})", 'probabilita': pa}
    if kind == 'derived_sicuro':
        # eventi quasi certi: Over 0.5 (~94%), Under 5.5 (~96%), Over 1.5 se molto probabile
        tot = _pmf(lh + la, 16)
        opts = [('over05', 'Over 0.5 gol', 1 - tot[0]), ('under55', 'Under 5.5 gol', sum(tot[:6])),
                ('over15', 'Over 1.5 gol', 1 - tot[0] - tot[1])]
        esito, et, prob = max(opts, key=lambda o: o[2])
        return {'esito': esito, 'etichetta': et, 'probabilita': prob}
    if kind == 'derived_over15':
        # almeno 2 gol: previsto 82%, reale 81% sulle partite concluse (86% con p>=0.85)
        return {'esito': 'over15', 'etichetta': 'Over 1.5 gol', 'probabilita': 1 - sum(_pmf(lh + la, 3)[:2])}
    if kind == 'derived_under':
        tot = _pmf(lh + la, 14)
        opts = [('under35', 'Under 3.5 gol', sum(tot[:4])), ('under45', 'Under 4.5 gol', sum(tot[:5]))]
        esito, et, prob = max(opts, key=lambda o: o[2])
        return {'esito': esito, 'etichetta': et, 'probabilita': prob}
    if kind == 'derived_multigol':
        tot = _pmf(lh + la, 14)
        # backtest 441 partite: 1-3 e 2-4 (~60%) sono troppo rischiosi, 1-4 e 1-5 vincono 76-84%
        opts = [('1-4', sum(tot[1:5])), ('1-5', sum(tot[1:6]))]
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
            if pick_field in MERCATO_DA_CAMPO:
                pick = pick_calibrato(MERCATO_DA_CAMPO[pick_field], pick)
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
                'probabilita_modello': round(pick.get('probabilita_modello', pick['probabilita']), 2),
                'confidenza_dati': 'MEDIA' if mercato_code in ('PT', 'AMM', 'COMBO') else confidenza(pick['probabilita']),
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
# Campionati con dati ancora scarsi (Süper Lig: stime basate solo sulla
# classifica delle prime giornate, senza uno storico dei nostri pronostici):
# al massimo MAX_EVENTI_LIMITATI eventi per schedina, cosi' le loro
# probabilita' (piu' incerte) non dominano le combinazioni.
CAMPIONATI_LIMITATI = ('Süper Lig',)
MAX_EVENTI_LIMITATI = 1


def _rispetta_limiti(eventi):
    return sum(e['campionato'] in CAMPIONATI_LIMITATI for e in eventi) <= MAX_EVENTI_LIMITATI


SEZIONI_VARIANTI = ('solo_gol', 'solo_under', 'solo_corner', 'solo_segna',
                    'solo_multigol', 'solo_primotempo', 'solo_ammonizioni', 'solo_combo', 'solo_sicure')
# La sezione combo ha quote alte per costruzione: solo livelli 4 e 5, e due
# schedine 'libera' / 'alternativa' invece del tetto di quota.
LIVELLI_SEZIONE = {'solo_combo': (4, 5)}
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


def build_variante(pool, level, variante, escludi=(), evita=()):
    """pool ordinato per probabilita' decrescente. Le partite in `escludi`
    (gia' presenti in un'altra schedina attiva dello STESSO livello) non
    vengono mai riusate; quelle in `evita` (presenti in schedine di altri
    livelli) si riusano solo se le partite nuove non bastano. 'quota_max' e
    'libera' differiscono solo nell'ordine di riempimento: la quota_max viene
    costruita per prima, quindi prende le partite piu' probabili rimaste."""
    candidati = [e for e in pool if e['partita'] not in escludi]
    nuove = [e for e in candidati if e['partita'] not in evita]
    eventi = []
    for gruppo in (nuove, candidati):
        for e in gruppo:
            if len(eventi) >= level:
                break
            if e in eventi or not _rispetta_limiti(eventi + [e]):
                continue
            eventi.append(e)
    if len(eventi) < level:
        return None
    eventi = sorted(eventi, key=lambda e: -e['probabilita_stimata'])
    return _schedina_variante(list(eventi), level, variante)


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
        markets = mercati_calibrati(p)
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
                'probabilita_modello': round(best[1].get('probabilita_modello', best[1]['probabilita']), 2),
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
        markets = mercati_calibrati(p)
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
        'campionato': p.get('_campionato', 'Nazionali'),
        'girone': p.get('girone'),
        'data': p['data'],
        'mercato': mkt_code,
        'pronostico': pick['etichetta'],
        'esito_pick': pick['esito'],
        'probabilita_stimata': round(pick['probabilita'], 2),
        'quota_stimata': round(1 / pick['probabilita'], 2),
                'probabilita_modello': round(pick.get('probabilita_modello', pick['probabilita']), 2),
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
        # Nazionali: una schedina non puo' scavalcare le due giornate della
        # stessa pausa (es. gio 12 e mar 17 novembre): al massimo 3 giorni e mezzo.
        if stesso_turno(dates) and (max(dates) - min(dates)).total_seconds() <= 3.5 * 86400:
            return chosen
    return None


def next_id(existing_ids, level):
    prefix = f"L{level}-"
    nums = [int(i[len(prefix):]) for i in existing_ids
            if i.startswith(prefix) and i[len(prefix):].isdigit()]
    return f"{prefix}{(max(nums) + 1) if nums else 1}"


# Coppe europee (Champions, Europa e Conference League): sezione dedicata della
# pagina schedine, file perpetuo data/schedine-coppe.json. Le partite si
# giocano a meta' settimana, quindi non passano dal filtro "solo weekend" delle
# altre sezioni; la finestra di un turno e' comunque quella standard.
COPPE_FILE = 'schedine-coppe.json'


def build_matches_coppe():
    """Come build_matches_nazionali(), ma per tutte le competizioni europee:
    partite non ancora iniziate con tutti i mercati disponibili."""
    path = os.path.join(DATA_DIR, 'pronostici-coppe-europee.json')
    if not os.path.exists(path):
        return []
    d = json.load(open(path, encoding='utf-8'))
    matches = []
    for comp in d.get('competizioni', []):
        for p in comp.get('partite', []):
            if p.get('risultato', {}).get('stato') != 'non_iniziata':
                continue
            try:
                kickoff = datetime.datetime.fromisoformat(p['data'])
            except Exception:
                continue
            if kickoff <= NOW:
                continue
            markets = mercati_calibrati(p)
            if not markets:
                continue
            markets.sort(key=lambda m: -m[1]['probabilita'])
            matches.append(({**p, '_campionato': comp.get('nome')}, markets))
    return matches


# Posizione di partenza (nella classifica delle partite per probabilita'
# decrescente) di ogni livello: il livello 4 prende le partite piu' sicure, i
# livelli successivi scivolano verso quelle meno sicure, cosi' le schedine
# condividono meno partite possibile e il rischio cresce con il livello.
COPPE_OFFSET = {4: 0, 5: 2, 6: 3, 7: 5}
# Seconda schedina dello stesso livello: parte da una posizione diversa e salta
# una partita ogni due, cosi' le due schedine non coincidono mai del tutto.
COPPE_OFFSET_B = {4: 1, 5: 1, 6: 1, 7: 2}
SCHEDINE_PER_LIVELLO_COPPE = 2


def build_levels_coppe(matches, variante=0):
    """matches: output di build_matches_coppe(). Per ogni partita usa il mercato
    piu' probabile tra tutti quelli disponibili e costruisce una schedina per
    ogni livello (4/5/6/7 eventi) per cui ci sono abbastanza partite."""
    if not matches:
        return []
    matches = _filter_same_round(matches, lambda m: datetime.datetime.fromisoformat(m[0]['data']))
    eventi = []
    for p, markets in matches:
        code, pick = markets[0]  # markets e' ordinato per probabilita' decrescente
        eventi.append(_evento_nazionale(p, code, pick))
    eventi.sort(key=lambda e: -e['probabilita_stimata'])
    schedine = []
    for level in LIVELLI_NAZIONALI:
        if len(eventi) < level:
            continue
        if variante == 0:
            start = min(COPPE_OFFSET[level], len(eventi) - level)
            scelti = eventi[start:start + level]
        else:
            start = COPPE_OFFSET_B[level]
            resto = eventi[start:]
            # una partita ogni tre viene saltata, per differenziare dalla prima
            scelti = [e for i, e in enumerate(resto) if i % 3 != 2][:level]
            if len(scelti) < level:
                continue
        pc = combo_prob(scelti)
        schedine.append({
            'livello_rischio': level,
            'quota_combinata': round(1 / pc, 2),
            'probabilita_combinata': round(pc, 3),
            'eventi': [dict(e) for e in scelti],
        })
    return schedine


def _ricalcola_coppe(summary):
    """Riporta forma, mercati e nota delle partite di coppa non ancora iniziate
    alle statistiche piu' recenti dei campionati (vedi coppe_modello.py)."""
    import copy
    import coppe_modello
    path = os.path.join(DATA_DIR, 'pronostici-coppe-europee.json')
    if not os.path.exists(path):
        return
    d = json.load(open(path, encoding='utf-8'))
    nuovo = copy.deepcopy(d)
    coppe_modello.ricalcola_non_iniziate(nuovo)
    if nuovo != d:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(nuovo, f, ensure_ascii=False, indent=2)
        summary.append('pronostici-coppe-europee.json: pronostici delle partite non iniziate ricalcolati sui dati recenti')


def _aggiorna_coppe(summary, lookup):
    """Archivia le schedine delle coppe concluse e ne pubblica di nuove finche'
    ci sono partite europee future disponibili. Ritorna True se il file cambia."""
    path = os.path.join(DATA_DIR, COPPE_FILE)
    if os.path.exists(path):
        data = json.load(open(path, encoding='utf-8'))
    else:
        data = {'id': 'coppe-europee', 'titolo': 'Coppe europee', 'generato_il': NOW.date().isoformat(),
                'stato': 'pubblicata', 'schedine': [],
                'nota_dati': 'Schedine costruite sulle partite di Champions League, Europa League e Conference League '
                             'del turno in corso, con il mercato piu\' supportato dai dati per ogni partita. '
                             'Si aggiornano da sole a ogni partita conclusa.'}
    changed = False

    for sch in data['schedine']:
        if sch.get('stato') == 'archiviata':
            continue
        outcomes = [event_outcome(ev, lookup) for ev in sch['eventi']]
        if any(e is None for e, _ in outcomes) and not any(e == 'perso' for e, _ in outcomes):
            continue
        for ev, (esito, punteggio) in zip(sch['eventi'], outcomes):
            ev['esito'] = esito
            ev['risultato_reale'] = punteggio
        sch['stato'] = 'archiviata'
        sch['esito_finale'] = 'vinta' if all(e in ('vinto', 'annullato') for e, _ in outcomes) else 'persa'
        sch['archiviata_il'] = NOW.isoformat()
        changed = True
        summary.append(f"{COPPE_FILE}: {sch['id']} archiviata ({sch['esito_finale']})")

    attive = [x for x in data['schedine'] if x.get('stato') != 'archiviata']
    for variante in range(SCHEDINE_PER_LIVELLO_COPPE):
        conteggio = {}
        for x in attive:
            conteggio[x['livello_rischio']] = conteggio.get(x['livello_rischio'], 0) + 1
        if all(conteggio.get(l, 0) > variante for l in LIVELLI_NAZIONALI):
            continue
        for nuova in build_levels_coppe(build_matches_coppe(), variante):
            lvl = nuova['livello_rischio']
            if conteggio.get(lvl, 0) > variante:
                continue
            sets = [frozenset(e['partita'] + e['mercato'] for e in x['eventi']) for x in attive if x['livello_rischio'] == lvl]
            if frozenset(e['partita'] + e['mercato'] for e in nuova['eventi']) in sets:
                continue
            nuova['id'] = next_id([x['id'] for x in data['schedine']], lvl)
            nuova['stato'] = 'pubblicata'
            data['schedine'].append(nuova)
            attive.append(nuova)
            conteggio[lvl] = conteggio.get(lvl, 0) + 1
            changed = True
            summary.append(f"{COPPE_FILE}: nuova schedina {nuova['id']} pubblicata "
                           f"({len(nuova['eventi'])} eventi, prob {nuova['probabilita_combinata']:.3f})")

    if changed:
        data['aggiornato_il'] = NOW.date().isoformat()
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    return changed


def backfill_esiti(lookup, files):
    """Completa esito e risultato_reale degli eventi delle schedine GIA'
    archiviate che sono rimasti vuoti (schedina persa prima che finissero tutte
    le partite). Non cambia mai lo stato di una schedina: serve solo a non
    perdere il risultato reale di ogni evento quando il file della lega viene
    sostituito dal turno successivo."""
    toccati = []
    for fn in files:
        path = os.path.join(DATA_DIR, fn)
        if not os.path.exists(path):
            continue
        data = json.load(open(path, encoding='utf-8'))
        mod = False
        for sch in data.get('schedine', []):
            if sch.get('stato') != 'archiviata':
                continue
            for ev in sch['eventi']:
                if ev.get('esito') is None:
                    esito, punteggio = event_outcome(ev, lookup)
                    if esito is not None:
                        ev['esito'] = esito
                        ev['risultato_reale'] = punteggio
                        mod = True
        if mod:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            toccati.append(fn)
    return toccati


def _chiave_infrasett(d):
    """Lunedi' della settimana a cui appartiene la data locale d: identifica
    il turno infrasettimanale (mar-gio) di quella settimana."""
    giorno = d.date()
    return (giorno - datetime.timedelta(days=giorno.weekday())).isoformat()


MESI_IT = ('gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno', 'luglio',
           'agosto', 'settembre', 'ottobre', 'novembre', 'dicembre')


def crea_turno_infrasettimanale(settimane, settimane_path, changed_files, summary):
    """Se ci sono abbastanza partite future di campionato nel turno
    infrasettimanale (mar-gio) e per quella settimana non esiste ancora un
    file dedicato, lo crea e lo mette in cima a settimane.json: le schedine
    vengono poi riempite da main() nello stesso giro. Il turno infrasettimanale
    e' sempre separato da quello del weekend (ven-lun)."""
    pool_inf = build_pool_tutti_mercati(GIORNI_INFRASETT)
    if len(pool_inf) < 8:  # sotto 8 partite non si riempiono le fasce: turno troppo piccolo
        return
    date = sorted(datetime.datetime.fromisoformat(m[0]['data']) for m in pool_inf)
    chiave = _chiave_infrasett(date[0])
    for w in settimane.get('settimane', []):
        p = os.path.join(DATA_DIR, w['file'])
        if w['file'].startswith('infra-') and os.path.exists(p) and \
                json.load(open(p, encoding='utf-8')).get('chiave_turno') == chiave:
            return
    a, b = date[0], date[-1]
    periodo = (f"{a.day} {MESI_IT[a.month - 1]} {a.year}" if a.date() == b.date() else
               f"{a.day}-{b.day} {MESI_IT[a.month - 1]} {a.year}" if a.month == b.month
               else f"{a.day} {MESI_IT[a.month - 1]} - {b.day} {MESI_IT[b.month - 1]} {a.year}")
    campionati = sorted({m[0]['campionato'] for m in pool_inf})
    fn = f"infra-{chiave}.json"
    data = {
        'id': f"infra-{chiave}",
        'titolo': f"Turno infrasettimanale del {periodo}",
        'generato_il': NOW.date().isoformat(),
        'aggiornato_il': NOW.date().isoformat(),
        'stato': 'pubblicata',
        'chiave_turno': chiave,
        'campionati_coperti': campionati,
        'nota_dati': ("Schedine costruite solo con le partite del turno infrasettimanale (martedi'-giovedi') "
                      "dei campionati per club, tenute separate da quelle del weekend: i due turni non si "
                      "mescolano mai nella stessa schedina. Stesse regole delle schedine del weekend: quattro "
                      "fasce di quota per ogni numero di eventi (4, 5, 6 e 7), ogni evento puo' usare uno qualsiasi "
                      "dei mercati della partita, la Serie C non e' inclusa e le partite gia' disputate sono escluse. "
                      "Con poche partite nel turno alcune fasce possono restare vuote."),
        'periodo': periodo,
        'schedine': [],
    }
    with open(os.path.join(DATA_DIR, fn), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    settimane['settimane'].insert(0, {'id': data['id'], 'titolo': data['titolo'], 'file': fn})
    with open(settimane_path, 'w', encoding='utf-8') as f:
        json.dump(settimane, f, ensure_ascii=False, indent=2)
    changed_files.extend([fn, 'settimane.json'])
    summary.append(f"{fn}: creato il turno infrasettimanale ({periodo}, {len(pool_inf)} partite)")


def main():
    try:
        import aggiorna_corner
        for _fn in aggiorna_corner.main():
            print('corner: aggiornato', _fn)
    except Exception as _e:  # il corner non deve mai bloccare il resto del giro
        print('corner: aggiornamento non riuscito:', _e)
    settimane_path = os.path.join(DATA_DIR, 'settimane.json')
    settimane = json.load(open(settimane_path, encoding='utf-8'))
    lookup = load_results()
    pool = None
    pool_naz = None
    changed_files = []
    summary = []

    tutti_i_file = [w['file'] for w in settimane.get('settimane', [])] + [
        'schedine-solo-gol.json', 'schedine-solo-under.json', 'schedine-solo-corner.json',
        'schedine-solo-segna.json', 'schedine-solo-multigol.json', 'schedine-solo-primotempo.json',
        'schedine-solo-ammonizioni.json', 'schedine-solo-combo.json', 'schedine-solo-sicure.json', 'schedine-coppe.json']
    for fn in backfill_esiti(lookup, tutti_i_file):
        changed_files.append(fn)
        summary.append(f"{fn}: risultati reali completati negli eventi di schedine gia' archiviate")

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
                                if not w['file'].startswith(('nazionali', 'infra-'))), None)
    crea_turno_infrasettimanale(settimane, settimane_path, changed_files, summary)

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
            sch['esito_finale'] = 'vinta' if all(e in ('vinto', 'annullato') for e, _ in outcomes) else 'persa'
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
        elif fn.startswith('infra-'):
            pool_inf = build_pool_tutti_mercati(GIORNI_INFRASETT)
            if pool_inf and _chiave_infrasett(datetime.datetime.fromisoformat(pool_inf[0][0]['data'])) == data.get('chiave_turno'):
                aggiunte = riempi_fasce(data['schedine'], partite=pool_inf, seed=NOW.date().isoformat())
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
        'solo_combo': 'schedine-solo-combo.json',
        'solo_sicure': 'schedine-solo-sicure.json',
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
            sch['esito_finale'] = 'vinta' if all(e in ('vinto', 'annullato') for e, _ in outcomes) else 'persa'
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
            for level in LIVELLI_SEZIONE.get(kind, LIVELLI_VARIANTI):
                del_livello = [x for x in attive if x['livello_rischio'] == level]
                prima = 'alternativa' if kind == 'solo_combo' else 'quota_max'
                if not any(x.get('variante') == prima for x in del_livello):
                    mancanti.append((level, prima))
                if not any(x.get('variante', 'libera') == 'libera' for x in del_livello):
                    mancanti.append((level, 'libera'))
            if mancanti:
                pool_v = build_pool_single_market(
                    pick_field, mercato_code, league_files,
                    weekend_only=(kind != 'solo_corner'))
                pool_v = _filter_same_round(pool_v, lambda e: datetime.datetime.fromisoformat(e['data']))
                # prima tutte le quota_max (usano i migliori eventi), poi le libere
                for level, variante in sorted(mancanti, key=lambda m: (m[1] not in ('quota_max', 'alternativa'), m[0])):
                    attive_ora = [x for x in data['schedine'] if x.get('stato') != 'archiviata']
                    escludi = {e['partita'] for x in attive_ora if x['livello_rischio'] == level for e in x['eventi']}
                    evita = {e['partita'] for x in attive_ora for e in x['eventi']}
                    # una partita puo' ripetersi tra livelli diversi (4, 5, 6, 7
                    # eventi) ma mai due volte nello stesso livello
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

    _ricalcola_coppe(summary)
    if _aggiorna_coppe(summary, lookup):
        changed_files.append(COPPE_FILE)

    print('\n'.join(summary) if summary else 'Nessuna schedina da archiviare in questo momento.')
    print('File modificati:', changed_files)


if __name__ == '__main__':
    main()
