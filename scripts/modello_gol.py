"""Gol attesi di una partita (modello v2, introdotto il 21/10/2026).

Rispetto alla v1 (media tra gol fatti a gara della squadra e gol subiti a gara
dell'avversaria, +8%/-8% fattore campo) la v2 corregge tre limiti emersi dal
backtest su 126 partite concluse (data/storico-partite.json + pronostici):

1. Campioni piccoli: i gol fatti/subiti a gara di una squadra dopo 6-9 partite
   sono molto rumorosi. Si avvicinano alla media di 1,4 gol con K_SHRINK
   partite "virtuali" (con il prior della stagione precedente, se presente,
   resta la regola gia' in uso di inserisci_turno.py).
2. Sottostima generale dei gol: la v1 prevedeva 2,94 gol a partita contro 3,29
   reali. Un fattore GOAL_SCALE sui gol attesi porta la media al livello reale
   (la verosimiglianza sui punteggi reali sale da -3,277 a circa -3,24).
3. Squadre molto offensive: anche dopo il fattore generale, le partite in cui
   una squadra segna piu' di 1,9 gol a gara hanno 3,9 gol reali contro 3,5
   previsti. Si aggiungono ATTACK_BOOST gol attesi per ogni gol a gara sopra
   ATTACK_REF (correzione parziale e prudente: il campione e' piccolo).

I parametri sono fissati a mano guardando il backtest, non ottimizzati fino
in fondo, per non adattarsi al rumore di 126 partite. Da rivedere quando
lo storico sara' piu' ampio (scripts/calibrazione_mercati.py).
"""
MODELLO_VERSIONE = 'v2'
MU_PRIOR = 1.4      # media gol a squadra verso cui si avvicinano i campioni piccoli
K_SHRINK = 4        # peso (in partite) del prior sulla media di 1,4
GOAL_SCALE = 1.08   # correzione generale della sottostima dei gol
ATTACK_REF = 1.6    # gol a gara oltre i quali una squadra e' "molto offensiva"
ATTACK_BOOST = 0.3  # gol attesi aggiunti per ogni gol a gara sopra ATTACK_REF
ATTACK_BOOST_MAX = 0.4  # tetto della correzione (nessun dato sopra 2,5 gol a gara nel backtest)
K_PRIOR = 6         # peso del prior stagione precedente (quando presente)


def tassi(g, gf, ga, prev=None, media=MU_PRIOR):
    """Gol fatti e subiti a gara stabilizzati. `prev` = {'g','gf','ga'} della
    stagione precedente (stessa lega), se disponibile."""
    if g <= 0:
        return media, media
    gf_pg, ga_pg = gf / g, ga / g
    if prev and prev.get('g'):
        pf = 0.6 * prev['gf'] / prev['g'] + 0.4 * media
        pa = 0.6 * prev['ga'] / prev['g'] + 0.4 * media
        return (gf_pg * g + pf * K_PRIOR) / (g + K_PRIOR), (ga_pg * g + pa * K_PRIOR) / (g + K_PRIOR)
    return (gf + media * K_SHRINK) / (g + K_SHRINK), (ga + media * K_SHRINK) / (g + K_SHRINK)


def gol_attesi(casa, trasf, media=MU_PRIOR):
    """casa/trasf = {'g','gf','ga'[,'prev']}. Restituisce (gol casa, gol
    trasferta, boost_applicato)."""
    gfh, gah = tassi(casa['g'], casa['gf'], casa['ga'], casa.get('prev'), media)
    gfa, gaa = tassi(trasf['g'], trasf['gf'], trasf['ga'], trasf.get('prev'), media)
    bh = min(ATTACK_BOOST_MAX, ATTACK_BOOST * max(0.0, gfh - ATTACK_REF))
    ba = min(ATTACK_BOOST_MAX, ATTACK_BOOST * max(0.0, gfa - ATTACK_REF))
    eh = (gfh + gaa) / 2 * 1.08 * GOAL_SCALE + bh
    ea = (gfa + gah) / 2 * 0.92 * GOAL_SCALE + ba
    return max(eh, 0.2), max(ea, 0.2), bool(bh or ba)
