# SANTÉ-TCHÉ — Générateur de Menus Nutritionnels
## Guide d'installation complet (Windows + XAMPP)

---

## PRÉREQUIS

- **XAMPP** (avec MySQL démarré) → https://www.apachefriends.org/
- **Python 3.10+** → https://www.python.org/downloads/
- **pip** (inclus avec Python)

---

## INSTALLATION EN 5 ÉTAPES

### 1. Copier le projet

Copiez le dossier `sante_tche/` dans le répertoire de votre choix.
Exemple : `C:\projets\sante_tche\`

---

### 2. Démarrer MySQL via XAMPP

Ouvrez **XAMPP Control Panel** → cliquez **Start** sur **MySQL**.

> La base de données `sante_tche` sera créée **automatiquement** au premier lancement.
> Aucune action manuelle dans phpMyAdmin n'est nécessaire.

---

### 3. Créer un environnement virtuel Python

```bash
cd C:\projets\sante_tche

# Créer l'environnement
python -m venv venv

# Activer (Windows)
venv\Scripts\activate

# Activer (Mac/Linux)
source venv/bin/activate
```

---

### 4. Installer les dépendances

```bash
pip install -r requirements.txt
```

#### ⚠️ WeasyPrint sur Windows nécessite GTK :
Télécharger et installer **GTK3 Runtime** depuis :
https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases
→ Choisir `gtk3-runtime-x.x.x-x.x.x-ts-win64.exe`

---

### 5. Lancer l'application

```bash
python app.py
```

Ouvrez votre navigateur → **http://localhost:5000**

---

## PREMIER LANCEMENT

1. Allez sur **http://localhost:5000/setup**
2. Créez votre compte nutritionniste (email + mot de passe)
3. Connectez-vous → Tableau de bord

> Maximum **3 comptes nutritionnistes** sur la plateforme.

---

## UTILISATION

### Créer un menu complet

```
1. Tableau de bord → "Nouveau patient"
   └── Renseignez nom, prénom, objectif

2. Fiche patient → "Nouveau menu"
   └── Choisissez la semaine (lundi de départ)

3. Saisie jour par jour (Lundi → Dimanche)
   Pour chaque jour :
   └── 5 repas avec horaires fixes (07h, 10h30, 12h30, 16h, 19h30)
   └── Chaque repas : image obligatoire + plats variables (quantité + nom)
   └── Bouton "➕ Ajouter un plat" pour ajouter autant de lignes que voulu
   └── Boutons ↑↓ pour réordonner les plats
   └── "📋 Copier vers un autre jour" pour dupliquer un repas
   └── Bandeau nutrition personnalisable (5 valeurs + barres de progression)

4. Jour 7 → "✅ Valider la semaine"
   └── Récapitulatif affiché avant validation finale
   └── Enregistrement en base MySQL

5. Export PDF
   └── "📄 PDF jour" → 1 page A4 par jour
   └── "📦 PDF semaine" → 7 pages A4 (semaine complète)
```

---

## STRUCTURE BDD (MySQL)

```
sante_tche
├── nutritionnistes     (max 3 comptes)
├── patients            (liés à un nutritionniste)
├── menus               (1 menu = 1 semaine pour 1 patient)
├── jours               (7 par menu)
├── nutrition_jours     (bandeau nutritionnel par jour)
├── repas               (5 par jour, horaires fixes)
├── plats               (variable par repas, ordre personnalisable)
├── templates_repas     (repas types sauvegardés)
└── templates_plats     (plats des templates)
```

---

## CONFIGURATION (optionnelle)

Modifier `config.py` pour changer :

```python
MYSQL_HOST     = 'localhost'   # Hôte MySQL
MYSQL_PORT     = 3306          # Port MySQL
MYSQL_USER     = 'root'        # Utilisateur (XAMPP = root)
MYSQL_PASSWORD = ''            # Mot de passe (XAMPP = vide par défaut)
MYSQL_DB       = 'sante_tche'  # Nom de la base
```

Ou via variables d'environnement :
```bash
set MYSQL_PASSWORD=monmotdepasse   # Windows
export MYSQL_PASSWORD=monmotdepasse  # Linux/Mac
```

---

## ARBORESCENCE DU PROJET

```
sante_tche/
├── app.py                    ← Point d'entrée Flask
├── config.py                 ← Configuration MySQL + Flask
├── db.py                     ← Création auto BDD + schéma SQL
├── requirements.txt          ← Dépendances Python
├── routes/
│   ├── auth.py               ← Login / Logout / Création compte
│   ├── main.py               ← Dashboard + Patients
│   ├── formulaire.py         ← Saisie 7 jours (session → BDD)
│   └── export.py             ← Export PDF WeasyPrint
├── templates/
│   ├── base.html             ← Layout principal avec navigation
│   ├── login.html            ← Page de connexion
│   ├── setup.html            ← Création compte
│   ├── dashboard.html        ← Liste patients
│   ├── patient_form.html     ← Créer / modifier patient
│   ├── fiche_patient.html    ← Fiche avec historique menus
│   ├── menu_nouveau.html     ← Choix semaine
│   ├── formulaire.html       ← Saisie jour par jour ← CŒUR APP
│   ├── apercu.html           ← Rendu Santé-Tché (Jinja) ← TEMPLATE FINAL
│   ├── apercu_semaine.html   ← 7 pages pour PDF semaine
│   └── validation.html       ← Récapitulatif avant BDD
└── static/
    ├── css/
    │   ├── style.css         ← Styles app générale
    │   └── formulaire.css    ← Styles formulaire de saisie
    └── uploads/              ← Images uploadées (auto-créé)
```

---

## FLUX DE DONNÉES

```
SAISIE (formulaire.html)
    │
    ▼ POST avec images + plats
SESSION Flask (stockage temporaire)
    │
    ▼ Validation jour par jour
    ▼ Aperçu possible à tout moment
    │
    ▼ Jour 7 → Page validation.html
    │
    ▼ POST validation finale
BASE MySQL (persistance définitive)
    │
    ├── Aperçu depuis BDD → apercu.html (Jinja)
    └── Export PDF → WeasyPrint → fichier .pdf
```

---

## DÉPENDANCES PYTHON

| Package | Usage |
|---------|-------|
| Flask | Framework web |
| mysql-connector-python | Connexion MySQL XAMPP |
| WeasyPrint | Génération PDF professionnelle |
| Werkzeug | Hash mots de passe + upload fichiers |
| Pillow | Traitement images (redimensionnement) |
| Flask-Session | Sessions côté serveur |

---

*Développé pour Santé-Tché — Nutrition & Diététique, Bénin*
