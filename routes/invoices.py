# routes/invoices.py
from flask import Blueprint, jsonify
from database import get_db, Invoice, InvoiceItem

invoices_bp = Blueprint("invoices", __name__)


@invoices_bp.route("/invoices", methods=["GET"])
def get_invoices():
    db = next(get_db())
    try:
        invoices = db.query(Invoice).all()
        result = []
        for invoice in invoices:
            result.append(
                {
                    "id": invoice.id,
                    "company_name": invoice.company_name,
                    "invoice_number": invoice.invoice_number,
                    "invoice_date": invoice.invoice_date,
                    "total_amount": invoice.total_amount,
                    "created_at": (
                        invoice.created_at.isoformat() if invoice.created_at else None
                    ),
                }
            )
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": f"Faled to retrieve invoices: {str(e)}"}), 500
    finally:
        db.close()


@invoices_bp.route("/invoices/<int:invoice_id>", methods=["GET"])
def get_invoice(invoice_id):
    db = next(get_db())
    try:
        invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
        if not invoice:
            return jsonify({"error": "Invoice not found"}), 404

        items = db.query(InvoiceItem).filter(InvoiceItem.invoice_id == invoice_id).all()
        items_data = [
            {
                "id": item.id,
                "description": item.description,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "amount": item.amount,
            }
            for item in items
        ]

        result = {
            "id": invoice.id,
            "company_name": invoice.company_name,
            "company_address": invoice.company_address,
            "customer_name": invoice.customer_name,
            "customer_address": invoice.customer_address,
            "invoice_number": invoice.invoice_number,
            "invoice_date": invoice.invoice_date,
            "due_date": invoice.due_date,
            "total_amount": invoice.total_amount,
            "taxes": invoice.taxes,
            "created_at": (
                invoice.created_at.isoformat() if invoice.created_at else None
            ),
            "items": items_data,
        }
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": f"Failed to retrieve invoice: {str(e)}"}), 500
    finally:
        db.close()
