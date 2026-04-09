"""
Seed script — заполняет базовые данные для MVP (Hessen).
Запуск: flask shell → exec(open('seed_data.py').read())
Или:    python seed_data.py (с установленным FLASK_APP)
"""
from app import create_app, db
from app.models.models import Gemeinde, BebauungsplanZone
from app.models.enums import ZoneType

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

        print("\nSeed abgeschlossen!")
        print(f"Gemeinden gesamt: {Gemeinde.query.count()}")
        print(f"Zonen gesamt:     {BebauungsplanZone.query.count()}")


if __name__ == '__main__':
    seed()
