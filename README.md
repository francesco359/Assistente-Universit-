# LectureForge

MVP GitHub-ready che trasforma materiali didattici e chat AI precedenti in:
- mappe concettuali;
- quiz interattivi con correzione immediata;
- flashcard.

## Formati supportati
PDF, DOCX, PPTX, XLSX, TXT, Markdown, HTML, CSV, JSON e ZIP di esportazioni chat. Per ChatGPT, Claude e Copilot, carica l'esportazione JSON/TXT/HTML selezionando **Chat AI precedenti**.

## Avvio con Docker
```bash
docker compose up --build
```
Apri `http://localhost:8000`.

## Avvio locale
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Test
```bash
pytest
```

## Flusso
1. Crea corso.
2. Carica dispense, slide, trascrizioni e chat AI pregresse.
3. Genera mappa, quiz e flashcard.
4. Apri gli artefatti nel browser.

## Chat AI supportate
Il parser normalizza strutture con campi comuni `role`, `author`, `sender`, `content`, `text`, `message`. Se il JSON non è riconosciuto, il file viene comunque trattato come testo.

## Cosa rende l'MVP funzionante senza API
Il generatore offline crea materiali usando estrazione, frasi e parole chiave. È utile per testare l'intero flusso senza chiavi cloud. In produzione sostituisci `make_map`, `make_cards` e `make_quiz` con un provider LLM che restituisce JSON strutturato, mantenendo le stesse API.

## Estensioni consigliate
- Azure AI Speech per audio/video;
- Microsoft Foundry con output strutturati;
- Azure AI Search per RAG e citazioni alle pagine;
- PostgreSQL e Blob Storage;
- autenticazione Entra ID;
- OCR per scansioni;
- esportazione DOCX/PDF/Anki.

## Privacy
Non caricare registrazioni senza autorizzazione. In produzione aggiungi consenso esplicito, cifratura, scadenza automatica, audit log e cancellazione dei file originali.

## Licenza
MIT.
