# GrillMe — Spezifikation v1

Ergebnis einer Grilling-Session vom 2026-08-20. Jede Entscheidung unten wurde
im Interview getroffen; die Begründungen sind Teil der Spezifikation, damit
spätere Änderungen wissen, wogegen sie argumentieren.

Status: Idee ausformuliert, noch keine Zeile Code. Dieses Verzeichnis wird zum
eigenen Repository, sobald die Implementierung beginnt.

---

## 1. Problem

Eine Idee entsteht als Funke, nicht als Anforderungsliste. Wer sie sofort
aufschreiben soll, schreibt das Offensichtliche auf und übersieht die
Entscheidungen, die daran hängen. Ein strukturiertes Interview — Frage,
Empfehlung, Antwort, nächste Runde — zwingt zum Nachdenken über genau die
Verzweigungen, die man allein überspringt, und produziert am Ende eine
Anforderungsbeschreibung, die deutlich besser ist als der erste Wurf.

Dieses Interview existiert heute als Agent-Skill in der Kommandozeile. GrillMe
macht daraus eine Anwendung mit Account, Verlauf und mehreren Eingabekanälen.

## 2. Produktumfang v1

Ein Nutzer meldet sich an, legt eine Session an, wählt ein Ausgabeformat und
lässt sich grillen — per Text, per Sprache oder mit Screenshots. Wenn der
Entscheidungsbaum abgearbeitet ist, meldet der Agent das, der Nutzer bestätigt,
und das Artefakt wird erzeugt: ein Markdown-Dokument und, je nach Format, ein
oder mehrere Tickets.

Bildschirme in v1: Login, Session-Liste, Chat, Export. Der Gamification-Stand
erscheint als kleine Anzeige im Header, ohne eigene Seite.

Betrieb in v1: `docker compose up` auf dem eigenen Rechner, ein Nutzer. Die
Architektur ist so gebaut, dass daraus später ein gehosteter Mehrbenutzerbetrieb
werden kann, ohne dass Datenmodell oder Storage angefasst werden müssen.

## 3. Architektur

```
Next.js + React (CopilotKit)          Frontend, AG-UI-Client
        │  SSE (AG-UI-Protokoll)
        ▼
FastAPI + ag-ui-claude-sdk            Backend
        │
        ├── claude-agent-sdk ──► Claude Code CLI (Subprozess) ──► Claude API
        ├── Postgres                  Wahrheit für State, Verlauf, Baum
        ├── MinIO                     Bilder
        ├── Transcriber (Interface)   Sprache zu Text
        └── Speaker (Interface)       Text zu Sprache
```

Alle Komponenten laufen als Dienste in einem Docker-Compose-Stack.

### 3.1 Agent-State lebt in Postgres

Das Claude Agent SDK bringt eigene Sessions mit, deren Zustand im
Dateisystem der CLI liegt. Diese Persistenz wird **nicht** benutzt. Postgres ist
die einzige Quelle der Wahrheit; jede Interview-Runde startet eine frische
SDK-Session und bekommt Entscheidungsbaum plus Verlauf als Prompt neu geliefert.

Begründung: Container-Neustarts, Wiederaufnahme einer Session nach Tagen und
späterer Mehrbenutzerbetrieb brechen alle an dateibasiertem Session-State. Die
SDK-Session ist ein wegwerfbarer Rechenschritt. Der Entscheidungsbaum als JSON
in Postgres ist ohnehin das, woraus das Endartefakt deterministisch generiert
wird. Die zusätzlichen Input-Tokens pro Runde fängt Prompt-Caching ab.

Praktische Folge: `resume=<session_id>` wird nicht verwendet, und `.claude/`
braucht kein persistentes Volume.

### 3.2 Transport: AG-UI

Das Backend nutzt `ag-ui-claude-agent-sdk`, die offizielle AG-UI-Integration für
das Claude Agent SDK in Python:

```python
from ag_ui_claude_sdk import ClaudeAgentAdapter, add_claude_fastapi_endpoint

adapter = ClaudeAgentAdapter(name="grill_agent", options={"model": "claude-opus-5"})
add_claude_fastapi_endpoint(app=app, adapter=adapter, path="/grill")
```

Mitgeliefert werden Streaming der Tool-Argumente, `adapter.interrupt()`,
Frontend-Tools mit Human-in-the-Loop-Stopp, bidirektionaler State-Sync und
Kontext-Injection — genau die Bausteine, die eine eigene SSE-Schicht wochenlang
nachbauen müsste. Das Frontend spricht über CopilotKit dasselbe Protokoll.

**Die Version wird auf 0.1.0 gepinnt.** Das Paket ist früh; der Adapter ist
klein genug, um ihn im Notfall zu vendoren und selbst zu pflegen.

### 3.3 Credentials

Das Backend spricht Claude über ein Provider-Interface mit zwei
Implementierungen an, beide ab Tag 1 vorhanden:

- `CLAUDE_CODE_OAUTH_TOKEN` — einmalig auf dem Host per `claude setup-token`
  erzeugt und in die `.env` des Compose-Stacks eingetragen. Kein Mount von
  `~/.claude` in den Container: das koppelt den Container an den Host-Zustand
  und bricht beim ersten Re-Login.
- `ANTHROPIC_API_KEY` — der Weg für jeden Betrieb, bei dem nicht nur der
  Betreiber selbst Nutzer ist.

**Harte Kopplung:** Der Mehrbenutzerbetrieb ist an die API-Key-Implementierung
gebunden und darf mit Subscription-Token nicht startbar sein. Auf einem
Consumer- oder Team-Abo gibt es keinen Auftragsverarbeitungsvertrag mit
Anthropic. Solange ausschließlich der Betreiber die Instanz nutzt, ist das eine
reine Frage der Nutzungsbedingungen und kein Datenschutzfall, weil es keinen
fremden Betroffenen gibt. Sobald ein zweiter Mensch Daten einspeist, ist es
beides. Das Schema sieht deshalb von Anfang an eine optionale
`user.anthropic_api_key`-Spalte vor (verschlüsselt), damit später jeder Nutzer
seinen eigenen Schlüssel hinterlegen kann.

Bei geteiltem Schlüssel wird der Token-Verbrauch pro Session protokolliert.

### 3.4 Anmeldung

E-Mail und Passwort (Argon2) in Postgres, Session-Cookie. Kein öffentlicher
Signup — Nutzer werden per CLI-Kommando angelegt. OIDC gegen einen externen
Provider wäre für einen lokalen Stack Overkill; gar kein Login würde bedeuten,
Authentifizierung später inklusive Datenmigration nachzurüsten.

## 4. Der Grill-Agent

### 4.1 Herkunft des Interviews

Der `grilling`-Skill aus `mattpocock-skills` (Lizenz: MIT, geprüft in
`.claude-plugin/plugin.json`) wird ins Repository vendort — inklusive
Copyright-Hinweis — und dann zu einer eigenen Variante weiterentwickelt. Das
Original interviewt nur; GrillMe muss am Ende zusätzlich ein Artefakt im
gewählten Format erzeugen.

### 4.2 Entscheidungsbaum

Der Baum liegt als JSON in Postgres: Knoten sind Entscheidungen mit Status
(offen / entschieden), Frage, Empfehlung und Antwort. Die Frontier — alle
Entscheidungen, deren Voraussetzungen geklärt sind — wird pro Runde neu
berechnet.

Ohne persistenten Baum verliert der Agent bei langen Sessions den Überblick über
das noch Offene und fragt im Kreis. Genau dieser Fehlermodus ist das, was die
Anwendung vermeiden soll.

### 4.3 Abschluss einer Session

Der Agent meldet, wenn die Frontier leer ist. Der Abschluss selbst ist ein
expliziter Schritt des Nutzers, der die Artefakt-Erzeugung auslöst. Ein
Sprachmodell hört zu früh auf, wenn man es allein entscheiden lässt. Nicht
bestätigte Sessions bleiben offen und wiederaufnehmbar.

Dieser Bestätigungsklick ist das Ereignis, das für die Gamification zählt.

## 5. Eingabekanäle

### 5.1 Zwei Modi, ein Verlauf

- **Text-Modus** — Diktiertes erscheint editierbar im Eingabefeld und wird
  manuell abgeschickt. Der Agent antwortet in Text.
- **Voice-Modus** — Erkannte Sprache geht direkt raus, der Agent antwortet
  zusätzlich per Sprachausgabe. Ein echtes Gespräch.

Der Modus ist **jederzeit mitten in der Session umschaltbar**. Eine Grill-Session
ist lang: zähe Denk-Passagen spricht man ein, präzise Antworten ("Q4: b") tippt
man. Ein sessionweiter Zwang schiebt den Nutzer regelmäßig in den falschen Modus.

Dass Transkripte im Text-Modus editierbar sind, ist keine Bequemlichkeit: falsch
erkannte Wörter erzeugen falsche Knoten im Entscheidungsbaum, und die kosten
später ganze Runden.

### 5.2 Sprachdialog

v1 ist **turn-based**: Sprachpausenerkennung, Audio ans Backend, Transkription,
Agent, Sprachausgabe. Rund zwei bis vier Sekunden pro Zug — bei kurzen Antworten
fühlt sich das bereits wie ein Gespräch an.

Vollduplex mit Unterbrechen des Agenten mitten im Satz ist Phase 2. Anthropic
bietet keine Realtime-Sprach-API; Transkription und Sprachausgabe müssten
getrennt gestreamt und selbst orchestriert werden. Ob sich der Aufwand lohnt,
zeigt sich erst nach einigen echten Sessions.

### 5.3 Bilder

Screenshots werden in MinIO abgelegt, bleiben dauerhaft Teil des Verlaufs und
werden bei jedem Folge-Aufruf wieder mitgeschickt. Ein Screenshot ist oft der
Kern einer Anforderung; der Agent darf ihn in Runde acht nicht vergessen haben.

Wenn Sessions so lang werden, dass die Bild-Tokens schmerzen, ist die
Optimierung, ältere Bilder durch ihre textliche Beschreibung zu ersetzen. Nicht
in v1.

### 5.4 Sprache zu Text und zurück

Beides läuft hinter Interfaces (`Transcriber`, `Speaker`) mit mehreren
austauschbaren Implementierungen — die Provider-Wahl ist eine
Konfigurationsentscheidung, kein Umbau.

**Standard ist Deepgram für beides**: Nova-3 für die Transkription, Aura-2 für
die Sprachausgabe. Ein Anbieter, ein Schlüssel, ein Guthaben ($200 zum Start,
$0,0043/Min. Transkription, $0,030/1.000 Zeichen Sprachausgabe), und Aura-2
beherrscht Deutsch.

Vorgesehene Alternativen hinter denselben Interfaces:

| Zweck | Alternative | Warum sie existiert |
|---|---|---|
| Transkription | Groq `whisper-large-v3-turbo` | dauerhaft gratis: 2.000 Requests/Tag, 7.200 Audiosekunden/Stunde; danach $0,04/h |
| Transkription | AssemblyAI Universal-3.5 Pro | beste Genauigkeit der Cloud-Anbieter (7,69 WER gegen 12,22 bei Nova-3), $50 Startguthaben ≈ 185 h |
| Transkription | faster-whisper lokal | kein Schlüssel, Audio verlässt die Maschine nicht |
| Sprachausgabe | Piper lokal | gratis und datenschutzunproblematisch, klingt synthetischer |

ElevenLabs ist ausgeschlossen: 10.000 Zeichen im Monat, keine kommerziellen
Rechte im Free-Tarif, Attributionspflicht.

Die Umschaltbarkeit ist kein Selbstzweck. Deutsch mit englischem Fachvokabular
ist der harte Fall, und welcher Anbieter ihn am besten trifft, entscheidet sich
an echten Aufnahmen, nicht an Benchmarks.

**Audio wird nach erfolgreicher Transkription gelöscht.** Nur der Text bleibt.
Sprachaufnahmen sind die heikelste Datenkategorie im System und werden danach
nicht mehr gebraucht; Löschen macht ein ganzes Datenschutzkapitel gegenstandslos,
statt es zu verwalten.

## 6. Prompt-Bibliothek und Ausgabeformate

Die Formate liegen als Einträge in Postgres. Ein Eintrag besteht aus einer
Ausgabevorlage und einem Interview-Fokus — ein Ticket-Grilling fragt nach
Akzeptanzkriterien, ein PRD-Grilling nach Zielgruppe und Hypothese.

Startset: `Spec (Markdown)`, `User Stories`, `Tickets`, `PRD`.

Der Nutzer **wählt das Format beim Anlegen der Session**. System-Einträge sind
kopierbar, nicht überschreibbar, damit eigene Varianten das Original nicht
zerstören. In v1 kommen die Einträge aus Seed-Daten; eine Verwaltungsoberfläche
entsteht erst, wenn sich zeigt, dass wirklich oft Varianten gebaut werden.

Ein voller Prompt-Baukasten mit Versionierung und Fork wäre ein eigenes Produkt
und wurde bewusst verworfen.

## 7. Gamification

Gezählt wird eine **abgeschlossene** Session — bestätigter Abschluss, erzeugtes
Artefakt. Das bloße Anlegen einer Session zählt nicht, sonst farmt man Punkte
durch Klicken.

Feste Sticker-Assets, kein generiertes Bildmaterial: das hieße dritter Anbieter,
Kosten pro Nutzer und unvorhersehbare Qualität für reine Dekoration.

Zwei Achsen, Schwellen und Namen in einer Seed-Tabelle und damit ohne
Code-Änderung anpassbar:

- Abgeschlossene Sessions: 1 / 5 / 10 / 25 / 50 — `Anzünder`, `Kohlenflüsterer`,
  `Grillmeister`, …
- Beantwortete Fragen: 50 / 250 / 1000

## 8. Datenschutz

Die technischen Voraussetzungen werden in v1 mitgebaut, der Papierkram entsteht
beim Hosting.

In v1 enthalten:

- Kontolöschung kaskadiert über alle Daten, ausdrücklich einschließlich der
  MinIO-Objekte
- Session-Export als JSON
- Audio-Löschung nach Transkription (siehe 5.4)
- Verarbeitungsverzeichnis als gepflegtes Dokument im Repository

Beim Hosting nachzuziehen: Auftragsverarbeitungsverträge mit allen
Auftragsverarbeitern (Anthropic, Transkription, Sprachausgabe),
Datenschutzerklärung, technische und organisatorische Maßnahmen,
Drittlandtransfer-Dokumentation.

Löschung und Export nachträglich einzubauen ist teuer, weil sie jedes Schema und
jeden Storage-Pfad berühren. Als Randbedingung von Anfang an kosten sie fast
nichts.

**Warnung zu Free-Tarifen:** Kostenlose Kontingente erlauben Anbietern
typischerweise die Nutzung der übermittelten Daten zum Training und kommen ohne
Auftragsverarbeitungsvertrag. Für den Einzelbetrieb unerheblich; für jeden
Betrieb mit fremden Nutzern sind bezahlte Tarife Pflicht. Das ist derselbe
Schnitt wie bei den Claude-Credentials in 3.3 — beide Schalter werden gemeinsam
umgelegt.

## 9. Datenmodell (Skizze)

| Tabelle | Zweck | Bemerkung |
|---|---|---|
| `user` | Konto | Argon2-Hash, optional verschlüsselter `anthropic_api_key` |
| `session` | Grill-Session | Besitzer, Format-Referenz, Status, Abschlusszeitpunkt |
| `message` | Verlauf | Rolle, Text, Modus (Text/Voice), Bildreferenzen |
| `decision_node` | Entscheidungsbaum | Frage, Empfehlung, Antwort, Status, Elternknoten |
| `image` | Screenshots | MinIO-Objektschlüssel, Session-Referenz |
| `prompt_template` | Bibliothek | Ausgabevorlage, Interview-Fokus, System-Flag |
| `artifact` | Ergebnis | erzeugtes Markdown, Tickets |
| `achievement` | Gamification | Schwellen und Titel als Seed-Daten |
| `token_usage` | Kostenkontrolle | pro Session, bei geteiltem Schlüssel unverzichtbar |

Jede nutzerbezogene Tabelle trägt von Anfang an eine `user_id`, auch solange nur
ein Nutzer existiert.

## 10. Bewusst auf Phase 2 verschoben

- Vollduplex-Sprachdialog mit Unterbrechen (siehe 5.2)
- Ticket-Erzeugung direkt in GitHub Issues; v1 exportiert Markdown-Dateien
- Verwaltungsoberfläche für die Prompt-Bibliothek
- Ersetzen alter Bilder durch textliche Beschreibungen zur Token-Ersparnis
- Mehrbenutzerbetrieb und Hosting, gekoppelt an den Wechsel auf API-Schlüssel

## 11. Quellen der Recherche

- [ag-ui claude-agent-sdk Integration](https://github.com/ag-ui-protocol/ag-ui/tree/main/integrations/claude-agent-sdk)
- [CopilotKit AG-UI](https://docs.copilotkit.ai/agentic-protocols/ag-ui)
- [Deepgram Preise](https://deepgram.com/pricing)
- [Groq Free-Tier-Limits](https://www.grizzlypeaksoftware.com/articles/p/groq-api-free-tier-limits-in-2026-what-you-actually-get-uwysd6mb)
- [AssemblyAI Startguthaben](https://costbench.com/software/ai-transcription-apis/assemblyai/free-plan/)
- [STT-Benchmarks 2026 (Coval)](https://www.coval.ai/blog/best-speech-to-text-providers-in-2026-independent-benchmarks-and-how-to-choose/)
- [ElevenLabs Preise und Rechte 2026](https://bigvu.tv/blog/elevenlabs-pricing-2026-plans-credits-commercial-rights-api-costs/)
- [Selbst gehostete TTS-Modelle 2026](https://www.sevenlabs.site/blogs/best-self-hosted-tts-models-2026)
