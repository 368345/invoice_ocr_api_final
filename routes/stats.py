# routes/stats.py
from flask import Blueprint, jsonify
from sqlalchemy import func
from database import get_db, Invoice

stats_bp = Blueprint("stats", __name__)


@stats_bp.route("/stats/summary", methods=["GET"])
def get_invoice_summary():
    db = next(get_db())
    try:
        # Total number of invoices
        total_invoices = db.query(func.count(Invoice.id)).scalar() or 0

        # Total revenue (sum of total_amount)
        total_revenue = db.query(func.sum(Invoice.total_amount)).scalar() or 0.0

        # Find customer with most invoices
        top_customer = (
            db.query(
                Invoice.customer_name, func.count(Invoice.id).label("invoice_count")
            )
            .group_by(Invoice.customer_name)
            .order_by(func.count(Invoice.id).desc())
            .first()
        )

        if top_customer and total_invoices > 0:
            top_customer_name = top_customer[0] or "Unknown"
            top_customer_invoice_count = top_customer[1]
            top_customer_percentage = round(
                (top_customer_invoice_count / total_invoices) * 100, 2
            )
        else:
            top_customer_name = None
            top_customer_invoice_count = 0
            top_customer_percentage = 0.0

        return jsonify(
            {
                "total_invoices": total_invoices,
                "total_revenue": total_revenue,
                "top_customer": {
                    "name": top_customer_name,
                    "invoice_count": top_customer_invoice_count,
                    "percentage_of_total": top_customer_percentage,
                },
            }
        )
    except Exception as e:
        return jsonify({"error": f"Failed to fetch invoice summary: {str(e)}"}), 500
    finally:
        db.close()


@stats_bp.route("/stats/total-revenue", methods=["GET"])
def get_total_revenue():
    db = next(get_db())
    try:
        total = db.query(func.sum(Invoice.total_amount)).scalar() or 0.0
        return jsonify({"total_revenue": total})
    except Exception as e:
        return jsonify({"error": f"Failed to fetch total revenue: {str(e)}"}), 500
    finally:
        db.close()


@stats_bp.route("/stats/revenue-per-company", methods=["GET"])
def get_revenue_per_company():
    db = next(get_db())
    try:
        data = (
            db.query(Invoice.company_name, func.sum(Invoice.total_amount))
            .group_by(Invoice.company_name)
            .all()
        )
        result = [
            {"company": row[0], "total_revenue": row[1] or 0.0}
            for row in data
            if row[0]
        ]
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": f"Failed to fetch revenue per company: {str(e)}"}), 500
    finally:
        db.close()
