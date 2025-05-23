import os
import json
from flask import Flask, request, jsonify
from database import get_db, create_tables, Invoice, InvoiceItem

app = Flask(__name__)

@app.route('/test_db', methods=['GET'])
def test_db_connection():
    """
    Test de la connexion à la base de données PostgreSQL
    """
    try:
        db = next(get_db())
        db.execute("SELECT 1")
        db.close()
        return jsonify({"status": "success", "message": "Connexion à la base de données PostgreSQL réussie!"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Erreur de connexion à la base de données: {str(e)}"})

@app.route('/setup_db', methods=['GET'])
def setup_database():
    """
    Initialise les tables dans la base de données
    """
    try:
        create_tables()
        return jsonify({"status": "success", "message": "Tables créées avec succès dans la base de données"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Erreur lors de la création des tables: {str(e)}"})

if __name__ == '__main__':
    app.run(debug=True, port=9091, host='0.0.0.0')
