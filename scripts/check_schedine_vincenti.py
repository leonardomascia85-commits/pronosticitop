"""Controlla tutte le schedine (data/settimane.json) e segnala quelle con TUTTI
i pronostici azzeccati (stato 'finale' su ogni evento, esito corretto) che non
sono ancora state promosse in data/schedine-vinte.json.

Replica la stessa logica live di schedine.html (parseScore/actualEsiti/liveInfo)
per restare coerente con lo stato mostrato agli utenti sul sito.

Uso: python3 scripts/check_schedine_vincenti.py
Stampa in JSON le schedine nuove da promuovere (array vuoto se nessuna).
Non scrive nulla: la promozione (articolo Notizie + voce in schedine-vinte.json
+ social) va fatta a mano dopo aver verificato i dati.
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")

LEAGUE_FILES = {
    'Serie A': 'pronostici-serie-a.json', 'Serie B': 'pronostici-serie-b.json', 'Serie C': 'pronostici-serie-c.json',
    'Premier League': 'pronostici-premier-league.json', 'La Liga': 'pronostici-la-liga.json',
    'Bundesliga': 'pronostici-bundesliga.json', 'Ligue 1': 'pronostici-ligue-1.json',
    'Liga Portugal': 'pronostici-liga-portugal.json', 'Eredivisie': 'pronostici-eredivisie.json',
    'Brasileirão': 'pronostici-brasileirao.json', 'Champions League': 'pronostici-champions-league.json'
}


def parse_score(punteggio):
    if not punteggio:
        return None
    parts = punteggio.split('-')
    if len(parts) != 2:
        return None
    try:
        return (int(parts[0]), int(parts[1]))
    except ValueError:
        return None


def actual_esiti(score):
    if not score:
        return None
    home, away = score
    return {
        '1X2': '1' if home > away else ('2' if home < away else 'X'),
        'OU25': 'over' if (home + away) > 2.5 else 'under',
        'OU35': 'over' if (home + away) > 3.5 else 'under',
        'GGNG': 'gol' if (home > 0 and away > 0) else 'nogol',
    }


def build_lookup(campionati):
    lookup = {}
    for camp in campionati:
        f = LEAGUE_FILES.get(camp)
        if not f:
            continue
        path = os.path.join(DATA_DIR, f)
        if not os.path.exists(path):
            continue
        d = json.load(open(path, encoding='utf-8'))
        for p in d.get('partite', []):
            lookup[camp + '||' + p['casa'] + ' - ' + p['trasferta']] = p.get('risultato')
    return lookup


def live_info(ev, lookup):
    risultato = lookup.get(ev['campionato'] + '||' + ev['partita'])
    if not risultato or risultato.get('stato') == 'non_iniziata':
        return {'state': 'pending'}
    score = parse_score(risultato.get('punteggio'))
    actual = actual_esiti(score)
    if risultato.get('stato') == 'finale':
        if not actual or not ev.get('esito_pick'):
            return {'state': 'pending'}
        mercato = ev['mercato']
        pick = ev['esito_pick']
        if mercato == 'DC':
            won = pick.find(actual['1X2']) != -1
        else:
            won = actual.get(mercato) == pick
        return {'state': 'win' if won else 'lose', 'punteggio': risultato.get('punteggio')}
    return {'state': 'live', 'punteggio': risultato.get('punteggio')}


def schedina_status(sch, lookup):
    states = [live_info(e, lookup)['state'] for e in sch['eventi']]
    if any(s == 'lose' for s in states):
        return 'lose'
    if all(s == 'win' for s in states):
        return 'win'
    if any(s == 'live' for s in states):
        return 'live'
    return 'pending'


def main():
    settimane = json.load(open(os.path.join(DATA_DIR, 'settimane.json'), encoding='utf-8'))['settimane']

    promosse_path = os.path.join(DATA_DIR, 'schedine-vinte.json')
    promosse_ids = set()
    if os.path.exists(promosse_path):
        promosse_ids = {x['id'] + '|' + x['settimana'] for x in json.load(open(promosse_path, encoding='utf-8')).get('promosse', [])}

    nuove = []
    for w in settimane:
        fpath = os.path.join(DATA_DIR, w['file'])
        if not os.path.exists(fpath):
            continue
        d = json.load(open(fpath, encoding='utf-8'))
        campionati = set(e['campionato'] for s in d['schedine'] for e in s['eventi'])
        lookup = build_lookup(campionati)
        for s in d['schedine']:
            st = schedina_status(s, lookup)
            if st != 'win':
                continue
            key = s['id'] + '|' + w['id']
            if key in promosse_ids:
                continue
            eventi_dettaglio = []
            for e in s['eventi']:
                li = live_info(e, lookup)
                eventi_dettaglio.append({
                    'partita': e['partita'], 'campionato': e['campionato'],
                    'pronostico': e['pronostico'], 'mercato': e['mercato'],
                    'risultato': li.get('punteggio'),
                })
            nuove.append({
                'id': s['id'], 'settimana': w['id'], 'titolo_settimana': w['titolo'],
                'livello_rischio': s['livello_rischio'],
                'quota_combinata': s.get('quota_combinata'),
                'probabilita_combinata': s.get('probabilita_combinata'),
                'eventi': eventi_dettaglio,
            })

    print(json.dumps(nuove, ensure_ascii=False, indent=2))
    return 0 if not nuove else 0


if __name__ == '__main__':
    sys.exit(main())
