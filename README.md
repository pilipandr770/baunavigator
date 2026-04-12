# BauNavigator

**KI-gestützter Assistent für privates Bauen und Immobilienerwerb in Deutschland**

> MVP-Region: Hessen · Stack: Python / Flask · KI: Claude (Anthropic) · Stand: April 2026

---

## Inhaltsverzeichnis

1. [Projektbeschreibung](#1-projektbeschreibung)
2. [Ziele](#2-ziele)
3. [Funktionsumfang (aktueller Stand)](#3-funktionsumfang-aktueller-stand)
4. [Technische Architektur](#4-technische-architektur)
5. [KI-Architektur](#5-ki-architektur)
6. [Datenmodell](#6-datenmodell)
7. [Schnellstart (lokale Entwicklung)](#7-schnellstart-lokale-entwicklung)
8. [Deployment auf Render.com](#8-deployment-auf-rendercom)
9. [Umgebungsvariablen](#9-umgebungsvariablen)
10. [Entwicklungs-Roadmap](#10-entwicklungs-roadmap)

---

## 1. Projektbeschreibung

BauNavigator ist eine webbasierte SaaS-Plattform, die Privatpersonen beim gesamten Prozess des Hausbaus oder Immobilienerwerbs in Deutschland begleitet — von der ersten Grundstückssuche bis zur Schlüsselübergabe.

Das System kombiniert:
- **KI-Beratung** (Claude API) für behördliche Schreiben, Genehmigungsanträge und Finanzierungsfragen
- **Projektverwaltung** mit klaren Bauphasen und Aufgaben-Tracking
- **Interaktive Karte** mit Grundstücksrecherche und Zonierungsdaten
- **Dienstleister-Marktplatz** (Architekten, Notare, Banken, Handwerker) inkl. Bewertungen und Terminbuchung
- **Automatisierte Benachrichtigungen** bei Gesetzesänderungen, Deadlines und Projektfortschritten
- **Baukamera-Monitoring** via RTSP und Telegram-Bot
- **E-Mail-Ausgangskorb** für rechtssichere Kommunikation mit Behörden

Die Plattform richtet sich primär an Privatbauherren ohne Vorwissen im deutschen Baurecht und Behördenwesen.

---

## 2. Ziele

| Ziel | Beschreibung |
|------|-------------|
| **Zugänglichkeit** | Komplexe Bau- und Behördenprozesse für Laien verständlich und beherrschbar machen |
| **Zeitersparnis** | Automatische Erstellung von Anträgen, Briefen und Checklisten statt stundenlanger Recherche |
| **Rechtssicherheit** | KI-Antworten werden mit aktuellem Baurecht abgeglichen; alle Aktionen werden protokolliert |
| **Transparenz** | Vollständige Nachverfolgung aller KI-Aktionen und ausgehenden Dokumente |
| **Monetarisierung** | Freemium-Modell (Free / Pro / Expert) + Provisionen vom Dienstleister-Marktplatz |
| **Skalierbarkeit** | Start in Hessen, geplante Ausweitung auf alle 16 Bundesländer |

---

## 3. Funktionsumfang (aktueller Stand)

### Implementiert (MVP)

#### Nutzer & Authentifizierung
- Registrierung, Login, E-Mail-Bestätigung
- Abonnement-Verwaltung (Free / Pro / Expert) mit Stripe-Integration
- Mehrsprachigkeit (Standardsprache: Deutsch)

#### Projektverwaltung
- Projekttypen: Neubau EFH, Neubau MFH, Umbau/Sanierung, Anbau, Kauf Bestandsimmobilie
- Strukturierte Bauphasen (Vorbereitung -> Planung -> Genehmigung -> Bau -> Abschluss)
- Aufgaben-Tracking pro Phase mit Status-Verwaltung
- Onboarding-Assistent für neue Projekte
- Druckbare Projektübersicht (PDF-ready)

#### KI-Assistent
- Kontextbewusste Beratung auf Basis des aktuellen Projektstatus
- Drei Aktionsmodi: `autonomous` / `confirmation_required` / `human_required`
- Automatische Erstellung von Behörden-E-Mails und Antragsschreiben
- Vollständiges Aktionsprotokoll (`ai_actions_log`)
- Rechtliche Wissensbasis mit automatischen Updates (`law_sources`, `law_update_logs`)

#### Karte & Grundstücke
- Interaktive Karte (Hessen) mit Grundstücks-Pins
- Grundstückstypen: Kauf, Miete/Pacht, Erbbaurecht, Kommunales Wohnbauland
- Zonentypen und Bebauungspläne
- Eigene Grundstücke des Nutzers verwalten

#### Dienstleister-Portal
- Kategorien: Architekt, Notar, Bank, Handwerker, Gutachter u. a.
- Anbieter-Registrierung mit Verifizierungsprozess
- Bewertungssystem (Sterne, Freitext)
- Terminslots und Lead-Verwaltung
- Eigenes Provider-Admin-Panel (Login, Dashboard, Profil, Chatbot, Slots, Leads)

#### Kommunikation & Benachrichtigungen
- Ausgangskorb für Behördenbriefe und Anträge
- Benachrichtigungstypen: Phasenwechsel, Gesetzesänderung, Finanzalarm, fehlende Dokumente, Deadline, Kamerabericht
- E-Mail-Versand via SMTP (Flask-Mail)
- Telegram-Bot-Integration für Kameraberichte und Statusupdates

#### Finanzierung
- Finanzierungsrechner (Tilgungsplan-Generator)
- Finanzierungsstatus-Tracking
- Integration in Projektphasen

#### Baukamera-Monitoring
- RTSP (IP-Kamera / ONVIF) und Telegram-Kameratypen
- Snapshot-Archiv
- Automatische Berichte

#### Admin-Panel
- Nutzer-, Anbieter- und Lead-Verwaltung
- Gesetzesupdate-Protokoll
- Systemstatistiken

---

## 4. Technische Architektur

```
baunavigator/
├── app/
│   ├── models/
│   │   ├── enums.py          # Alle Enum-Typen (StageKey, ActionMode, ...)
│   │   └── models.py         # SQLAlchemy-Modelle (15+ Tabellen)
│   ├── routes/
│   │   ├── auth.py           # Registrierung / Login
│   │   ├── dashboard.py      # Nutzerdashboard
│   │   ├── project.py        # Projekte & Bauphasen
│   │   ├── map.py            # Karte & Grundstücke
│   │   ├── providers.py      # Dienstleister-Marktplatz
│   │   ├── provider_admin.py # Provider-Self-Service-Portal
│   │   ├── ai.py             # KI-Endpunkte
│   │   ├── notifications.py  # Benachrichtigungen
│   │   ├── outbox.py         # Ausgangskorb
│   │   ├── legal.py          # Impressum / AGB / Datenschutz
│   │   ├── webhooks.py       # Stripe & externe Webhooks
│   │   ├── telegram_bot.py   # Telegram-Bot-Handler
│   │   └── admin.py          # Admin-Panel
│   ├── services/
│   │   ├── ai_service.py         # Claude API Integration
│   │   ├── agents.py             # KI-Agenten-Logik
│   │   ├── law_agent.py          # Rechtsmodul (automatische Updates)
│   │   ├── notification_service.py # Push- & E-Mail-Benachrichtigungen
│   │   ├── scheduler.py          # Hintergrundaufgaben (APScheduler)
│   │   ├── camera_service.py     # RTSP-Kamera-Integration
│   │   ├── browser_tools.py      # Web-Scraping-Hilfsmittel
│   │   └── gmail_service.py      # Gmail OAuth-Versand
│   ├── templates/            # Jinja2-Templates (HTML)
│   └── static/               # CSS, JS, Bilder, Snapshots
├── migrations/               # Alembic-Datenbankmigrationen
├── run.py                    # Anwendungs-Einstiegspunkt
├── seed_data.py              # Testdaten
├── requirements.txt
├── Dockerfile
└── render.yaml
```

**Tech-Stack:**

| Komponente | Technologie |
|-----------|------------|
| Backend | Python 3.12, Flask 3.0 |
| Datenbank | PostgreSQL 15 + PostGIS |
| ORM | SQLAlchemy 2.0, Flask-Migrate (Alembic) |
| KI | Anthropic Claude API |
| Geodaten | GeoAlchemy2, Shapely |
| Hintergrundaufgaben | APScheduler |
| Payments | Stripe |
| E-Mail | Flask-Mail (SMTP) / Gmail OAuth |
| Deployment | Render.com, Docker |
| Frontend | Jinja2, Vanilla JS, CSS |

---

## 5. KI-Architektur

Der KI-Assistent arbeitet in drei Aktionsmodi (`ActionMode`):

| Modus | Verhalten |
|-------|-----------|
| `autonomous` | Führt die Aktion selbstständig aus und zeigt das Ergebnis |
| `confirmation_required` | Erstellt einen Entwurf und wartet auf Nutzerfreigabe |
| `human_required` | Erklärt, warum ein Experte benötigt wird, und schlägt Dienstleister vor |

- Alle KI-Aktionen werden vollständig in `ai_actions_log` protokolliert
- Alle ausgehenden Dokumente durchlaufen den `messages_outbox`-Workflow
- Das Rechtsmodul (`law_agent`) überwacht automatisch Änderungen im Baurecht und benachrichtigt betroffene Nutzer
- Die KI-Agenten (`agents.py`) sind modular aufgebaut und ermöglichen zukünftige Erweiterung um spezialisierte Agenten

---

## 6. Datenmodell

Wichtigste Tabellen (15+):

| Tabelle | Beschreibung |
|---------|-------------|
| `users` | Nutzerkonten, Abonnementstufe, Sprache |
| `subscriptions` | Stripe-Abonnements |
| `projects` | Bauprojekte mit Typ und Status |
| `project_stages` | Bauphasen je Projekt |
| `ai_actions_log` | Vollprotokoll aller KI-Aktionen |
| `messages_outbox` | Ausgehende Briefe und Anträge |
| `providers` | Dienstleister-Verzeichnis |
| `provider_reviews` | Bewertungen |
| `leads` | Anfragen an Dienstleister |
| `gemeinden` | Gemeindeverzeichnis mit Bauamt-Kontakten |
| `parcels` | Grundstücke auf der Karte |
| `law_sources` | Rechtsquellen für KI-Kontext |
| `law_update_logs` | Protokoll der Rechtsänderungen |
| `notifications` | Nutzerbenachrichtigungen |
| `cameras` | Baukameras je Projekt |

---

## 7. Schnellstart (lokale Entwicklung)

```bash
# 1. Repository klonen und in Verzeichnis wechseln
git clone <repo-url>
cd baunavigator

# 2. Virtuelle Umgebung erstellen
python -m venv .venv
.venv\Scripts\activate   # Windows
# oder: source .venv/bin/activate  (Linux/macOS)

# 3. Abhängigkeiten installieren
pip install -r requirements.txt

# 4. Umgebungsvariablen konfigurieren
cp .env.example .env
# .env mit eigenen Werten befüllen (siehe Abschnitt 9)

# 5. Datenbank initialisieren
flask db upgrade

# 6. Testdaten laden (optional)
python seed_data.py

# 7. Server starten
flask run
```

### Gemeinde-Stammdaten anlegen

```python
flask shell
>>> from app import db
>>> from app.models import Gemeinde
>>> g = Gemeinde(
...     name='Frankfurt am Main',
...     land='HE',
...     landkreis='kreisfrei',
...     ags_code='06412000',
...     bauamt_email='bauaufsicht@stadt-frankfurt.de',
...     bauamt_url='https://www.bauaufsicht-frankfurt.de'
... )
>>> db.session.add(g)
>>> db.session.commit()
```

---

## 8. Deployment auf Render.com

1. Neuen **Web Service** aus GitHub-Repository erstellen
2. **Build command:** `pip install -r requirements.txt`
3. **Start command:** `gunicorn --bind 0.0.0.0:$PORT --workers 2 run:app`
4. Umgebungsvariablen aus `.env.example` hinzufügen
5. Nach erstem Deploy: `flask db upgrade` (via Render Shell)

Die `render.yaml` enthält eine fertige Render-Blueprint-Konfiguration.

Docker-Build lokal testen:

```bash
docker build -t baunavigator .
docker run -p 5000:5000 --env-file .env baunavigator
```

---

## 9. Umgebungsvariablen

| Variable | Pflicht | Beschreibung |
|----------|---------|-------------|
| `DATABASE_URL` | ja | PostgreSQL-Verbindungs-URL (Render.com oder lokal) |
| `SECRET_KEY` | ja | Zufälliger String, min. 32 Zeichen |
| `ANTHROPIC_API_KEY` | ja | Claude API-Schlüssel (console.anthropic.com) |
| `MAIL_SERVER` | ja | SMTP-Hostname (z. B. `smtp.gmail.com`) |
| `MAIL_PORT` | ja | SMTP-Port (587 für TLS) |
| `MAIL_USERNAME` | ja | Absender-E-Mail-Adresse |
| `MAIL_PASSWORD` | ja | SMTP-Passwort oder App-Passwort |
| `STRIPE_SECRET_KEY` | nein | Stripe-Geheimschlüssel (für Abonnements) |
| `STRIPE_WEBHOOK_SECRET` | nein | Stripe-Webhook-Signaturschlüssel |
| `TELEGRAM_BOT_TOKEN` | nein | Telegram-Bot-Token (BotFather) |

---

## 10. Entwicklungs-Roadmap

### Phase 1 — MVP Hessen (aktuell, Q1-Q2 2026)
- [x] Nutzerverwaltung & Authentifizierung
- [x] Projektverwaltung mit Bauphasen
- [x] KI-Assistent (Behörden-E-Mails, Beratung)
- [x] Grundstückskarte (Hessen)
- [x] Dienstleister-Marktplatz (Basis)
- [x] Benachrichtigungssystem
- [x] Baukamera-Integration (RTSP + Telegram)
- [x] Finanzierungsrechner & Tilgungsplan
- [x] Ausgangskorb für Behördenkommunikation
- [x] Admin-Panel
- [x] Stripe-Abonnements (Free / Pro / Expert)

### Phase 2 — Ausbau & Qualität (Q3 2026)
- [ ] Vollständige Testabdeckung (pytest, >80 %)
- [ ] Erweiterte Geodaten: Bebauungspläne-Overlay (WMS/WFS)
- [ ] Dokumenten-Upload und -Verwaltung je Projektetappe
- [ ] OCR-Auswertung von Baugenehmigungen und Beschlüssen
- [ ] Mehrsprachigkeit: EN, TR, RU (neben DE)
- [ ] Mobile-optimiertes UI (PWA)
- [ ] Öffentliche API (REST) für Partnerintegrationen

### Phase 3 — Skalierung auf Deutschland (Q4 2026)
- [ ] Alle 16 Bundesländer inkl. länderspezifisches Baurecht
- [ ] Automatisierte Bauamts-Posteingangserkennung per E-Mail
- [ ] Notarielle Dokumenten-Workflows (eIDAS)
- [ ] KI-Bauleiter: automatische Baufortschritts-Auswertung via Kamera
- [ ] KfW-/BAFA-Fördermittel-Assistent
- [ ] White-Label für Bauträger und Banken

### Phase 4 — Marktplatz & Ökosystem (2027)
- [ ] Integrations-Marketplace (Hausplaner, ERP, CAD-Tools)
- [ ] Community-Forum & Erfahrungsberichte
- [ ] Versicherungsvergleich und -abschluss im Plattformkontext
- [ ] Nachhaltigkeits-Score und Energie-Berechnungen (GEG)
- [ ] Expansion Österreich / Schweiz

---

## Lizenz

Proprietär — alle Rechte vorbehalten. Nutzung nur mit ausdrücklicher Genehmigung.

---

*BauNavigator — Weil Hausbau kompliziert genug ist.*