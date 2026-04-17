from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from db import get_connection, dict_cursor

auth_bp = Blueprint('auth', __name__)


def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'nutritionniste_id' not in session:
            flash('Veuillez vous connecter.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'nutritionniste_id' in session:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        conn = get_connection()
        cur  = dict_cursor(conn)
        cur.execute("SELECT * FROM nutritionnistes WHERE email=%s AND actif=1", (email,))
        user = cur.fetchone()
        cur.close(); conn.close()

        if user and check_password_hash(user['password_hash'], password):
            session['nutritionniste_id']  = user['id']
            session['nutritionniste_nom'] = f"{user['prenom']} {user['nom']}"
            flash(f"Bienvenue, {user['prenom']} !", 'success')
            return redirect(url_for('main.dashboard'))
        flash('Email ou mot de passe incorrect.', 'danger')

    return render_template('login.html')


@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('Déconnexion réussie.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/setup', methods=['GET', 'POST'])
def setup():
    """Création du 1er compte (accessible seulement si 0 nutritionniste)."""
    conn = get_connection()
    cur  = dict_cursor(conn)
    cur.execute("SELECT COUNT(*) as nb FROM nutritionnistes")
    count = cur.fetchone()['nb']

    if count >= 3:
        cur.close(); conn.close()
        flash('Nombre maximum de nutritionnistes atteint (3).', 'warning')
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        nom    = request.form.get('nom', '').strip()
        prenom = request.form.get('prenom', '').strip()
        email  = request.form.get('email', '').strip().lower()
        pwd    = request.form.get('password', '')
        pwd2   = request.form.get('password2', '')

        if pwd != pwd2:
            flash('Les mots de passe ne correspondent pas.', 'danger')
        elif len(pwd) < 6:
            flash('Mot de passe trop court (6 caractères min).', 'danger')
        else:
            hashed = generate_password_hash(pwd)
            try:
                cur.execute(
                    "INSERT INTO nutritionnistes (nom, prenom, email, password_hash) VALUES (%s,%s,%s,%s)",
                    (nom, prenom, email, hashed)
                )
                conn.commit()
                flash('Compte créé ! Connectez-vous.', 'success')
                cur.close(); conn.close()
                return redirect(url_for('auth.login'))
            except Exception as e:
                flash(f'Erreur : {e}', 'danger')

    cur.close(); conn.close()
    return render_template('setup.html', count=count)
