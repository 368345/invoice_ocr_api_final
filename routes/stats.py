# routes/stats.py
from flask import Blueprint, jsonify
from sqlalchemy import func
from database import get_db, Invoice

stats_bp = Blueprint("stats", __name__)


@stats_bp.route("/stats/total-invoices", methods=["GET"])
def get_total_invoices():
    db = next(get_db())
    try:
        count = db.query(func.count(Invoice.id)).scalar()
        return jsonify({"total_invoices": count})
    except Exception as e:
        return jsonify({"error": f"Failed to fetch invoice count: {str(e)}"}), 500
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
