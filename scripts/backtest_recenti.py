"""Backtest del peso delle partite recenti (23/10/2026): confronta la verosimiglianza
Poisson dei punteggi reali mescolando i tassi stagionali con la media delle ultime
N partite tracciate dal sito. Al 23/10 solo 8 partite hanno almeno una partita
precedente tracciata per entrambe le squadre: campione troppo piccolo, il peso
rimane a 0 nel modello. Da rilanciare quando lo storico sara' piu' ampio
(servono almeno 150 partite utilizzabili).
Uso: python3 scripts/backtest_recenti.py
"""
import json,re,glob,collections,math,sys
sys.path.insert(0,'scripts')
import modello_gol as M
MIN_PREC=1
rows=[];seen=set()
for f in glob.glob('data/pronostici-*.json')+['data/storico-partite.json']:
    d=json.load(open(f))
    camp=d.get('campionato')
    for p in d.get('partite',[]):
        k=(p['casa'],p['trasferta'],p['data'])
        if k in seen: continue
        seen.add(k)
        r=p.get('risultato') or {}
        if r.get('stato')!='finale' or not r.get('punteggio'): continue
        mc=re.search(r'in (\d+) gare.*?(\d+)-(\d+)',p.get('forma_casa',''))
        mt=re.search(r'in (\d+) gare.*?(\d+)-(\d+)',p.get('forma_trasferta',''))
        if not(mc and mt): continue
        h,a=map(int,r['punteggio'].split('-'))
        rows.append(dict(data=p['data'],casa=p['casa'],tr=p['trasferta'],h=h,a=a,
          c=tuple(map(int,mc.groups())),t=tuple(map(int,mt.groups())),lega=p.get('campionato') or camp or f))
rows.sort(key=lambda x:x['data'])
print(len(rows))
hist=collections.defaultdict(list)  # team -> [(gf,ga)] precedenti tracciati
def ll(lam,k): return -lam+k*math.log(lam)-math.lgamma(k+1)
def run(w,N,Kr):
    hist.clear(); tot=0;n=0
    for r in rows:
        c=dict(g=r['c'][0],gf=r['c'][1],ga=r['c'][2]);t=dict(g=r['t'][0],gf=r['t'][1],ga=r['t'][2])
        gfh,gah=M.tassi(c['g'],c['gf'],c['ga']);gfa,gaa=M.tassi(t['g'],t['gf'],t['ga'])
        hc,ht=hist[(r['lega'],r['casa'])],hist[(r['lega'],r['tr'])]
        def rec(hh,gf,ga):
            L=hh[-N:]
            if len(L)<MIN_PREC: return gf,ga
            rf=(sum(x[0] for x in L)+gf*Kr)/(len(L)+Kr); ra=(sum(x[1] for x in L)+ga*Kr)/(len(L)+Kr)
            return (1-w)*gf+w*rf,(1-w)*ga+w*ra
        gfh,gah=rec(hc,gfh,gah);gfa,gaa=rec(ht,gfa,gaa)
        bh=min(M.ATTACK_BOOST_MAX,M.ATTACK_BOOST*max(0,gfh-M.ATTACK_REF));ba=min(M.ATTACK_BOOST_MAX,M.ATTACK_BOOST*max(0,gfa-M.ATTACK_REF))
        eh=max(.2,(gfh+gaa)/2*1.08*M.GOAL_SCALE+bh);ea=max(.2,(gfa+gah)/2*.92*M.GOAL_SCALE+ba)
        if len(hc)>=MIN_PREC and len(ht)>=MIN_PREC:
            tot+=ll(eh,r['h'])+ll(ea,r['a']);n+=1
        hc.append((r['h'],r['a']));ht.append((r['a'],r['h']))
    return tot/n/2,n
for N in(3,5):
  for w in(0,.2,.35,.5,.7):
    print(N,w,run(w,N,2))

