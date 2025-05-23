# Guide d'intégration de PostgreSQL à l'API OCR de factures

Ce document explique les modifications apportées au projet pour intégrer une base de données PostgreSQL afin de stocker les résultats d'OCR des factures.

## Structure de la base de données

La base de données comprend deux tables principales :

1. **invoices** : Stocke les informations générales des factures
   - id (clé primaire)
   - company_name (nom de l'entreprise)
   - company_address (adresse de l'entreprise)
   - customer_name (nom du client)
   - customer_address (adresse du client)
   - invoice_number (numéro de facture)
   - invoice_date (date de facture)
   - due_date (date d'échéance)
   - total_amount (montant total)
   - taxes (montant des taxes)
   - created_at (date de création dans le système)
   - raw_text (texte brut extrait de l'image)
   - raw_json (données JSON complètes)
   - image_path (chemin vers l'image de la facture, si sauvegardée)

2. **invoice_items** : Stocke les éléments individuels de chaque facture
   - id (clé primaire)
   - invoice_id (clé étrangère vers invoices)
   - description (description de l'article)
   - quantity (quantité)
   - unit_price (prix unitaire)
   - amount (montant total de la ligne)

## Fichiers modifiés ou ajoutés

1. **database.py** : Définit les modèles SQLAlchemy et la connexion à la base de données
2. **app.py** : Modifié pour intégrer la persistance des données et ajouter des endpoints API
3. **requirements.txt** : Mis à jour avec les dépendances PostgreSQL
4. **setup_db.sh** : Script pour installer et configurer PostgreSQL
5. **test_db.py** : Utilitaire pour tester la connexion à la base de données

## Installation et configuration

1. Installez PostgreSQL et configurez la base de données :
   ```bash
   chmod +x setup_db.sh
   ./setup_db.sh
   ```

2. Installez les dépendances Python :
   ```bash
   pip install -r requirements.txt
   ```

3. Testez la connexion à la base de données :
   ```bash
   python test_db.py
   ```
   Accédez à http://localhost:9091/test_db pour vérifier la connexion
   Accédez à http://localhost:9091/setup_db pour créer les tables

4. Lancez l'API principale :
   ```bash
   python app.py
   ```

## Nouveaux endpoints API

L'API a été enrichie avec les endpoints suivants :

1. **POST /ocr** : Endpoint existant, maintenant avec persistance des données
   - Traite l'image de facture et stocke les résultats dans la base de données
   - Retourne les données extraites avec un ID de facture

2. **GET /invoices** : Récupère la liste de toutes les factures traitées
   - Retourne un tableau avec les informations de base de chaque facture

3. **GET /invoices/{invoice_id}** : Récupère les détails d'une facture spécifique
   - Retourne toutes les informations de la facture, y compris les éléments

## Variables d'environnement

- **DATABASE_URL** : URL de connexion à la base de données PostgreSQL
  - Format : `postgresql://utilisateur:mot_de_passe@hôte:port/nom_base`
  - Par défaut : `postgresql://postgres:postgres@localhost:5432/invoice_ocr`

## Remarques importantes

- La base de données est automatiquement initialisée au démarrage de l'application
- Les données extraites des factures sont stockées à la fois sous forme structurée et brute
- Pour une utilisation en production, il est recommandé de modifier les identifiants par défaut de la base de données
