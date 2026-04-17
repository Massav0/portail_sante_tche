import os, uuid, json, copy
from flask import (Blueprint, render_template, request, redirect,
                   url_for, session, flash, jsonify)
from werkzeug.utils import secure_filename
from routes.auth import login_required
from db import get_connection, dict_cursor, JOURS_SEMAINE, REPAS_DEFAUTS
from config import Config

formulaire_bp = Blueprint('formulaire', __name__)

ALLOWED_EXT = {'jpg', 'jpeg', 'png', 'webp', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT

def _session_key(menu_id):
    return f'menu_draft_{menu_id}'

def _init_draft(menu_id, patient_nom):
    """Initialise la structure de draft en session pour les 7 jours."""
    key = _session_key(menu_id)
    if key not in session:
        draft = {'patient_nom': patient_nom, 'jours': {}}
        for i, nom in enumerate(JOURS_SEMAINE, 1):
            draft['jours'][str(i)] = {
                'nom': nom,
                'repas': {
                    str(r[0]): {
                        'ordre': r[0], 'nom': r[1], 'heure': r[2], 'icone': r[3],
                        'image_path': None, 'image_temp': None,
                        'plats': []
                    } for r in REPAS_DEFAUTS
                },
                'nutrition': {
                    'nb_repas': '5', 'regime': 'Équilibré',
                    'apport_cle': '↑ Fibres', 'restriction': '↓ Sucres',
                    'proteines': '150 g',
                    'bar_nb_repas': 100, 'bar_regime': 80,
                    'bar_apport': 72, 'bar_restriction': 60, 'bar_proteines': 65
                }
            }
        session[key] = draft
        session.modified = True
    return session[key]


# ── CRÉER UN NOUVEAU MENU ─────────────────────────────────────────────────────
@formulaire_bp.route('/patients/<int:pid>/menu/nouveau', methods=['GET', 'POST'])
@login_required
def nouveau_menu(pid):
    conn = get_connection()
    cur  = dict_cursor(conn)
    cur.execute("SELECT * FROM patients WHERE id=%s AND nutritionniste_id=%s",
                (pid, session['nutritionniste_id']))
    patient = cur.fetchone()
    if not patient:
        cur.close(); conn.close()
        flash('Patient introuvable.', 'danger')
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        semaine = request.form.get('semaine_debut')
        titre   = request.form.get('titre', '').strip() or f"Menu semaine {semaine}"

        # ✅ RETURNING id pour récupérer le vrai menu_id
        cur.execute("""
            INSERT INTO menus (patient_id, nutritionniste_id, semaine_debut, titre, statut)
            VALUES (%s,%s,%s,%s,'brouillon') RETURNING id
        """, (pid, session['nutritionniste_id'], semaine, titre))
        conn.commit()
        menu_id = cur.fetchone()['id']  # ✅ vrai id, plus "1" codé en dur
        cur.close(); conn.close()

        patient_nom = f"{patient['prenom']} {patient['nom']}"
        _init_draft(menu_id, patient_nom)
        return redirect(url_for('formulaire.saisie_jour',
                                menu_id=menu_id, jour_num=1))

    cur.close(); conn.close()
    return render_template('menu_nouveau.html', patient=patient)


# ── SAISIE JOUR PAR JOUR ──────────────────────────────────────────────────────
@formulaire_bp.route('/menu/<int:menu_id>/jour/<int:jour_num>', methods=['GET', 'POST'])
@login_required
def saisie_jour(menu_id, jour_num):
    if jour_num < 1 or jour_num > 7:
        return redirect(url_for('formulaire.saisie_jour', menu_id=menu_id, jour_num=1))

    conn = get_connection()
    cur  = dict_cursor(conn)
    cur.execute("""
        SELECT m.*, p.nom AS p_nom, p.prenom AS p_prenom, p.id AS pid
        FROM menus m JOIN patients p ON p.id = m.patient_id
        WHERE m.id=%s AND m.nutritionniste_id=%s
    """, (menu_id, session['nutritionniste_id']))
    menu = cur.fetchone()
    cur.close(); conn.close()

    if not menu:
        flash('Menu introuvable.', 'danger')
        return redirect(url_for('main.dashboard'))

    patient_nom = f"{menu['p_prenom']} {menu['p_nom']}"
    draft = _init_draft(menu_id, patient_nom)
    jour_data = draft['jours'][str(jour_num)]

    # ── POST : sauvegarder ce jour en session ─────────────────────────────────
    if request.method == 'POST':
        action = request.form.get('action', 'suivant')
        errors = []

        for r_ordre in range(1, 6):
            r_key  = str(r_ordre)
            repas  = jour_data['repas'][r_key]
            r_nom  = repas['nom']

            # Plats
            quantites = request.form.getlist(f'repas_{r_ordre}_quantite[]')
            noms_plat = request.form.getlist(f'repas_{r_ordre}_nom[]')
            plats = []
            for q, n in zip(quantites, noms_plat):
                q, n = q.strip(), n.strip()
                if q or n:
                    if not q:
                        errors.append(f"Quantité manquante pour un plat de « {r_nom} »")
                    elif not n:
                        errors.append(f"Nom manquant pour un plat de « {r_nom} »")
                    else:
                        plats.append({'quantite': q, 'nom': n})

            if not plats:
                errors.append(f"Ajoutez au moins un plat pour « {r_nom} »")
            repas['plats'] = plats

            # Image upload
            img_file = request.files.get(f'repas_{r_ordre}_image')
            if img_file and img_file.filename and allowed_file(img_file.filename):
                ext      = img_file.filename.rsplit('.', 1)[1].lower()
                fname    = f"menu{menu_id}_j{jour_num}_r{r_ordre}_{uuid.uuid4().hex[:8]}.{ext}"
                savepath = os.path.join(Config.UPLOAD_FOLDER, fname)
                os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
                img_file.save(savepath)
                repas['image_path'] = f"uploads/{fname}"
            elif img_file and img_file.filename:
                errors.append(f"Format d'image invalide pour « {r_nom} » (jpg/png/webp)")

            if not repas['image_path']:
                errors.append(f"L'image de « {r_nom} » est obligatoire")

        # Nutrition
        nutr = jour_data['nutrition']
        for field in ['nb_repas','regime','apport_cle','restriction','proteines']:
            val = request.form.get(f'nutr_{field}', '').strip()
            if val:
                nutr[field] = val
        for field in ['bar_nb_repas','bar_regime','bar_apport','bar_restriction','bar_proteines']:
            val = request.form.get(f'nutr_{field}', '')
            if val.isdigit():
                nutr[field] = int(val)

        session.modified = True

        if errors and action != 'sauvegarder':
            for e in errors:
                flash(e, 'danger')
            return render_template('formulaire.html',
                                   menu=menu, jour_num=jour_num,
                                   jour_data=jour_data, draft=draft,
                                   jours=JOURS_SEMAINE, errors=errors)

        if action == 'precedent':
            return redirect(url_for('formulaire.saisie_jour',
                                    menu_id=menu_id, jour_num=max(1, jour_num-1)))
        elif action == 'apercu':
            return redirect(url_for('formulaire.apercu',
                                    menu_id=menu_id, jour_num=jour_num))
        elif action == 'valider':
            return redirect(url_for('formulaire.valider_menu', menu_id=menu_id))
        else:  # suivant
            if jour_num < 7:
                return redirect(url_for('formulaire.saisie_jour',
                                        menu_id=menu_id, jour_num=jour_num+1))
            else:
                return redirect(url_for('formulaire.valider_menu', menu_id=menu_id))

    return render_template('formulaire.html',
                           menu=menu, jour_num=jour_num,
                           jour_data=jour_data, draft=draft,
                           jours=JOURS_SEMAINE, errors=[])


# ── APERÇU D'UN JOUR ──────────────────────────────────────────────────────────
@formulaire_bp.route('/menu/<int:menu_id>/apercu/<int:jour_num>')
@login_required
def apercu(menu_id, jour_num):
    conn = get_connection()
    cur  = dict_cursor(conn)
    cur.execute("""
        SELECT m.*, p.nom AS p_nom, p.prenom AS p_prenom
        FROM menus m JOIN patients p ON p.id=m.patient_id
        WHERE m.id=%s AND m.nutritionniste_id=%s
    """, (menu_id, session['nutritionniste_id']))
    menu = cur.fetchone()
    cur.close(); conn.close()

    if not menu:
        flash('Menu introuvable.', 'danger')
        return redirect(url_for('main.dashboard'))

    key = _session_key(menu_id)
    draft = session.get(key)
    if not draft:
        flash('Aucune donnée en cours pour ce menu.', 'warning')
        return redirect(url_for('formulaire.saisie_jour',
                                menu_id=menu_id, jour_num=jour_num))

    patient_nom = f"{menu['p_prenom']} {menu['p_nom']}"
    jour_data   = draft['jours'][str(jour_num)]
    date_str    = menu['semaine_debut'].strftime('%d_%m_%Y') if hasattr(menu['semaine_debut'], 'strftime') else str(menu['semaine_debut'])

    return render_template('apercu.html',
                           menu=menu, jour_num=jour_num,
                           jour_data=jour_data, patient_nom=patient_nom,
                           date_str=date_str, jours=JOURS_SEMAINE,
                           preview_mode=True)


# ── APERÇU DEPUIS BDD (menu déjà validé) ─────────────────────────────────────
@formulaire_bp.route('/menu/<int:menu_id>/voir/<int:jour_num>')
@login_required
def voir_menu(menu_id, jour_num):
    conn = get_connection()
    cur  = dict_cursor(conn)
    cur.execute("""
        SELECT m.*, p.nom AS p_nom, p.prenom AS p_prenom
        FROM menus m JOIN patients p ON p.id=m.patient_id
        WHERE m.id=%s AND m.nutritionniste_id=%s
    """, (menu_id, session['nutritionniste_id']))
    menu = cur.fetchone()
    if not menu:
        cur.close(); conn.close()
        flash('Menu introuvable.', 'danger')
        return redirect(url_for('main.dashboard'))

    cur.execute("SELECT * FROM jours WHERE menu_id=%s AND numero=%s", (menu_id, jour_num))
    jour_row = cur.fetchone()
    if not jour_row:
        cur.close(); conn.close()
        flash('Jour non trouvé.', 'danger')
        return redirect(url_for('main.fiche_patient', pid=menu['patient_id']))

    jour_id = jour_row['id']

    cur.execute("SELECT * FROM nutrition_jours WHERE jour_id=%s", (jour_id,))
    nutr = cur.fetchone() or {}

    cur.execute("SELECT * FROM repas WHERE jour_id=%s ORDER BY ordre", (jour_id,))
    repas_rows = cur.fetchall()
    repas_dict = {}
    for r in repas_rows:
        cur.execute("SELECT * FROM plats WHERE repas_id=%s ORDER BY ordre", (r['id'],))
        plats = cur.fetchall()
        repas_dict[str(r['ordre'])] = {
            'ordre': r['ordre'], 'nom': r['nom'], 'heure': r['heure'],
            'icone': r['icone'], 'image_path': r['image_path'],
            'plats': [{'quantite': p['quantite'], 'nom': p['nom']} for p in plats]
        }
    cur.close(); conn.close()

    jour_data = {
        'nom': jour_row['nom_jour'],
        'repas': repas_dict,
        'nutrition': {
            'nb_repas':        nutr.get('nb_repas', '5'),
            'regime':          nutr.get('regime', 'Équilibré'),
            'apport_cle':      nutr.get('apport_cle', '↑ Fibres'),
            'restriction':     nutr.get('restriction', '↓ Sucres'),
            'proteines':       nutr.get('proteines', '150 g'),
            'bar_nb_repas':    nutr.get('bar_nb_repas', 100),
            'bar_regime':      nutr.get('bar_regime', 80),
            'bar_apport':      nutr.get('bar_apport', 72),
            'bar_restriction': nutr.get('bar_restriction', 60),
            'bar_proteines':   nutr.get('bar_proteines', 65),
        }
    }
    patient_nom = f"{menu['p_prenom']} {menu['p_nom']}"
    date_str = menu['semaine_debut'].strftime('%d_%m_%Y') if hasattr(menu['semaine_debut'], 'strftime') else str(menu['semaine_debut'])

    return render_template('apercu.html',
                           menu=menu, jour_num=jour_num,
                           jour_data=jour_data, patient_nom=patient_nom,
                           date_str=date_str, jours=JOURS_SEMAINE,
                           preview_mode=False)


# ── VALIDER ET PERSISTER EN BDD ───────────────────────────────────────────────
@formulaire_bp.route('/menu/<int:menu_id>/valider', methods=['GET','POST'])
@login_required
def valider_menu(menu_id):
    key   = _session_key(menu_id)
    draft = session.get(key)
    if not draft:
        flash('Aucune donnée à valider.', 'warning')
        return redirect(url_for('main.dashboard'))

    conn = get_connection()
    cur  = dict_cursor(conn)
    cur.execute("SELECT * FROM menus WHERE id=%s AND nutritionniste_id=%s",
                (menu_id, session['nutritionniste_id']))
    menu = cur.fetchone()
    if not menu:
        cur.close(); conn.close()
        flash('Menu introuvable.', 'danger')
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        try:
            # DELETE ne retourne rien → pas de fetchone
            cur.execute("DELETE FROM jours WHERE menu_id=%s", (menu_id,))

            for j_num in range(1, 8):
                j_data = draft['jours'][str(j_num)]

                # ✅ RETURNING id sur tous les INSERT dont on a besoin de l'id
                cur.execute(
                    "INSERT INTO jours (menu_id, numero, nom_jour) VALUES (%s,%s,%s) RETURNING id",
                    (menu_id, j_num, j_data['nom'])
                )
                jour_id = cur.fetchone()['id']

                n = j_data['nutrition']
                # nutrition_jours : on n'a pas besoin de son id → pas de RETURNING
                cur.execute("""
                    INSERT INTO nutrition_jours
                    (jour_id, nb_repas, regime, apport_cle, restriction, proteines,
                     bar_nb_repas, bar_regime, bar_apport, bar_restriction, bar_proteines)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (jour_id, n['nb_repas'], n['regime'], n['apport_cle'],
                      n['restriction'], n['proteines'], n['bar_nb_repas'],
                      n['bar_regime'], n['bar_apport'], n['bar_restriction'],
                      n['bar_proteines']))

                for r_ordre in range(1, 6):
                    r = j_data['repas'][str(r_ordre)]

                    # ✅ RETURNING id car repas_id est utilisé pour les plats
                    cur.execute("""
                        INSERT INTO repas (jour_id, ordre, nom, heure, icone, image_path)
                        VALUES (%s,%s,%s,%s,%s,%s) RETURNING id
                    """, (jour_id, r_ordre, r['nom'], r['heure'],
                          r['icone'], r.get('image_path')))
                    repas_id = cur.fetchone()['id']

                    for idx, plat in enumerate(r['plats'], 1):
                        # plats : on n'a pas besoin de son id → pas de RETURNING
                        cur.execute(
                            "INSERT INTO plats (repas_id, ordre, quantite, nom) VALUES (%s,%s,%s,%s)",
                            (repas_id, idx, plat['quantite'], plat['nom'])
                        )

            # UPDATE ne retourne rien → pas de fetchone
            cur.execute("UPDATE menus SET statut='validé' WHERE id=%s", (menu_id,))
            conn.commit()

            session.pop(key, None)
            session.modified = True

            flash('Menu validé et enregistré avec succès !', 'success')
            cur.close(); conn.close()
            return redirect(url_for('formulaire.voir_menu', menu_id=menu_id, jour_num=1))

        except Exception as e:
            conn.rollback()
            cur.close(); conn.close()
            flash(f'Erreur lors de la sauvegarde : {e}', 'danger')

    cur.close(); conn.close()
    return render_template('validation.html', menu=menu, draft=draft, jours=JOURS_SEMAINE)


# ── API : DUPLIQUER UN REPAS ──────────────────────────────────────────────────
@formulaire_bp.route('/api/menu/<int:menu_id>/dupliquer', methods=['POST'])
@login_required
def api_dupliquer(menu_id):
    data     = request.get_json()
    src_jour = str(data.get('source_jour'))
    src_rep  = str(data.get('source_repas'))
    dst_jour = str(data.get('dest_jour'))

    key   = _session_key(menu_id)
    draft = session.get(key)
    if not draft:
        return jsonify({'ok': False, 'msg': 'Session expirée'}), 400

    src = draft['jours'].get(src_jour, {}).get('repas', {}).get(src_rep)
    dst = draft['jours'].get(dst_jour, {}).get('repas', {}).get(src_rep)
    if not src or not dst:
        return jsonify({'ok': False, 'msg': 'Repas introuvable'}), 404

    dst['plats'] = copy.deepcopy(src['plats'])
    session.modified = True
    return jsonify({'ok': True, 'plats': dst['plats']})


# ── HELPER : charger BDD → draft session ─────────────────────────────────────
def _load_db_into_draft(menu_id, patient_nom):
    """
    Lit un menu validé en BDD et reconstruit la structure draft identique
    à _init_draft(). Permet la réutilisation complète de saisie_jour.
    """
    conn = get_connection()
    cur  = dict_cursor(conn)

    draft = {'patient_nom': patient_nom, 'jours': {}}
    for i, nom in enumerate(JOURS_SEMAINE, 1):
        draft['jours'][str(i)] = {
            'nom': nom,
            'repas': {
                str(r[0]): {
                    'ordre': r[0], 'nom': r[1], 'heure': r[2], 'icone': r[3],
                    'image_path': None, 'image_temp': None,
                    'plats': []
                } for r in REPAS_DEFAUTS
            },
            'nutrition': {
                'nb_repas': '5', 'regime': 'Équilibré',
                'apport_cle': '↑ Fibres', 'restriction': '↓ Sucres',
                'proteines': '150 g',
                'bar_nb_repas': 100, 'bar_regime': 80,
                'bar_apport': 72, 'bar_restriction': 60, 'bar_proteines': 65
            }
        }

    cur.execute("SELECT * FROM jours WHERE menu_id=%s ORDER BY numero", (menu_id,))
    jours_rows = cur.fetchall()

    for jour_row in jours_rows:
        j_num   = str(jour_row['numero'])
        jour_id = jour_row['id']

        cur.execute("SELECT * FROM nutrition_jours WHERE jour_id=%s", (jour_id,))
        nutr = cur.fetchone()
        if nutr:
            draft['jours'][j_num]['nutrition'] = {
                'nb_repas':        nutr['nb_repas'],
                'regime':          nutr['regime'],
                'apport_cle':      nutr['apport_cle'],
                'restriction':     nutr['restriction'],
                'proteines':       nutr['proteines'],
                'bar_nb_repas':    nutr['bar_nb_repas'],
                'bar_regime':      nutr['bar_regime'],
                'bar_apport':      nutr['bar_apport'],
                'bar_restriction': nutr['bar_restriction'],
                'bar_proteines':   nutr['bar_proteines'],
            }

        cur.execute("SELECT * FROM repas WHERE jour_id=%s ORDER BY ordre", (jour_id,))
        repas_rows = cur.fetchall()

        for r in repas_rows:
            r_key = str(r['ordre'])
            cur.execute(
                "SELECT * FROM plats WHERE repas_id=%s ORDER BY ordre",
                (r['id'],)
            )
            plats = cur.fetchall()

            draft['jours'][j_num]['repas'][r_key] = {
                'ordre':      r['ordre'],
                'nom':        r['nom'],
                'heure':      r['heure'],
                'icone':      r['icone'],
                'image_path': r['image_path'],
                'image_temp': None,
                'plats': [
                    {'quantite': p['quantite'], 'nom': p['nom']}
                    for p in plats
                ]
            }

    cur.close()
    conn.close()
    return draft


# ── ÉDITER UN MENU EXISTANT ───────────────────────────────────────────────────
@formulaire_bp.route('/menu/<int:menu_id>/editer', methods=['GET'])
@login_required
def editer_menu(menu_id):
    conn = get_connection()
    cur  = dict_cursor(conn)
    cur.execute("""
        SELECT m.*, p.nom AS p_nom, p.prenom AS p_prenom
        FROM menus m JOIN patients p ON p.id = m.patient_id
        WHERE m.id=%s AND m.nutritionniste_id=%s
    """, (menu_id, session['nutritionniste_id']))
    menu = cur.fetchone()
    cur.close(); conn.close()

    if not menu:
        flash('Menu introuvable.', 'danger')
        return redirect(url_for('main.dashboard'))

    patient_nom = f"{menu['p_prenom']} {menu['p_nom']}"
    key         = _session_key(menu_id)

    session[key]     = _load_db_into_draft(menu_id, patient_nom)
    session.modified = True

    # UPDATE ne retourne rien → pas de fetchone
    conn = get_connection()
    cur  = dict_cursor(conn)
    cur.execute("UPDATE menus SET statut='brouillon' WHERE id=%s", (menu_id,))
    conn.commit()
    cur.close(); conn.close()

    flash('Menu chargé. Vous pouvez maintenant le modifier.', 'info')
    return redirect(url_for('formulaire.saisie_jour', menu_id=menu_id, jour_num=1))