from .connection import db
from .models import Feature, Message


def init_database():
    with db as conn:
        conn.create_tables([Feature, Message])
