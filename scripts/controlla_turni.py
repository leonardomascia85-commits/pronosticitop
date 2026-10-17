"""Controllo di aggiornamento di tutti i file pronostici-*.json (solo lettura, nessuna rete).

Segnala per ogni campionato/coppa:
  - TURNO DA INSERIRE: non c'e' nessuna partita futura (il turno e' finito o sta finendo);
  - RISULTATI MANCANTI: partite con calcio d'inizio passato da piu' di 100 minuti e stato non finale;
  - VUOTO: nessuna partita.
Si lancia a ogni controllo periodico, insieme alla scansione dei risultati: la scansione
delle sole partite iniziate non basta, perche' non vede i campionati fermi al turno precedente.
Uso: python3 scripts/controlla_turni.py
"""
import json, glob, os, datetime

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
NOW = datetime.datetime.now(datetime.timezone.utc)


def dt(s):
    return datetime.datetime.fromisoformat(s).astimezone(datetime.timezone.utc)


def blocchi(f, d):
    if 'competizioni' in d:
        for c in d['competizioni']:
            yield f"{os.path.basename(f)} [{c.get('nome')}]", c.get('partite', [])
    else:
        yield os.path.basename(f), d.get('partite', [])


def main():
    problemi = 0
    for f in sorted(glob.glob(os.path.join(DATA, 'pronostici-*.json'))):
        d = json.load(open(f, encoding='utf-8'))
        for nome, ps in blocchi(f, d):
            if nome.startswith('pronostici-nazionali'):
                continue  # le nazionali sono su calendario a finestre: controllo a parte
            if not ps:
                if 'champions-league.json' not in nome:
                    print(f'VUOTO: {nome}'); problemi += 1
                continue
            futuri = [p for p in ps if p['risultato']['stato'] == 'non_iniziata' and dt(p['data']) > NOW]
            mancanti = [p for p in ps if p['risultato']['stato'] not in ('finale', 'sospesa')
                        and (NOW - dt(p['data'])).total_seconds() > 100 * 60]
            if not futuri:
                print(f'TURNO DA INSERIRE: {nome} ({d.get("giornata")}, ultima partita {max(p["data"] for p in ps)[:16]})'); problemi += 1
            for p in mancanti:
                print(f'RISULTATO MANCANTE: {nome} | {p["casa"]} - {p["trasferta"]} | {p["data"][:16]} | stato={p["risultato"]["stato"]}'); problemi += 1
    print('OK: tutto aggiornato' if not problemi else f'{problemi} segnalazioni')


if __name__ == '__main__':
    main()
