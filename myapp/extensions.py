from flask_cors import CORS
from flask_session import Session
import pymongo

session_ext = Session()
cors = CORS()

def init_db(app):
    mongo_client = pymongo.MongoClient(app.config['MONGODB_URI'])
    db = mongo_client[app.config['DB_NAME']]
    app.db = db
