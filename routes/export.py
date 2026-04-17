import os
from flask import Blueprint, render_template, make_response, request, url_for
from db import get_connection, dict_cursor

export_bp = Blueprint('export', __name__)


def _get_menu_et_patient(cur, menu_id):
    cur.execute("""
        SELECT m.*, p.nom AS p_nom, p.prenom AS p_prenom
        FROM menus m
        JOIN patients p ON p.id = m.patient_id
        WHERE m.id=%s
    """, (menu_id,))
    return cur.fetchone()


def _get_jour_data(cur, menu_id, jour_num):
    cur.execute("SELECT * FROM jours WHERE menu_id=%s AND numero=%s", (menu_id, jour_num))
    jour_row = cur.fetchone()
    if not jour_row:
        return None, None

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
            'ordre':      r['ordre'],
            'nom':        r['nom'],
            'heure':      r['heure'],
            'icone':      r['icone'],
            'image_path': r['image_path'],
            'plats': [{'quantite': p['quantite'], 'nom': p['nom']} for p in plats]
        }

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
    return jour_row, jour_data


def _html_vers_pdf(html_string, format_a4=False):
    """Convertit un HTML string en PDF via xhtml2pdf — 100% Python."""
    from xhtml2pdf import pisa
    import io

    buffer = io.BytesIO()
    pisa.CreatePDF(
        src=html_string,
        dest=buffer,
        encoding='utf-8'
    )
    return buffer.getvalue()

# ─────────────────────────────────────────────
# PDF D'UN JOUR
# ─────────────────────────────────────────────
@export_bp.route('/menu/<int:menu_id>/pdf/<int:jour_num>')
def pdf_jour(menu_id, jour_num):
    conn = get_connection()
    cur  = dict_cursor(conn)

    menu = _get_menu_et_patient(cur, menu_id)
    if not menu:
        cur.close(); conn.close()
        return "Menu introuvable", 404

    jour_row, jour_data = _get_jour_data(cur, menu_id, jour_num)
    cur.close(); conn.close()

    if not jour_row:
        return "Jour introuvable", 404

    patient_nom = f"{menu['p_prenom']} {menu['p_nom']}"
    date_str    = menu['semaine_debut'].strftime('%d_%m_%Y') if hasattr(menu['semaine_debut'], 'strftime') else ""

    # ✅ Rendu HTML en mémoire — pas d'appel réseau
    html_string = render_template(
        'apercu.html',
        menu=menu,
        jour_num=jour_num,
        jour_data=jour_data,
        patient_nom=patient_nom,
        date_str=date_str,
        jours=[],
        preview_mode=False,
        pdf_mode=True
    )

    pdf_bytes = _html_vers_pdf(html_string, format_a4=False)

    nom_fichier = f"menu_{patient_nom.replace(' ', '_')}_{jour_data['nom']}_{date_str}.pdf"
    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename="{nom_fichier}"'
    return response


# ─────────────────────────────────────────────
# PDF SEMAINE COMPLÈTE
# ─────────────────────────────────────────────
@export_bp.route('/menu/<int:menu_id>/pdf/semaine')
def pdf_semaine(menu_id):
    conn = get_connection()
    cur  = dict_cursor(conn)

    menu = _get_menu_et_patient(cur, menu_id)
    if not menu:
        cur.close(); conn.close()
        return "Menu introuvable", 404

    jours_data = []
    for j in range(1, 8):
        jour_row, jour_data = _get_jour_data(cur, menu_id, j)
        if jour_data:
            jours_data.append((j, jour_data))

    cur.close(); conn.close()

    patient_nom = f"{menu['p_prenom']} {menu['p_nom']}"
    date_str    = menu['semaine_debut'].strftime('%d_%m_%Y') if hasattr(menu['semaine_debut'], 'strftime') else ""

    # ✅ Rendu HTML en mémoire — pas d'appel réseau
    html_string = render_template(
        'apercu_semaine.html',
        menu=menu,
        jours_data=jours_data,
        patient_nom=patient_nom,
        date_str=date_str,
        pdf_mode=True
    )

    pdf_bytes = _html_vers_pdf(html_string, format_a4=True)

    nom_fichier = f"menu_semaine_{patient_nom.replace(' ', '_')}_{date_str}.pdf"
    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename="{nom_fichier}"'
    return response


# ─────────────────────────────────────────────
# PAGES DE PRÉVISUALISATION (SANS LOGIN)
# gardées pour consultation directe navigateur
# ─────────────────────────────────────────────
@export_bp.route('/export/menu/<int:menu_id>/voir/<int:jour_num>')
def export_voir(menu_id, jour_num):
    conn = get_connection()
    cur  = dict_cursor(conn)

    menu = _get_menu_et_patient(cur, menu_id)
    if not menu:
        cur.close(); conn.close()
        return "Menu introuvable", 404

    jour_row, jour_data = _get_jour_data(cur, menu_id, jour_num)
    cur.close(); conn.close()

    if not jour_row:
        return "Jour introuvable", 404

    patient_nom = f"{menu['p_prenom']} {menu['p_nom']}"
    date_str    = menu['semaine_debut'].strftime('%d_%m_%Y') if hasattr(menu['semaine_debut'], 'strftime') else ""

    return render_template(
        'apercu.html',
        menu=menu,
        jour_num=jour_num,
        jour_data=jour_data,
        patient_nom=patient_nom,
        date_str=date_str,
        jours=[],
        preview_mode=False,
        pdf_mode=False
    )


@export_bp.route('/export/menu/<int:menu_id>/semaine')
def export_semaine(menu_id):
    conn = get_connection()
    cur  = dict_cursor(conn)

    menu = _get_menu_et_patient(cur, menu_id)
    if not menu:
        cur.close(); conn.close()
        return "Menu introuvable", 404

    jours_data = []
    for j in range(1, 8):
        jour_row, jour_data = _get_jour_data(cur, menu_id, j)
        if jour_data:
            jours_data.append((j, jour_data))

    cur.close(); conn.close()

    patient_nom = f"{menu['p_prenom']} {menu['p_nom']}"
    date_str    = menu['semaine_debut'].strftime('%d_%m_%Y') if hasattr(menu['semaine_debut'], 'strftime') else ""

    return render_template(
        'apercu_semaine.html',
        menu=menu,
        jours_data=jours_data,
        patient_nom=patient_nom,
        date_str=date_str,
        pdf_mode=False
    )
