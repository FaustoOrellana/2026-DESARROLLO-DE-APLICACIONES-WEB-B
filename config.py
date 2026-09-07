import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = 'techmanager_secret_key_semana11_secure'
    
    SQLALCHEMY_DATABASE_URI = (
        'sqlite:///' + 
        os.path.join(BASE_DIR, 'data', 'techmanager.db')
    )
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    