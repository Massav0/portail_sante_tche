from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from routes.auth import login_required
from db import get_connection, dict_cursor

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
@login_required
def dashboard():
    nid  = session['nutritionniste_id']
    conn = get_connection()
    cur  = dict_cursor(conn)

    cur.execute("""
        SELECT p.*, 
               COUNT(DISTINCT m.id) AS nb_menus,
               MAX(m.semaine_debut)  AS derniere_semaine
        FROM patients p
        LEFT JOIN menus m ON m.patient_id = p.id
        WHERE p.nutritionniste_id = %s AND p.actif = 1
        GROUP BY p.id
        ORDER BY p.nom, p.prenom
    """, (nid,))
    patients = cur.fetchall()
    cur.close(); conn.close()

    return render_template('dashboard.html', patients=patients)


# ── PATIENTS ──────────────────────────────────────────────────────────────────
@main_bp.route('/patients/nouveau', methods=['GET', 'POST'])
@login_required
def nouveau_patient():
    if request.method == 'POST':
        nid = session['nutritionniste_id']
        conn = get_connection()
        cur  = dict_cursor(conn)
        cur.execute("""
            INSERT INTO patients (nutritionniste_id, nom, prenom, date_naissance, sexe, objectif, notes)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
        """, (
            nid,
            request.form.get('nom','').strip(),
            request.form.get('prenom','').strip(),
            request.form.get('date_naissance') or None,
            request.form.get('sexe') or None,
            request.form.get('objectif','').strip(),
            request.form.get('notes','').strip(),
        ))
        conn.commit()
        pid = cur.lastrowid
        cur.close(); conn.close()
        flash('Patient créé avec succès.', 'success')
        return redirect(url_for('main.fiche_patient', pid=pid))

    return render_template('patient_form.html', patient=None)


@main_bp.route('/patients/<int:pid>')
@login_required
def fiche_patient(pid):
    conn = get_connection()
    cur  = dict_cursor(conn)
    cur.execute("SELECT * FROM patients WHERE id=%s AND nutritionniste_id=%s",
                (pid, session['nutritionniste_id']))
    patient = cur.fetchone()
    if not patient:
        cur.close(); conn.close()
        flash('Patient introuvable.', 'danger')
        return redirect(url_for('main.dashboard'))

    cur.execute("""
        SELECT * FROM menus WHERE patient_id=%s ORDER BY semaine_debut DESC
    """, (pid,))
    menus = cur.fetchall()
    cur.close(); conn.close()

    return render_template('fiche_patient.html', patient=patient, menus=menus)


@main_bp.route('/patients/<int:pid>/editer', methods=['GET', 'POST'])
@login_required
def editer_patient(pid):
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
        cur.execute("""
            UPDATE patients SET nom=%s, prenom=%s, date_naissance=%s, sexe=%s, objectif=%s, notes=%s
            WHERE id=%s
        """, (
            request.form.get('nom','').strip(),
            request.form.get('prenom','').strip(),
            request.form.get('date_naissance') or None,
            request.form.get('sexe') or None,
            request.form.get('objectif','').strip(),
            request.form.get('notes','').strip(),
            pid
        ))
        conn.commit()
        flash('Patient mis à jour.', 'success')
        cur.close(); conn.close()
        return redirect(url_for('main.fiche_patient', pid=pid))

    cur.close(); conn.close()
    return render_template('patient_form.html', patient=patient)
