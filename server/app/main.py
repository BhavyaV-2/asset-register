import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from psycopg import IntegrityError, DataError
from app import database, people
from app.settings import secret
from db.seed.make_seed import make_seed

@asynccontextmanager
async def lifespan(app):
    secret()
    database.migrate()
    make_seed()
    yield

app = FastAPI(title='Asset Register',lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=os.getenv('ALLOWED_ORIGINS','http://localhost:5173').split(','),allow_methods=['GET','POST','PATCH','PUT'],allow_headers=['Authorization','Content-Type'],expose_headers=['X-Tile-Trimmed'])
app.include_router(people.router)
from app import areas, asset_types, department_systems
for routes in [areas.router, asset_types.router, department_systems.router]:
    app.include_router(routes)

@app.exception_handler(HTTPException)
async def handle_error(request, error):
    return JSONResponse({'message':str(error.detail)},status_code=error.status_code)

@app.exception_handler(RequestValidationError)
async def handle_input(request, error):
    return JSONResponse({'message':'Check the supplied fields and try again.'},status_code=422)

@app.exception_handler(IntegrityError)
@app.exception_handler(DataError)
async def handle_database_input(request, error):
    return JSONResponse({'message':'These values cannot be saved. Check linked records and duplicate values.'},status_code=400)

@app.get('/health')
def health():
    database.one('SELECT 1')
    return {'ok':True}
