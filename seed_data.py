"""
Seed script — заполняет базовые данные для MVP (Hessen).
Запуск: flask shell → exec(open('seed_data.py').read())
Или:    python seed_data.py (с установленным FLASK_APP)
"""
from app import create_app, db
from app.models.models import Gemeinde, BebauungsplanZone, Provider, ProviderService
from app.models.enums import ZoneType, ProviderCategory, VerifiedStatus, StageKey

app = create_app()

GEMEINDEN_HESSEN = [
    {
        'name': 'Frankfurt am Main',
        'land': 'HE',
        'landkreis': 'kreisfrei',
        'ags_code': '06412000',
        'lat': 50.1109,
        'lng': 8.6821,
        'bauamt_name': 'Bauaufsicht Frankfurt',
        'bauamt_email': 'bauaufsicht@stadt-frankfurt.de',
        'bauamt_phone': '+49 69 212-0',
        'bauamt_url': 'https://www.bauaufsicht-frankfurt.de',
        'bauordnung_url': 'https://www.rv.hessenrecht.hessen.de/bshe/document/jlr-BauOHE2018rahmen',
        'bauleitplan_portal_url': 'https://bauleitplanung.hessen.de',
    },
    {
        'name': 'Wiesbaden',
        'land': 'HE',
        'landkreis': 'kreisfrei',
        'ags_code': '06414000',
        'lat': 50.0826,
        'lng': 8.2400,
        'bauamt_name': 'Bauaufsichtsamt Wiesbaden',
        'bauamt_email': 'bauaufsicht@wiesbaden.de',
        'bauamt_phone': '+49 611 31-0',
        'bauamt_url': 'https://www.wiesbaden.de/bauaufsicht',
        'bauordnung_url': 'https://www.rv.hessenrecht.hessen.de/bshe/document/jlr-BauOHE2018rahmen',
    },
    {
        'name': 'Darmstadt',
        'land': 'HE',
        'landkreis': 'kreisfrei',
        'ags_code': '06411000',
        'lat': 49.8728,
        'lng': 8.6512,
        'bauamt_name': 'Bauaufsicht Darmstadt',
        'bauamt_email': 'bauaufsicht@darmstadt.de',
        'bauamt_url': 'https://www.darmstadt.de/leben-in-darmstadt/bauen-wohnen',
    },
    {
        'name': 'Kassel',
        'land': 'HE',
        'landkreis': 'kreisfrei',
        'ags_code': '06611000',
        'lat': 51.3127,
        'lng': 9.4797,
        'bauamt_name': 'Bauaufsicht Kassel',
        'bauamt_email': 'bauaufsicht@kassel.de',
        'bauamt_url': 'https://www.kassel.de/buerger/bauen_und_wohnen',
    },
    {
        'name': 'Offenbach am Main',
        'land': 'HE',
        'landkreis': 'kreisfrei',
        'ags_code': '06413000',
        'lat': 50.1046,
        'lng': 8.7639,
        'bauamt_name': 'Bauaufsicht Offenbach',
        'bauamt_email': 'bauaufsicht@offenbach.de',
        'bauamt_url': 'https://www.offenbach.de',
    },
    {
        'name': 'Hanau',
        'land': 'HE',
        'landkreis': 'Main-Kinzig-Kreis',
        'ags_code': '06435014',
        'lat': 50.1337,
        'lng': 8.9169,
        'bauamt_name': 'Bauaufsicht Hanau',
        'bauamt_email': 'bauaufsicht@hanau.de',
        'bauamt_url': 'https://www.hanau.de',
    },
    {
        'name': 'Marburg',
        'land': 'HE',
        'landkreis': 'Marburg-Biedenkopf',
        'ags_code': '06534010',
        'lat': 50.8021,
        'lng': 8.7711,
        'bauamt_name': 'Bauaufsicht Marburg-Biedenkopf',
        'bauamt_email': 'bauaufsicht@marburg-biedenkopf.de',
        'bauamt_url': 'https://www.marburg-biedenkopf.de',
    },
    {
        'name': 'Gießen',
        'land': 'HE',
        'landkreis': 'Gießen',
        'ags_code': '06531010',
        'lat': 50.5839,
        'lng': 8.6784,
        'bauamt_name': 'Bauaufsicht Gießen',
        'bauamt_email': 'bauaufsicht@giessen.de',
        'bauamt_url': 'https://www.giessen.de',
    },
    {
        'name': 'Fulda',
        'land': 'HE',
        'landkreis': 'Fulda',
        'ags_code': '06631010',
        'lat': 50.5557,
        'lng': 9.6751,
        'bauamt_name': 'Bauaufsicht Fulda',
        'bauamt_email': 'bauaufsicht@fulda.de',
        'bauamt_url': 'https://www.fulda.de',
    },
    {
        'name': 'Bad Homburg vor der Höhe',
        'land': 'HE',
        'landkreis': 'Hochtaunuskreis',
        'ags_code': '06434004',
        'lat': 50.2271,
        'lng': 8.6176,
        'bauamt_name': 'Bauaufsicht Hochtaunuskreis',
        'bauamt_email': 'bauaufsicht@hochtaunuskreis.de',
        'bauamt_url': 'https://www.hochtaunuskreis.de',
    },
    {
        'name': 'Rüsselsheim am Main',
        'land': 'HE',
        'landkreis': 'Groß-Gerau',
        'ags_code': '06438011',
        'lat': 49.9924,
        'lng': 8.4133,
        'bauamt_name': 'Bauaufsicht Groß-Gerau',
        'bauamt_email': 'bauaufsicht@kreisgg.de',
        'bauamt_url': 'https://www.kreisgg.de',
    },
    {
        'name': 'Wetzlar',
        'land': 'HE',
        'landkreis': 'Lahn-Dill-Kreis',
        'ags_code': '06532025',
        'lat': 50.5631,
        'lng': 8.5072,
        'bauamt_name': 'Bauaufsicht Lahn-Dill-Kreis',
        'bauamt_email': 'bauaufsicht@lahn-dill-kreis.de',
        'bauamt_url': 'https://www.lahn-dill-kreis.de',
    },
    {
        'name': 'Oberursel (Taunus)',
        'land': 'HE',
        'landkreis': 'Hochtaunuskreis',
        'ags_code': '06434012',
        'lat': 50.2003,
        'lng': 8.5806,
        'bauamt_name': 'Bauaufsicht Hochtaunuskreis',
        'bauamt_email': 'bauaufsicht@hochtaunuskreis.de',
        'bauamt_url': 'https://www.hochtaunuskreis.de',
    },
    {
        'name': 'Langen (Hessen)',
        'land': 'HE',
        'landkreis': 'Offenbach',
        'ags_code': '06438007',
        'lat': 49.9896,
        'lng': 8.6579,
        'bauamt_name': 'Bauaufsicht Landkreis Offenbach',
        'bauamt_email': 'bauaufsicht@kreis-offenbach.de',
        'bauamt_url': 'https://www.kreis-offenbach.de',
    },
    {
        'name': 'Dreieich',
        'land': 'HE',
        'landkreis': 'Offenbach',
        'ags_code': '06438003',
        'lat': 50.0213,
        'lng': 8.6973,
        'bauamt_name': 'Bauaufsicht Landkreis Offenbach',
        'bauamt_email': 'bauaufsicht@kreis-offenbach.de',
        'bauamt_url': 'https://www.kreis-offenbach.de',
    },
]

# Пример зон Bebauungsplan для Frankfurt
FRANKFURT_ZONES = [
    {
        'plan_name': 'B-Plan 831 — Sachsenhausen Nord',
        'plan_number': '831',
        'zone_type': ZoneType.WA,
        'grz_max': 0.4,
        'gfz_max': 0.8,
        'max_geschosse': 2,
        'max_hoehe_m': 9.0,
        'bauweise': 'o',
    },
    {
        'plan_name': 'B-Plan 632 — Bornheim',
        'plan_number': '632',
        'zone_type': ZoneType.WA,
        'grz_max': 0.6,
        'gfz_max': 1.2,
        'max_geschosse': 3,
        'max_hoehe_m': 12.0,
        'bauweise': 'g',
    },
    {
        'plan_name': 'Innenstadt — Kerngebiet',
        'zone_type': ZoneType.GI,
        'grz_max': 1.0,
        'gfz_max': 3.5,
        'max_geschosse': 8,
        'max_hoehe_m': None,
        'bauweise': 'g',
    },
    {
        'plan_name': 'Gewerbegebiet Fechenheim',
        'zone_type': ZoneType.GE,
        'grz_max': 0.8,
        'gfz_max': 2.4,
        'max_geschosse': 6,
        'max_hoehe_m': 22.0,
        'bauweise': 'o',
    },
    {
        'plan_name': 'Nied — Mischgebiet',
        'zone_type': ZoneType.MI,
        'grz_max': 0.6,
        'gfz_max': 1.2,
        'max_geschosse': 4,
        'max_hoehe_m': 15.0,
        'bauweise': 'g',
    },
]


def seed():
    with app.app_context():
        print("Seeding Gemeinden...")
        created = 0
        updated = 0
        for data in GEMEINDEN_HESSEN:
            existing = Gemeinde.query.filter_by(ags_code=data['ags_code']).first()
            if not existing:
                g = Gemeinde(**data)
                db.session.add(g)
                created += 1
            else:
                # Update lat/lng if missing
                if existing.lat is None and data.get('lat'):
                    existing.lat = data['lat']
                    existing.lng = data['lng']
                    updated += 1
        db.session.commit()
        print(f"  ✓ {created} Gemeinden erstellt, {updated} aktualisiert")

        # Зоны для Frankfurt
        ffm = Gemeinde.query.filter_by(ags_code='06412000').first()
        if ffm:
            existing_zones = ffm.zones.count()
            if existing_zones == 0:
                print("Seeding Frankfurt zones...")
                for zdata in FRANKFURT_ZONES:
                    z = BebauungsplanZone(gemeinde_id=ffm.id, **zdata)
                    db.session.add(z)
                db.session.commit()
                print(f"  ✓ {len(FRANKFURT_ZONES)} Zonen erstellt")

        print(f"\nSeed abgeschlossen!")
        print(f"Gemeinden gesamt: {Gemeinde.query.count()}")
        print(f"Zonen gesamt:     {BebauungsplanZone.query.count()}")

        seed_providers()


def seed_providers():
    """Seed 22 фиктивных верифицированных провайдера Hessen для демо."""
    PROVIDERS = [
        {
            'company_name': 'Architekturbüro Müller & Partner',
            'contact_email': 'info@architektur-mueller-frankfurt.de',
            'contact_phone': '+49 69 1234-5678',
            'website': 'https://www.architektur-mueller-frankfurt.de',
            'description': 'Erfahrenes Architekturbüro in Frankfurt am Main. Schwerpunkt Einfamilienhäuser und Sanierungen in Hessen. Mitglied der Architektenkammer Hessen.',
            'legal_form': 'Partnerschaft',
            'vat_id': 'DE123456789',
            'rating_avg': 4.8,
            'review_count': 12,
            'category': ProviderCategory.ARCHITEKT,
            'stages': ['architect_select', 'design_planning', 'building_permit'],
            'plz': '60311',
        },
        {
            'company_name': 'BauStatik Hessen GmbH',
            'contact_email': 'statik@baustatik-hessen.de',
            'contact_phone': '+49 611 987-654',
            'website': 'https://www.baustatik-hessen.de',
            'description': 'Ingenieurbüro für Tragwerksplanung und Statik. Zertifiziert nach DIN EN 1990 Eurocode. Projekte in ganz Hessen.',
            'legal_form': 'GmbH',
            'rating_avg': 4.9,
            'review_count': 8,
            'category': ProviderCategory.STATIKER,
            'stages': ['design_planning', 'building_permit', 'foundation', 'walls_ceilings'],
            'plz': '65185',
        },
        {
            'company_name': 'KfW-Energieberatung Schmidt',
            'contact_email': 'beratung@energieschmidt-hessen.de',
            'contact_phone': '+49 6151 332211',
            'website': 'https://www.energieberatung-schmidt-darmstadt.de',
            'description': 'Zugelassener Energieeffizienz-Experte (dena-Liste). KfW-BnD und Energieausweise für Neubau und Sanierung. Fördermittelberatung WIBank Hessen.',
            'legal_form': 'Einzelunternehmen',
            'rating_avg': 4.7,
            'review_count': 23,
            'category': ProviderCategory.ENERGIEBERATER,
            'stages': ['financing', 'heating', 'solar_pv', 'ventilation', 'energy_certificate', 'facade_insulation'],
            'plz': '64283',
        },
        {
            'company_name': 'Elektro Baumann Meisterbetrieb',
            'contact_email': 'info@elektro-baumann-kassel.de',
            'contact_phone': '+49 561 77889900',
            'website': 'https://www.elektro-baumann-kassel.de',
            'description': 'Meisterbetrieb seit 1987 in Kassel. VDE-zertifizierte Elektroinstallation, Photovoltaik, Smart Home KNX. Eingetragen Handwerkskammer Kassel.',
            'legal_form': 'Einzelunternehmen',
            'rating_avg': 4.6,
            'review_count': 41,
            'category': ProviderCategory.HANDWERK_ELEKTRO,
            'stages': ['electrical', 'lighting', 'solar_pv', 'smart_home'],
            'plz': '34117',
        },
        {
            'company_name': 'SHK Therm Wiesbaden GmbH',
            'contact_email': 'service@shk-therm-wiesbaden.de',
            'contact_phone': '+49 611 445566',
            'website': 'https://www.shk-therm-wiesbaden.de',
            'description': 'Sanitär-, Heizungs- und Klimatechnik. Wärmepumpen (Vaillant, Viessmann), Fußbodenheizung, Rohrinstallation. BAFA-Förderberechtigter Fachbetrieb.',
            'legal_form': 'GmbH',
            'rating_avg': 4.5,
            'review_count': 37,
            'category': ProviderCategory.HANDWERK_SANITAER,
            'stages': ['plumbing', 'heating', 'flooring'],
            'plz': '65185',
        },
        {
            'company_name': 'Dach & Wand Rhein-Main GmbH',
            'contact_email': 'info@dach-wand-rheinmain.de',
            'contact_phone': '+49 6101 556677',
            'website': 'https://www.dach-wand-rheinmain.de',
            'description': 'Dachdeckermeisterbetrieb für Dacheindeckung, WDVS-Fassade, Dachbegrünung. Zertifizierter Verarbeiter Sto und Caparol WDVS-Systeme.',
            'legal_form': 'GmbH',
            'rating_avg': 4.4,
            'review_count': 19,
            'category': ProviderCategory.HANDWERK_DACHDECKER,
            'stages': ['roof', 'facade_insulation'],
            'plz': '63450',
        },
        {
            'company_name': 'Rohbau Hessen AG',
            'contact_email': 'projekte@rohbau-hessen.de',
            'contact_phone': '+49 69 8899-0',
            'website': 'https://www.rohbau-hessen.de',
            'description': 'Generalunternehmer für Rohbauarbeiten in Hessen. Erdbau, Fundamente, Mauerwerk, Betonbau. ISO 9001 zertifiziert, IHK Frankfurt Mitglied.',
            'legal_form': 'AG',
            'rating_avg': 4.3,
            'review_count': 54,
            'category': ProviderCategory.BAUFIRMA,
            'stages': ['earthworks', 'foundation', 'walls_ceilings', 'roof'],
            'plz': '60311',
        },
        {
            'company_name': 'Fenster & Türen Meissner KG',
            'contact_email': 'vertrieb@fenster-meissner-gmbh.de',
            'contact_phone': '+49 561 223344',
            'website': 'https://www.fenster-meissner-nordhessen.de',
            'description': 'Fensterbau und Montage in Nordhessen. RAL-Montage zertifiziert. Dreifach-Verglasung, Schallschutz, RC 2 Haustüren. Rollläden und Jalousien.',
            'legal_form': 'KG',
            'rating_avg': 4.7,
            'review_count': 28,
            'category': ProviderCategory.BAUFIRMA,
            'stages': ['windows_doors_raw', 'doors_stairs'],
            'plz': '34117',
        },
        {
            'company_name': 'Maler Kraft Meisterbetrieb',
            'contact_email': 'info@maler-kraft-frankfurt.de',
            'contact_phone': '+49 69 556677',
            'website': 'https://www.malerkraft-frankfurt.de',
            'description': 'Malermeisterbetrieb seit 1995. Innen- und Außenputz, Raumgestaltung, Dämmputz, dekorative Techniken. Qualitätsstufe Q3/Q4.',
            'legal_form': 'Einzelunternehmen',
            'rating_avg': 4.6,
            'review_count': 33,
            'category': ProviderCategory.HANDWERK_MALER,
            'stages': ['plastering'],
            'plz': '60311',
        },
        {
            'company_name': 'Fliesen Wagner GmbH',
            'contact_email': 'kontakt@fliesen-wagner-hessen.de',
            'contact_phone': '+49 6151 778899',
            'website': 'https://www.fliesen-wagner-darmstadt.de',
            'description': 'Fliesenlegebetrieb mit 20 Jahren Erfahrung. Verbundabdichtung, großformatige Fliesen, Bodenheizung-Abdeckung, Nassbereich-Spezialist.',
            'legal_form': 'GmbH',
            'rating_avg': 4.8,
            'review_count': 16,
            'category': ProviderCategory.HANDWERK_FLIESENLEGER,
            'stages': ['tiling'],
            'plz': '64283',
        },
        {
            'company_name': 'Parkett & Boden Fischer',
            'contact_email': 'fischer@boden-rheinmain.de',
            'contact_phone': '+49 6101 334455',
            'website': 'https://www.parkettfischer-offenbach.de',
            'description': 'Bodenleger für Parkett, Vinyl, Teppich und Laminat. CM-Messungen im Haus. Schleifen und Versiegeln. Spezialität: Mosaik- und Diagonalverlegung.',
            'legal_form': 'Einzelunternehmen',
            'rating_avg': 4.5,
            'review_count': 22,
            'category': ProviderCategory.HANDWERK_BODENLEGER,
            'stages': ['flooring'],
            'plz': '63065',
        },
        {
            'company_name': 'Solar Hessen GmbH',
            'contact_email': 'info@solar-hessen.de',
            'contact_phone': '+49 611 223344',
            'website': 'https://www.solar-hessen.de',
            'description': 'Photovoltaik-Fachbetrieb. Planung und Montage PV-Anlagen bis 100 kWp. KfW-270 Förderantrag, Marktstammdatenregister-Anmeldung im Service enthalten.',
            'legal_form': 'GmbH',
            'rating_avg': 4.9,
            'review_count': 61,
            'category': ProviderCategory.PV_SOLAR,
            'stages': ['solar_pv', 'electrical', 'smart_home'],
            'plz': '65185',
        },
        {
            'company_name': 'Wärmepumpe & Klima Nordhessen',
            'contact_email': 'service@waermepumpe-nordhessen.de',
            'contact_phone': '+49 561 889900',
            'website': 'https://www.wp-nordhessen.de',
            'description': 'Spezialist für Luftwärmepumpen, Erdwärme, Hybridheizung. GEG-konforme Planung. BAFA-Förderberechtigter Fachbetrieb, F-Gas-Zertifizierung.',
            'legal_form': 'GmbH & Co. KG',
            'rating_avg': 4.7,
            'review_count': 18,
            'category': ProviderCategory.HEIZUNG,
            'stages': ['heating', 'ventilation', 'energy_certificate'],
            'plz': '34117',
        },
        {
            'company_name': 'Smarthome Solutions Frankfurt',
            'contact_email': 'info@smarthome-ffm.de',
            'contact_phone': '+49 69 44556677',
            'website': 'https://www.smarthome-ffm.de',
            'description': 'KNX-Systemintegrator und Loxone-Partner. Smart-Home-Planung, Installation, Programmierung. Matter-kompatible Systeme, Photovoltaik-Integration.',
            'legal_form': 'GmbH',
            'rating_avg': 4.6,
            'review_count': 9,
            'category': ProviderCategory.SMARTHOME,
            'stages': ['smart_home', 'lighting', 'electrical'],
            'plz': '60311',
        },
        {
            'company_name': 'Gartenbau & Landschaft Grün',
            'contact_email': 'kontakt@gartengruen-hessen.de',
            'contact_phone': '+49 6032 556677',
            'website': 'https://www.gartengruen-wetterau.de',
            'description': 'Garten- und Landschaftsbau im Raum Frankfurt/Wetterau. Terassen, Einfriedungen, Sichtschutz, Gartenplanung. Regenwasserversickerung und Zisternen.',
            'legal_form': 'GmbH',
            'rating_avg': 4.5,
            'review_count': 14,
            'category': ProviderCategory.GARTENBAUER,
            'stages': ['garden', 'driveway', 'fencing'],
            'plz': '61169',
        },
        {
            'company_name': 'Makler Hessen Premium',
            'contact_email': 'info@makler-hessen-premium.de',
            'contact_phone': '+49 611 778899',
            'website': 'https://www.maklerhessen-premium.de',
            'description': 'Immobilienmakler mit Hessen-weitem Netzwerk. Baugrundstücke, Neubau-Erstbezug, Kapitalanlagen. IHK-zertifiziert nach §34c GewO. Energieausweis-Beratung.',
            'legal_form': 'GmbH',
            'rating_avg': 4.3,
            'review_count': 47,
            'category': ProviderCategory.MAKLER,
            'stages': ['land_search', 'land_check', 'land_purchase'],
            'plz': '65185',
        },
        {
            'company_name': 'Notar Dr. Bernd Hofmann',
            'contact_email': 'kanzlei@notar-hofmann-marburg.de',
            'contact_phone': '+49 6421 112233',
            'website': 'https://www.notar-hofmann-marburg.de',
            'description': 'Notariat in Marburg. Grundstückskaufverträge, Bauträgerkaufverträge, Grundbucheintragungen, Dienstbarkeiten. Spezialisiert auf Baurecht Hessen.',
            'legal_form': 'Einzelkanzlei',
            'rating_avg': 4.9,
            'review_count': 31,
            'category': ProviderCategory.NOTAR,
            'stages': ['land_purchase', 'official_notices'],
            'plz': '35037',
        },
        {
            'company_name': 'Baugutachter Hessen GbR',
            'contact_email': 'gutachten@baugutachter-hessen.de',
            'contact_phone': '+49 69 334455',
            'website': 'https://www.baugutachter-hessen.de',
            'description': 'Öffentlich bestellte und vereidigte Sachverständige für Immobilienbewertung und Schäden. Bodengutachten, Rissanalyse, Übernahmeprotokoll.',
            'legal_form': 'GbR',
            'rating_avg': 4.8,
            'review_count': 7,
            'category': ProviderCategory.GUTACHTER,
            'stages': ['land_check', 'final_acceptance', 'warranty_tracking'],
            'plz': '60311',
        },
        {
            'company_name': 'Küchen & Design Marburg',
            'contact_email': 'planung@kuechen-marburg.de',
            'contact_phone': '+49 6421 445566',
            'website': 'https://www.kuechen-design-marburg.de',
            'description': 'Küchenstudio mit eigenem Einbauservice. Maßküchen, Einbauschränke, Garderobe. Barrierefreie Küchenplanung nach DIN 18040. Lieferung und Montage Mittelhessen.',
            'legal_form': 'GmbH',
            'rating_avg': 4.5,
            'review_count': 25,
            'category': ProviderCategory.KUECHE_MOEBEL,
            'stages': ['built_in_furniture'],
            'plz': '35037',
        },
        {
            'company_name': 'Zimmerei & Dachbau Weber',
            'contact_email': 'info@zimmerei-weber-giessen.de',
            'contact_phone': '+49 641 556677',
            'website': 'https://www.zimmerei-weber-giessen.de',
            'description': 'Zimmereimeisterbetrieb in Gießen, Vogelsberg, Lahn-Dill. Holzrahmenbau, Dachstuhl, Gauben, Dachgeschossausbau. Holzschutz und Feuchteschutz.',
            'legal_form': 'Einzelunternehmen',
            'rating_avg': 4.7,
            'review_count': 20,
            'category': ProviderCategory.BAUFIRMA,
            'stages': ['roof', 'walls_ceilings', 'doors_stairs'],
            'plz': '35390',
        },
        {
            'company_name': 'Lüftungstechnik Hessen GmbH',
            'contact_email': 'info@lueftungshessen.de',
            'contact_phone': '+49 6151 998877',
            'website': 'https://www.lueftungshessen.de',
            'description': 'Spezialist für kontrollierte Wohnraumlüftung (KWL). Blower-Door-Prüfungen, Lüftungskonzepte nach DIN 1946-6. Passivhaus- und KfW-Effizienzhaus-Erfahrung.',
            'legal_form': 'GmbH',
            'rating_avg': 4.6,
            'review_count': 11,
            'category': ProviderCategory.HEIZUNG,
            'stages': ['ventilation', 'energy_certificate'],
            'plz': '64283',
        },
        {
            'company_name': 'Versicherungsmakler Bau-Protect',
            'contact_email': 'info@bau-protect-hessen.de',
            'contact_phone': '+49 611 112233',
            'website': 'https://www.bauprotect-wiesbaden.de',
            'description': 'Spezialisierter Versicherungsmakler für Bauherren. Bauherrenhaftpflicht, Bauleistungsversicherung, Feuerrohbauversicherung, Gebäudeversicherung.',
            'legal_form': 'GmbH',
            'rating_avg': 4.4,
            'review_count': 19,
            'category': ProviderCategory.VERSICHERUNG,
            'stages': ['financing', 'earthworks', 'final_acceptance', 'official_notices'],
            'plz': '65185',
        },
    ]

    print("Seeding Providers...")
    created = 0
    for p in PROVIDERS:
        if Provider.query.filter_by(contact_email=p['contact_email']).first():
            continue

        stages = p.pop('stages')
        category = p.pop('category')
        plz = p.pop('plz')

        provider = Provider(
            verified_status=VerifiedStatus.VERIFIED,
            is_active=True,
            **p,
        )
        db.session.add(provider)
        db.session.flush()  # Get provider.id

        svc = ProviderService(
            provider_id=provider.id,
            category=category,
            relevant_stages=[s for s in stages],
            service_area_plz=[plz],
        )
        db.session.add(svc)
        created += 1

    db.session.commit()
    print(f"  ✓ {created} Providers erstellt")
    print(f"Providers gesamt: {Provider.query.count()}")


if __name__ == '__main__':
    seed()
