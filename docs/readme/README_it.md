<div align="center">

[English](../../README.md) · [简体中文](README_zh.md) · [日本語](README_ja.md) · [한국어](README_ko.md) · [Español](README_es.md) · **Italiano**

# IRP: Costruisci qualsiasi articolo. Dimostra ogni affermazione.

### Un server MCP e una CLI che permettono al tuo agente di programmazione di trasformare un articolo scientifico in codice funzionante, eseguirlo e dimostrare, affermazione per affermazione, quanto ci si avvicina.

**Dagli un articolo. Ricevi codice funzionante e un report che puoi verificare senza fidarti dell'agente.**

[![PyPI version](https://img.shields.io/pypi/v/irp?style=flat-square&color=3775a9)](https://pypi.org/project/irp-agents/)
[![MCP tool catalog](https://img.shields.io/badge/MCP-tool_catalog-5c4ee5?style=flat-square)](../mcp-contracts.md#generated-catalog)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776ab?style=flat-square&logo=python&logoColor=white)](#cosa-puoi-riprodurre)
[![MIT license](https://img.shields.io/badge/license-MIT-f4c430?style=flat-square)](../../LICENSE)

[Avvio rapido](#avvio-rapido) · [Come funziona](#come-funziona) · [Il report](#il-report) · [Cosa puoi riprodurre](#cosa-puoi-riprodurre) · [Domande frequenti](#domande-frequenti) · [Documentazione](#documentazione)

<code>uvx irp-agents setup</code>

</div>

> [!IMPORTANT]
> Scarican IRP solo da [Noshadi-sec/irp](https://github.com/Noshadi-sec/irp) o dal
> [pacchetto irp su PyPI](https://pypi.org/project/irp-agents/). Un nome di
> repository simile o un README copiato non dimostrano che un download sia ufficiale.

<div align="center">

<img src="../assets/irp-flow.svg" alt="Flusso di IRP: chiedi al tuo agente di costruire un articolo; l'agente legge l'articolo, registra le affermazioni, scrive il codice e decide le esecuzioni con gli strumenti di IRP; IRP recupera l'articolo, esegue il codice e registra ogni passo in un registro di prove concatenato da hash; il report viene scritto solo da quel registro." width="900" />

</div>

---

Hai trovato un articolo senza codice, o con codice di cui non ti fidi? Chiedi al tuo agente
di costruirlo con IRP. L'agente legge l'articolo, registra ogni numero che dichiara,
scrive l'implementazione, la esegue e confronta i risultati. IRP si occupa di recuperare,
eseguire e registrare, e rifiuta le scorciatoie: un numero digitato a mano non conta mai,
un'esecuzione accorciata non conta mai e il report viene scritto solo dal registro delle prove.

IRP collega il tuo agente (Claude Code, Codex o Cursor) a strumenti per leggere
l'articolo, creare ambienti, eseguire, misurare ed emettere verdetti. Puoi usare gli stessi
strumenti dal terminale. Tutto gira in locale; IRP non chiama mai un modello.

## Avvio rapido

### Configura il tuo agente

Con [uv](https://docs.astral.sh/uv/) installato, esegui:

```bash
uvx irp-agents setup
```

Scegli i tuoi agenti, rivedi le modifiche proposte e approvale. Setup aggiunge il server MCP
di IRP e la sua skill di flusso di lavoro, con copie di backup della configurazione
esistente. Poi riavvia l'agente.

Setup supporta Claude Code, Codex e Cursor. Gli altri client MCP possono usare la
[registrazione manuale](../installation.md#manual-registration).

### Chiedi al tuo agente

```text
Build arXiv 2501.12345 and check Table 2.
```

Ricevi una cartella di codice funzionante e un report: ogni affermazione, il numero
dell'articolo, il tuo numero e un verdetto.

### Usa il terminale

Ogni strumento è anche un comando. Recupera un articolo in un nuovo studio e leggine l'indice:

```bash
irp fetch 2501.12345 --study ~/studies/example
irp section index --study ~/studies/example
```

Per installare il comando `irp`:

```bash
uv tool install irp-agents
irp --help
```

Consulta la [guida alla CLI](../cli.md) per il flusso completo dal terminale.

### Controlla che sia tutto pronto

```bash
irp doctor
```

Doctor controlla Python, uv, git, Docker, le GPU, lo spazio su disco e la registrazione dei
tuoi agenti, senza modificare nulla.

### Aggiornan IRP

```bash
irp update
```

Con uvx, aggiorna la configurazione dell'agente con `uvx irp-agents@latest setup`, rivedi il
piano e riavvia l'agente.

## Come funziona

Il tuo agente pensa; IRP agisce e conserva le ricevute. L'agente legge l'articolo, scrive
il codice e decide cosa eseguire. Ogni azione passa da un unico nucleo, quindi la CLI e il
server MCP si comportano allo stesso modo, e ogni passo finisce in un registro delle prove solo
in aggiunta e concatenato da hash. Il report viene costruito solo da quel registro.

| Fase | Strumento | Cosa fa |
| --- | --- | --- |
| Lettura | `fetch_paper` | Scarica il sorgente LaTeX da arXiv o il PDF, ne calcola l'hash e lo divide in sezioni |
| Lettura | `get_section`, `get_page_image` | Restituisce il testo di una sezione con file e numero di riga, o una pagina come immagine per equazioni e figure |
| Affermazioni | `add_claim`, `list_claims` | Registra ogni affermazione: metrica, valore, dove compare e la soglia di successo |
| Piano | `add_guess` | Registra un dettaglio mancante, la scelta fatta e il perché |
| Piano | `map_method` | Collega un'equazione o un passo di algoritmo a un file e a una riga |
| Costruzione | `create_env` | Crea un ambiente uv o un'immagine Docker e scrive il file di lock |
| Esecuzione | `run`, `run_status` | Esegue un comando; salva output, codice di uscita, tempo, memoria, seed, commit e file |
| Esecuzione | `run_remote` | Lo stesso su una GPU a pagamento, dopo una stima dei costi e un'approvazione |
| Misura | `extract_metrics` | Estrae numeri da log e file di risultati, con file e riga |
| Verdetto | `compare`, `add_note` | Mette affermazione e misura fianco a fianco e dà uno di quattro verdetti |
| Report | `report`, `verify`, `study_status` | Scrive report.md e report.json dal registro; ricontrolla la catena di hash |

La skill di flusso di lavoro dà all'agente sei regole rigide, e gli strumenti le fanno rispettare
ovunque possono:

1. Non digitare, stimare o copiare mai un numero come risultato.
2. Non cambiare mai il metodo dell'articolo per far riuscire un'esecuzione; registra un'ipotesi.
3. Segnala "impossibile eseguire" con l'errore bloccante invece di forzare.
4. Esegui prima la versione fedele più piccola; le esecuzioni accorciate non contano mai.
5. Registra ogni affermazione prima di scrivere codice.
6. Chiedi prima di qualsiasi calcolo a pagamento.

## Il report

Il report è il prodotto: una persona deve poter verificare ogni verdetto senza fidarsi
dell'agente. Ha cinque parti: la tabella delle affermazioni, quattro verdetti (riprodotto,
vicino, non riprodotto da questa esecuzione, impossibile eseguire), l'elenco delle ipotesi,
la mappa del metodo dalle equazioni alle righe di codice e la provenienza (ID e versione arXiv,
hash dei file, commit git, file di lock, GPU, seed, ogni comando con il suo codice di uscita e
un comando verify che ricontrolla la catena di hash).

L'agente non può finire finché ogni affermazione non ha un verdetto con prove.

Esempio di `report.md` (numeri inventati):

```markdown
# Reproduction report: Example Paper (arXiv 2501.12345v2)

Result: 2 reproduced, 1 close, 1 could not run (of 4 claims)

| Claim | Where | Paper | Ours | Verdict |
| --- | --- | --- | --- | --- |
| c1 Test accuracy | Table 2, row 3 | 94.1% | 93.8% (3 seeds, std 0.2) | close |
| c2 Training loss | Figure 4 | 0.31 | 0.31 (3 seeds) | reproduced |
| c3 Speed-up | Section 5.2 | 2.0x | 2.1x | reproduced |
| c4 ImageNet top-1 | Table 3 | 81.2% | not run: needs 8 GPUs for 2 days | could not run |
```

Consulta [prove e report](../evidence-and-report.md) per ogni campo.

## Cosa puoi riprodurre

IRP richiede Python 3.11+ su macOS o Linux. Gli altri strumenti dipendono dall'articolo:

| Esigenza | Cosa usan IRP | Requisiti e guida |
| --- | --- | --- |
| Lettura dell'articolo | Prima il sorgente LaTeX di arXiv, poi il PDF, e immagini di pagina per equazioni e figure | Accesso ad arXiv; [lettura degli articoli](../paper-intake.md) |
| Struttura PDF migliore | Docling per testo e tabelle | Opzionale `irp-agents[docling]` |
| Ambienti | Ambienti virtuali uv con file di lock, o immagini Docker per l'isolamento | uv o Docker; [ambienti](../environments.md) |
| Calcolo | La tua CPU o GPU; sandbox GPU di Modal dopo stima e approvazione (sperimentale) | Opzionale `irp-agents[modal]`; [calcolo](../compute.md) |
| Agenti | Claude Code, Codex, Cursor; qualsiasi client MCP a mano | [installazione](../installation.md) |

IRP supporta articoli computazionali: apprendimento automatico, algoritmi e simulazioni.
Non supporta il lavoro di laboratorio sperimentale né nulla che riguardi le armi.

## Casi esemplari

Non sono ancora stati pubblicati casi esemplari. Ognuno avrà il proprio repository e il proprio
report. Segui i progressi nella [roadmap](../roadmap.md).

## Domande frequenti

<details>
<summary><strong>Quali agenti possono usare IRP?</strong></summary>

Qualsiasi agente che supporti server MCP locali. Setup configura Claude Code, Codex e Cursor.

</details>

<details>
<summary><strong>IRP chiama un modello di IA o carica il mio articolo?</strong></summary>

No. Il cervello è il tuo agente; IRP non chiama mai un modello e non ha chiavi API.
Scarica articoli da arXiv, installa pacchetti con uv o Docker ed esegue codice sulla tua macchina.

</details>

<details>
<summary><strong>È sicuro eseguire il codice di un articolo?</strong></summary>

Un ambiente virtuale uv non è una sandbox: il codice gira con i tuoi permessi. Usa
`backend: "docker"` per codice che non hai scritto o di cui non ti fidi. Vedi la
[politica di sicurezza](../../SECURITY.md).

</details>

<details>
<summary><strong>Che cosa significa "non riprodotto"?</strong></summary>

Che questa esecuzione, con le ipotesi registrate, non ha raggiunto il numero dell'articolo entro
la soglia indicata. Il report dice "not reproduced by this run" ed elenca ogni ipotesi. È una
prova su un tentativo, non un verdetto sull'articolo; contatta gli autori prima di pubblicarlo.

</details>

<details>
<summary><strong>IRP può spendere soldi?</strong></summary>

Solo su GPU a pagamento, solo dopo che hai registrato un prezzo e un budget da terminale con
`irp budget`, e solo dopo che hai approvato la stima mostrata dall'agente. Il limite di tempo
dell'esecuzione è pari alle ore stimate.

</details>

## Documentazione

- [Installazione e configurazione](../installation.md)
- [CLI](../cli.md)
- [Contratti MCP](../mcp-contracts.md) e [prompt](../mcp-prompts.md)
- [Prove e report](../evidence-and-report.md)
- [Lettura degli articoli](../paper-intake.md), [ambienti](../environments.md) e [calcolo](../compute.md)
- [Benchmark](../benchmarks.md) e [roadmap](../roadmap.md)

Segnala le vulnerabilità tramite [SECURITY.md](../../SECURITY.md).

## Avvertenze

Vedi [DISCLAIMER.md](../../DISCLAIMER.md) per l'uso responsabile. Un verdetto "non riprodotto" è
una prova su un'esecuzione, non un giudizio sull'articolo o sui suoi autori.

## Contribuire

I contributi sono benvenuti. Vedi [CONTRIBUTING.md](../../CONTRIBUTING.md).

## Licenza

[MIT](../../LICENSE). Il materiale di terze parti mantiene le proprie licenze; vedi gli
[avvisi di terze parti](../../THIRD_PARTY_NOTICES.md).
