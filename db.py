import psycopg2
import psycopg2.extras
from config import Config

# ─────────────────────────────────────────────────────────────
#  CONNEXION
# ─────────────────────────────────────────────────────────────
def get_connection():
    conn = psycopg2.connect(Config.DATABASE_URL, sslmode='require')
    return conn

def dict_cursor(conn):
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


# ─────────────────────────────────────────────────────────────
#  DONNÉES FIXES (inchangées)
# ─────────────────────────────────────────────────────────────
JOURS_SEMAINE = ['Lundi','Mardi','Mercredi','Jeudi','Vendredi','Samedi','Dimanche']

REPAS_DEFAUTS = [
    (1, 'Petit-déjeuner',      '07h00', '🌅'),
    (2, 'Collation avant-midi','10h30', '🥗'),
    (3, 'Déjeuner',            '12h30', '🍽️'),
    (4, 'Collation après-midi','16h00', '🍊'),
    (5, 'Dîner',               '19h30', '🌙'),
]


# ─────────────────────────────────────────────────────────────
#  CRÉATION AUTOMATIQUE DES TABLES
# ─────────────────────────────────────────────────────────────
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS nutritionnistes (
    id            SERIAL PRIMARY KEY,
    nom           VARCHAR(100) NOT NULL,
    prenom        VARCHAR(100) NOT NULL,
    email         VARCHAR(150) NOT NULL UNIQUE,
    password_hash VARCHAR(256) NOT NULL,
    actif         SMALLINT     NOT NULL DEFAULT 1,
    created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS patients (
    id                SERIAL PRIMARY KEY,
    nutritionniste_id INT          NOT NULL,
    nom               VARCHAR(100) NOT NULL,
    prenom            VARCHAR(100) NOT NULL,
    date_naissance    DATE,
    sexe              VARCHAR(10),
    objectif          VARCHAR(200),
    notes             TEXT,
    actif             SMALLINT     NOT NULL DEFAULT 1,
    created_at        TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (nutritionniste_id) REFERENCES nutritionnistes(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS menus (
    id                SERIAL PRIMARY KEY,
    patient_id        INT          NOT NULL,
    nutritionniste_id INT          NOT NULL,
    semaine_debut     DATE         NOT NULL,
    titre             VARCHAR(200),
    statut            VARCHAR(20)  NOT NULL DEFAULT 'brouillon',
    created_at        TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id)        REFERENCES patients(id)        ON DELETE RESTRICT,
    FOREIGN KEY (nutritionniste_id) REFERENCES nutritionnistes(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS jours (
    id       SERIAL PRIMARY KEY,
    menu_id  INT     NOT NULL,
    numero   SMALLINT NOT NULL,
    nom_jour VARCHAR(20) NOT NULL,
    FOREIGN KEY (menu_id) REFERENCES menus(id) ON DELETE CASCADE,
    UNIQUE (menu_id, numero)
);

CREATE TABLE IF NOT EXISTS nutrition_jours (
    id               SERIAL PRIMARY KEY,
    jour_id          INT          NOT NULL UNIQUE,
    nb_repas         VARCHAR(20)  DEFAULT '5',
    regime           VARCHAR(100) DEFAULT 'Équilibré',
    apport_cle       VARCHAR(100) DEFAULT '↑ Fibres',
    restriction      VARCHAR(100) DEFAULT '↓ Sucres',
    proteines        VARCHAR(50)  DEFAULT '150 g',
    bar_nb_repas     SMALLINT     DEFAULT 100,
    bar_regime       SMALLINT     DEFAULT 80,
    bar_apport       SMALLINT     DEFAULT 72,
    bar_restriction  SMALLINT     DEFAULT 60,
    bar_proteines    SMALLINT     DEFAULT 65,
    FOREIGN KEY (jour_id) REFERENCES jours(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS repas (
    id         SERIAL PRIMARY KEY,
    jour_id    INT          NOT NULL,
    ordre      SMALLINT     NOT NULL,
    nom        VARCHAR(100) NOT NULL,
    heure      VARCHAR(10)  NOT NULL,
    icone      VARCHAR(10)  NOT NULL DEFAULT '🍽️',
    image_path VARCHAR(300),
    FOREIGN KEY (jour_id) REFERENCES jours(id) ON DELETE CASCADE,
    UNIQUE (jour_id, ordre)
);

CREATE TABLE IF NOT EXISTS plats (
    id       SERIAL PRIMARY KEY,
    repas_id INT          NOT NULL,
    ordre    SMALLINT     NOT NULL DEFAULT 1,
    quantite VARCHAR(80)  NOT NULL,
    nom      VARCHAR(200) NOT NULL,
    FOREIGN KEY (repas_id) REFERENCES repas(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS templates_repas (
    id                SERIAL PRIMARY KEY,
    nutritionniste_id INT          NOT NULL,
    nom_template      VARCHAR(150) NOT NULL,
    nom_repas         VARCHAR(100) NOT NULL,
    heure             VARCHAR(10)  NOT NULL,
    icone             VARCHAR(10)  NOT NULL DEFAULT '🍽️',
    created_at        TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (nutritionniste_id) REFERENCES nutritionnistes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS templates_plats (
    id          SERIAL PRIMARY KEY,
    template_id INT          NOT NULL,
    ordre       SMALLINT     NOT NULL DEFAULT 1,
    quantite    VARCHAR(80)  NOT NULL,
    nom         VARCHAR(200) NOT NULL,
    FOREIGN KEY (template_id) REFERENCES templates_repas(id) ON DELETE CASCADE
);
"""


def init_db():
    """Crée toutes les tables si elles n'existent pas."""
    try:
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute(SCHEMA_SQL)
        conn.commit()
        cur.close()
        conn.close()
        print("[DB] Tables PostgreSQL initialisées.")
    except Exception as e:
        print(f"[DB ERROR] {e}")
        raise