from fastapi import FastAPI
from app.config import settings
from app.database import engine, Base
from fastapi.middleware.cors import CORSMiddleware

# import routers (akan ditambahkan bertahap)
from app.routers import auth, resellers, routers, profiles, users, invoices, customer_invoices, monitoring, logs, reports

# buat tabel kalau belum ada (sementara auto create)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="BayarInternet API",
    version="1.0.0",
    description="API Backend untuk sistem reseller Mikrotik + Radius"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],            # Mengizinkan semua origin
    allow_credentials=True,
    allow_methods=["*"],            # Mengizinkan semua metode HTTP (GET, POST, dll)
    allow_headers=["*"],           # Mengizinkan semua header
)
# register routers
app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(resellers.router, prefix="/resellers", tags=["Resellers"])
app.include_router(routers.router, prefix="/routers", tags=["Routers"])
app.include_router(profiles.router, prefix="/profiles", tags=["Profiles"])
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(invoices.router, prefix="/invoices", tags=["Invoices"])
app.include_router(customer_invoices.router, prefix="/customer-invoices", tags=["Customer Invoices"])
app.include_router(monitoring.router, prefix="/sessions", tags=["Monitoring"])
app.include_router(logs.router, prefix="/logs", tags=["Logs"])
app.include_router(reports.router, prefix="/reports", tags=["Reports"])
