from flask import Flask, request, jsonify
import cv2
import numpy as np
import base64
import pytesseract
import tensorflow as tf
import matplotlib
import ollama
import os
import json
from datetime import datetime
from sqlalchemy.orm import Session
from database import get_db, create_tables, Invoice, InvoiceItem, engine

app = Flask(__name__)

# Créer les tables dans la base de données au démarrage
create_tables()

def preprocess_image(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    denoised = cv2.fastNlMeansDenoising(binary, None, 30, 7, 21)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(denoised)
    return enhanced

matplotlib.use('Agg')
model_path = 'models/saved_model'
model = tf.saved_model.load(model_path)

def save_invoice_to_db(invoice_data, raw_text, raw_json):
    """
    Enregistre les données de la facture dans la base de données PostgreSQL
    """
    db = next(get_db())
    try:
        # Créer une nouvelle entrée de facture
        new_invoice = Invoice(
            company_name=invoice_data.get('Company Name', ''),
            company_address=invoice_data.get('Company Address', ''),
            customer_name=invoice_data.get('Customer Name', ''),
            customer_address=invoice_data.get('Customer Address', ''),
            invoice_number=invoice_data.get('Invoice Number', ''),
            invoice_date=invoice_data.get('Invoice Date', ''),
            due_date=invoice_data.get('Due Date', ''),
            total_amount=float(invoice_data.get('Total', 0)) if invoice_data.get('Total') else None,
            taxes=float(invoice_data.get('Taxes', 0)) if invoice_data.get('Taxes') else None,
            raw_text=raw_text,
            raw_json=raw_json
        )
        
        db.add(new_invoice)
        db.commit()
        db.refresh(new_invoice)
        
        # Ajouter les éléments de la facture s'ils existent
        if isinstance(invoice_data.get('Description'), list):
            descriptions = invoice_data.get('Description', [])
            quantities = invoice_data.get('Quantity', [])
            unit_prices = invoice_data.get('Unit Price', [])
            amounts = invoice_data.get('Amount', [])
            
            for i in range(len(descriptions)):
                item = InvoiceItem(
                    invoice_id=new_invoice.id,
                    description=descriptions[i] if i < len(descriptions) else None,
                    quantity=float(quantities[i]) if i < len(quantities) and quantities[i] else None,
                    unit_price=float(unit_prices[i]) if i < len(unit_prices) and unit_prices[i] else None,
                    amount=float(amounts[i]) if i < len(amounts) and amounts[i] else None
                )
                db.add(item)
        else:
            # Si les éléments ne sont pas des listes, ajouter un seul élément
            item = InvoiceItem(
                invoice_id=new_invoice.id,
                description=invoice_data.get('Description', ''),
                quantity=float(invoice_data.get('Quantity', 0)) if invoice_data.get('Quantity') else None,
                unit_price=float(invoice_data.get('Unit Price', 0)) if invoice_data.get('Unit Price') else None,
                amount=float(invoice_data.get('Amount', 0)) if invoice_data.get('Amount') else None
            )
            db.add(item)
            
        db.commit()
        return new_invoice.id
    except Exception as e:
        db.rollback()
        print(f"Erreur lors de l'enregistrement dans la base de données: {str(e)}")
        return None
    finally:
        db.close()
   
import re

@app.route('/ocr', methods=['POST'])
def predict():
    if not request.is_json:
        return jsonify({'error': 'Request must be application/json'}), 415

    data = request.get_json()

    if 'image' not in data:
        return jsonify({'error': 'No image data provided'}), 400

    base64_image = data['image']

    try:
        # Remove base64 prefix if present (e.g. data:image/png;base64,...)
        match = re.match(r"^data:image\/[a-zA-Z]+;base64,(.+)", base64_image)
        if match:
            base64_image = match.group(1)

        # Ensure proper base64 padding
        base64_image = base64_image.strip().replace('\n', '')
        missing_padding = len(base64_image) % 4
        if missing_padding:
            base64_image += '=' * (4 - missing_padding)

        image_data = base64.b64decode(base64_image)
        image_array = np.frombuffer(image_data, np.uint8)
        image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

    except Exception as e:
        return jsonify({'error': f'Invalid image data: {str(e)}'}), 400

    if image is None:
        return jsonify({'error': 'Failed to decode image data'}), 400

    try:
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        input_tensor = tf.convert_to_tensor(image_rgb, dtype=tf.uint8)
        input_tensor = input_tensor[tf.newaxis, ...]
        detections = model(input_tensor)
        num_detections = int(detections.pop('num_detections'))
        detections = {key: value[0, :num_detections].numpy()
              for key, value in detections.items()}
        detections['num_detections'] = num_detections
        boxes = detections['detection_boxes']
        classes = detections['detection_classes'].astype(np.int64)
        scores = detections['detection_scores']
        threshold = 0.5
        valid_detections = scores >= threshold
        boxes = boxes[valid_detections]
        scores = scores[valid_detections]
        classes = classes[valid_detections]
        
        extracted_texts = []
        config = '--oem 3 --psm 6'
        
        for i in range(len(boxes)):
            box = boxes[i]
            ymin, xmin, ymax, xmax = box
            start_point = (int(xmin * image.shape[1]), int(ymin * image.shape[0]))
            end_point = (int(xmax * image.shape[1]), int(ymax * image.shape[0]))
            color = (0, 255, 0)
            thickness = 2
            image = cv2.rectangle(image, start_point, end_point, color, thickness)
            roi = image[int(ymin * image.shape[0]):int(ymax * image.shape[0]), int(xmin * image.shape[1]):int(xmax * image.shape[1])]
            preprocessed_roi = preprocess_image(roi)
            text = pytesseract.image_to_string(preprocessed_roi, config=config,lang='eng')
            extracted_texts.append(f'{text.strip()}')
            label = f'{int(classes[i])}: {scores[i]:.2f}'
            label_size, base_line = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            top_left = (start_point[0], start_point[1] - label_size[1])
            bottom_right = (start_point[0] + label_size[0], start_point[1])
            image = cv2.rectangle(image, top_left, bottom_right, color, cv2.FILLED)
            image = cv2.putText(image, label, start_point, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
        texts = '   |||   '.join(extracted_texts)
        
        msg = "can you parse this text and give me json format version with these corresponding values: Company Name, Company Address, Customer Name, Customer Address, Invoice Number, Invoice Date, Due Date, Description, Quantity, Unit Price, Taxes, Amount, Total. If you can't find values of corresponding field then leave it empty. The text is :"
        
        response = ollama.chat(
        model="gemma2:2b",
        messages=[
            {
                "role": "user",
                "content": msg+texts,
            },
        ],
        )
        ollama_out = (response["message"]["content"])
        # Split the response to extract the JSON part
        start_index = ollama_out.find('{')
        end_index = ollama_out.rfind('}') + 1
        json_part = ollama_out[start_index:end_index]
        
        # Enregistrer les résultats dans la base de données
        try:
            invoice_data = json.loads(json_part)
            invoice_id = save_invoice_to_db(invoice_data, texts, json_part)
            
            # Ajouter l'ID de la facture à la réponse JSON
            result_json = json.loads(json_part)
            result_json["invoice_id"] = invoice_id
            return jsonify(result_json)
        except json.JSONDecodeError:
            # Si le parsing JSON échoue, renvoyer le texte brut
            return json_part
        
    except Exception as e:
        return jsonify({'error': f'Failed to process image: {str(e)}'}), 500

@app.route('/invoices', methods=['GET'])
def get_invoices():
    """
    Récupère la liste des factures enregistrées dans la base de données
    """
    db = next(get_db())
    try:
        invoices = db.query(Invoice).all()
        result = []
        for invoice in invoices:
            result.append({
                'id': invoice.id,
                'company_name': invoice.company_name,
                'invoice_number': invoice.invoice_number,
                'invoice_date': invoice.invoice_date,
                'total_amount': invoice.total_amount,
                'created_at': invoice.created_at.isoformat() if invoice.created_at else None
            })
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': f'Failed to retrieve invoices: {str(e)}'}), 500
    finally:
        db.close()

@app.route('/invoices/<int:invoice_id>', methods=['GET'])
def get_invoice(invoice_id):
    """
    Récupère les détails d'une facture spécifique
    """
    db = next(get_db())
    try:
        invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
        if not invoice:
            return jsonify({'error': 'Invoice not found'}), 404
            
        items = db.query(InvoiceItem).filter(InvoiceItem.invoice_id == invoice_id).all()
        items_data = []
        for item in items:
            items_data.append({
                'id': item.id,
                'description': item.description,
                'quantity': item.quantity,
                'unit_price': item.unit_price,
                'amount': item.amount
            })
            
        result = {
            'id': invoice.id,
            'company_name': invoice.company_name,
            'company_address': invoice.company_address,
            'customer_name': invoice.customer_name,
            'customer_address': invoice.customer_address,
            'invoice_number': invoice.invoice_number,
            'invoice_date': invoice.invoice_date,
            'due_date': invoice.due_date,
            'total_amount': invoice.total_amount,
            'taxes': invoice.taxes,
            'created_at': invoice.created_at.isoformat() if invoice.created_at else None,
            'items': items_data
        }
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': f'Failed to retrieve invoice: {str(e)}'}), 500
    finally:
        db.close()
            
if __name__ == '__main__':
    app.run(debug=True, port=9090, host='0.0.0.0')
