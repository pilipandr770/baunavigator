import enum


class ParcelType(str, enum.Enum):
    KAUF        = 'kauf'         # Grundstück kaufen
    MIETE       = 'miete'        # Grundstück mieten/pachten
    ERBBAURECHT = 'erbbaurecht'  # Erbbaurecht
    GEMEINDE    = 'gemeinde'     # Kommunales Wohnbauland


PARCEL_TYPE_LABELS = {
    ParcelType.KAUF:        'Zu verkaufen',
    ParcelType.MIETE:       'Zu vermieten / Pacht',
    ParcelType.ERBBAURECHT: 'Erbbaurecht',
    ParcelType.GEMEINDE:    'Kommunales Wohnbauland',
}

PARCEL_TYPE_COLORS = {
    ParcelType.KAUF:        '#ea580c',  # orange
    ParcelType.MIETE:       '#7c3aed',  # purple
    ParcelType.ERBBAURECHT: '#0891b2',  # teal
    ParcelType.GEMEINDE:    '#16a34a',  # green
}


class ParcelStatus(str, enum.Enum):
    ACTIVE   = 'active'
    RESERVED = 'reserved'
    SOLD     = 'sold'
    INACTIVE = 'inactive'


class NotificationType(str, enum.Enum):
    STAGE_CHANGE      = 'stage_change'       # Этап изменён
    LAW_UPDATE        = 'law_update'         # Изменение закона
    FINANCE_ALERT     = 'finance_alert'      # Финансовый алерт
    DOCUMENT_MISSING  = 'document_missing'   # Недостающий документ
    CAMERA_REPORT     = 'camera_report'      # Отчёт с камеры
    DEADLINE          = 'deadline'           # Дедлайн
    SYSTEM            = 'system'             # Системное


class CameraFeedType(str, enum.Enum):
    RTSP     = 'rtsp'     # IP-камера / ONVIF
    TELEGRAM = 'telegram' # Telegram-бот (внутренние работы)


class SubscriptionPlan(str, enum.Enum):
    FREE = 'free'
    PRO = 'pro'
    EXPERT = 'expert'


class SubscriptionStatus(str, enum.Enum):
    ACTIVE = 'active'
    CANCELLED = 'cancelled'
    PAST_DUE = 'past_due'
    TRIALING = 'trialing'


class ProjectType(str, enum.Enum):
    NEUBAU_EFH = 'neubau_efh'          # Новый дом (EFH)
    NEUBAU_MFH = 'neubau_mfh'          # Многоквартирный
    UMBAU = 'umbau'                      # Реконструкция
    ANBAU = 'anbau'                      # Пристройка
    KAUF = 'kauf'                        # Покупка готового


PROJECT_TYPE_LABELS = {
    ProjectType.NEUBAU_EFH: 'Neubau Einfamilienhaus',
    ProjectType.NEUBAU_MFH: 'Neubau Mehrfamilienhaus',
    ProjectType.UMBAU:      'Umbau / Sanierung',
    ProjectType.ANBAU:      'Anbau / Erweiterung',
    ProjectType.KAUF:       'Kauf Bestandsimmobilie',
}


class StageKey(str, enum.Enum):
    # Фаза A — Vorbereitung
    LAND_SEARCH = 'land_search'
    LAND_CHECK = 'land_check'
    FINANCING = 'financing'
    LAND_PURCHASE = 'land_purchase'
    # Фаза B — Genehmigung
    ARCHITECT_SELECT = 'architect_select'
    DESIGN_PLANNING = 'design_planning'
    BUILDING_PERMIT = 'building_permit'
    TENDERING = 'tendering'
    # Фаза C — Rohbau
    EARTHWORKS = 'earthworks'
    FOUNDATION = 'foundation'
    WALLS_CEILINGS = 'walls_ceilings'
    ROOF = 'roof'
    WINDOWS_DOORS_RAW = 'windows_doors_raw'
    # Фаза D — Innenausbau
    ELECTRICAL = 'electrical'
    PLUMBING = 'plumbing'
    FLOORING = 'flooring'
    TILING = 'tiling'
    PLASTERING = 'plastering'
    BUILT_IN_FURNITURE = 'built_in_furniture'
    LIGHTING = 'lighting'
    DOORS_STAIRS = 'doors_stairs'
    # Фаза E — Aussenanlagen
    FACADE_INSULATION = 'facade_insulation'
    GARAGE = 'garage'
    GARDEN = 'garden'
    DRIVEWAY = 'driveway'
    FENCING = 'fencing'
    # Фаза F — Energiesysteme
    HEATING = 'heating'
    SOLAR_PV = 'solar_pv'
    VENTILATION = 'ventilation'
    ENERGY_CERTIFICATE = 'energy_certificate'
    SMART_HOME = 'smart_home'
    # Фаза G — Abschluss
    FINAL_ACCEPTANCE = 'final_acceptance'
    OFFICIAL_NOTICES = 'official_notices'
    MOVE_IN = 'move_in'
    WARRANTY_TRACKING = 'warranty_tracking'


# Человекочитаемые названия для UI
STAGE_LABELS = {
    StageKey.LAND_SEARCH: 'Grundstücksuche',
    StageKey.LAND_CHECK: 'Grundstücksprüfung',
    StageKey.FINANCING: 'Finanzierung',
    StageKey.LAND_PURCHASE: 'Grundstückskauf',
    StageKey.ARCHITECT_SELECT: 'Architektenauswahl',
    StageKey.DESIGN_PLANNING: 'Entwurfsplanung',
    StageKey.BUILDING_PERMIT: 'Bauantrag',
    StageKey.TENDERING: 'Ausschreibung',
    StageKey.EARTHWORKS: 'Erdarbeiten',
    StageKey.FOUNDATION: 'Fundament & Keller',
    StageKey.WALLS_CEILINGS: 'Mauerwerk & Decken',
    StageKey.ROOF: 'Dach',
    StageKey.WINDOWS_DOORS_RAW: 'Fenster & Türen',
    StageKey.ELECTRICAL: 'Elektroinstallation',
    StageKey.PLUMBING: 'Sanitär & Rohre',
    StageKey.FLOORING: 'Böden',
    StageKey.TILING: 'Fliesen & Bad',
    StageKey.PLASTERING: 'Wände & Putz',
    StageKey.BUILT_IN_FURNITURE: 'Küche & Einbaumöbel',
    StageKey.LIGHTING: 'Beleuchtung',
    StageKey.DOORS_STAIRS: 'Türen & Treppenhaus',
    StageKey.FACADE_INSULATION: 'Fassade & Dämmung',
    StageKey.GARAGE: 'Garage & Carport',
    StageKey.GARDEN: 'Garten & Terrasse',
    StageKey.DRIVEWAY: 'Zufahrt & Pflaster',
    StageKey.FENCING: 'Einfriedung & Zaun',
    StageKey.HEATING: 'Heizung',
    StageKey.SOLAR_PV: 'Photovoltaik',
    StageKey.VENTILATION: 'Lüftung & Klima',
    StageKey.ENERGY_CERTIFICATE: 'Energieausweis',
    StageKey.SMART_HOME: 'Smarthome',
    StageKey.FINAL_ACCEPTANCE: 'Bauabnahme',
    StageKey.OFFICIAL_NOTICES: 'Behördenmeldungen',
    StageKey.MOVE_IN: 'Einzug & Ummeldung',
    StageKey.WARRANTY_TRACKING: 'Gewährleistung',
}

# Фазы — группировка этапов
STAGE_PHASES = {
    'A': {
        'label': 'Vorbereitung',
        'label_ru': 'Подготовка',
        'color': 'blue',
        'stages': [StageKey.LAND_SEARCH, StageKey.LAND_CHECK,
                   StageKey.FINANCING, StageKey.LAND_PURCHASE],
    },
    'B': {
        'label': 'Genehmigung',
        'label_ru': 'Разрешения',
        'color': 'purple',
        'stages': [StageKey.ARCHITECT_SELECT, StageKey.DESIGN_PLANNING,
                   StageKey.BUILDING_PERMIT, StageKey.TENDERING],
    },
    'C': {
        'label': 'Rohbau',
        'label_ru': 'Коробка',
        'color': 'amber',
        'stages': [StageKey.EARTHWORKS, StageKey.FOUNDATION,
                   StageKey.WALLS_CEILINGS, StageKey.ROOF, StageKey.WINDOWS_DOORS_RAW],
    },
    'D': {
        'label': 'Innenausbau',
        'label_ru': 'Внутренняя отделка',
        'color': 'teal',
        'stages': [StageKey.ELECTRICAL, StageKey.PLUMBING, StageKey.FLOORING,
                   StageKey.TILING, StageKey.PLASTERING, StageKey.BUILT_IN_FURNITURE,
                   StageKey.LIGHTING, StageKey.DOORS_STAIRS],
    },
    'E': {
        'label': 'Aussenanlagen',
        'label_ru': 'Внешние работы',
        'color': 'green',
        'stages': [StageKey.FACADE_INSULATION, StageKey.GARAGE,
                   StageKey.GARDEN, StageKey.DRIVEWAY, StageKey.FENCING],
    },
    'F': {
        'label': 'Energiesysteme',
        'label_ru': 'Энергетика',
        'color': 'coral',
        'stages': [StageKey.HEATING, StageKey.SOLAR_PV, StageKey.VENTILATION,
                   StageKey.ENERGY_CERTIFICATE, StageKey.SMART_HOME],
    },
    'G': {
        'label': 'Abschluss',
        'label_ru': 'Завершение',
        'color': 'gray',
        'stages': [StageKey.FINAL_ACCEPTANCE, StageKey.OFFICIAL_NOTICES,
                   StageKey.MOVE_IN, StageKey.WARRANTY_TRACKING],
    },
}


class StageStatus(str, enum.Enum):
    PENDING = 'pending'
    ACTIVE = 'active'
    BLOCKED = 'blocked'
    DONE = 'done'
    SKIPPED = 'skipped'


class ActionMode(str, enum.Enum):
    AUTONOMOUS = 'autonomous'
    CONFIRMATION_REQUIRED = 'confirmation_required'
    HUMAN_REQUIRED = 'human_required'


class ActionType(str, enum.Enum):
    ZONE_LOOKUP = 'zone_lookup'
    DRAFT_LETTER = 'draft_letter'
    KFW_CALC = 'kfw_calc'
    PROVIDER_SEARCH = 'provider_search'
    DOCUMENT_GENERATE = 'document_generate'
    TILGUNGSPLAN = 'tilgungsplan'
    CHECKLIST_GENERATE = 'checklist_generate'
    DEADLINE_SET = 'deadline_set'
    REVIEW_ANALYZE = 'review_analyze'
    GENERAL_CONSULT = 'general_consult'


class OutboxStatus(str, enum.Enum):
    DRAFT = 'draft'
    AWAITING_APPROVAL = 'awaiting_approval'
    APPROVED = 'approved'
    SENT = 'sent'
    FAILED = 'failed'


class RecipientType(str, enum.Enum):
    BAUAMT = 'bauamt'
    KFW = 'kfw'
    BANK = 'bank'
    NOTAR = 'notar'
    PROVIDER = 'provider'
    VERSICHERUNG = 'versicherung'
    OTHER = 'other'


class DocType(str, enum.Enum):
    LAGEPLAN = 'lageplan'
    BAUZEICHNUNG = 'bauzeichnung'
    STATIK = 'statik'
    KFW_ANTRAG = 'kfw_antrag'
    BRIEF = 'brief'
    GENEHMIGUNG = 'genehmigung'
    VERTRAG = 'vertrag'
    PROTOKOLL = 'protokoll'
    ENERGIEAUSWEIS = 'energieausweis'
    VERSICHERUNG = 'versicherung'
    RECHNUNG = 'rechnung'
    SONSTIGES = 'sonstiges'


DOC_TYPE_LABELS = {
    DocType.LAGEPLAN:      'Lageplan',
    DocType.BAUZEICHNUNG:  'Bauzeichnung',
    DocType.STATIK:        'Statik / Standsicherheit',
    DocType.KFW_ANTRAG:    'KfW-Antrag',
    DocType.BRIEF:         'Brief / Schreiben',
    DocType.GENEHMIGUNG:   'Genehmigung / Bescheid',
    DocType.VERTRAG:       'Vertrag',
    DocType.PROTOKOLL:     'Protokoll / Abnahme',
    DocType.ENERGIEAUSWEIS:'Energieausweis',
    DocType.VERSICHERUNG:  'Versicherung',
    DocType.RECHNUNG:      'Rechnung',
    DocType.SONSTIGES:     'Sonstiges',
}


class ZoneType(str, enum.Enum):
    WA = 'WA'   # Allgemeines Wohngebiet
    WR = 'WR'   # Reines Wohngebiet
    WB = 'WB'   # Besonderes Wohngebiet
    MI = 'MI'   # Mischgebiet
    MU = 'MU'   # Urbanes Gebiet
    MD = 'MD'   # Dorfgebiet
    GE = 'GE'   # Gewerbegebiet
    GI = 'GI'   # Industriegebiet
    SO = 'SO'   # Sondergebiet
    FK = 'FK'   # Fläche für Gemeinbedarf
    PARAGRAPH_34 = 'paragraph_34'  # Innenbereich ohne B-Plan
    PARAGRAPH_35 = 'paragraph_35'  # Außenbereich


class ProviderCategory(str, enum.Enum):
    BAUFIRMA = 'baufirma'
    HANDWERK_ELEKTRO = 'handwerk_elektro'
    HANDWERK_SANITAER = 'handwerk_sanitaer'
    HANDWERK_DACHDECKER = 'handwerk_dachdecker'
    HANDWERK_MALER = 'handwerk_maler'
    HANDWERK_FLIESENLEGER = 'handwerk_fliesenleger'
    HANDWERK_BODENLEGER = 'handwerk_bodenleger'
    ARCHITEKT = 'architekt'
    STATIKER = 'statiker'
    ENERGIEBERATER = 'energieberater'
    GUTACHTER = 'gutachter'
    NOTAR = 'notar'
    MAKLER = 'makler'
    TRANSPORT = 'transport'
    KUECHE_MOEBEL = 'kueche_moebel'
    GARTENBAUER = 'gartenbauer'
    PV_SOLAR = 'pv_solar'
    HEIZUNG = 'heizung'
    SMARTHOME = 'smarthome'
    VERSICHERUNG = 'versicherung'
    UMZUG = 'umzug'
    SONSTIGES = 'sonstiges'


PROVIDER_CATEGORY_LABELS = {
    ProviderCategory.BAUFIRMA: 'Baufirma',
    ProviderCategory.HANDWERK_ELEKTRO: 'Elektriker',
    ProviderCategory.HANDWERK_SANITAER: 'Klempner / Sanitär',
    ProviderCategory.HANDWERK_DACHDECKER: 'Dachdecker',
    ProviderCategory.HANDWERK_MALER: 'Maler / Putz',
    ProviderCategory.HANDWERK_FLIESENLEGER: 'Fliesenleger',
    ProviderCategory.HANDWERK_BODENLEGER: 'Bodenleger',
    ProviderCategory.ARCHITEKT: 'Architekt',
    ProviderCategory.STATIKER: 'Statiker',
    ProviderCategory.ENERGIEBERATER: 'Energieberater',
    ProviderCategory.GUTACHTER: 'Gutachter / Sachverständiger',
    ProviderCategory.NOTAR: 'Notar',
    ProviderCategory.MAKLER: 'Immobilienmakler',
    ProviderCategory.TRANSPORT: 'Transport & Logistik',
    ProviderCategory.KUECHE_MOEBEL: 'Küche & Einbaumöbel',
    ProviderCategory.GARTENBAUER: 'Gartenbau & Landschaft',
    ProviderCategory.PV_SOLAR: 'Photovoltaik & Solar',
    ProviderCategory.HEIZUNG: 'Heizung & Wärmepumpe',
    ProviderCategory.SMARTHOME: 'Smarthome & Automation',
    ProviderCategory.VERSICHERUNG: 'Versicherungen',
    ProviderCategory.UMZUG: 'Umzugsunternehmen',
    ProviderCategory.SONSTIGES: 'Sonstiges',
}


# ── Stage → empfohlene Fachbetrieb-Kategorien ────────────────────────────────
STAGE_PROVIDER_CATEGORIES = {
    StageKey.LAND_SEARCH:        [ProviderCategory.MAKLER, ProviderCategory.GUTACHTER],
    StageKey.LAND_CHECK:         [ProviderCategory.GUTACHTER, ProviderCategory.NOTAR],
    StageKey.FINANCING:          [ProviderCategory.ENERGIEBERATER],
    StageKey.LAND_PURCHASE:      [ProviderCategory.NOTAR],
    StageKey.ARCHITECT_SELECT:   [ProviderCategory.ARCHITEKT],
    StageKey.DESIGN_PLANNING:    [ProviderCategory.ARCHITEKT, ProviderCategory.STATIKER, ProviderCategory.ENERGIEBERATER],
    StageKey.BUILDING_PERMIT:    [ProviderCategory.ARCHITEKT, ProviderCategory.STATIKER],
    StageKey.TENDERING:          [ProviderCategory.ARCHITEKT, ProviderCategory.BAUFIRMA],
    StageKey.EARTHWORKS:         [ProviderCategory.BAUFIRMA, ProviderCategory.GUTACHTER],
    StageKey.FOUNDATION:         [ProviderCategory.BAUFIRMA, ProviderCategory.STATIKER],
    StageKey.WALLS_CEILINGS:     [ProviderCategory.BAUFIRMA],
    StageKey.ROOF:               [ProviderCategory.HANDWERK_DACHDECKER, ProviderCategory.BAUFIRMA],
    StageKey.WINDOWS_DOORS_RAW:  [ProviderCategory.BAUFIRMA],
    StageKey.ELECTRICAL:         [ProviderCategory.HANDWERK_ELEKTRO],
    StageKey.PLUMBING:           [ProviderCategory.HANDWERK_SANITAER],
    StageKey.FLOORING:           [ProviderCategory.HANDWERK_BODENLEGER],
    StageKey.TILING:             [ProviderCategory.HANDWERK_FLIESENLEGER],
    StageKey.PLASTERING:         [ProviderCategory.HANDWERK_MALER],
    StageKey.BUILT_IN_FURNITURE: [ProviderCategory.KUECHE_MOEBEL],
    StageKey.LIGHTING:           [ProviderCategory.HANDWERK_ELEKTRO, ProviderCategory.SMARTHOME],
    StageKey.DOORS_STAIRS:       [ProviderCategory.BAUFIRMA, ProviderCategory.HANDWERK_MALER],
    StageKey.FACADE_INSULATION:  [ProviderCategory.BAUFIRMA, ProviderCategory.HANDWERK_MALER, ProviderCategory.ENERGIEBERATER],
    StageKey.GARAGE:             [ProviderCategory.BAUFIRMA],
    StageKey.GARDEN:             [ProviderCategory.GARTENBAUER],
    StageKey.DRIVEWAY:           [ProviderCategory.BAUFIRMA, ProviderCategory.GARTENBAUER],
    StageKey.FENCING:            [ProviderCategory.BAUFIRMA, ProviderCategory.GARTENBAUER],
    StageKey.HEATING:            [ProviderCategory.HEIZUNG, ProviderCategory.ENERGIEBERATER],
    StageKey.SOLAR_PV:           [ProviderCategory.PV_SOLAR],
    StageKey.VENTILATION:        [ProviderCategory.HEIZUNG, ProviderCategory.HANDWERK_SANITAER],
    StageKey.ENERGY_CERTIFICATE: [ProviderCategory.ENERGIEBERATER],
    StageKey.SMART_HOME:         [ProviderCategory.SMARTHOME, ProviderCategory.HANDWERK_ELEKTRO],
    StageKey.FINAL_ACCEPTANCE:   [ProviderCategory.GUTACHTER],
    StageKey.OFFICIAL_NOTICES:   [],
    StageKey.MOVE_IN:            [ProviderCategory.UMZUG],
    StageKey.WARRANTY_TRACKING:  [ProviderCategory.GUTACHTER],
}


# ── Обязательные документы по этапам ─────────────────────────────────────────
# Каждый элемент: {name, desc, critical}
# critical=True — блокирующий документ, без него нельзя двигаться дальше
STAGE_REQUIRED_DOCS = {
    StageKey.LAND_SEARCH: [
        {"name": "Bebauungsplan-Auszug",            "desc": "Nachweis Baurechte, Nutzungszone (B-Plan oder §34 BauGB)",   "critical": True},
        {"name": "Bodenrichtwert-Auskunft (BORIS)",  "desc": "Aktuelle Bodenwerte Hessen",                                 "critical": False},
        {"name": "Grundstücks-Exposé / Angebot",     "desc": "Angebotsdokument vom Makler oder Eigentümer",               "critical": False},
    ],
    StageKey.LAND_CHECK: [
        {"name": "Bodengutachten",                   "desc": "Baugrunduntersuchung, Tragfähigkeit, Grundwasserstand",      "critical": True},
        {"name": "Altlastenauskunft",                "desc": "Katasterauszug auf Altlasten (HLNUG Hessen)",                "critical": True},
        {"name": "Grundbuchauszug",                  "desc": "Aktueller Grundbuchauszug (Lasten, Rechte, Eigentümer)",     "critical": True},
        {"name": "Erschließungsnachweis",            "desc": "Bestätigung Wasser, Abwasser, Strom, Telekom verfügbar",     "critical": False},
        {"name": "Kampfmittelfreiheitsbescheinigung","desc": "Hessischer Kampfmittelräumdienst (Pflicht Hessen)",          "critical": True},
    ],
    StageKey.FINANCING: [
        {"name": "Finanzierungsbestätigung (Bank)",  "desc": "Vorläufige Finanzierungszusage der finanzierenden Bank",     "critical": True},
        {"name": "KfW-Antragsdokumentation",         "desc": "KfW-Antrag VOR Baubeginn! (Programme 124, 261, 300)",       "critical": True},
        {"name": "Eigenkapitalnachweis",             "desc": "Kontoauszug oder Depotauszug als EK-Nachweis",              "critical": True},
        {"name": "Tilgungsplan",                     "desc": "Annuitäten-Tilgungsplan der Bank",                          "critical": False},
    ],
    StageKey.LAND_PURCHASE: [
        {"name": "Notarieller Kaufvertrag",          "desc": "Beurkundeter Grundstückskaufvertrag (§311b BGB)",           "critical": True},
        {"name": "Grunderwerbsteuer-Bescheid",       "desc": "Steuerbescheid Grunderwerbsteuer Hessen (6 %)",             "critical": True},
        {"name": "Grundbucheintragung / Auflassung", "desc": "Auflassungsvormerkung im Grundbuch",                        "critical": True},
        {"name": "Finanzierungsbestätigung (Final)", "desc": "Finale Darlehenszusage der Bank",                           "critical": True},
    ],
    StageKey.ARCHITECT_SELECT: [
        {"name": "Architektenvertrag (HOAI)",         "desc": "Unterschriebener Architektenvertrag mit Leistungsphasen",  "critical": True},
        {"name": "Kammermitgliedsnachweis Architekt","desc": "Nachweis Eintragung Architektenkammer Hessen (akh.de)",    "critical": True},
    ],
    StageKey.DESIGN_PLANNING: [
        {"name": "Vorentwurf (LP 2) / Entwurf (LP 3)","desc": "Architektonische Vorentwurfs- und Entwurfsplanung",       "critical": True},
        {"name": "GEG-Energievorberechnung",           "desc": "Nachweis Gebäudeenergiegesetz für Baugenehmigung",        "critical": True},
        {"name": "Lageplan (amtlich M 1:500)",         "desc": "Amtlicher Lageplan vom Katasteramt",                     "critical": True},
        {"name": "Abstandsflächennachweis",            "desc": "Nachweis §6 HBO Abstandsflächen",                        "critical": False},
    ],
    StageKey.BUILDING_PERMIT: [
        {"name": "Bauantrag (vollständig)",           "desc": "Eingereichte und vollständige Antragsunterlagen §64 HBO",  "critical": True},
        {"name": "Baugenehmigungsbescheid",           "desc": "Schriftlicher Genehmigungsbescheid der Bauaufsicht",       "critical": True},
        {"name": "Statik / Standsicherheitsnachweis", "desc": "Geprüfte Standsicherheit vom Statiker",                   "critical": True},
        {"name": "Entwässerungsplan",                 "desc": "Genehmigter Plan Untere Wasserbehörde",                   "critical": True},
    ],
    StageKey.TENDERING: [
        {"name": "Leistungsverzeichnisse (LV)",       "desc": "LV je Gewerk vom Architekten erstellt",                   "critical": True},
        {"name": "Min. 3 Angebote je Gewerk",         "desc": "Vergleichbare Bieterangebote",                            "critical": True},
        {"name": "Vergabevermerk",                    "desc": "Dokumentation Vergabeentscheidung",                       "critical": False},
        {"name": "Werkverträge / Bauverträge",        "desc": "Unterschriebene Verträge je Unternehmen",                 "critical": True},
    ],
    StageKey.EARTHWORKS: [
        {"name": "Leitungsauskunft (vollständig)",    "desc": "Gas, Wasser, Strom, Telekom — vor Baubeginn Pflicht",     "critical": True},
        {"name": "Baugenehmigung (Bauschild)",        "desc": "Original auf Baustelle aushängen (HBO §72)",              "critical": True},
        {"name": "Bautagebuch Eröffnung",             "desc": "Start Bautagebuch-Führung",                               "critical": False},
        {"name": "Entsorgungsnachweis Erdaushub",     "desc": "Schadstoffdokumentation Aushubmaterial",                  "critical": False},
    ],
    StageKey.FOUNDATION: [
        {"name": "Statik Fundament",                  "desc": "Geprüfte Fundamentstatik vom Statiker",                  "critical": True},
        {"name": "Abdichtungskonzept (DIN 18533)",    "desc": "Erdberührte Bauteile — Abdichtungsplanung",              "critical": True},
        {"name": "Betonierprotokoll",                 "desc": "Dokumentation Betongüte, Schalung, Bewehrung",           "critical": False},
    ],
    StageKey.WALLS_CEILINGS: [
        {"name": "Mauerwerk-Abnahmeprotokoll",        "desc": "Abnahme Rohbau-Außenwände vor Dachaufbau",              "critical": False},
        {"name": "GEG U-Wert-Nachweis Außenwand",     "desc": "U-Wert ≤ 0,28 W/(m²K) für Außenwand",                  "critical": True},
    ],
    StageKey.ROOF: [
        {"name": "Zimmerermannsvertrag",              "desc": "Vertrag mit eingetragenem Zimmerer",                     "critical": True},
        {"name": "Dachkonstruktions-Statik",          "desc": "Standsicherheitsnachweis Dachstuhl (DIN 1052)",         "critical": True},
        {"name": "Dachdeckungsprotokoll",             "desc": "Abnahmedokumentation Dachdecker",                      "critical": False},
    ],
    StageKey.WINDOWS_DOORS_RAW: [
        {"name": "U-Wert-Nachweis Fenster/Türen",    "desc": "GEG: Fenster ≤ 1,3 W/(m²K), Tür ≤ 1,8 W/(m²K)",       "critical": True},
        {"name": "RAL-Montageprotokoll",             "desc": "Fachgerechter Einbau nach RAL-Leitfaden",               "critical": False},
    ],
    StageKey.ELECTRICAL: [
        {"name": "VDE-Protokoll",                    "desc": "Elektroabnahme nach VDE 0100 — vor Netzanschluss",      "critical": True},
        {"name": "Netzanschlussantrag",              "desc": "Anmeldung beim Netzbetreiber",                          "critical": True},
        {"name": "E-Plan (Stromkreisverteiler)",     "desc": "Schaltplan/Installationsplan",                         "critical": False},
    ],
    StageKey.PLUMBING: [
        {"name": "Druckprüfprotokoll (10 bar, 30 min)","desc": "Druckprüfung Wasserleitungen vor Verputz",           "critical": True},
        {"name": "Leitungsplan Sanitär",             "desc": "Dokumentation aller Wasserleitungen",                  "critical": True},
        {"name": "Abnahme Hauswasseranschluss",      "desc": "Abnahme durch Netzbetreiber / Gemeinde",               "critical": True},
    ],
    StageKey.FLOORING: [
        {"name": "Estrich-Protokoll",                "desc": "Dokumentation Estrichverlegung und Heizprotokoll",      "critical": True},
        {"name": "CM-Messung Belegreife",            "desc": "Feuchtemessung vor Parkett/Vinyl (< 2 % CM)",          "critical": True},
    ],
    StageKey.TILING: [
        {"name": "Verbundabdichtungs-Nachweis",      "desc": "Abdichtung Nassbereiche vor Fliesenverlegung",         "critical": True},
    ],
    StageKey.PLASTERING: [
        {"name": "Abnahmeprotokoll Putz",            "desc": "Qualitätsstufe Q3/Q4 dokumentiert",                    "critical": False},
    ],
    StageKey.BUILT_IN_FURNITURE: [
        {"name": "Küchenvertrag",                    "desc": "Bestätigter Auftrag Küche/Einbaumöbel",                "critical": False},
    ],
    StageKey.LIGHTING: [
        {"name": "Beleuchtungsplan",                 "desc": "Elektrischen Installationsplan Beleuchtung",           "critical": False},
    ],
    StageKey.DOORS_STAIRS: [
        {"name": "Abnahmeprotokoll Innentüren",      "desc": "Prüfung Schallschutz DIN 4109 + Brandschutz",         "critical": False},
    ],
    StageKey.FACADE_INSULATION: [
        {"name": "WDVS-Übereinstimmungserklärung",   "desc": "CE-Kennzeichnung Dämmstoff WDVS",                     "critical": True},
        {"name": "Energieberater-Bescheinigung",     "desc": "Nachweis GEG-Anforderungen Fassade",                  "critical": True},
    ],
    StageKey.GARAGE: [
        {"name": "Genehmigung Garage/Carport",       "desc": "Baugenehmigung oder Freistellungsbescheid",            "critical": True},
    ],
    StageKey.GARDEN: [
        {"name": "Bepflanzungsplan",                 "desc": "Sofern B-Plan Begrünung vorschreibt",                  "critical": False},
    ],
    StageKey.DRIVEWAY: [
        {"name": "Entwässerungsantrag Zufahrt",      "desc": "Genehmigung Straßenentwässerung",                      "critical": False},
    ],
    StageKey.FENCING: [
        {"name": "Genehmigung Einfriedung",          "desc": "Falls B-Plan Grenzabstand vorschreibt",                "critical": False},
    ],
    StageKey.HEATING: [
        {"name": "GEG-konformer Heizungsnachweis",   "desc": "§71 GEG — 65 % erneuerbare Energie ab 2024",          "critical": True},
        {"name": "BEG/BAFA-Förderantrag",            "desc": "Antrag KfW-458 oder BAFA — vor Einbau stellen!",      "critical": True},
        {"name": "Inbetriebnahmeprotokoll Heizung",  "desc": "Herstellerprotokoll + Abnahme Schornsteinfeger",       "critical": True},
    ],
    StageKey.SOLAR_PV: [
        {"name": "Netzanmeldung Marktstammdatenregister","desc": "Bundesnetzagentur — Pflicht nach EEG",             "critical": True},
        {"name": "KfW-270-Antrag",                   "desc": "Vor Beauftragung stellen",                            "critical": False},
        {"name": "PV-Abnahmeprotokoll",              "desc": "Netzbetreiber-Abnahme Einspeiseanlage",               "critical": True},
    ],
    StageKey.VENTILATION: [
        {"name": "Lüftungskonzept (DIN 1946-6)",     "desc": "Pflichtnachweis für luftdichtes Gebäude",              "critical": True},
        {"name": "Inbetriebnahmeprotokoll Lüftung",  "desc": "Luftmengenabgleich und Abnahme",                      "critical": False},
    ],
    StageKey.ENERGY_CERTIFICATE: [
        {"name": "Energieausweis (Bedarfsausweis)",  "desc": "Ausgestellt von KfW-Experten nach GEG §79",           "critical": True},
        {"name": "Blower-Door-Test-Protokoll",       "desc": "Luftdichtheitsmessung n50 ≤ 1,5 h⁻¹",                "critical": False},
    ],
    StageKey.SMART_HOME: [
        {"name": "Smart-Home-Konfigurationsplan",    "desc": "Installationsplan Bussystem / Steuerlogik",            "critical": False},
    ],
    StageKey.FINAL_ACCEPTANCE: [
        {"name": "Abnahmeprotokoll Bauabnahme",      "desc": "Gemeinsame Abnahme mit Bauleiter — Mängelliste",      "critical": True},
        {"name": "Fertigstellungsanzeige",           "desc": "HBO §74 Fertigstellung anzeigen (Bauaufsicht)",       "critical": True},
        {"name": "Sachverständigenprotokoll",        "desc": "Unabhängige Abnahme empfohlen (DEKRA/TÜV)",           "critical": False},
    ],
    StageKey.OFFICIAL_NOTICES: [
        {"name": "Nutzungsänderungsanzeige",         "desc": "Falls Nutzung abweicht von Genehmigung",              "critical": False},
        {"name": "Fertigstellungsanzeige eingereicht","desc": "Eingangsbestätigung Bauaufsicht",                    "critical": True},
    ],
    StageKey.MOVE_IN: [
        {"name": "Ummeldebescheinigung",             "desc": "Anmeldung neuer Wohnsitz beim Einwohnermeldeamt",     "critical": True},
        {"name": "Versicherungsnachweis Wohngebäude","desc": "Wohngebäudeversicherung ab Einzug aktiv",            "critical": True},
        {"name": "Zählerstandsprotokoll",            "desc": "Strom- und Gaszähler-Ablesedokumentation",            "critical": False},
    ],
    StageKey.WARRANTY_TRACKING: [
        {"name": "Mängelliste & Nachbesserungs-Protokolle","desc": "Dokumentation aller gemeldeten Mängel",        "critical": False},
        {"name": "Gewährleistungsfristen-Übersicht", "desc": "je Gewerk (i.d.R. 5 Jahre nach BGB §634a)",          "critical": True},
    ],
}


class LicenseType(str, enum.Enum):
    MEISTERBRIEF = 'meisterbrief'
    KAMMERMITGLIED = 'kammermitglied'
    KFW_EXPERTE = 'kfw_experte'
    GUTACHTER_OBUV = 'gutachter_obuv'
    NOTARZULASSUNG = 'notarzulassung'
    HAFTPFLICHT = 'haftpflicht'
    GEWERBEANMELDUNG = 'gewerbeanmeldung'
    BAULEITER_ZULASSUNG = 'bauleiter_zulassung'


class VerifiedStatus(str, enum.Enum):
    PENDING = 'pending'
    VERIFIED = 'verified'
    REJECTED = 'rejected'
    SUSPENDED = 'suspended'


class ProviderPlan(str, enum.Enum):
    BASIC = 'basic'
    PREMIUM = 'premium'


class LeadStatus(str, enum.Enum):
    SENT = 'sent'
    VIEWED = 'viewed'
    CONTACTED = 'contacted'
    WON = 'won'
    LOST = 'lost'


class FinancingStatus(str, enum.Enum):
    DRAFT = 'draft'
    KFW_APPLIED = 'kfw_applied'
    BANK_APPLIED = 'bank_applied'
    APPROVED = 'approved'
    ACTIVE = 'active'
