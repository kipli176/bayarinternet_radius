from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from app.database import get_db
from app import models
from app.schemas.reports import ResellerReportResponse, UserReportResponse, UserInvoiceSummary, UserUsageSummary, SystemReportResponse
from app.routers.resellers import get_current_reseller
from app.utils.responses import success_response, error_response

router = APIRouter()

# 📊 laporan reseller
@router.get("/reseller", response_model=ResellerReportResponse)
def reseller_report(db: Session = Depends(get_db), reseller=Depends(get_current_reseller)):

    # total users
    total_users = db.query(func.count(models.user.PPPUser.id)).filter(
        models.user.PPPUser.reseller_id == reseller.id
    ).scalar()

    # active & suspended users
    active_users = db.query(func.count(models.user.PPPUser.id)).filter(
        models.user.PPPUser.reseller_id == reseller.id,
        models.user.PPPUser.status == "active"
    ).scalar()

    suspended_users = db.query(func.count(models.user.PPPUser.id)).filter(
        models.user.PPPUser.reseller_id == reseller.id,
        models.user.PPPUser.status == "suspended"
    ).scalar()

    # total routers
    total_routers = db.query(func.count(models.router.MikrotikRouter.id)).filter(
        models.router.MikrotikRouter.reseller_id == reseller.id
    ).scalar()

    # invoices grouping
    invoices_grouped = db.query(
        models.invoice.Invoice.status,
        func.count(models.invoice.Invoice.id),
        func.coalesce(func.sum(models.invoice.Invoice.total), 0)
    ).filter(
        models.invoice.Invoice.reseller_id == reseller.id
    ).group_by(models.invoice.Invoice.status).all()

    invoices_draft = invoices_paid = invoices_overdue = 0
    total_revenue = 0.0

    for status, count, amount in invoices_grouped:
        if status == "draft":
            invoices_draft = count
        elif status == "paid":
            invoices_paid = count
            total_revenue += float(amount or 0)
        elif status == "overdue":
            invoices_overdue = count

    # last invoice date
    last_invoice_date = db.query(
        func.max(models.invoice.Invoice.created_at)
    ).filter(
        models.invoice.Invoice.reseller_id == reseller.id
    ).scalar()

    report = ResellerReportResponse(
        reseller_id=str(reseller.id),
        reseller_name=reseller.name,
        total_users=total_users,
        active_users=active_users,
        suspended_users=suspended_users,
        total_routers=total_routers,
        invoices_draft=invoices_draft,
        invoices_paid=invoices_paid,
        invoices_overdue=invoices_overdue,
        total_revenue=total_revenue,
        last_invoice_date=last_invoice_date
    )
    return success_response(report.dict(), "Reseller report retrieved successfully")



# 📊 laporan detail per user
@router.get("/user/{user_id}", response_model=UserReportResponse)
def user_report(user_id: str, db: Session = Depends(get_db), reseller=Depends(get_current_reseller)):
    user = db.query(models.user.PPPUser).filter(
        models.user.PPPUser.id == user_id,
        models.user.PPPUser.reseller_id == reseller.id
    ).first()

    if not user:
        return error_response("User not found", 404)

    # invoices user
    invoices = db.query(models.customer_invoice.CustomerInvoice).filter(
        models.customer_invoice.CustomerInvoice.user_id == user.id,
        models.customer_invoice.CustomerInvoice.reseller_id == reseller.id
    ).order_by(models.customer_invoice.CustomerInvoice.created_at.desc()).all()

    invoices_summary = [
        UserInvoiceSummary(
            id=str(inv.id),
            status=inv.status,
            amount=float(inv.amount or 0),
            period_start=inv.period_start,
            period_end=inv.period_end
        ) for inv in invoices
    ]

    # usage summary dari radacct
    usage_query = db.query(
        func.count(models.radacct.RadAcct.radacctid),
        func.coalesce(func.sum(models.radacct.RadAcct.acctinputoctets), 0),
        func.coalesce(func.sum(models.radacct.RadAcct.acctoutputoctets), 0),
        func.max(models.radacct.RadAcct.acctstarttime),
        func.max(models.radacct.RadAcct.acctstoptime),
    ).filter(models.radacct.RadAcct.username == user.username).first()

    usage_summary = UserUsageSummary(
        total_sessions=usage_query[0] or 0,
        total_bytes_in=int(usage_query[1] or 0),
        total_bytes_out=int(usage_query[2] or 0),
        last_session_start=usage_query[3],
        last_session_stop=usage_query[4]
    )

    report = UserReportResponse(
        user_id=str(user.id),
        username=user.username,
        full_name=user.full_name,
        phone=user.phone,
        status=user.status,
        active_until=user.active_until,
        invoices=invoices_summary,
        usage=usage_summary
    )
    return success_response(report.dict(), "User report retrieved successfully")


# 📊 laporan global sistem (admin only)
@router.get("/system", response_model=SystemReportResponse)
def system_report(db: Session = Depends(get_db)):
    # total resellers
    total_resellers = db.query(func.count(models.reseller.Reseller.id)).scalar()

    # total users
    total_users = db.query(func.count(models.user.PPPUser.id)).scalar()

    active_users = db.query(func.count(models.user.PPPUser.id)).filter(
        models.user.PPPUser.status == "active"
    ).scalar()

    suspended_users = db.query(func.count(models.user.PPPUser.id)).filter(
        models.user.PPPUser.status == "suspended"
    ).scalar()

    # invoices
    invoices_total = db.query(func.count(models.customer_invoice.CustomerInvoice.id)).scalar()
    invoices_paid = db.query(func.count(models.customer_invoice.CustomerInvoice.id)).filter(
        models.customer_invoice.CustomerInvoice.status == "paid"
    ).scalar()
    invoices_overdue = db.query(func.count(models.customer_invoice.CustomerInvoice.id)).filter(
        models.customer_invoice.CustomerInvoice.status == "overdue"
    ).scalar()

    # revenue
    total_revenue = db.query(
        func.coalesce(func.sum(models.customer_invoice.CustomerInvoice.amount), 0)
    ).filter(models.customer_invoice.CustomerInvoice.status == "paid").scalar()

    report = SystemReportResponse(
        total_resellers=total_resellers,
        total_users=total_users,
        active_users=active_users,
        suspended_users=suspended_users,
        total_invoices=invoices_total,
        invoices_paid=invoices_paid,
        invoices_overdue=invoices_overdue,
        total_revenue=float(total_revenue or 0),
    )
    return success_response(report.dict(), "System report retrieved successfully")
