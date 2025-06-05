# routes/invoices.py
from flask import Blueprint, jsonify, request
from database import get_db, Invoice, InvoiceItem
from datetime import date, datetime

invoices_bp = Blueprint("invoices", __name__)

@invoices_bp.route("/invoices", methods=["GET"])
def get_invoices():
    db = next(get_db())
    try:
        invoices = db.query(Invoice).order_by(Invoice.created_at.desc()).all()
        result = []

        for invoice in invoices:
            invoice_date = invoice.invoice_date
            created_at = invoice.created_at

            if isinstance(invoice_date, (datetime, date)):
                invoice_date = invoice_date.isoformat()

            if isinstance(created_at, (datetime, date)):
                created_at = created_at.isoformat()

            total_amount = float(invoice.total_amount) if invoice.total_amount is not None else 0.0

            # Calculate status dynamically
            if total_amount <= 0:
                status = "paid"
            elif invoice.due_date:
                try:
                    due = invoice.due_date
                    if isinstance(due, str):
                        due = datetime.fromisoformat(due)
                    if due < datetime.utcnow():
                        status = "overdue"
                    else:
                        status = "pending"
                except Exception:
                    status = "pending"
            else:
                status = "pending"

            result.append({
                "id": invoice.id,
                "company_name": invoice.company_name,
                "invoice_number": invoice.invoice_number,
                "invoice_date": invoice_date,
                "total_amount": total_amount,
                "status": status,
                "created_at": created_at,
            })

        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": f"Failed to retrieve invoices: {str(e)}"}), 500
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


@invoices_bp.route("/clients", methods=["GET"])
def get_clients():
    db = next(get_db())
    try:
        invoices = db.query(Invoice).all()

        client_map = {}

        for inv in invoices:
            raw_name = (inv.customer_name or "").strip().lower()
            clean_name = raw_name if raw_name and raw_name != "null" else None

            if not clean_name:
                continue  # Skip empty/null clients
            
            clean_address = inv.customer_address.strip() if inv.customer_address else ""
            if clean_address.lower() == "null":
                clean_address = ""

            if clean_name not in client_map:
                client_map[clean_name] = {
                    "id": len(client_map) + 1,
                    "name": inv.customer_name or "",
                    "email": "",  # No email in your DB model — keep empty or add if available
                    "address": clean_address,
                    "createdAt":inv.created_at,
                    "invoiceCount": 1,
                    "totalValue": inv.total_amount or 0,
                    "lastInvoiceDate": inv.created_at
                }
            else:
                client = client_map[clean_name]
                client["invoiceCount"] += 1
                client["totalValue"] += inv.total_amount or 0

                # Update lastInvoiceDate if this invoice is newer
                if inv.created_at and (not client["lastInvoiceDate"] or inv.created_at >client["lastInvoiceDate"]):
                    client["lastInvoiceDate"] = inv.created_at

        # Return list of clients with camelCase keys, aggregated totals and dates
        return jsonify(list(client_map.values())), 200

    except Exception as e:
        return jsonify({"error": f"Failed to retrieve clients: {str(e)}"}), 500
    finally:
        db.close()

        
@invoices_bp.route("/invoices/<int:invoice_id>", methods=["PUT"])
def update_invoice(invoice_id):
    db = next(get_db())
    try:
        data = request.get_json()

        invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
        if not invoice:
            return jsonify({"error": "Invoice not found"}), 404

        # Update invoice fields
        invoice.invoice_number = data.get('invoiceNumber')
        invoice.company_name = data.get('companyName')
        invoice.company_address = data.get('companyAddress')
        invoice.customer_name = data.get('clientName')
        invoice.customer_address = data.get('clientAddress')
        invoice.invoice_date = data.get('date')
        invoice.due_date = data.get('dueDate')
        invoice.taxes = data.get('taxes')
        invoice.total_amount = data.get('total')

        # Optional: Update single item info if you don’t support multi-items yet
        if invoice.items:
            item = invoice.items[0]
        else:
            item = InvoiceItem(invoice_id=invoice.id)
            db.add(item)

        item.description = data.get('description')
        item.quantity = data.get('quantity')
        item.unit_price = data.get('unitPrice')
        item.amount = data.get('amount')

        db.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.rollback()
        return jsonify({"error": "Something went wrong", "details": str(e)}), 500