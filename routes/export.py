import os
from flask import Blueprint, render_template, make_response, request
from playwright.sync_api import sync_playwright
from db import get_connection, dict_cursor

export_bp = Blueprint('export', __name__)


# ─────────────────────────────────────────────
# PDF D'UN JOUR (PLAYWRIGHT)
# ─────────────────────────────────────────────
@export_bp.route('/menu/<int:menu_id>/pdf/<int:jour_num>')
def pdf_jour(menu_id, jour_num):

    url = f"http://127.0.0.1:5000/export/menu/{menu_id}/voir/{jour_num}"

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(1000)

        # 👉 calcul taille réelle de la page
        width = page.evaluate("document.body.scrollWidth")
        height = page.evaluate("document.body.scrollHeight")

        pdf_bytes = page.pdf(
            print_background=True,
            width=f"{width}px",
            height=f"{height}px",
            margin={
                "top": "0",
                "bottom": "0",
                "left": "0",
                "right": "0"
            }
        )

        browser.close()

    nom_fichier = f"menu_jour_{menu_id}_{jour_num}.pdf"

    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename="{nom_fichier}"'
    return response

# ─────────────────────────────────────────────
# PDF SEMAINE COMPLETE
# ─────────────────────────────────────────────
@export_bp.route('/menu/<int:menu_id>/pdf/semaine')
def pdf_semaine(menu_id):

    url = f"http://127.0.0.1:5000/export/menu/{menu_id}/semaine"

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        # ── Chargement page ─────────────────────────────
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(3000)

        # ── Sécurité rendu DOM ──────────────────────────
        page.wait_for_selector("body")

        # force affichage si CSS cache quelque chose
        page.evaluate("""
            () => {
                document.body.style.display = 'block';
                document.body.style.visibility = 'visible';
            }
        """)

        # ── Taille réelle page ──────────────────────────
        width = page.evaluate("document.documentElement.scrollWidth")
        height = page.evaluate("document.documentElement.scrollHeight")

        if not height or height < 500:
            height = 3000  # sécurité semaine

        # ── Génération PDF ───────────────────────────────
        pdf_bytes = page.pdf(
            format="A4",
            print_background=True,
            margin={
                "top": "0",
                "bottom": "0",
                "left": "0",
                "right": "0"
            },
            prefer_css_page_size=True
        )

    # ── Réponse download ───────────────────────────────
    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'attachment; filename="menu_semaine.pdf"'
    return response
# ─────────────────────────────────────────────
# PAGE UTILISEE PAR PLAYWRIGHT (SANS LOGIN)
# ─────────────────────────────────────────────
@export_bp.route('/export/menu/<int:menu_id>/voir/<int:jour_num>')
def export_voir(menu_id, jour_num):

    conn = get_connection()
    cur = dict_cursor(conn)

    # MENU
    cur.execute("""
        SELECT m.*, p.nom AS p_nom, p.prenom AS p_prenom
        FROM menus m
        JOIN patients p ON p.id = m.patient_id
        WHERE m.id=%s
    """, (menu_id,))
    menu = cur.fetchone()

    if not menu:
        cur.close(); conn.close()
        return "Menu introuvable", 404

    # JOUR
    cur.execute("SELECT * FROM jours WHERE menu_id=%s AND numero=%s", (menu_id, jour_num))
    jour_row = cur.fetchone()

    if not jour_row:
        cur.close(); conn.close()
        return "Jour introuvable", 404

    jour_id = jour_row['id']

    # NUTRITION
    cur.execute("SELECT * FROM nutrition_jours WHERE jour_id=%s", (jour_id,))
    nutr = cur.fetchone() or {}

    # REPAS
    cur.execute("SELECT * FROM repas WHERE jour_id=%s ORDER BY ordre", (jour_id,))
    repas_rows = cur.fetchall()

    repas_dict = {}

    for r in repas_rows:
        cur.execute("SELECT * FROM plats WHERE repas_id=%s ORDER BY ordre", (r['id'],))
        plats = cur.fetchall()

        repas_dict[str(r['ordre'])] = {
            'ordre': r['ordre'],
            'nom': r['nom'],
            'heure': r['heure'],
            'icone': r['icone'],
            'image_path': r['image_path'],
            'plats': [
                {'quantite': p['quantite'], 'nom': p['nom']}
                for p in plats
            ]
        }

    cur.close()
    conn.close()

    jour_data = {
        'nom': jour_row['nom_jour'],
        'repas': repas_dict,
        'nutrition': {
            'nb_repas': nutr.get('nb_repas', '5'),
            'regime': nutr.get('regime', 'Équilibré'),
            'apport_cle': nutr.get('apport_cle', '↑ Fibres'),
            'restriction': nutr.get('restriction', '↓ Sucres'),
            'proteines': nutr.get('proteines', '150 g'),
        }
    }

    date_str = menu['semaine_debut'].strftime('%d_%m_%Y') if hasattr(menu['semaine_debut'], 'strftime') else ""

    return render_template(
        'apercu.html',
        menu=menu,
        jour_num=jour_num,
        jour_data=jour_data,
        patient_nom=f"{menu['p_prenom']} {menu['p_nom']}",
        date_str=date_str,
        preview_mode=False
    )
    


# ─────────────────────────────────────────────
# PAGE SEMAINE POUR EXPORT
# ─────────────────────────────────────────────
@export_bp.route('/export/menu/<int:menu_id>/semaine')
def export_semaine(menu_id):

    conn = get_connection()
    cur = dict_cursor(conn)

    cur.execute("""
        SELECT m.*, p.nom AS p_nom, p.prenom AS p_prenom
        FROM menus m
        JOIN patients p ON p.id = m.patient_id
        WHERE m.id=%s
    """, (menu_id,))
    menu = cur.fetchone()

    if not menu:
        cur.close(); conn.close()
        return "Menu introuvable", 404

    jours_data = []

    for j in range(1, 8):
        cur.execute("SELECT * FROM jours WHERE menu_id=%s AND numero=%s", (menu_id, j))
        jour_row = cur.fetchone()

        if not jour_row:
            continue

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
                'ordre': r['ordre'],
                'nom': r['nom'],
                'heure': r['heure'],
                'icone': r['icone'],
                'image_path': r['image_path'],
                'plats': [{'quantite': p['quantite'], 'nom': p['nom']} for p in plats]
            }

        jour_data = {
            'nom': jour_row['nom_jour'],
            'repas': repas_dict,
            'nutrition': nutr
        }

        # ✅ IMPORTANT: on stocke bien un couple (num, data)
        jours_data.append((j, jour_data))

    cur.close(); conn.close()

    date_str = menu['semaine_debut'].strftime('%d_%m_%Y') if menu.get('semaine_debut') else ""
    patient_nom = f"{menu['p_prenom']} {menu['p_nom']}"

    return render_template(
        'apercu_semaine.html',
        menu=menu,
        jours_data=jours_data,
        pdf_mode=True,
        date_str=date_str,
        patient_nom=patient_nom
    )
