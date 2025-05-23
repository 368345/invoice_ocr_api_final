# crud.py
from database import Invoice, InvoiceItem, get_db
from sqlalchemy.orm import Session
from utils.ocr_utils import safe_parse_float


def save_invoice_to_db(invoice_data: dict, raw_text: str, raw_json: str) -> int | None:
    db_gen = get_db()
    db: Session = next(db_gen)
    try:
        new_invoice = Invoice(
            company_name=invoice_data.get("Company Name", ""),
            company_address=invoice_data.get("Company Address", ""),
            customer_name=invoice_data.get("Customer Name", ""),
            customer_address=invoice_data.get("Customer Address", ""),
            invoice_number=invoice_data.get("Invoice Number", ""),
            invoice_date=invoice_data.get("Invoice Date", ""),
            due_date=invoice_data.get("Due Date", ""),
            total_amount=safe_parse_float(invoice_data.get("Total")),
            taxes=safe_parse_float(invoice_data.get("Taxes")),
            raw_text=raw_text,
            raw_json=raw_json,
        )

        db.add(new_invoice)
        db.commit()
        db.refresh(new_invoice)

        # Handle items
        if isinstance(invoice_data.get("Description"), list):
            descriptions = invoice_data.get("Description", [])
            quantities = invoice_data.get("Quantity", [])
            unit_prices = invoice_data.get("Unit Price", [])
            amounts = invoice_data.get("Amount", [])

            for i in range(len(descriptions)):
                item = InvoiceItem(
                    invoice_id=new_invoice.id,
                    description=descriptions[i] if i < len(descriptions) else None,
                    quantity=(
                        safe_parse_float(quantities[i]) if i < len(quantities) else None
                    ),
                    unit_price=(
                        safe_parse_float(unit_prices[i])
                        if i < len(unit_prices)
                        else None
                    ),
                    amount=safe_parse_float(amounts[i]) if i < len(amounts) else None,
                )
                db.add(item)
        else:
            item = InvoiceItem(
                invoice_id=new_invoice.id,
                description=invoice_data.get("Description", ""),
                quantity=safe_parse_float(invoice_data.get("Quantity")),
                unit_price=safe_parse_float(invoice_data.get("Unit Price")),
                amount=safe_parse_float(invoice_data.get("Amount")),
            )
            db.add(item)

        db.commit()
        return new_invoice.id
    except Exception as e:
        db.rollback()
        print(f"Error saving invoice to DB: {str(e)}")
        return None
    finally:
        db.close()
