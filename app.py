from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from extensions import db
from dotenv import load_dotenv
import os
from urllib.parse import quote_plus


# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Database Config
# Database Config
db_user = quote_plus(os.getenv('DB_USER') or 'root')
db_password = quote_plus(os.getenv('DB_PASSWORD') or '')
db_host = os.getenv('DB_HOST') or '127.0.0.1'
db_name = os.getenv('DB_NAME') or 'event_scheduling_db'

if db_host == 'localhost':
    db_host = '127.0.0.1'

app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+mysqlconnector://{db_user}:{db_password}@{db_host}/{db_name}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# Import models to ensure they are registered with SQLAlchemy
# We import them *after* db initialization to avoid circular import issues if they import db from here
from models import Resource, Event, EventResourceAllocation


# Endpoint to initialize database (for testing convenience, though CLI is better)
@app.route('/api/init-db', methods=['POST'])
def init_db():
    try:
        db.create_all()
        return jsonify({"message": "Database tables created successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Import routes & views
from routes import api_bp
from views import views_bp

# Global Error Handlers
from flask import make_response

@app.errorhandler(400)
def bad_request(error):
    if request.path.startswith('/api/'):
        return jsonify({'error': str(error.description)}), 400
    return error

@app.errorhandler(404)
def not_found(error):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Resource not found'}), 404
    return error

@app.errorhandler(500)
def internal_error(error):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Internal Server Error'}), 500
    return error

app.register_blueprint(views_bp)
app.register_blueprint(api_bp)

if __name__ == '__main__':
    app.run(debug=True, port=5000)

