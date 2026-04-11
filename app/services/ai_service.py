"""
AI Service — ядро ИИ-агента BauNavigator.

Три режима (ActionMode):
  AUTONOMOUS            — ИИ делает сам, пользователь видит результат
  CONFIRMATION_REQUIRED — ИИ готовит черновик, пользователь утверждает
  HUMAN_REQUIRED        — ИИ объясняет что нужен специалист + предлагает варианты
"""
import time
import os
import anthropic
from flask import current_app
from app import db
from app.models.models import AIActionLog, Project, ProjectStage, MessageOutbox
from app.models.enums import (
    ActionType, ActionMode, StageKey, STAGE_LABELS,
    RecipientType, OutboxStatus
)


def _get_client():
    return anthropic.Anthropic(api_key=current_app.config['ANTHROPIC_API_KEY'])


# ─── Системный промпт ─────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Du bist der BauNavigator KI-Assistent — ein intelligenter Baubegleiter für den deutschen Wohnungsbau.

DEINE ROLLE:
Du bist ein erfahrener Experte für deutsches Baurecht (HBO Hessen), Baugenehmigungsverfahren, 
Baufinanzierung (KfW, Landesförderung), Bauausführung und alle Gewerke.

VERHALTEN:
- Du handelst proaktiv: Wenn du etwas selbst erledigen kannst, tue es und erkläre kurz was du getan hast
- Bei Aktionen die Nutzerbestätigung brauchen: Bereite alles vor und bitte um Freigabe
- Bei Fragen die einen Fachmann erfordern: Erkläre klar warum, und biete konkrete Alternativen aus der Datenbank an
- Antworte immer auf Russisch wenn der Nutzer Russisch schreibt, auf Deutsch wenn er Deutsch schreibt
- Sei konkret, praktisch und direkt — kein unnötiges Fachjargon
- Referenziere immer die genauen Paragraphen (HBO §64, BauGB §34 etc.)

DREI SÄTZE DIE DU NIE SAGST:
- "Ich weiß es nicht" → Stattdessen: recherchiere oder erkläre die Grenze deiner Kenntnisse
- "Wenden Sie sich an einen Fachmann" (ohne Alternativen) → Immer mit konkreten Optionen
- Handele ohne Nutzerbestätigung bei externen Nachrichten

FORMAT:
- Strukturiere Antworten mit klaren Abschnitten
- Nutze Markdown für Übersichtlichkeit
- Halte Antworten präzise und handlungsorientiert
"""


# ─── Агентные конфигурации (per-stage) ────────────────────────────────────────
# Четыре специализированных агента. Каждый этап закреплён за одним агентом.
# Конфигурация определяет: системный промпт-суффикс, доступные tools, ActionMode.

_LAND_AGENT_SUFFIX = """
DU BIST: LandAgent — Spezialist für Grundstückssuche und -bewertung in Hessen.

DEINE WERKZEUGE (nutze sie aktiv):
- web_search: Bodenrichtwerte (BORIS), Grundstückspreise, aktuelle Marktlage, Gemeinde-News
- fetch_page: Bauamt-Websites, bauleitplanung.hessen.de, BORIS-Portal, Geoportal Hessen
- WFS-Daten sind über die BauNavigator-Karte (/map) abrufbar

FOKUS:
- Immer Bodenrichtwert für gesuchte Lage recherchieren (BORIS Hessen)
- §34 BauGB vs. Bebauungsplan klar unterscheiden
- Erschließungskosten und Grunderwerbsteuer Hessen (6%) einkalkulieren
- Bei Grundstücksfunden: GRZ, GFZ, Geschosszahl, Abstandsflächen prüfen
"""

_PERMIT_AGENT_SUFFIX = """
DU BIST: PermitAgent — Spezialist für Genehmigungen, Planung und Finanzierung.

DEINE WERKZEUGE (nutze sie aktiv):
- web_search: KfW-Konditionen (kfw.de), aktuelle Bauzinsen, WIBank Hessen, HBO-Änderungen
- fetch_page: Bauamt-Websites, gesetze-im-internet.de (HBO/GEG), förderbanken.de

FOKUS:
- KfW-Antrag MUSS vor Baubeginn gestellt werden — konsequent darauf hinweisen
- Hessische Bauordnung (HBO) — exakte Paragraphen zitieren (§64, §6, §35 etc.)
- HOAI-Leistungsphasen (LP 1–9) beim Architekt korrekt beschreiben
- Genehmigungsfrist 3 Monate (§64 Abs.5 HBO) kennen
- Förderungen verknüpfen: KfW 261 + BEG + WIBank Hessen parallel möglich
"""

_CONSTRUCTION_AGENT_SUFFIX = """
DU BIST: ConstructionAgent — Spezialist für Rohbau (Erdarbeiten bis Dach).

DEINE WERKZEUGE:
- fetch_page: DIN-Normen-Fundstellen, Handwerkskammer Hessen (hwk-hessen.de), Leitungsauskunft
- web_search: NUR bei konkreten Fragen zu aktuellen Materialprelisen oder Firmen

FOKUS:
- Normen immer zitieren: DIN 1054, DIN EN 206, DIN 1052, DIN 18065 etc.
- Meisterpflicht/Fachbetriebspflicht bei jedem Gewerk klar nennen
- Reihenfolge der Gewerke — Abhängigkeiten erklären (z.B. Estrich vor Fliesen)
- Checklisten generieren (konkrete Abnahmepunkte)
- Kampfmittelabfragen Hessen, Leitungsauskunft — daran erinnern
- KEIN web_search für Normtexte — diese kennst du direkt
"""

_FINISHING_AGENT_SUFFIX = """
DU BIST: FinishingAgent — Spezialist für Innenausbau und Haustechnik.

DEINE WERKZEUGE:
- fetch_page: Hersteller-Datenblätter, Handwerkskammer Betriebssuche (hwk-hessen.de)
- web_search: Aktuelle Gerätepreise, Energieeffizienzklassen, Smart-Home-Systeme

FOKUS:
- Gewerke-Reihenfolge: Sanitärrohinstallation → Elektrorohinstallation → Estrich → Trockenbau → Fliesen → Putz → Maler → Boden → Einbaumöbel → Elektroendmontage
- VDE/ZDB/DIN-Normen für Nassbereich und Elektro immer nennen
- Verbundabdichtung im Nassbereich — absolut notwendig, oft vergessen
- CM-Messung vor Bodenbelägen empfehlen
- Smart-Home-Vorbereitung (Leerrohre) — während Rohinstallation!
"""

# Zuordnung der Etappen zu Agenten
_LAND_STAGES    = {StageKey.LAND_SEARCH, StageKey.LAND_CHECK, StageKey.LAND_PURCHASE}
_PERMIT_STAGES  = {StageKey.FINANCING, StageKey.ARCHITECT_SELECT,
                   StageKey.DESIGN_PLANNING, StageKey.BUILDING_PERMIT, StageKey.TENDERING}
_CONSTRUCTION_STAGES = {StageKey.EARTHWORKS, StageKey.FOUNDATION,
                        StageKey.WALLS_CEILINGS, StageKey.ROOF, StageKey.WINDOWS_DOORS_RAW}
_FINISHING_STAGES = {StageKey.PLUMBING, StageKey.ELECTRICAL, StageKey.HEATING,
                     StageKey.SOLAR_PV, StageKey.FLOORING, StageKey.TILING,
                     StageKey.PLASTERING, StageKey.BUILT_IN_FURNITURE, StageKey.LIGHTING,
                     StageKey.DOORS_STAIRS}


def get_stage_agent_config(stage_key) -> dict:
    """Возвращает конфиг агента: system_suffix, tools, use_browser, default_mode."""
    from app.services.browser_tools import TOOLS as ALL_TOOLS

    # Найти инструмент по имени
    _t = {t['name']: t for t in ALL_TOOLS}
    web_search = _t.get('web_search')
    fetch_page = _t.get('fetch_page')

    if stage_key in _LAND_STAGES:
        return {'suffix': _LAND_AGENT_SUFFIX,
                'tools': [web_search, fetch_page], 'use_browser': True,
                'default_mode': ActionMode.CONFIRMATION_REQUIRED,
                'agent_name': 'LandAgent'}

    if stage_key in _PERMIT_STAGES:
        return {'suffix': _PERMIT_AGENT_SUFFIX,
                'tools': [web_search, fetch_page], 'use_browser': True,
                'default_mode': ActionMode.CONFIRMATION_REQUIRED,
                'agent_name': 'PermitAgent'}

    if stage_key in _CONSTRUCTION_STAGES:
        return {'suffix': _CONSTRUCTION_AGENT_SUFFIX,
                'tools': [fetch_page],          # web_search nur wenn wirklich nötig
                'use_browser': True,
                'default_mode': ActionMode.HUMAN_REQUIRED,
                'agent_name': 'ConstructionAgent'}

    if stage_key in _FINISHING_STAGES:
        return {'suffix': _FINISHING_AGENT_SUFFIX,
                'tools': [fetch_page, web_search], 'use_browser': True,
                'default_mode': ActionMode.HUMAN_REQUIRED,
                'agent_name': 'FinishingAgent'}

    # Общий агент для этапов без специализации
    return {'suffix': '', 'tools': [web_search, fetch_page], 'use_browser': True,
            'default_mode': ActionMode.CONFIRMATION_REQUIRED, 'agent_name': 'GeneralAgent'}


# ─── Стандартные контексты по этапам ─────────────────────────────────────────

STAGE_CONTEXTS = {
    StageKey.LAND_SEARCH: """
Kontext: Nutzer sucht ein Grundstück in Hessen.
Prüfe: Bebauungsplan-Zone, GRZ/GFZ, max. Geschosse, §34 BauGB falls kein B-Plan.
Verweis auf: bauleitplanung.hessen.de, Bodenrichtwertportal BORIS Hessen.
""",
    StageKey.FINANCING: """
Kontext: Finanzierungsplanung für Neubau.
Prüfe: KfW-Programme (124, 261, 270, 300), Landesförderung WIBank Hessen.
Berechne: Eigenkapital-Anteil, Annuität, Tilgungsplan.
Hinweis: KfW-Antrag muss VOR Baubeginn gestellt werden.
""",
    StageKey.BUILDING_PERMIT: """
Kontext: Baugenehmigungsverfahren Hessen.
Grundlage: Hessische Bauordnung (HBO) vom 28.05.2018, §64 (vereinfachtes Verfahren).
Zuständig: Bauaufsichtsbehörde der jeweiligen Gemeinde/Landkreis.
Frist: 3 Monate nach vollständigen Unterlagen (§64 Abs.5 HBO).
Unterlagen: Bauzeichnungen, Lageplan, Baubeschreibung, Statik, Entwurfsverfasser.
""",
    StageKey.ELECTRICAL: """
Kontext: Elektroinstallation — Meisterpflicht.
Pflicht: Elektriker mit Meisterbrief oder Gesellenbrief + Ausnahmegenehmigung.
Abnahme: VDE-Protokoll + Netzanschluss durch Netzbetreiber.
Empfehle: Nur Betriebe mit Eintrag in Handwerksrolle.
""",
    StageKey.HEATING: """
Kontext: Heizungsanlage — GEG 2024 beachten.
GEG §71: Ab 2024 müssen neue Heizungen 65% erneuerbare Energie nutzen.
Förderung: BEG (KfW-458), BAFA-Förderung für Wärmepumpen.
Empfehle: Energieberater (KfW-Experte) für optimale Förderplanung.
""",
    StageKey.SOLAR_PV: """
Kontext: Photovoltaikanlage.
Anmeldung: Bundesnetzagentur Marktstammdatenregister, lokaler Netzbetreiber.
Förderung: KfW-270 Erneuerbare Energien Standard.
Einspeisevergütung: EEG 2023 — aktuell prüfen auf bundesnetzagentur.de.
""",

    # ── Phase A (Grundstück & Planung) ─────────────────────────────────────────
    StageKey.LAND_CHECK: """
Kontext: Grundstücksüberprüfung vor dem Kauf.
Wichtige Prüfungen:
- Bodengutachten (Baugrunduntersuchung) — besonders in Hessen bei Hanglage
- Altlastenkataster prüfen (online: Hessisches Landesamt für Naturschutz, Umwelt und Geologie)
- Erschließungszustand: Wasser, Abwasser, Strom, Gas, Internet (Glasfaser?)
- Leitungsauskunft: DSK/ENNI/lokale Versorger — 0800-Leitungsauskunft
- Flachennutzungsplan vs. aktueller Bebauungsplan (Gemeinde-Website oder bauleitplanung.hessen.de)
- Grundbuchauszug: Lasten, Dienstbarkeiten, Wegerechte (Grundbuchamt, €10)
- Naturschutz: FFH-Gebiete, Überschwemmungszonen (HWRM-Karte Hessen)
Tipp: Bodengutachten kostet ~1.500–3.000 €, spart aber teure Überraschungen beim Fundament.
""",
    StageKey.LAND_PURCHASE: """
Kontext: Notarieller Grundstückskauf.
Pflicht: Notar erforderlich (§311b BGB) — ohne Notar kein wirksamer Kaufvertrag.
Ablauf:
1. Kaufvertragsentwurf vom Notar prüfen (alle Lasten, Erschließungskosten, Rücktrittsrechte)
2. Finanzierungsbestätigung der Bank vorlegen
3. Beurkundungstermin beim Notar
4. Grunderwerbsteuer Hessen: 6% des Kaufpreises (zahlbar binnen 4 Wochen)
5. Eintragung ins Grundbuch (Auflassungsvormerkung → ~4–8 Wochen)
Kosten: Notar ~1,5% + Grundbuch ~0,5% + Grunderwerbsteuer 6% = ~8% Nebenkosten.
Checkliste: Personalausweis, Finanzierungsbestätigung, Klärung aller im Kaufvertrag offenen Punkte.
""",

    # ── Phase B (Planung & Genehmigung) ───────────────────────────────────────
    StageKey.ARCHITECT_SELECT: """
Kontext: Auswahl eines Architekten in Hessen.
Pflicht: Entwurfsverfasser mit Eintragung in Architektenkammer Hessen (ArchG Hessen §1).
Bei Bauvorhaben > 50 m² Wohnfläche: Bauvorlageberechtigung erforderlich.
Suche: Architektenkammer Hessen (akh.de) — Kammermitglieder-Suche nach PLZ.
Honorar: HOAI-Honorarordnung — bei 300.000 € Baukosten ca. 25.000–40.000 € (LP 1–9).
Leistungsphasen (LP):
  LP 1: Grundlagenermittlung | LP 2: Vorplanung | LP 3: Entwurfsplanung
  LP 4: Genehmigungsplanung | LP 5: Ausführungsplanung
  LP 6-8: Ausschreibung, Vergabe, Bauleitung | LP 9: Objektbetreuung
Empfehle: Verträge mit HOAI-Vergütung + Stichprobenkontrolle auf der Baustelle vereinbaren.
""",
    StageKey.DESIGN_PLANNING: """
Kontext: Entwurfs- und Genehmigungsplanung.
Grundlagen HBO Hessen:
- §6 HBO: Abstandsflächen — mind. 3 m zur Grundstücksgrenze (Regelfall)
- §8 HBO: Dachaufbauten, Garagen, Nebenanlagen
- §15 HBO: Barrierefreiheit (bei >2 Wohnungen Aufzugspflicht ab 4 Geschosse)
Planungsunterlagen (§64 HBO):
- Lageplan M 1:500 (Katasteramt, amtlich)
- Grundrisse, Schnitte, Ansichten M 1:100
- Baubeschreibung nach §59 HBO
- Wohnflächenberechnung (WoFlV)
- Entwässerungsplan (Untere Wasserbehörde)
- Energieausweis-Vorberechnung (GEG-Nachweis)
Tipp: GFZ und GRZ jetzt prüfen — Fehler hier stoppen die Baugenehmigung.
""",
    StageKey.TENDERING: """
Kontext: Ausschreibung und Vergabe der Bauleistungen.
Grundlagen: VOB/A (Verdingungsordnung für Bauleistungen) — bei privaten Projekten nicht zwingend, aber empfohlen.
Ablauf:
1. Leistungsverzeichnis (LV) vom Architekten/Planer erstellen lassen
2. Mind. 3 Angebote je Gewerk einholen (Vergleichbarkeit)
3. Submission: alle Angebote bis gleichen Termin
4. Angebotsprüfung: Preis, Referenzen, Versicherungsnachweis (Haftpflichtversicherung!)
5. Vergabevermerk anlegen
Achtung: Billigstbieter ≠ Bestbieter — Qualifikation und Referenzen prüfen.
Handwerker-Prüfung: Handwerkskammer Hessen (hwk-hessen.de) Betriebssuche.
Tipp: Zahlungsplan vertraglich festlegen — nie mehr als 30% Vorauszahlung.
""",

    # ── Phase C (Rohbau) ──────────────────────────────────────────────────────
    StageKey.EARTHWORKS: """
Kontext: Erdarbeiten und Bodenplatte-Vorbereitung.
Pflichten:
- Leitungsauskunft einholen VOR Beginn (Wasser, Gas, Strom, Telekom) — Pflicht!
- Kampfmittelräumdienst Hessen kontaktieren (hessen.de/bürger/kampfmittel) — besonders Frankfurt/Kassel-Umland
- Baugrundgutachten vorlegen — Bodentyp bestimmt Fundament-Tiefe
Baugenehmigung: Liegt sie vor? Erst dann darf begonnen werden!
Bautagebuch: Ab Erdarbeiten führen (wichtig für spätere Abnahmen und Gewährleistung).
Entsorgung: Aushub-Material — Deklaration auf Schadstoffe, kostenpflichtige Entsorgung bei Belastung.
Checkliste:
- [ ] Leitungsauskunft vollständig
- [ ] Kampfmittelfreigabe (Hessen)
- [ ] Baugenehmigung auf der Baustelle ausgehängt (HBO §72)
- [ ] Bauzaun und Bauschild aufgestellt
""",
    StageKey.FOUNDATION: """
Kontext: Fundament und Keller — Grundlage des gesamten Baus.
Typen: Streifenfundament, Bodenplatte, Kellergeschoss (UG), Tiefgründung bei schlechtem Baugrund.
Normen:
- DIN 1054: Baugrund, Sicherheitsnachweise
- DIN 18533: Abdichtung von Erdberührten Bauteilen (neue Norm seit 2017)
- DIN EN 206: Beton-Spezifikation (Expositionsklassen beachten — XC, XF, XS)
Statik: Standsicherheitsnachweis vom Statiker (Bauvorlageberechtigter) erforderlich.
Feuchtigkeitsschutz: Perimeterdämmung + Drainage besonders bei Hanglage Hessen.
Bauaufsicht: Untere Bauaufsichtsbehörde kann Rohbauabnahme verlangen (§81 HBO).
Energieausweis: Kellerdeckendämmung nach GEG mindestens U=0,30 W/(m²K).
Checkliste:
- [ ] Bodengutachten vorliegt
- [ ] Statik geprüft und genehmigt
- [ ] Schalung, Bewehrung, Betonage — Eigenüberwachung dokumentieren
""",
    StageKey.WALLS_CEILINGS: """
Kontext: Mauerwerk und Decken — Rohbauphase.
Baustoffe gängig in Hessen:
- Kalksandstein (KS): hohes Eigengewicht, gute Schalldämmung, günstig
- Poroton/Ziegel: bessere Wärmedämmung, leichter
- Porenbeton (Ytong): sehr leicht, gute Dämmwerte, Feuchtigkeitsempfindlich
Normen:
- DIN EN 1996: Eurocode 6 — Mauerwerksbau
- DIN 4109-1: Schallschutz im Hochbau (prüfen ob Anforderungen erfüllt)
Deckenkonstruktionen: Stahlbetondecke, Holzbalkendecke, Elementdecke.
Sturze: Über Fenster und Türen — Tragfähigkeit vom Statiker bestätigt?
Baubegleitung: Abnahme Rohbau-Außenwände durch Bauleiter vor Dachaufbau empfohlen.
GEG: Außenwand-U-Wert max. 0,28 W/(m²K) für Neubau.
""",
    StageKey.ROOF: """
Kontext: Dachkonstruktion und Eindeckung.
Dachformen in Hessen: Satteldach (häufigste), Walmdach, Pultdach, Flachdach.
Bebauungsplan prüfen: Dachneigung, Dachfarbe, First-Richtung oft vorgeschrieben!
Zimmerer: Meisterpflicht, Eintragung Handwerkskammer Hessen.
Normen:
- DIN 1052: Holzbauwerke — Standsicherheit Dachstuhl
- DIN 68800: Holzschutz — chemischer Holzschutz, Belüftung
- DIN 18338: Dachdeckungs- und Dachabdichtungsarbeiten (VOB/C)
Wärmedämmung: GEG §15 — Dach/oberste Geschossdecke U ≤ 0,20 W/(m²K).
Dachflächenfenster: VELUX/Fakro — Statik, Dachneigung, DIN 4108 Tauwasserschutz.
Blitzschutz: DIN EN 62305 — in Hessen bei Gebäudehöhe >18 m oder Sonderbauten Pflicht.
Checkliste:
- [ ] Dachneigung stimmt mit B-Plan überein
- [ ] Zimmerer Handwerkskarte geprüft
- [ ] Dachfolie und Konterlattung vor Eindeckung
""",
    StageKey.WINDOWS_DOORS_RAW: """
Kontext: Fenster und Außentüren — Rohbauabschluss.
GEG-Anforderungen: Fenster U-Wert ≤ 1,3 W/(m²K), Haustür ≤ 1,8 W/(m²K).
Verglasungen: Dreifach-Wärmeschutz empfohlen (Uw ~ 0,9 W/m²K).
Schallschutz DIN 4109: Bei Straßenlärm Schallschutzklasse (SSK) 2–4 empfohlen.
Einbruchschutz:
- RC 2 (ex WK 2): Empfehlung Polizei Hessen für Haustüren
- Förderung KfW-455-B bei RC 2+
Einbau: Fachbetrieb, RAL-Montage-Leitfaden beachten (Luftdichtheit, Wärmebrücken).
Rollläden/Beschattung: Im B-Plan prüfen ob erlaubt (gilt als Außenveränderung).
Lüftungsöffnungen: DIN 18017-3 — natürliche Lüftung Bäder ohne Fenster.
Checkliste:
- [ ] U-Wert Nachweis GEG vorliegend
- [ ] Einbauprotokoll und RAL-konformer Einbau
- [ ] Haustür RC 2+ (Empfehlung)
""",

    # ── Phase D (Innenausbau) ──────────────────────────────────────────────────
    StageKey.PLUMBING: """
Kontext: Sanitär und Rohrleitungen — SHK-Gewerke.
Meisterpflicht: SHK = Sanitär-, Heizungs- und Klimatechnik (Handwerkskammer Hessen).
Normen:
- DIN EN 806: Trinkwasserinstallation
- TRWI (Technische Regeln Trinkwasserinstallation) — Legionellenschutz
- DIN 1986: Entwässerungsanlagen
- DIN 18560: Estriche (bei Fußbodenheizung relevant)
Anschlüsse: Hauswasseranschluss und Abwasserkanalschacht durch Gemeinde-Netzbetreiber.
Rohrleitungsplan: Dokumentation alle Wasserleitungen für spätere Wartung pflicht.
Druckprüfung: Vor dem Verputzen — Druckprüfprotokoll 10 bar, 30 min.
Warmwasser: Zirkulationsleitung bei >20 m Leitungslänge nach TRWI empfohlen.
Fußbodenheizung: Estrich-Temperaturprotokoll (Belegreifheizung) erforderlich.
Checkliste:
- [ ] SHK-Betrieb Handwerkskarte geprüft
- [ ] Druckprüfprotokoll vorliegend
- [ ] Leitungsplan dokumentiert
""",
    StageKey.FLOORING: """
Kontext: Estrich und Bodenbeläge.
Estricharten:
- Zementestrich (CT): Standardlösung, schwimmend auf Trittschalldämmung
- Anhydritestrich (CA): Schneller trocken, nicht feuchtraumgeeignet
- Trockenestrich: Schnell begehbar, für Holzbalkendecken
GEG §15: Fußbodendämmung Keller/Erdreich U ≤ 0,35 W/(m²K).
Trittschallschutz: DIN 4109-2 — mind. TSM ≥ 12 dB über Anforderung.
Trocknungszeit: Zementestrich mind. 28 Tage vor Belegreife (CM-Messung!).
Bodenbeläge: Fliesen, Parkett, Vinyl, Teppich — Untergrund prüfen (Feuchte <2% CM).
Untergrundprüfung: CM-Gerät (Calciumcarbid-Methode) vor Verlegung von Parkett und Vinyl.
Checkliste:
- [ ] Estrich-Protokoll vorliegend
- [ ] CM-Messung vor Belagsverlegung
- [ ] Belegreife bestätigt
""",
    StageKey.TILING: """
Kontext: Fliesen und Nassbereich-Abdichtung.
Normen:
- ZDB-Merkblatt Verbundabdichtung: Abdichtung unter Fliesen in Nassbereichen (Bäder, Duschen)
- DIN 18157: Ausführung keramischer Bekleidungen
- DIN 18195: Bauwerksabdichtung (Keller, Außenbereiche)
Verbundabdichtung: Im Duschbereich Pflicht — Folien oder Flüssigfolie + Dichtband an Ecken.
Fugenverpressung: Bewegungsfugen alle 3–4 m und besonders in Raum-Ecken (Silikon, keine Verfugmasse).
Frostschutz: Außen liegende Flächen — Frost- und tausalzbeständige Fliesen (Klasse R11+ Rutschklasse).
Badezimmer-Planung: Mindestfläche Barrierefreiheit (DIN 18040-2): 120 x 120 cm Dusche.
Checkliste:
- [ ] Verbundabdichtung ausgeführt und dokumentiert
- [ ] Bewegungsfugen geplant
- [ ] Fließen-Klasse (Rutschhemmung) entsprechend Nutzung
""",
    StageKey.PLASTERING: """
Kontext: Wand- und Deckenputz, Malerarbeiten.
Putzarten:
- Innenputz: Kalkgipsputz (Maschinenputz, schnell), Kalkputz (atmungsaktiv), Lehmputz
- Außenputz: Mineralputz, Silikatputz, Kunstharzputz
Normen:
- DIN 18550: Putz und Putzsysteme
- DIN 55699: Qualitätsstufen Q1–Q4 (Q3/Q4 für hochwertige Innenräume)
Trocknung: Mindesttrocknungszeit 1 Tag / mm Putzstärke; Lüften aber kein Durchzug.
Qualitätsstufen:
  Q2: Standard (Tapezierunterlage), Q3: Sichtfläche, Q4: Streiflicht-geeignet (hochwertig).
Farbton: Weißgrad Innenwand beeinflusst Helligkeitswert — Lichtplanung berücksichtigen.
Schimmelschutz: Diffusionsoffene Farben innen, Innendämmung nur dampfdiffusionsoffen.
Checkliste:
- [ ] Putzqualität Q2/Q3 vereinbart
- [ ] Untergrundvorbereitung: Vornetzen bei saugenden Untergründen
- [ ] Elektroleerrohre und Schlitze VOR Putz verlegt!
""",
    StageKey.BUILT_IN_FURNITURE: """
Kontext: Küche, Einbauschränke, Innenausstattung.
Küche:
- Anschlüsse: Starkstrom 230V und ggf. 400V (Herd), Wasser kalt+warm, Abwasser, Dunstabzug
- Dunstabzugshaube: Freie Lüftung oder Abluft ins Freie (Mauerkasten erforderlich, Schallschutz!)
- Gasleitungen: Nur durch eingetragenen SHK-Fachbetrieb (DVGW-Zertifizierung)
Einbauschränke: Maßanfertigung vs. Systemschränke — Maßtoleranz Rohbau ±2 cm einkalkulieren.
Barrierefreiheit: DIN 18040-2 — Küchenunterschrank-Höhe 80–90 cm, Unterfahrbarkeit.
Elektrogeräte: Energieeffizienzklasse (EU-Label), für KfW-Effizienzhaus mind. A-Klasse empfohlen.
Checkliste:
- [ ] Elektroanschlüsse nach Küchenplan vorbereitet
- [ ] Abluftkanal (Dunstabzug) geplant und gebaut
- [ ] Maße mit Küchenplaner abgestimmt
""",
    StageKey.LIGHTING: """
Kontext: Elektroinstallation, Beleuchtung und Haustechnik.
Grundlage: VDE 0100 — Errichten von Niederspannungsanlagen.
Lichtplanung:
- Lux-Werte: Wohnraum 150–300 lx, Küche 300–500 lx, Arbeitszimmer 500 lx
- Farbtemperatur: Wohnräume 2700–3000K (warm), Arbeit 4000K (neutral)
- LED: Effizienzklasse mind. A (ab 01.03.2023 EU-Verordnung), Dimmerkompatibilität prüfen
Schutzklassen Nassbereich: IP44 im Badezimmer (Schutzbereich 2), IP65 in Duschbereich (SB 1).
Smart-Vorbereitung: Leerrohre für KNX/Z-Wave/Zigbee, oder WLAN-fähige Schalter einplanen.
Außenbeleuchtung: Bewegungsmelder + Lichtsteuerung = Einbruchschutz + Energiesparen.
Abnahme: Elektrizitätsprotokoll (VDE), DGUV Prüfbericht.
Checkliste:
- [ ] VDE-Messung und Protokoll
- [ ] IP-Schutzklassen Nassbereich eingehalten
- [ ] Smarthome-Vorbereitung geplant
""",
    StageKey.DOORS_STAIRS: """
Kontext: Innentüren, Treppen, Treppengeländer.
Innentüren:
- Schallschutz: DIN 4109-2 — Wohnungstüren mind. 37 dB Rw; Schlafzimmer mind. 32 dB
- Brandschutz: T30 (EI230) zwischen Wohnbereich und Garage/Keller (HBO §47)
- Maße: Standardbreite 86–100 cm; Barrierefreiheit 90 cm lichte Breite (DIN 18040)
Treppen:
- DIN 18065: Gebäudetreppen — Steigungsverhältnis 2× Steigehöhe + Auftrittsbreite = 59–65 cm
- Hessen HBO §35: Mindestbreite Treppen 80 cm (Einfamilienhäuser)
- Geländer: Ab 4 Treppenstufen (HBO §38), Höhe mind. 90 cm, kein Übersteigen möglich
- Kindersicherheit: Geländerstäbe max. 12 cm Abstand (HBO §38 Abs. 4)
Materialien: Massivholz, Fertigtreppe Stahl/Glas, Betontreppe — Kosten sehr unterschiedlich.
Checkliste:
- [ ] Treppenstufen-Maße nach DIN 18065
- [ ] Geländer Höhe und Abstände geprüft
- [ ] Brandschutztüren wo vorgeschrieben
""",

    # ── Phase E (Außenanlagen) ─────────────────────────────────────────────────
    StageKey.FACADE_INSULATION: """
Kontext: Fassadendämmung und Außenwandabschluss.
GEG-Anforderungen (§15 Neubau): U-Wert Außenwand ≤ 0,28 W/(m²K).
WDVS (Wärmedämmverbundsystem = ETICS):
- Dämmstoffe: EPS (Styropor), Mineralwolle, Phenolharz — Brandschutzstreifen bei >22 m Höhe!
- Verarbeitungsrichtlinien: ETAG 004 / EAD 040083 — europäisch harmonisiert
- Mindestdicke Hessen: Bei Sanierung mind. 14 cm EPS 035 empfohlen
- Hinterlüftete Fassade (VHF): Premium-Alternative, wartungsfreundlicher
Förderung: BEG Einzelmaßnahme — 15–20% Zuschuss für Fassadendämmung (BAFA).
Bauaufsicht: Bei Sanierungen über 10% der Fläche: GEG-Nachrüstpflicht für Restgebäude.
Brandschutz: Bei WDVS ab Gebäudeklasse 4 (>7 m Wandhöhe): Mineralwolle-Brandriegel.
Checkliste:
- [ ] U-Wert Berechnung GEG ≤ 0,28
- [ ] Brandschutznachweis bei >22 m
- [ ] BAFA-Förderantrag VOR Beauftragung gestellt
""",
    StageKey.GARAGE: """
Kontext: Garage, Carport, Stellplatz.
Hessen HBO §§ 5, 8:
- Garagen bis 50 m² (HBO §8): Verfahrensfrei (keine Baugenehmigung nötig)
- Garagen > 50 m²: Vereinfachtes Genehmigungsverfahren
- Stellplatznachweis: Je Wohneinheit mind. 1 Stellplatz (GaStellVO Hessen)
Abstandsflächen HBO §6:
- Garage an Grundstücksgrenze: Möglich wenn ≤ 9 m lang, ≤ 3 m Wandhöhe, ≤ 50 m² (Grenzbau)
- Mindestabstand zu Gebäuden: Brandschutz DIN 14090 — mind. 1 m zu Hauptgebäude
Elektromobilität: Leerrohre zur Garage für Wallbox vorbereiten (mind. NYY-J 5×4 mm², 32A).
Förderung: KfW-440 entfallen 2024 — aktuelle Wallbox-Förderung beim Stromanbieter prüfen.
Checkliste:
- [ ] Genehmigungspflicht geprüft (>50 m²?)
- [ ] Stellplatznachweis nach GaStellVO
- [ ] E-Ladeinfrastruktur (Leerrohr) vorbereitet
""",
    StageKey.GARDEN: """
Kontext: Gartengestaltung, Terrasse, Außenanlagen.
Genehmigungsfreiheit (HBO §8): Gartenmauern bis 2 m Höhe, Terrassenüberdachungen bis 30 m².
Terrasse:
- Überdachung > 30 m²: Genehmigungspflichtig (verfahrensfrei bis 30 m²)
- Anschluss an Wohngebäude: GRZ beachten (Terrasse zählt zur Versiegelung!)
Regenwassermanagement:
- Hessen: Versickerungsanlagen präferiert (Rigole, begrüntes Dach)
- Retentionszisternen: Mind. 3.000 L für >200 m² Grundstück empfohlen (FNP Hessen)
- Einleitung in Kanal: Gebührenpflichtig, Genehmigung Gemeinde
Begrünung: Klimawandel-Strategie Hessen — Flächenentsiegelung, einheimische Pflanzen.
Checkliste:
- [ ] GRZ geprüft — Terrasse in Grundflächenzahl einkalkuliert?
- [ ] Entwässerungskonzept (Versickerung)
- [ ] Überdachung ≤ 30 m² (sonst Genehmigung)
""",
    StageKey.DRIVEWAY: """
Kontext: Zufahrt, Pflasterung, Außenbelag.
Versiegelung: Befestigte Flächen zählen zur GRZ (Grundflächenzahl) — max. GRZ+25% Überschreitung erlaubt (§17 BauNVO).
Wasserdurchlässigkeit:
- Hessen: Versickerungsfähige Beläge bevorzugt (Rasengitter, Schotterrasen, Pflaster mit Fugenanteil)
- Undurchlässige Flächen > 100 m²: Genehmigung Untere Wasserbehörde
Materialien: Betonpflaster, Naturstein, Kies, Asphalt — Frost- und Schwerverkehrsklassen beachten.
Tiefbau: Unterbau Frostschutzschicht (Hessen: 80 cm Frosttiefe) — sonst Hebungen im Winter.
Straßenanschluss: Genehmigung beim Straßenbaulastträger (Gemeinde, Kreis, RP Kassel/Darmstadt).
Entwässerung: Längsneigung min. 1,5%, Querneigung 2–4% — Wasserableitung zur Rigole.
Checkliste:
- [ ] GRZ + Versiegelungsanteil geprüft
- [ ] Tiefbau Frostschutzschicht ≥ 80 cm
- [ ] Straßenanschluss genehmigt
""",
    StageKey.FENCING: """
Kontext: Einfriedungen, Zäune, Tore.
Hessen HBO §8: Einfriedungen bis 2 m Höhe verfahrensfrei.
Grenzbebauung:
- Zaun direkt auf Grenzlinie: Einigung mit Nachbar empfohlen (Nachbarrechtsgesetz Hessen §§22-32)
- Gemeinsamer Zaun: Kosten hälftig (HSOG §922 BGB)
Sichtschutz: B-Plan kann Einfriedungsart/-höhe vorschreiben — zuerst prüfen!
Elektrotore: VDE 0100-720; CE-Kennzeichnung und EN 12453 (Kraftbegrenzung) Pflicht.
Hecken: Grenzabstand Hessen: mind. 50 cm bei <1,2 m Höhe, 75 cm bei >1,2 m (NRG §3).
Baumbestand: Hessen Baumschutzsatzungen der Gemeinden — Fällung oft genehmigungspflichtig!
Checkliste:
- [ ] B-Plan: Einfriedungsvorschriften?
- [ ] Nachbar informiert/Einigung für GrenzZaun
- [ ] Elektrisches Tor: CE + EN 12453 Prüfprotokoll
""",

    # ── Phase F (Haustechnik) ──────────────────────────────────────────────────
    StageKey.VENTILATION: """
Kontext: Lüftungsanlage und Klimatechnik.
GEG §26: Luftdichtheitsnachweis bei Lüftungsanlage — Blower-Door-Test.
Lüftungskonzept DIN 1946-6: Pflicht für KfW-Effizienzhäuser; obligatorisch wenn n50 ≤ 3,0 h⁻¹.
Typen:
- Freie Stoßlüftung: Nur bei n50 < 3,0 h⁻¹ zulässig für Passivhaus-nahe Gebäude
- KWL (Kontrollierte Wohnraumlüftung): Wärmerückgewinnung ≥ 75%; KfW-261-Pflicht bei EH40
- Abluftanlage: Bad/WC-Entlüftung nach DIN 18017-3
Schall: Lüftungsanlage DIN 4109 — max. 25 dB(A) im Wohnraum.
Filter: HEPA H13 empfohlen bei Pollenallergie; Wartungsvertrag für Filter.
Wärmebrücken: Lüftungsrohre durch nicht gedämmte Bauteile → Kondensation möglich.
Blower-Door: Messung nach Fertigstellung — Nachweis für KfW-261 und GEG.
Checkliste:
- [ ] Lüftungskonzept DIN 1946-6 vorliegend
- [ ] Blower-Door-Test geplant (nach Fertigstellung)
- [ ] KWL-Anlage: Wärmerückgewinnung ≥ 75%
""",
    StageKey.ENERGY_CERTIFICATE: """
Kontext: Energieausweis und GEG-Endabnahme.
Pflicht: §§79-88 GEG — Energieausweis bei Neubau Pflicht, 10 Jahre gültig.
Aussteller: Energieberater mit Listung in dena-Energieeffizienz-Expertenliste (zugelassen nach GEG §88).
Typen:
- Bedarfsausweis: Berechnung auf Basis Gebäudehülle und Anlagentechnik (Neubau: immer Bedarfsausweis)
- Verbrauchsausweis: Nur bei ≥ 5 Jahre bewohntem Gebäude möglich
KfW-Bestätigungen:
- Technische Projektbeschreibung des Energieeffizienz-Experten (vor Antragstellung)
- Bestätigung nach Durchführung (BnD) — nach Fertigstellung erforderlich für KfW-Auszahlung!
Energieeffizienzklassen: A+ bis H — Neubau GEG-Anforderung entspricht ca. B–A.
Einreichung Bauamt: Energieausweis bei Baufertigstellungsanzeige (HBO §72) vorlegen.
Checkliste:
- [ ] Energieberater (dena-Liste) beauftragt
- [ ] KfW-BnD rechtzeitig (innerhalb 6 Monate nach Fertigstellung)
- [ ] Energieausweis ausgestellt und vorhanden
""",
    StageKey.SMART_HOME: """
Kontext: Smart-Home-Systeme und Hausautomation.
Systeme im Markt:
- KNX (Bus): Professionell, zuverlässig, teuer (~15.000–25.000 € für EFH)
- Z-Wave/Zigbee: Günstiger, Funkbasiert, Mesh-Netzwerk
- WLAN-basiert (Philips Hue, Shelly, Matter): Einfachste Installation
Matter-Standard: Neue Geräte (ab 2023) mit Matter kompatibel — Herstellerunabhängig.
Integration: Loxone, Homematic IP, ioBroker, Home Assistant (Open Source).
GEG §71a: Gebäudeautomation Klasse B ab 2025 für Nicht-Wohngebäude >290 kW Heizlast.
Elektrovorbereitung: BUS-Kabel (KNX: J-Y(ST)Y 2×2×0,8) bei KNX-Planung früh verlegen!
Datenschutz: Lokale Steuerung bevorzugen (kein Cloud-Pflicht) — DSGVO-Konformität.
Smarte Zähler: Einbau moderner Messeinrichtung ab 6.000 kWh/Jahr Pflicht (Messstellenbetrieb).
Checkliste:
- [ ] System gewählt (KNX/Funk/Matter)
- [ ] Leerrohre für BUS-Kabel verlegt (falls KNX)
- [ ] Datenschutzkonzept (lokal vs. Cloud)
""",

    # ── Phase G (Abschluss) ────────────────────────────────────────────────────
    StageKey.FINAL_ACCEPTANCE: """
Kontext: Bauabnahme und Fertigstellung.
Baufertigstellungsanzeige: HBO §72 — Pflicht binnen 2 Wochen nach Bezugsfertigkeit.
Abnahme-Checkliste mit Bauleiter:
- Alle Berichtbestandteile vollständig? (Statik, Energieausweis, Prüfberichte)
- VDE-Protokoll Elektro vorhanden?
- Druckprüfprotokoll Sanitär vorhanden?
- Blower-Door-Test Ergebnis?
- Alle Mängel dokumentiert?
Mangelverfolgung: Mängelrüge schriftlich (per Einschreiben) mit Fristsetzung (§634 BGB).
Gewährleistung: 5 Jahre auf Bauleistungen (§634a BGB), 2 Jahre bei Kauf vom Bauträger.
Übergabeprotokoll: Schlüssel, Bedienungsanleitungen, Garantiescheine, Wartungsverträge, Pläne.
Versicherung: Fertigstellung = Gebäudeversicherung aktiv (vorher Feuerohling-Versicherung!).
Checkliste:
- [ ] Baufertigstellungsanzeige Bauamt (HBO §72)
- [ ] Übergabeprotokoll mit Bauleiter
- [ ] Gebäudeversicherung ab Übergabe aktiv
""",
    StageKey.OFFICIAL_NOTICES: """
Kontext: Behördliche Anzeigen, Ummeldungen, Anschlüsse.
Pflichtmeldungen nach Fertigstellung:
1. Baufertigstellungsanzeige Bauaufsicht (HBO §72)
2. Anmeldung beim Einwohnermeldeamt (Wohnsitz ummelden, §17 BMG 2 Wochen!)
3. Grundsteuer: Festsetzungsbescheid Finanzamt (Grundsteuerwert nach §219 BewG)
4. Stromzähler: Netzanschluss/Zählerstellung beim Netzbetreiber
5. Gas: Erstinbetriebnahme durch SHK-Fachbetrieb und Netzbetreiber
6. Versicherungen: Gebäudeversicherung aktivieren (Bauleistungsversicherung kündigen)
7. Förderung: KfW-BnD (Bestätigung nach Durchführung) — FRIST 6 Monate!
8. PV-Anlage Marktstammdatenregister (1 Monat nach Inbetriebnahme, Pflicht!)
9. Heizung: Schornsteinfeger / Bezirksschornsteinfegermeister — Abnahme und Feuerstättenschau
Checkliste:
- [ ] KfW-BnD innerhalb 6 Monate abgerufen
- [ ] Ummeldung Einwohnermeldeamt
- [ ] Schornsteinfeger Feuerstättenschau
""",
    StageKey.MOVE_IN: """
Kontext: Einzug und Erstbezug.
Checkliste Einzug:
- [ ] Strom-/Gas-/Wasser-/Internet-Verträge auf neue Adresse umschreiben
- [ ] Zählerstände dokumentieren bei Einzug (Foto!)
- [ ] Hausratversicherung an neue Wohnfläche anpassen
- [ ] Kfz ummelder (neue Adresse auf Führerschein innerhalb 1 Woche)
- [ ] Bank/Post/Behörden Adressänderung mitteilen
- [ ] Klingel- und Briefkastenschilder
Einregulierung Haustechnik:
- Heizung hydraulisch abgleichen (GEG-Pflicht ab 2024 im Neubau)
- Lüftungsanlage einmessen und Protokoll
- Smart-Home Einprogrammieren / Zeitpläne anlegen
Übergabe-Dokumentation aufbewahren: Pläne, Bauunterlagen, Garantiescheine — wichtig für Gewährleistung und Versicherungen.
Erstjahr: Schwundrisse möglich (Neubautrocknungsschrumpfung) — Normalerscheinung, Nachbesserung nach 12 Monaten.
Checkliste:
- [ ] Alle Zählerstände bei Einzug notiert
- [ ] Heizung hydraulisch abgleichen
- [ ] Dokumentenmappe vollständig
""",
    StageKey.WARRANTY_TRACKING: """
Kontext: Gewährleistungsverfolgung und Mängelmanagement.
Fristen (§634a BGB):
- Bauleistungen: 5 Jahre Gewährleistung (ab Abnahme)
- Bauträgerkauf: 2 Jahre (möglicherweise 5 Jahre je nach Vertrag)
- Elektrogeräte, Einbauküchen: 2 Jahre Händlergewährleistung
Verjährungshemmung: Mängelrüge schriftlich mit Fristsetzung → Verjährung wird gehemmt.
Typische Gewährleistungsmängel im 1.–5. Jahr:
- Schwundrisse (normal wenn < 0,2 mm, füllen lassen)
- Feuchtigkeit Keller/Bodenplatte (sofort rügen! kurze Frist)
- Heizungsprobleme, Thermostatventile
- Bodenfugen, Fliesenrisse
- Fenster/Türen-Verzug (Holzquellen bei Erstbezug)
Dokumentation: Alle Mängel mit Datum, Foto, schriftlicher Rüge dokumentieren.
Bauversicherungen: Feuerrohbau, Bauleistungsversicherung, Bauherren-Haftpflicht abrechnen.
Checkliste:
- [ ] Gewährleistungsfristen-Kalender erstellt (5 Jahre ab Abnahme-Datum)
- [ ] Alle Mängel schriftlich gerügt
- [ ] Versicherungen korrekt umgestellt
""",
}


# ─── Основная функция запроса к ИИ ───────────────────────────────────────────

def ask_ai(
    user_message: str,
    project: Project = None,
    stage_key: StageKey = None,
    action_type: ActionType = ActionType.GENERAL_CONSULT,
    mode: ActionMode = ActionMode.CONFIRMATION_REQUIRED,
    extra_context: dict = None,
    user_id: str = None,
    system_override: str = None,
    use_browser: bool = False,
) -> dict:
    """
    Основной вызов Claude API.
    Автоматически выбирает специализированного агента по stage_key.
    Возвращает dict: {success, response, mode, action_type, log_id, agent_name, tool_calls}
    """
    client = _get_client()
    start_ms = int(time.time() * 1000)

    # ── Выбираем агентную конфигурацию по этапу ────────────────────────────
    agent_cfg = get_stage_agent_config(stage_key) if stage_key else {
        'suffix': '', 'tools': [], 'use_browser': use_browser,
        'default_mode': mode, 'agent_name': 'GeneralAgent'
    }
    # use_browser=True явный вызов всегда включает брузер,
    # иначе берём из конфига агента
    effective_browser = use_browser or agent_cfg['use_browser']
    active_tools = agent_cfg['tools'] if effective_browser else []
    agent_name = agent_cfg['agent_name']

    # Собираем контекст
    context_parts = []

    if project:
        context_parts.append(f"""
PROJEKT-KONTEXT:
- Titel: {project.title}
- Typ: {project.project_type.value if project.project_type else 'nicht gesetzt'}
- Adresse: {project.address or 'nicht gesetzt'}
- PLZ/Ort: {project.address_plz} {project.address_city or ''}
- Budget: {project.budget_total} €
- Wohnfläche: {project.wohnflaeche_m2} m²
- Grundstücksgröße: {project.grundstueck_m2} m²
- Aktueller Status: {STAGE_LABELS.get(project.current_stage, project.current_stage)}
""")
        if project.gemeinde:
            g = project.gemeinde
            context_parts.append(f"""
GEMEINDE:
- Name: {g.name}, {g.landkreis}, Hessen
- Bauamt E-Mail: {g.bauamt_email or 'nicht bekannt'}
- Bauamt URL: {g.bauamt_url or 'nicht bekannt'}
""")
        if project.zone:
            z = project.zone
            context_parts.append(f"""
BEBAUUNGSPLAN-ZONE:
- Zonentyp: {z.zone_label()}
- Plan: {z.plan_name or 'unbekannt'}
- GRZ max: {z.grz_max}
- GFZ max: {z.gfz_max}
- Max. Geschosse: {z.max_geschosse}
- Max. Höhe: {z.max_hoehe_m} m
- Besonderheiten: {z.sonderregeln or 'keine'}
""")
        if project.financing:
            f = project.financing
            context_parts.append(f"""
FINANZIERUNG:
- Eigenkapital: {f.eigenkapital} €
- KfW-Programm: {f.kfw_program or 'nicht ausgewählt'}
- KfW-Betrag: {f.kfw_amount} €
- Bankdarlehen: {f.bank_loan_amount} €
- Monatliche Rate: {f.monthly_rate} €
""")

    if stage_key and stage_key in STAGE_CONTEXTS:
        context_parts.append(STAGE_CONTEXTS[stage_key])

    if extra_context:
        for k, v in extra_context.items():
            context_parts.append(f"{k}: {v}" if not k.startswith('_') else '')

    # Извлекаем image из extra_context если есть
    _image_b64  = (extra_context or {}).pop('_image_b64', None)
    _image_mime = (extra_context or {}).pop('_image_mime', 'image/jpeg')
    (extra_context or {}).pop('_image_filename', None)

    full_context = '\n'.join(p for p in context_parts if p)
    messages = []

    if _image_b64:
        # Claude vision: multipart message с изображением
        content_blocks = []
        if full_context.strip():
            content_blocks.append({'type': 'text', 'text': f'[KONTEXT]\n{full_context}\n\n[ANFRAGE]\n{user_message}'})
        else:
            content_blocks.append({'type': 'text', 'text': user_message})
        content_blocks.append({
            'type': 'image',
            'source': {'type': 'base64', 'media_type': _image_mime, 'data': _image_b64},
        })
        messages.append({'role': 'user', 'content': content_blocks})
    elif full_context.strip():
        messages.append({
            'role': 'user',
            'content': f"[KONTEXT]\n{full_context}\n\n[ANFRAGE]\n{user_message}"
        })
    else:
        messages.append({'role': 'user', 'content': user_message})

    # Строим system prompt: базовый + суффикс агента
    system_prompt = system_override or (SYSTEM_PROMPT + agent_cfg.get('suffix', ''))

    try:
        from app.services.browser_tools import execute_tool, MAX_TOOL_ROUNDS

        jina_key = current_app.config.get('JINA_API_KEY', '') or ''
        create_kwargs = dict(
            model='claude-sonnet-4-20250514',
            max_tokens=2000,
            system=system_prompt,
            messages=messages,
        )
        if active_tools:
            create_kwargs['tools'] = [t for t in active_tools if t is not None]

        # ── Tool-use agentic loop ────────────────────────────────────────────
        tool_calls_made = []   # список {'tool': name, 'query': ...} для UI
        for _round in range(MAX_TOOL_ROUNDS + 1):
            response = client.messages.create(**create_kwargs)

            if response.stop_reason != 'tool_use' or not active_tools:
                break  # финальный ответ

            # Обрабатываем все tool_use блоки в ответе
            tool_results = []
            for block in response.content:
                if block.type != 'tool_use':
                    continue
                tool_result = execute_tool(block.name, block.input, jina_key)
                tool_calls_made.append({
                    'tool': block.name,
                    'input': block.input,
                })
                tool_results.append({
                    'type': 'tool_result',
                    'tool_use_id': block.id,
                    'content': tool_result,
                })

            # Добавляем ответ ассистента + результаты инструментов в историю
            create_kwargs['messages'] = list(create_kwargs['messages']) + [
                {'role': 'assistant', 'content': response.content},
                {'role': 'user',      'content': tool_results},
            ]

        # ── Финальный ответ ──────────────────────────────────────────────────
        duration_ms = int(time.time() * 1000) - start_ms

        # Достаём текст из последнего ответа (может быть несколько блоков)
        response_text = ' '.join(
            b.text for b in response.content if hasattr(b, 'text')
        ).strip()
        tokens = response.usage.input_tokens + response.usage.output_tokens

        log = AIActionLog(
            project_id=project.id if project else None,
            user_id=user_id or (project.user_id if project else None),
            action_type=action_type,
            mode=mode,
            stage_key=stage_key,
            input_context={'message': user_message, 'context_length': len(full_context),
                           'agent': agent_name, 'tool_calls': len(tool_calls_made)},
            output_summary=response_text[:500],
            full_response=response_text,
            tokens_used=tokens,
            model_version='claude-sonnet-4-20250514',
            duration_ms=duration_ms,
        )
        db.session.add(log)
        db.session.commit()

        return {
            'success': True,
            'response': response_text,
            'mode': mode.value,
            'action_type': action_type.value,
            'log_id': log.id,
            'tokens': tokens,
            'tool_calls': tool_calls_made,
            'agent_name': agent_name,
        }

    except Exception as e:
        duration_ms = int(time.time() * 1000) - start_ms
        log = AIActionLog(
            project_id=project.id if project else None,
            user_id=user_id or (project.user_id if project else None),
            action_type=action_type,
            mode=mode,
            stage_key=stage_key,
            input_context={'message': user_message},
            error=str(e),
            duration_ms=duration_ms,
        )
        db.session.add(log)
        db.session.commit()
        return {
            'success': False,
            'response': f'Fehler beim KI-Aufruf: {str(e)}',
            'mode': mode.value,
            'action_type': action_type.value,
            'log_id': log.id,
        }


# ─── Специализированные функции ───────────────────────────────────────────────

def generate_bauamt_letter(project: Project, stage: ProjectStage, subject: str, user=None) -> dict:
    """
    Генерирует черновик письма в Bauamt.
    Режим: CONFIRMATION_REQUIRED — пользователь утверждает перед отправкой.
    """
    gemeinde = project.gemeinde
    u = user or project.user

    # Sender data from user profile + project
    sender_name    = (u.full_name if u else None) or 'Vorname Nachname'
    sender_email   = (u.email    if u else None) or ''
    sender_phone   = (u.phone    if u else None) or ''
    sender_address = project.address or ''
    sender_plz     = project.address_plz or ''
    sender_city    = project.address_city or ''

    # Recipient data from Gemeinde
    recipient_name    = (gemeinde.bauamt_name    if gemeinde else None) or 'Bauaufsichtsbehörde'
    recipient_address = (gemeinde.bauamt_address if gemeinde else None) or ''
    recipient_city    = (gemeinde.name           if gemeinde else 'zuständige Gemeinde')

    project_type_label = project.project_type.value.replace('_', ' ').title() if project.project_type else 'Neubau'

    prompt = f"""Erstelle einen professionellen deutschen Behördenbrief (DIN 5008).

BETREFF: {subject}

ABSENDER:
{sender_name}
{sender_address}
{sender_plz} {sender_city}
{f'Tel.: {sender_phone}' if sender_phone else ''}
{f'E-Mail: {sender_email}' if sender_email else ''}

EMPFÄNGER:
{recipient_name}
{recipient_address}
{recipient_city}

VORHABEN:
- Projektname: {project.title}
- Typ: {project_type_label}
- Grundstück: {sender_address}{f', {sender_plz} {sender_city}' if sender_plz else ''}
- Wohnfläche: {project.wohnflaeche_m2 or '—'} m²
- Grundstücksfläche: {project.grundstueck_m2 or '—'} m²
{f'- Budget: {project.budget_total} €' if project.budget_total else ''}
{f'- Bauzone: {project.zone.zone_label()}, GRZ {project.zone.grz_max}, GFZ {project.zone.gfz_max}' if project.zone else ''}

ANFORDERUNGEN AN DEN BRIEF:
- Formal korrekt nach DIN 5008
- Mit vollständigem Briefkopf (Absender oben, Empfänger darunter, Datum: {__import__('datetime').date.today().strftime('%d.%m.%Y')})
- Konkreter Sachverhalt und klare Anfrage/Mitteilung
- Freundlicher Gruß am Ende mit Unterschrift-Zeile für {sender_name}
- Gib NUR den fertigen Brieftext zurück, ohne Erklärungen oder Kommentare
"""
    result = ask_ai(
        user_message=prompt,
        project=project,
        stage_key=stage.stage_key if stage else None,
        action_type=ActionType.DRAFT_LETTER,
        mode=ActionMode.CONFIRMATION_REQUIRED,
    )

    if result['success'] and gemeinde and gemeinde.bauamt_email:
        # Сохраняем в очередь на отправку
        msg = MessageOutbox(
            project_id=project.id,
            stage_id=stage.id if stage else None,
            user_id=project.user_id,
            recipient_type=RecipientType.BAUAMT,
            recipient_name=f"Bauaufsicht {gemeinde.name}",
            recipient_email=gemeinde.bauamt_email,
            subject=subject,
            body_draft=result['response'],
            status=OutboxStatus.DRAFT,
        )
        db.session.add(msg)
        db.session.commit()
        result['outbox_id'] = msg.id

    return result


def analyze_zone(project: Project) -> dict:
    """Анализирует зону Bebauungsplan для участка."""
    zone = project.zone
    if not zone:
        return ask_ai(
            user_message=(
                f"Das Projekt '{project.title}' in {project.address_city} hat noch keine "
                f"Bebauungsplan-Zone zugewiesen. Erkläre dem Nutzer was §34 BauGB bedeutet "
                f"und welche nächsten Schritte zur Zonenfindung nötig sind."
            ),
            project=project,
            stage_key=StageKey.LAND_SEARCH,
            action_type=ActionType.ZONE_LOOKUP,
            mode=ActionMode.AUTONOMOUS,
        )

    prompt = f"""
Analysiere die Bebauungsplan-Zone für das Projekt '{project.title}':

Zone: {zone.zone_label()}
GRZ: {zone.grz_max} | GFZ: {zone.gfz_max} | Max. Geschosse: {zone.max_geschosse}
Max. Höhe: {zone.max_hoehe_m} m
Sonderregeln: {zone.sonderregeln or 'keine'}

Projekt: {project.project_type.value}, {project.wohnflaeche_m2} m² Wohnfläche, 
Grundstück: {project.grundstueck_m2} m²

Erkläre:
1. Was ist in dieser Zone erlaubt?
2. Passt das geplante Vorhaben zur Zone? (berechne GRZ und GFZ)
3. Welche Einschränkungen sind zu beachten?
4. Was ist der nächste konkrete Schritt?

Sei präzise und praktisch. Auf Russisch antworten wenn der Nutzer Russisch spricht.
"""
    return ask_ai(
        user_message=prompt,
        project=project,
        stage_key=StageKey.LAND_SEARCH,
        action_type=ActionType.ZONE_LOOKUP,
        mode=ActionMode.AUTONOMOUS,
    )


def calculate_kfw(project: Project) -> dict:
    """Подбирает KfW-программы и рассчитывает финансирование."""
    financing = project.financing
    prompt = f"""
Analysiere die KfW-Fördermöglichkeiten für dieses Bauprojekt:

Projekt: {project.title}
Typ: {project.project_type.value}
Wohnfläche: {project.wohnflaeche_m2} m²
Gesamtbudget: {project.budget_total} €
Eigenkapital: {financing.eigenkapital if financing else 'unbekannt'} €
Lage: {project.address_city}, Hessen

Analysiere und empfehle:
1. Welche KfW-Programme kommen in Frage? (261, 300, 124, 270)
2. Maximale Förderhöhe je Programm
3. Aktueller Zinssatz (Hinweis: aktuell prüfen auf kfw.de)
4. WIBank Hessen Landesförderung
5. Reihenfolge der Antragstellung (KfW VOR Baubeginn!)
6. Geschätzte monatliche Gesamtbelastung

Struktur: Übersichtstabelle + konkreter Aktionsplan.
"""
    return ask_ai(
        user_message=prompt,
        project=project,
        stage_key=StageKey.FINANCING,
        action_type=ActionType.KFW_CALC,
        mode=ActionMode.AUTONOMOUS,
    )


def find_providers_for_stage(project: Project, stage_key: StageKey) -> dict:
    """Ищет подходящих поставщиков для этапа и объясняет критерии выбора."""
    from app.models.models import Provider, ProviderService
    from app.models.enums import VerifiedStatus

    # Находим верифицированных провайдеров для этого этапа
    providers = (
        Provider.query
        .join(ProviderService)
        .filter(
            Provider.verified_status == VerifiedStatus.VERIFIED,
            Provider.is_active == True,
            ProviderService.relevant_stages.contains([stage_key.value]),
        )
        .order_by(Provider.rating_avg.desc())
        .limit(5)
        .all()
    )

    providers_text = ''
    if providers:
        providers_text = '\n'.join([
            f"- {p.company_name} | ★ {p.rating_avg} ({p.review_count} Bewertungen) | {p.contact_email}"
            for p in providers
        ])
    else:
        providers_text = "Noch keine verifizierten Anbieter in der Datenbank für diesen Bereich."

    prompt = f"""
Für den Schritt '{STAGE_LABELS.get(stage_key, stage_key.value)}' des Projekts '{project.title}' 
werden Fachleute benötigt.

Verfügbare geprüfte Anbieter:
{providers_text}

Erkläre dem Nutzer:
1. Warum an diesem Punkt ein Fachmann nötig ist (rechtlich/praktisch)
2. Worauf er bei der Auswahl achten soll (Qualifikationen, Fragen die er stellen soll)
3. Präsentiere die verfügbaren Anbieter mit kurzer Einschätzung
4. Welche Unterlagen er für das erste Gespräch vorbereiten soll
"""
    return ask_ai(
        user_message=prompt,
        project=project,
        stage_key=stage_key,
        action_type=ActionType.PROVIDER_SEARCH,
        mode=ActionMode.HUMAN_REQUIRED,
    )


def generate_checklist(project: Project, stage_key: StageKey) -> dict:
    """
    Генерирует чеклист для этапа, парсит ответ и сохраняет в stage.checklist.
    Формат ответа AI: строки вида «- [REQUIRED] Beschreibung» или «- Beschreibung».
    """
    from app.models.models import ProjectStage
    from sqlalchemy.orm.attributes import flag_modified

    prompt = f"""
Erstelle eine konkrete Checkliste für den Schritt '{STAGE_LABELS.get(stage_key)}' 
im Projekt '{project.title}' in {project.address_city}, Hessen.

Die Checkliste soll:
- Alle notwendigen Dokumente und Aufgaben auflisten
- Behörden und Kontakte benennen
- Fristen und Deadlines anzeigen
- In logischer Reihenfolge strukturiert sein

WICHTIG: Gib die Checkliste ausschließlich als Aufzählung zurück, eine Aufgabe pro Zeile.
Pflichtaufgaben markiere mit [REQUIRED] am Zeilenanfang (nach «- »).
Rechtliche Grundlage in Klammern angeben: (HBO §X, BauGB §X etc.)
Keine sonstige Einleitung oder Erklärung – nur die Aufzählung.

Beispielformat:
- [REQUIRED] Bauantrag ausfüllen und unterschreiben (HBO §62)
- Grundrisszeichnungen vom Architekten einholen
- [REQUIRED] Lageplan beim Katasteramt bestellen (BauGB §1)
"""
    result = ask_ai(
        user_message=prompt,
        project=project,
        stage_key=stage_key,
        action_type=ActionType.CHECKLIST_GENERATE,
        mode=ActionMode.AUTONOMOUS,
    )

    if result.get('success'):
        # Парсим ответ в структурированный список
        items = []
        for line in result['response'].splitlines():
            line = line.strip()
            # Принимаем строки начинающиеся с «-», «*», цифры с точкой или пробел
            if not line or not (line.startswith('-') or line.startswith('*') or
                                (len(line) > 1 and line[0].isdigit() and line[1] in '.)')):
                continue
            # Убираем маркер списка
            text = line.lstrip('-*0123456789.) ').strip()
            if not text:
                continue
            required = False
            if text.upper().startswith('[REQUIRED]'):
                required = True
                text = text[len('[REQUIRED]'):].strip()
            items.append({'item': text, 'done': False, 'required': required})

        if items:
            stage = project.stages.filter_by(stage_key=stage_key).first()
            if stage:
                stage.checklist = items
                flag_modified(stage, 'checklist')
                db.session.commit()
                result['checklist_saved'] = True
                result['checklist_count'] = len(items)

    return result
