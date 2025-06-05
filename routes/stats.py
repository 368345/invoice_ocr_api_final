# routes/stats.py
from flask import Blueprint, jsonify
from datetime import datetime, timedelta
from sqlalchemy import func, cast, Date, desc
from database import get_db, Invoice
from flask import request

stats_bp = Blueprint("stats", __name__)


@stats_bp.route("/stats/revenue-per-day", methods=["GET"])
def get_revenue_per_day():
    db = next(get_db())
    try:
        days = int(request.args.get("days", 7))

        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        start_date = today - timedelta(days=days - 1)

        result = (
            db.query(
                cast(Invoice.created_at, Date).label("day"),
                func.coalesce(func.sum(Invoice.total_amount), 0).label("total")  # 👈 Coalesce here
            )
            .filter(Invoice.created_at >= start_date)
            .group_by("day")
            .order_by("day")
            .all()
        )

        day_totals = {day.strftime("%Y-%m-%d"): total for day, total in result}

        response = []
        for i in range(days):
            date_obj = start_date + timedelta(days=i)
            date_str = date_obj.strftime("%Y-%m-%d")
            weekday = date_obj.strftime("%a")
            response.append({
                "date": date_str,
                "day": weekday,
                "total": float(day_totals.get(date_str, 0.0))
            })

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
