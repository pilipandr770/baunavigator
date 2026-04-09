import enum


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
