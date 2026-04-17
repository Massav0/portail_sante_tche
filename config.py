import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'sante_tche_secret_2026')

    # PostgreSQL Render
    DATABASE_URL = os.environ.get(
        'DATABASE_URL',
        'postgresql://massavo:cMBWRTGOVir582mzuaHzUsWm7UZO5oj6@dpg-d7h802pj2pic73fvekkg-a.oregon-postgres.render.com/sante_tche'
    )

    # Upload
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024

    SESSION_TYPE = 'filesystem'
    SESSION_PERMANENT = False
    PERMANENT_SESSION_LIFETIME = 3600