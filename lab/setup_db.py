import sqlite3
import pandas as pd
import os

def create_mock_database():
    """
    Spins up a local SQLite database with realistic material data.
    Expanded with eco-friendly alternatives to train the KNN Machine Learning model,
    and Revit default material names (English / Spanish / Portuguese) to avoid 400
    errors when processing real BIM models.
    """
    print("Setting up EcoBIM local database...")
    db_path = "ecobim_materials.db"
    
    # remove old db if it exists to start fresh
    if os.path.exists(db_path):
        os.remove(db_path)
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # create materials table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS materials (
            material_id TEXT PRIMARY KEY,
            name TEXT,
            category TEXT,
            density_kg_m3 REAL,
            gwp_factor_kgco2_per_kg REAL,
            structural_class TEXT
        )
    ''')

    # realistic mock data (density in kg/m3, gwp in kgCO2e/kg)
    # Includes standard materials, green alternatives (for ML recommender),
    # and Revit default material names in EN / ES / PT.
    materials_data = [
        # Concrete
        ('Concrete',               'Concrete 30MPa (Standard)',           'Concrete',   2400.0, 0.150, 'A'),
        ('Eco_Concrete_1',         'Eco Concrete (20% Fly Ash)',          'Concrete',   2350.0, 0.110, 'A'),
        ('Eco_Concrete_2',         'Geopolymer Concrete',                 'Concrete',   2400.0, 0.080, 'A'),
        ('High_Strength_Concrete', 'Concrete 50MPa',                     'Concrete',   2500.0, 0.180, 'A'),

        # Wood
        ('Timber',  'CLT Timber (Standard)',   'Wood',  500.0, 0.050, 'B'),
        ('Bamboo',  'Engineered Bamboo',       'Wood',  600.0, 0.020, 'B'),

        # Metal
        ('Steel',          'Structural Steel (Virgin)',       'Metal', 7850.0, 1.800, 'A'),
        ('Recycled_Steel', 'Structural Steel (90% Recycled)', 'Metal', 7850.0, 0.450, 'A'),

        # Glass
        ('Glass', 'Window Glass', 'Glass', 2500.0, 0.850, 'C'),

        # Masonry
        ('Brick',     'Clay Brick',                           'Masonry', 1800.0, 0.240, 'B'),
        ('AAC_Block', 'Autoclaved Aerated Concrete Block',   'Masonry',  650.0, 0.380, 'B'),

        # Insulation
        ('EPS_Insulation', 'EPS Foam Insulation',    'Insulation',  20.0, 3.500, 'C'),
        ('Mineral_Wool',   'Mineral Wool Insulation','Insulation',  30.0,  1.200, 'C'),

        # Finishes
        ('Plaster',      'Gypsum Plaster',       'Finish', 1200.0, 0.120, 'C'),
        ('Ceramic_Tile', 'Ceramic Floor Tile',   'Finish', 2000.0, 0.670, 'C'),

        # Revit Defaults English
        ('Default Wall',        'Revit Default Wall Material',    'Concrete', 2200.0, 0.140, 'A'),
        ('Default Floor',       'Revit Default Floor Material',   'Concrete', 2400.0, 0.150, 'A'),
        ('Default Roof',        'Revit Default Roof Material',    'Concrete', 2400.0, 0.150, 'A'),
        ('Default Ceiling',     'Revit Default Ceiling Material', 'Finish',   1200.0, 0.120, 'C'),
        ('Generic',             'Generic Material',               'Concrete', 2000.0, 0.130, 'A'),
        ('Generic - 200mm',     'Generic 200mm',                  'Concrete', 2000.0, 0.130, 'A'),
        ('Generic - 300mm',     'Generic 300mm',                  'Concrete', 2000.0, 0.130, 'A'),
        ('Finishes - Interior', 'Interior Finish',                'Finish',   1200.0, 0.120, 'C'),

        # Revit Defaults Spanish
        ('Muro por defecto',     'Material de muro generico',    'Concrete', 2200.0, 0.140, 'A'),
        ('Suelos por defecto',   'Material de suelo generico',   'Concrete', 2400.0, 0.150, 'A'),
        ('Cubierta por defecto', 'Material de cubierta generico','Concrete', 2400.0, 0.150, 'A'),
        ('Techo por defecto',    'Material de techo generico',   'Finish',   1200.0, 0.120, 'C'),
        ('Enlucido - Blanco',    'Enlucido blanco estandar',     'Finish',    900.0, 0.110, 'C'),
        ('Enlucido - Gris',      'Enlucido gris estandar',       'Finish',    950.0, 0.115, 'C'),
        ('Hormigon',             'Hormigon estandar 30MPa',      'Concrete', 2400.0, 0.150, 'A'),
        ('Hormigon armado',      'Hormigon armado estandar',     'Concrete', 2450.0, 0.165, 'A'),
        ('Ladrillo',             'Ladrillo ceramico estandar',   'Masonry',  1800.0, 0.240, 'B'),
        ('Acero estrutural',     'Acero estructural virgen',      'Metal',   7850.0, 1.800, 'A'),
        ('Madera',               'Madera estandar',               'Wood',     550.0, 0.050, 'B'),
        ('Vidrio',               'Vidrio estandar',               'Glass',   2500.0, 0.850, 'C'),
        ('Generico - 200mm',     'Generico 200mm',                'Concrete', 2000.0, 0.130, 'A'),
        ('Generico - 225mm',     'Generico 225mm',                'Concrete', 2000.0, 0.130, 'A'),
        ('Acabados interiores',  'Acabados de interior',          'Finish',   1100.0, 0.115, 'C'),

        # Revit Defaults Portuguese
        ('Parede padrao',        'Material de parede generico',  'Concrete', 2200.0, 0.140, 'A'),
        ('Piso padrao',          'Material de piso generico',    'Concrete', 2400.0, 0.150, 'A'),
        ('Laje padrao',          'Material de laje generico',    'Concrete', 2400.0, 0.150, 'A'),
        ('Cobertura padrao',     'Material de cobertura generico','Concrete',2400.0, 0.150, 'A'),
        ('Concreto',             'Concreto 30MPa',               'Concrete', 2400.0, 0.150, 'A'),
        ('Concreto armado',      'Concreto armado padrao',       'Concrete', 2450.0, 0.165, 'A'),
        ('Tijolo',               'Tijolo ceramico padrao',       'Masonry',  1800.0, 0.240, 'B'),
        ('Aco estrutural',       'Aco estrutural virgem',         'Metal',   7850.0, 1.800, 'A'),
        ('Madeira',              'Madeira padrao',                'Wood',     550.0, 0.050, 'B'),
        ('Vidro',                'Vidro padrao',                  'Glass',   2500.0, 0.850, 'C'),
        ('Reboco - Branco',      'Reboco branco padrao',          'Finish',   900.0, 0.110, 'C'),
        ('Generico - 200mm PT',  'Generico 200mm PT',            'Concrete', 2000.0, 0.130, 'A'),
    ]

    # bulk insert
    cursor.executemany('''
        INSERT OR IGNORE INTO materials (material_id, name, category, density_kg_m3, gwp_factor_kgco2_per_kg, structural_class)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', materials_data)

    conn.commit()
    conn.close()
    print(f"Database '{db_path}' created successfully with {len(materials_data)} materials!")

if __name__ == "__main__":
    create_mock_database()