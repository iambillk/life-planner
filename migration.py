python
>>> from app import create_app
>>> app = create_app()
>>> with app.app_context():
...     from models.base import db
...     db.create_all()