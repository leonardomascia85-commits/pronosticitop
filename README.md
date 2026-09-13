# PronosticiTop

Sito pubblico di pronostici calcio settimanali basati su analisi statistica reale
(forma, gol fatti/subiti, classifica, infortuni). Finanziato tramite pubblicità
standard (Google AdSense), nessuna registrazione richiesta per consultare i
contenuti.

## Struttura

- `index.html` — homepage: mostra le schedine del turno selezionato, raggruppate
  per livello di rischio, con storico dei risultati.
- `chi-siamo.html` — spiegazione del metodo (analisi statistica, mercati usati,
  livelli di rischio, confidenza dei dati).
- `termini.html` — termini di utilizzo e disclaimer (nessun consiglio di
  scommessa, vietato ai minori di 18 anni, gioco responsabile).
- `privacy.html`, `cookie-policy.html` — informativa privacy (GDPR) e cookie
  (Google Analytics + Google AdSense).
- `cookie-banner.js` — banner di consenso cookie con Google Consent Mode
  (categorie: necessari, analytics, pubblicità).
- `data/settimane.json` + `data/<id>.json` — dati delle schedine (stesso schema
  della sezione privata in analisiebusinessplan/pronostici — vedi quel repo per
  la documentazione completa dello schema dati e dei criteri di generazione).
- `robots.txt`, `sitemap.xml` — SEO di base.

## Deploy

Pensato per deploy statico automatico (Vercel/Netlify) collegato a questo
repository: ogni push sul branch principale pubblica la nuova versione.
Dominio: pronosticitop.it (+ pronosticitop.com).

## Da fare prima del lancio pubblico

- [ ] Collegare il dominio pronosticitop.it (DNS) all'hosting statico scelto
- [ ] Richiedere l'approvazione Google AdSense e inserire lo script reale
      (attualmente ci sono solo placeholder `<div class="ad-slot">`)
- [ ] Sostituire `G-XXXXXXXXXX` in `cookie-banner.js` con l'ID Google Analytics
      reale, quando creato
- [ ] Verificare testo legale (termini/privacy) con un consulente prima del
      lancio definitivo
- [ ] Impostare l'automazione settimanale (vedi repo analisiebusinessplan) per
      pubblicare anche qui i nuovi turni, oppure sincronizzare manualmente
      `data/` da quel repo ogni settimana
