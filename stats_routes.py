from flask import Blueprint, jsonify, request
from sqlalchemy import func, desc, case, extract
from sqlalchemy.orm import Session
from database import get_db, Invoice, InvoiceItem
from datetime import datetime, timedelta
import calendar

# Création du Blueprint pour les routes de statistiques
stats_bp = Blueprint('stats', __name__, url_prefix='/api/stats')

def get_period_dates(period):
    """
    Retourne les dates de début et de fin en fonction de la période spécifiée
    """
    today = datetime.utcnow().date()
    
    if period == 'week':
        start_date = today - timedelta(days=7)
    elif period == 'month':
        start_date = today.replace(day=1)
    elif period == 'quarter':
        current_month = today.month
        current_quarter = (current_month - 1) // 3 + 1
        start_month = (current_quarter - 1) * 3 + 1
        start_date = today.replace(month=start_month, day=1)
    elif period == 'year':
        start_date = today.replace(month=1, day=1)
    elif period == '7days':
        start_date = today - timedelta(days=7)
    elif period == '30days':
        start_date = today - timedelta(days=30)
    elif period == '90days':
        start_date = today - timedelta(days=90)
    else:  # 'all' ou valeur par défaut
        start_date = None
    
    return start_date, today

def get_previous_period_dates(start_date, end_date):
    """
    Calcule la période précédente de même durée
    """
    if start_date is None:
        return None, None
        
    duration = (end_date - start_date).days
    prev_end_date = start_date - timedelta(days=1)
    prev_start_date = prev_end_date - timedelta(days=duration)
    
    return prev_start_date, prev_end_date

def calculate_change_percentage(current_value, previous_value):
    """
    Calcule le pourcentage de changement entre deux valeurs
    """
    if previous_value == 0:
        return 0, True if current_value > 0 else False
        
    change = ((current_value - previous_value) / previous_value) * 100
    return round(change), change > 0

@stats_bp.route('/dashboard', methods=['GET'])
def get_dashboard_stats():
    """
    Endpoint pour obtenir les statistiques globales du tableau de bord
    """
    period = request.args.get('period', 'all')
    db = next(get_db())
    
    try:
        # Obtenir les dates de la période
        start_date, end_date = get_period_dates(period)
        
        # Requête de base pour les factures de la période actuelle
        query = db.query(Invoice)
        if start_date:
            query = query.filter(func.date(Invoice.created_at) >= start_date,
                                func.date(Invoice.created_at) <= end_date)
        
        # Calculer les statistiques pour la période actuelle
        total_revenue = query.with_entities(func.sum(Invoice.total_amount)).scalar() or 0
        processed_invoices = query.count()
        
        # Nombre de clients actifs (clients distincts dans les factures)
        active_clients = query.with_entities(func.count(func.distinct(Invoice.customer_name))).scalar() or 0
        
        # Taux de traitement (pourcentage de factures traitées avec succès)
        # Hypothèse : une facture est traitée avec succès si elle a un montant total
        total_invoices = processed_invoices
        successful_invoices = query.filter(Invoice.total_amount != None).count()
        processing_rate = round((successful_invoices / total_invoices * 100) if total_invoices > 0 else 0)
        
        # Calculer les statistiques pour la période précédente
        prev_start_date, prev_end_date = get_previous_period_dates(start_date, end_date)
        period_comparison = {}
        
        if prev_start_date:
            prev_query = db.query(Invoice).filter(
                func.date(Invoice.created_at) >= prev_start_date,
                func.date(Invoice.created_at) <= prev_end_date
            )
            
            prev_total_revenue = prev_query.with_entities(func.sum(Invoice.total_amount)).scalar() or 0
            prev_processed_invoices = prev_query.count()
            prev_active_clients = prev_query.with_entities(func.count(func.distinct(Invoice.customer_name))).scalar() or 0
            
            prev_total_invoices = prev_processed_invoices
            prev_successful_invoices = prev_query.filter(Invoice.total_amount != None).count()
            prev_processing_rate = round((prev_successful_invoices / prev_total_invoices * 100) if prev_total_invoices > 0 else 0)
            
            # Calculer les pourcentages de changement
            revenue_change, revenue_positive = calculate_change_percentage(total_revenue, prev_total_revenue)
            invoices_change, invoices_positive = calculate_change_percentage(processed_invoices, prev_processed_invoices)
            clients_change, clients_positive = calculate_change_percentage(active_clients, prev_active_clients)
            rate_change, rate_positive = calculate_change_percentage(processing_rate, prev_processing_rate)
            
            period_comparison = {
                "totalRevenue": {
                    "change": revenue_change,
                    "positive": revenue_positive
                },
                "processedInvoices": {
                    "change": invoices_change,
                    "positive": invoices_positive
                },
                "activeClients": {
                    "change": clients_change,
                    "positive": clients_positive
                },
                "processingRate": {
                    "change": rate_change,
                    "positive": rate_positive
                }
            }
        
        return jsonify({
            "totalRevenue": float(total_revenue),
            "processedInvoices": processed_invoices,
            "activeClients": active_clients,
            "processingRate": processing_rate,
            "periodComparison": period_comparison
        })
        
    except Exception as e:
        db.close()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()

@stats_bp.route('/invoice-activity', methods=['GET'])
def get_invoice_activity():
    """
    Endpoint pour obtenir l'activité des factures pour les graphiques
    """
    period = request.args.get('period', '30days')
    group_by = request.args.get('groupBy')
    
    # Déterminer le regroupement par défaut en fonction de la période
    if not group_by:
        if period == '7days':
            group_by = 'day'
        elif period == '30days':
            group_by = 'day'
        else:  # '90days'
            group_by = 'week'
    
    db = next(get_db())
    
    try:
        # Obtenir les dates de la période
        start_date, end_date = get_period_dates(period)
        
        # Préparer les listes pour les résultats
        labels = []
        invoices_data = []
        amounts_data = []
        
        if group_by == 'day':
            # Générer toutes les dates de la période
            current_date = start_date
            while current_date <= end_date:
                labels.append(current_date.isoformat())
                
                # Compter les factures pour cette date
                day_invoices = db.query(Invoice).filter(
                    func.date(Invoice.created_at) == current_date
                ).count()
                invoices_data.append(day_invoices)
                
                # Calculer le montant total pour cette date
                day_amount = db.query(func.sum(Invoice.total_amount)).filter(
                    func.date(Invoice.created_at) == current_date
                ).scalar() or 0
                amounts_data.append(float(day_amount))
                
                current_date += timedelta(days=1)
                
        elif group_by == 'week':
            # Calculer le nombre de semaines dans la période
            weeks = (end_date - start_date).days // 7 + 1
            
            for i in range(weeks):
                week_start = start_date + timedelta(days=i*7)
                week_end = min(week_start + timedelta(days=6), end_date)
                labels.append(f"{week_start.isoformat()} to {week_end.isoformat()}")
                
                # Compter les factures pour cette semaine
                week_invoices = db.query(Invoice).filter(
                    func.date(Invoice.created_at) >= week_start,
                    func.date(Invoice.created_at) <= week_end
                ).count()
                invoices_data.append(week_invoices)
                
                # Calculer le montant total pour cette semaine
                week_amount = db.query(func.sum(Invoice.total_amount)).filter(
                    func.date(Invoice.created_at) >= week_start,
                    func.date(Invoice.created_at) <= week_end
                ).scalar() or 0
                amounts_data.append(float(week_amount))
                
        elif group_by == 'month':
            # Déterminer le nombre de mois dans la période
            months_diff = (end_date.year - start_date.year) * 12 + end_date.month - start_date.month + 1
            
            for i in range(months_diff):
                month = (start_date.month + i - 1) % 12 + 1
                year = start_date.year + (start_date.month + i - 1) // 12
                
                month_start = datetime(year, month, 1).date()
                last_day = calendar.monthrange(year, month)[1]
                month_end = datetime(year, month, last_day).date()
                
                if month_end > end_date:
                    month_end = end_date
                
                labels.append(f"{year}-{month:02d}")
                
                # Compter les factures pour ce mois
                month_invoices = db.query(Invoice).filter(
                    func.date(Invoice.created_at) >= month_start,
                    func.date(Invoice.created_at) <= month_end
                ).count()
                invoices_data.append(month_invoices)
                
                # Calculer le montant total pour ce mois
                month_amount = db.query(func.sum(Invoice.total_amount)).filter(
                    func.date(Invoice.created_at) >= month_start,
                    func.date(Invoice.created_at) <= month_end
                ).scalar() or 0
                amounts_data.append(float(month_amount))
        
        return jsonify({
            "labels": labels,
            "datasets": [
                {
                    "label": "Factures traitées",
                    "data": invoices_data
                },
                {
                    "label": "Montant (€)",
                    "data": amounts_data
                }
            ]
        })
        
    except Exception as e:
        db.close()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()

@stats_bp.route('/top-clients', methods=['GET'])
def get_top_clients():
    """
    Endpoint pour obtenir les meilleurs clients
    """
    sort_by = request.args.get('sortBy', 'revenue')
    limit = int(request.args.get('limit', 5))
    
    db = next(get_db())
    
    try:
        # Calculer le revenu total pour le calcul des pourcentages
        total_revenue = db.query(func.sum(Invoice.total_amount)).scalar() or 0
        
        # Requête pour obtenir les statistiques par client
        query = db.query(
            Invoice.company_name.label('name'),
            func.count(Invoice.id).label('invoiceCount'),
            func.sum(Invoice.total_amount).label('totalValue')
        ).group_by(Invoice.company_name)
        
        # Trier selon le critère spécifié
        if sort_by == 'revenue':
            query = query.order_by(desc('totalValue'))
        else:  # 'volume'
            query = query.order_by(desc('invoiceCount'))
        
        # Limiter le nombre de résultats
        clients = query.limit(limit).all()
        
        result = {
            "clients": [],
            "totalRevenue": float(total_revenue)
        }
        
        # Formater les résultats
        for i, client in enumerate(clients):
            percentage = round((client.totalValue / total_revenue * 100) if total_revenue > 0 else 0)
            
            result["clients"].append({
                "id": f"client-{i+1}",  # ID généré car nous n'avons pas d'ID client dans la requête
                "name": client.name,
                "totalValue": float(client.totalValue),
                "invoiceCount": client.invoiceCount,
                "percentage": percentage
            })
        
        return jsonify(result)
        
    except Exception as e:
        db.close()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()

@stats_bp.route('/client/<client_name>', methods=['GET'])
def get_client_stats(client_name):
    """
    Endpoint pour obtenir les statistiques d'un client spécifique
    """
    period = request.args.get('period', 'all')
    
    db = next(get_db())
    
    try:
        # Obtenir les dates de la période
        start_date, end_date = get_period_dates(period)
        
        # Requête de base pour les factures du client
        query = db.query(Invoice).filter(Invoice.company_name == client_name)
        
        if start_date:
            query = query.filter(func.date(Invoice.created_at) >= start_date,
                                func.date(Invoice.created_at) <= end_date)
        
        # Calculer les statistiques de base
        total_invoices = query.count()
        total_value = query.with_entities(func.sum(Invoice.total_amount)).scalar() or 0
        average_value = total_value / total_invoices if total_invoices > 0 else 0
        
        # Calculer les statuts de paiement
        # Note: Comme nous n'avons pas de statut de paiement dans notre modèle actuel,
        # nous allons simuler cela en fonction des dates
        today = datetime.utcnow().date()
        
        paid_count = query.filter(
            func.date(Invoice.invoice_date) <= today - timedelta(days=30)
        ).count()
        
        pending_count = query.filter(
            func.date(Invoice.invoice_date) > today - timedelta(days=30),
            func.date(Invoice.invoice_date) <= today
        ).count()
        
        overdue_count = query.filter(
            func.date(Invoice.due_date) < today
        ).count()
        
        # Calculer l'activité par mois (pour les 5 derniers mois)
        activity_labels = []
        activity_data = []
        
        for i in range(4, -1, -1):
            month_date = today.replace(day=1) - timedelta(days=i*30)
            month_name = month_date.strftime("%b")
            activity_labels.append(month_name)
            
            month_start = month_date
            month_end = (month_date.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
            
            month_count = query.filter(
                func.date(Invoice.created_at) >= month_start,
                func.date(Invoice.created_at) <= month_end
            ).count()
            
            activity_data.append(month_count)
        
        return jsonify({
            "totalInvoices": total_invoices,
            "totalValue": float(total_value),
            "averageValue": float(average_value),
            "paymentStatus": {
                "paid": paid_count,
                "pending": pending_count,
                "overdue": overdue_count
            },
            "activity": {
                "labels": activity_labels,
                "data": activity_data
            }
        })
        
    except Exception as e:
        db.close()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()

@stats_bp.route('/invoice-status', methods=['GET'])
def get_invoice_status_stats():
    """
    Endpoint pour obtenir les statistiques de statut des factures
    """
    period = request.args.get('period', 'all')
    
    db = next(get_db())
    
    try:
        # Obtenir les dates de la période
        start_date, end_date = get_period_dates(period)
        
        # Requête de base pour les factures de la période
        query = db.query(Invoice)
        
        if start_date:
            query = query.filter(func.date(Invoice.created_at) >= start_date,
                                func.date(Invoice.created_at) <= end_date)
        
        # Calculer le nombre total de factures
        total_count = query.count()
        
        # Calculer les statuts de paiement
        # Note: Comme nous n'avons pas de statut de paiement dans notre modèle actuel,
        # nous allons simuler cela en fonction des dates
        today = datetime.utcnow().date()
        
        paid_count = query.filter(
            func.date(Invoice.invoice_date) <= today - timedelta(days=30)
        ).count()
        
        pending_count = query.filter(
            func.date(Invoice.invoice_date) > today - timedelta(days=30),
            func.date(Invoice.invoice_date) <= today
        ).count()
        
        overdue_count = query.filter(
            func.date(Invoice.due_date) < today
        ).count()
        
        # Calculer les pourcentages
        paid_percent = round((paid_count / total_count * 100) if total_count > 0 else 0)
        pending_percent = round((pending_count / total_count * 100) if total_count > 0 else 0)
        overdue_percent = round((overdue_count / total_count * 100) if total_count > 0 else 0)
        
        return jsonify({
            "status": {
                "paid": paid_count,
                "pending": pending_count,
                "overdue": overdue_count
            },
            "percentages": {
                "paid": paid_percent,
                "pending": pending_percent,
                "overdue": overdue_percent
            },
            "totalCount": total_count
        })
        
    except Exception as e:
        db.close()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()
