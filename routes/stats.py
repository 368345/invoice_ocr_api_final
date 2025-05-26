# routes/stats.py
from flask import Blueprint, jsonify
from datetime import datetime, timedelta
from sqlalchemy import func, cast, Date, desc
from database import get_db, Invoice

stats_bp = Blueprint("stats", __name__)


@stats_bp.route("/stats/revenue-per-day", methods=["GET"])
def get_revenue_per_day():
    db = next(get_db())
    try:
        today = datetime.utcnow()
        start_of_week = today - timedelta(days=today.weekday())  # Monday
        
        # Query: sum total_amount grouped by each day (UTC)
        result = (
            db.query(
                cast(Invoice.created_at, Date).label("day"),
                func.sum(Invoice.total_amount).label("total")
            )
            .filter(Invoice.created_at >= start_of_week)
            .group_by("day")
            .order_by("day")
            .all()
        )

        # Map dates to weekday names and build a dict for quick access
        day_totals = {day.strftime("%a"): total for day, total in result}
        weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

        response = [{"day": day, "total": float(day_totals.get(day, 0.0))} for day in weekdays]

        return jsonify(response)
    except Exception as e:
        return jsonify({"error": f"Failed to fetch revenue per day: {str(e)}"}), 500
    finally:
        db.close()
        
@stats_bp.route("/stats/summary", methods=["GET"])
def get_invoice_summary():
    db = next(get_db())
    try:
        # Total number of invoices
        total_invoices = db.query(func.count(Invoice.id)).scalar() or 0

        # Total revenue (sum of total_amount)
        total_revenue = db.query(func.sum(Invoice.total_amount)).scalar() or 0.0

        # Number of unique clients
        total_clients = db.query(func.count(func.distinct(Invoice.customer_name))).scalar() or 0

        return jsonify(
            {
                "total_revenue": total_revenue,
                "total_clients": total_clients,
                "total_invoices": total_invoices,
            }
        )
    except Exception as e:
        return jsonify({"error": f"Failed to fetch invoice summary: {str(e)}"}), 500
    finally:
        db.close()

@stats_bp.route("/stats/top-clients", methods=["GET"])
def get_top_clients():
    db = next(get_db())
    try:
        data = (
            db.query(
                Invoice.customer_name.label("name"),
                func.sum(Invoice.total_amount).label("total_value")
            )
            .group_by(Invoice.customer_name)
            .order_by(desc(func.sum(Invoice.total_amount)))
            .limit(10)
            .all()
        )

        result = [
            {"name": row.name, "totalValue": row.total_value or 0.0}
            for row in data if row.name
        ]
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": f"Failed to fetch top clients: {str(e)}"}), 500
    finally:
        db.close()

@stats_bp.route("/stats/recent-invoices", methods=["GET"])
def get_recent_invoices():
    db = next(get_db())
    try:
        invoices = (
            db.query(
                Invoice.id,
                Invoice.invoice_number,
                Invoice.customer_name,
                Invoice.created_at,
                Invoice.total_amount,
                Invoice.due_date
            )
            .order_by(desc(Invoice.created_at))
            .limit(10)
            .all()
        )

        result = []
        for inv in invoices:
            # Determine status
            if inv.total_amount is not None and inv.total_amount <= 0:
                status = "paid"
            elif inv.due_date:
                try:
                    due = datetime.fromisoformat(inv.due_date)
                    if due < datetime.utcnow():
                        status = "overdue"
                    else:
                        status = "pending"
                except ValueError:
                    status = "pending"
            else:
                status = "pending"

            result.append({
                "id": inv.id,
                "invoiceNumber": inv.invoice_number,
                "clientName": inv.customer_name,
                "date": inv.created_at.isoformat(),
                "amount": inv.total_amount,
                "status": status
            })

        return jsonify(result)
    except Exception as e:
        return jsonify({"error": f"Failed to fetch recent invoices: {str(e)}"}), 500
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
