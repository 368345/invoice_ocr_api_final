# app.py
from flask import Flask, request, jsonify
from flask_cors import CORS
import base64
import numpy as np
import cv2
import tensorflow as tf
import json
import re
import matplotlib
import ollama

from crud import save_invoice_to_db
from database import create_tables, get_db, Invoice, InvoiceItem
from utils.ocr_utils import preprocess_image

matplotlib.use("Agg")

app = Flask(__name__)
CORS(app)

from routes.invoices import invoices_bp
from routes.stats import stats_bp

# Create tables at startup
create_tables()

# Register blueprint
app.register_blueprint(invoices_bp)
app.register_blueprint(stats_bp)


model_path = "models/saved_model"
model = tf.saved_model.load(model_path)


@app.route("/ocr", methods=["POST"])
def predict():
    if not request.is_json:
        return jsonify({"error": "Request must be application/json"}), 415

    data = request.get_json()

    if "image" not in data:
        return jsonify({"error": "No image data provided"}), 400

    base64_image = data["image"]

    try:
        # Strip base64 prefix if present
        match = re.match(r"^data:image\/[a-zA-Z]+;base64,(.+)", base64_image)
        if match:
            base64_image = match.group(1)

        base64_image = base64_image.strip().replace("\n", "")
        missing_padding = len(base64_image) % 4
        if missing_padding:
            base64_image += "=" * (4 - missing_padding)

        image_data = base64.b64decode(base64_image)
        image_array = np.frombuffer(image_data, np.uint8)
        image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
    except Exception as e:
        return jsonify({"error": f"Invalid image data: {str(e)}"}), 400

    if image is None:
        return jsonify({"error": "Failed to decode image data"}), 400

    try:
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        input_tensor = tf.convert_to_tensor(image_rgb, dtype=tf.uint8)[tf.newaxis, ...]
        detections = model(input_tensor)
        num_detections = int(detections.pop("num_detections"))
        detections = {
            key: value[0, :num_detections].numpy() for key, value in detections.items()
        }

        boxes = detections["detection_boxes"]
        classes = detections["detection_classes"].astype(np.int64)
        scores = detections["detection_scores"]
        threshold = 0.5

        valid_detections = scores >= threshold
        boxes = boxes[valid_detections]
        scores = scores[valid_detections]
        classes = classes[valid_detections]

        extracted_texts = []
        config = "--oem 3 --psm 6"

        for i in range(len(boxes)):
            box = boxes[i]
            ymin, xmin, ymax, xmax = box
            roi = image[
                int(ymin * image.shape[0]) : int(ymax * image.shape[0]),
                int(xmin * image.shape[1]) : int(xmax * image.shape[1]),
            ]
            preprocessed_roi = preprocess_image(roi)
            import pytesseract

            text = pytesseract.image_to_string(
                preprocessed_roi, config=config, lang="eng"
            )
            extracted_texts.append(text.strip())

        texts = "   |||   ".join(extracted_texts)

        msg = (
            "can you parse this text and give me json format version with these corresponding values: "
            "Company Name, Company Address, Customer Name, Customer Address, Invoice Number, Invoice Date, Due Date, "
            "Description, Quantity, Unit Price, Taxes, Amount, Total. If you can't find values of corresponding field then leave it empty. The text is :"
        )

        response = ollama.chat(
            model="gemma2:2b",
            messages=[{"role": "user", "content": msg + texts}],
        )
        ollama_out = response["message"]["content"]

        start_index = ollama_out.find("{")
        end_index = ollama_out.rfind("}") + 1
        json_part = ollama_out[start_index:end_index]

        try:
            invoice_data = json.loads(json_part)
            invoice_id = save_invoice_to_db(invoice_data, texts, json_part)
            result_json = invoice_data
            result_json["invoice_id"] = invoice_id
            return jsonify(result_json)
        except json.JSONDecodeError:
            return json_part

    except Exception as e:
        return jsonify({"error": f"Failed to process image: {str(e)}"}), 500


if __name__ == "__main__":
    app.run(debug=True, port=9090, host="0.0.0.0")
