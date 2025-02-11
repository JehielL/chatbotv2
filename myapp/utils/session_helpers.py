import uuid

def ensure_user_id(session):
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
        session.modified = True
