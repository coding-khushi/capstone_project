from database.models import init_db

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = init_db()
    return _engine
