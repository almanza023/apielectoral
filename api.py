from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional, Dict, Any
import asyncio
import os
import sys
import time
import requests
from datetime import datetime

# Importar utilidades
from models.request import PeticionRequest, BulkSisbenRequest, BulkNameRequest, ConsultaNombreRequest
from utils.time_utils import format_execution_time, calculate_response_time, get_current_timestamp
from utils.captcha_solver import TwoCaptchaSolver

# Importar gestor de tareas
from task_manager import (
    create_task,
    get_task,
    delete_task,
    list_tasks,
    process_bulk_sisben_task,
    process_bulk_name_task,
    get_tasks_directory,
    get_task_count
)


# Importar clases existentes
from config import settings
from scrapper.registraduria_scraper_optimizado import RegistraduriaScraperAuto, save_registraduria_results
from scrapper.police_scraper import PoliciaScraperAuto, save_police_results 
from scrapper.procuraduria_scraper import ProcuraduriaScraperAuto, save_procuraduria_results
from scrapper.sisben_scraper import SisbenScraperAuto, save_sisben_results
from scrapper.adres_scraper import AdresScraperAuto, save_adres_results
from scrapper.policiajudicial_scraper import PoliciaJudicialScraper, save_policia_results

# Crear la aplicación FastAPI
app = FastAPI(
    title=settings.API_TITLE,
    description=settings.API_DESCRIPTION,
    version=settings.API_VERSION
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
)

# Configuración global
API_KEY = os.getenv('APIKEY_2CAPTCHA')
if not API_KEY:
    print("❌ Error: No se encontró la API key de 2captcha")
    sys.exit(1)

@app.on_event("startup")
async def startup_event():
    """Evento de inicio de la aplicación"""
    print("🚀 API Electoral")
    print(f"🔑 API Key configurada: {API_KEY[:10]}...")
    print(f"📁 Directorio de tareas: {get_tasks_directory().absolute()}")
    print(f"📊 Tareas guardadas: {get_task_count()}")
    print(f"\n🌐 URLs de API Externa:")
    print(f"   📝 Nombre: {settings.EXTERNAL_API_NOMBRE_URL}")
    print(f"   🗳️  Puesto: {settings.EXTERNAL_API_PUESTO_URL}")

@app.get("/balance")
async def get_balance():
    """
    Obtener balance de la cuenta de 2captcha y estimado de peticiones
    
    Returns:
        dict: Balance en USD, costo por captcha y estimado de peticiones disponibles
    """
    try:
        solver = TwoCaptchaSolver(API_KEY)
        balance_info = solver.get_balance()
        return balance_info
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Error al consultar balance: {e}"
        }


@app.post("/consultar-nombres-v1")
async def get_procuraduria_data(request: PeticionRequest):
    """
    Consulta nombre en Procuraduría
    
    Args:
        request.nuip: Número de identificación
        request.enviarapi: Si es True, envía el nombre al API externo
    """
    start_time = time.time()
    scraper = None
    try:
        scraper = ProcuraduriaScraperAuto(API_KEY)
        result = scraper.scrape_nuip(request.nuip)
        
        # Si enviarapi es True y se encontró el nombre, enviar al API externo
        if request.enviarapi and result.get("status") == "success":
            nombre = result.get("name", "")
            if nombre and nombre.strip():
                print(f"📤 Enviando nombre al API externo (v1)...")
                api_response = send_name_to_external_api(request.nuip, nombre.strip())
                result["api_externa"] = api_response
        
        return result
    except Exception as e:
        response_time_seconds, execution_time = calculate_response_time(start_time)
        
        raise HTTPException(
            status_code=500,
            detail={
                "error": f"Error al procesar la consulta: {str(e)}",
                "response_time_seconds": response_time_seconds,
                "execution_time": execution_time
            }
        )
    finally:
        if scraper:
            scraper.close()
    
@app.post("/consultar-nombres-v2")
async def get_police_data(request: PeticionRequest):
    """
    Consulta nombre en Policía
    
    Args:
        request.nuip: Número de identificación
        request.fecha_expedicion: Fecha de expedición (opcional)
        request.enviarapi: Si es True, envía el nombre al API externo
    """
    start_time = time.time()
    try:
        scraper = PoliciaScraperAuto(headless=True)
        result = scraper.scrape_name_by_nuip(request.nuip, request.fecha_expedicion)
        
        # Si enviarapi es True y se encontró el nombre, enviar al API externo
        if request.enviarapi and result.get("status") == "success":
            nombre = result.get("name", "")
            if nombre and nombre.strip():
                print(f"📤 Enviando nombre al API externo (v2)...")
                api_response = send_name_to_external_api(request.nuip, nombre.strip())
                result["api_externa"] = api_response
        
        return result    
    except Exception as e:
        response_time_seconds, execution_time = calculate_response_time(start_time)
        
        raise HTTPException(
            status_code=500,
            detail={
                "error": f"Error al procesar la consulta: {str(e)}",
                "response_time_seconds": response_time_seconds,
                "execution_time": execution_time
            }
        )
    finally:
        scraper.close()

@app.post("/consultar-nombres-v3")
async def get_sisben_data(request: PeticionRequest):
    start_time = time.time()
    scraper = None
    try:
        scraper = SisbenScraperAuto(headless=True)
        result = scraper.scrape_name_by_nuip(request.nuip)
        return result    
    except Exception as e:
        response_time_seconds, execution_time = calculate_response_time(start_time)
        
        raise HTTPException(
            status_code=500,
            detail={
                "error": f"Error al procesar la consulta: {str(e)}",
                "response_time_seconds": response_time_seconds,
                "execution_time": execution_time
            }
        )
    finally:
        if scraper:
            scraper.close()

@app.post("/consultar-nombres-v4")
async def get_adres_data(request: PeticionRequest):
    """
    Consulta nombre en ADRES
    
    Args:
        request.nuip: Número de identificación
        request.enviarapi: Si es True, envía el nombre al API externo
    """
    start_time = time.time()
    scraper = None
    try:
        scraper = AdresScraperAuto(API_KEY)
        result = scraper.scrape_nuip(request.nuip)

        # Construir campo 'name' a partir de NOMBRES y APELLIDOS si existe
        nombres = (result.get('NOMBRES') or '').strip()
        apellidos = (result.get('APELLIDOS') or '').strip()
        full_name = ' '.join([x for x in [nombres, apellidos] if x]).strip()
        if full_name:
            result['name'] = full_name

        # Si enviarapi es True y se encontró el nombre, enviar al API externo
        if request.enviarapi and result.get("status") == "success":
            nombre = result.get("name", "")
            if nombre and nombre.strip():
                print(f"📤 Enviando nombre al API externo (v4)...")
                api_response = send_name_to_external_api(request.nuip, nombre.strip())
                result["api_externa"] = api_response

        return result
    except Exception as e:
        response_time_seconds, execution_time = calculate_response_time(start_time)
        
        raise HTTPException(
            status_code=500,
            detail={
                "error": f"Error al procesar la consulta: {str(e)}",
                "response_time_seconds": response_time_seconds,
                "execution_time": execution_time
            }
        )
    finally:
        if scraper:
            scraper.close()

@app.post("/consultar-nombres-v5")
async def get_policiajudicial_data(request: PeticionRequest):
    """
    Consulta nombre en Policía Judicial (WebJudicial)

    Args:
        request.nuip: Número de identificación
        request.enviarapi: Si es True, envía el nombre al API externo
    """
    start_time = time.time()
    scraper = None
    try:
        scraper = PoliciaJudicialScraper(API_KEY)
        result = scraper.scrape_nuip(request.nuip)

        # Construir campo 'name' a partir de NOMBRES si existe
        nombres = (result.get('NOMBRES') or '').strip()
        if nombres:
            result['name'] = nombres

        # Si enviarapi es True y se encontró el nombre, enviar al API externo
        if request.enviarapi and result.get("status") == "success":
            nombre = result.get("name", "")
            if nombre and nombre.strip():
                print(f"📤 Enviando nombre al API externo (v5)...")
                api_response = send_name_to_external_api(request.nuip, nombre.strip())
                result["api_externa"] = api_response

        return result
    except Exception as e:
        response_time_seconds, execution_time = calculate_response_time(start_time)
        
        raise HTTPException(
            status_code=500,
            detail={
                "error": f"Error al procesar la consulta: {str(e)}",
                "response_time_seconds": response_time_seconds,
                "execution_time": execution_time
            }
        )
    finally:
        if scraper:
            scraper.close()

@app.post("/consultar-puesto-votacion")
async def get_registraduria_data(request: PeticionRequest):
    """
    Consulta puesto de votación en Registraduría
    
    Args:
        request.nuip: Número de identificación
        request.enviarapi: Si es True, envía el puesto al API externo
    """
    start_time = time.time() 
    
    try:
        # Crear scraper sin verificar balance (más rápido)
        scraper = RegistraduriaScraperAuto(API_KEY, check_balance=False, proxy_list=settings.PROXY_LIST if settings.PROXY_ENABLED else None)
        
        try:

            result = scraper.scrape_nuip(request.nuip)

            # Imprimir el JSON completo del puesto de votación si existe
            if result.get("status") == "success":
                data_records = result.get("data", [])
                if data_records and len(data_records) > 0:
                    import json
                    print("\n===== JSON DE PUESTO DE VOTACIÓN =====")
                    print(json.dumps(data_records[0], indent=2, ensure_ascii=False))
                    print("======================================\n")

            # Si enviarapi es True y se encontró el puesto, enviar al API externo
            if request.enviarapi and result.get("status") == "success":
                data_records = result.get("data", [])
                if data_records and len(data_records) > 0:
                    voting_data = data_records[0]
                    print(f"📤 Enviando puesto de votación al API externo...")
                    api_response = send_voting_place_to_external_api(request.nuip, voting_data)
                    result["api_externa"] = api_response

            return result
            
        finally:
            scraper.close()
            
    except Exception as e:
        response_time_seconds, execution_time = calculate_response_time(start_time)
        
        raise HTTPException(
            status_code=500,
            detail={
                "error": f"Error al procesar la consulta: {str(e)}",
                "response_time_seconds": response_time_seconds,
                "execution_time": execution_time
            }
        )

def send_name_to_external_api(numero_documento: str, nombre_completo: str) -> dict:
    """
    Envía el nombre encontrado al endpoint externo
    
    Args:
        numero_documento: Número de documento
        nombre_completo: Nombre completo encontrado
    
    Returns:
        dict: Respuesta del endpoint externo con status y message
    """
    try:
        url = settings.EXTERNAL_API_NOMBRE_URL
        print(f"🔍 DEBUG - URL cargada: {url}")
        print(f"🔍 DEBUG - Tipo de URL: {type(url)}")
        
        payload = {
            "numerodocumento": numero_documento,
            "nombrecompleto": nombre_completo
        }
        
        print(f"📤 Enviando NOMBRE al endpoint externo: {url}")
        print(f"   Documento: {numero_documento}, Nombre: {nombre_completo}")
        
        response = requests.post(url, json=payload, timeout=20)
        response.raise_for_status()
        
        result = response.json()
        print(f"✅ Respuesta del endpoint de nombre: {result}")
        
        return {
            "nombre_api_called": True,
            "nombre_api_status": result.get("status"),
            "nombre_api_message": result.get("message")
        }
        
    except requests.exceptions.Timeout:
        print(f"⚠️ Timeout al llamar al endpoint de nombre")
        return {
            "nombre_api_called": False,
            "nombre_api_error": "Timeout al conectar con el endpoint de nombre"
        }
    except requests.exceptions.RequestException as e:
        print(f"⚠️ Error al llamar al endpoint de nombre: {e}")
        return {
            "nombre_api_called": False,
            "nombre_api_error": str(e)
        }
    except Exception as e:
        print(f"⚠️ Error inesperado al llamar al endpoint de nombre: {e}")
        return {
            "nombre_api_called": False,
            "nombre_api_error": str(e)
        }

def send_voting_place_to_external_api(numero_documento: str, voting_data: dict) -> dict:
    """
    Envía los datos del puesto de votación al endpoint externo
    
    Args:
        numero_documento: Número de documento
        voting_data: Datos del puesto de votación (departamento, municipio, puesto, dirección, mesa)
    
    Returns:
        dict: Respuesta del endpoint externo con status y message
    """
    try:
        url = settings.EXTERNAL_API_PUESTO_URL
        print(f"🔍 DEBUG - URL cargada: {url}")
        print(f"🔍 DEBUG - Tipo de URL: {type(url)}")
        
        payload = {
            "numerodocumento": numero_documento,
            "departamento": voting_data.get("DEPARTAMENTO", ""),
            "municipio": voting_data.get("MUNICIPIO", ""),
            "puesto": voting_data.get("PUESTO", ""),
            "direccion": voting_data.get("DIRECCIÓN", ""),
            "mesa": voting_data.get("MESA", "")
        }
        
        print(f"📤 Enviando PUESTO DE VOTACIÓN al endpoint externo: {url}")
        print(f"   Documento: {numero_documento}, Puesto: {voting_data.get('PUESTO', 'N/A')}")
        
        response = requests.post(url, json=payload, timeout=20)
        response.raise_for_status()
        
        result = response.json()
        print(f"✅ Respuesta del endpoint de puesto: {result}")
        
        return {
            "puesto_api_called": True,
            "puesto_api_status": result.get("status"),
            "puesto_api_message": result.get("message")
        }
        
    except requests.exceptions.Timeout:
        print(f"⚠️ Timeout al llamar al endpoint de puesto")
        return {
            "puesto_api_called": False,
            "puesto_api_error": "Timeout al conectar con el endpoint de puesto"
        }
    except requests.exceptions.RequestException as e:
        print(f"⚠️ Error al llamar al endpoint de puesto: {e}")
        return {
            "puesto_api_called": False,
            "puesto_api_error": str(e)
        }
    except Exception as e:
        print(f"⚠️ Error inesperado al llamar al endpoint de puesto: {e}")
        return {
            "puesto_api_called": False,
            "puesto_api_error": str(e)
        }

async def process_single_nuip(
    nuip: str,
    enviarapi: bool = False,
    consultarpuesto: bool = True,
    consultarnombre: bool = True
) -> dict:
    """
    Procesa un solo NUIP buscando el nombre en orden:
    1. Sisben (si consultarnombre=True)
    2. Procuraduría (si no se encontró en Sisben y consultarnombre=True)
    3. Registraduría (consulta puesto de votación solo si consultarpuesto=True)
    
    Args:
        nuip: Número de identificación a consultar
        enviarapi: Si es True, envía los datos al API externo
        consultarpuesto: Si es True, consulta el puesto de votación en Registraduría
        consultarnombre: Si es True, consulta nombre en Sisben y Procuraduría
    
    Returns:
        dict: Resultado de la consulta con nombre, voting_place, source y respuesta del API externo
        Incluye status: "success", "partial_success", "not_found", o "error"
    """
    start_time = time.time()
    name = ""
    source = None
    
    try:
        # 1. Buscar en Sisben primero (solo si consultarnombre=True)
        if consultarnombre:
            max_intentos_sisben = 1
            for intento_sisben in range(1, max_intentos_sisben + 1):
                scraper_sisben = None
                try:
                    print(f"🔍 Sisben - Intento {intento_sisben}/{max_intentos_sisben}")
                    scraper_sisben = SisbenScraperAuto(headless=True)
                    
                    # Usar timeout de 60 segundos para Sisben
                    result_sisben = await asyncio.wait_for(
                        asyncio.to_thread(scraper_sisben.scrape_name_by_nuip, nuip),
                        timeout=60.0
                    )
                    
                    # Verificar si se encontró el nombre
                    if result_sisben.get("status") == "success":
                        extracted_name = result_sisben.get("name")
                        if extracted_name and extracted_name.strip():
                            name = extracted_name.strip()
                            source = "sisben"
                            print(f"✅ Nombre encontrado en Sisben: {name}")
                            break  # Salir del loop si se encontró
                except asyncio.TimeoutError:
                    print(f"⏱️ Timeout en Sisben intento {intento_sisben} (60s excedidos)")
                except Exception as e:
                    print(f"⚠️ Error en Sisben intento {intento_sisben}: {e}")
                finally:
                    if scraper_sisben:
                        try:
                            scraper_sisben.close()
                        except Exception as close_error:
                            print(f"⚠️ Error al cerrar Sisben: {close_error}")
                
                # Esperar un poco antes del siguiente intento (solo si no es el último)
                if intento_sisben < max_intentos_sisben and not name:
                    await asyncio.sleep(2)
        else:
            print("⏭️ Saltando búsqueda de nombre (consultarnombre=False)")
        
        # 2. Si no se encontró en Sisben, buscar en Procuraduría (solo si consultarnombre=True)
        if consultarnombre and not name:
            scraper_procuraduria = None
            try:
                print(f"🔍 Buscando en Procuraduría...")
                scraper_procuraduria = ProcuraduriaScraperAuto(API_KEY)
                
                # Usar timeout de 60 segundos para Procuraduría
                result_procuraduria = await asyncio.wait_for(
                    asyncio.to_thread(scraper_procuraduria.scrape_nuip, nuip),
                    timeout=60.0
                )
                
                # Verificar si se encontró el nombre
                if result_procuraduria.get("status") == "success":
                    extracted_name = result_procuraduria.get("name")
                    if extracted_name and extracted_name.strip():
                        name = extracted_name.strip()
                        source = "procuraduria"
                        print(f"✅ Nombre encontrado en Procuraduría: {name}")
            except asyncio.TimeoutError:
                print(f"⏱️ Timeout en Procuraduría (60s excedidos)")
            except Exception as e:
                print(f"⚠️ Error en Procuraduría: {e}")
            finally:
                if scraper_procuraduria:
                    try:
                        scraper_procuraduria.close()
                    except Exception as close_error:
                        print(f"⚠️ Error al cerrar Procuraduría: {close_error}")
        
        # 3. Enviar nombre al API externo si se encontró (solo si enviarapi=True)
        nombre_response = {}
        if name and enviarapi:
            print(f"📤 Enviando nombre al API externo...")
            nombre_response = send_name_to_external_api(nuip, name)
        
        # 4. Consultar puesto de votación en registraduría solo si consultarpuesto=True
        voting_data = None
        if consultarpuesto:
            scraper_registraduria = None
            try:
                print(f"🗳️ Consultando puesto de votación para {nuip}...")
                scraper_registraduria = RegistraduriaScraperAuto(API_KEY, proxy_list=settings.PROXY_LIST if settings.PROXY_ENABLED else None)
                
                # Usar asyncio.wait_for para timeout de 120 segundos
                voting_result = await asyncio.wait_for(
                    asyncio.to_thread(scraper_registraduria.scrape_nuip, nuip),
                    timeout=120.0
                )
                
                if voting_result.get("status") == "success":
                    data_records = voting_result.get("data", [])
                    if data_records and len(data_records) > 0:
                        voting_data = data_records[0]
                        print(f"✅ Puesto de votación encontrado: {voting_data.get('PUESTO', 'N/A')}")
                    else:
                        print(f"⚠️ No se encontró puesto de votación")
                else:
                    print(f"⚠️ Error al consultar puesto de votación: {voting_result.get('message', 'Unknown')}")
            except asyncio.TimeoutError:
                print(f"⏱️ Timeout al consultar puesto de votación (120s excedidos)")
                voting_data = None
            except Exception as e:
                print(f"⚠️ Error al consultar puesto de votación: {e}")
            finally:
                if scraper_registraduria:
                    try:
                        scraper_registraduria.close()
                    except Exception as close_error:
                        print(f"⚠️ Error al cerrar scraper de registraduría: {close_error}")
        else:
            print(f"⏭️ Saltando consulta de puesto de votación (consultarpuesto=False)")
        
        # 5. Enviar puesto de votación al endpoint externo (solo si enviarapi=True y se encontró)
        puesto_response = {}
        if enviarapi and voting_data:
            print(f"📤 Enviando puesto de votación al API externo...")
            puesto_response = send_voting_place_to_external_api(nuip, voting_data)
        
        response_time_seconds, execution_time = calculate_response_time(start_time)
        
        # 6. Determinar el status de la respuesta
        if name:
            # Se encontró nombre en sisben o procuraduría
            return {
                "nuip": nuip,
                "status": "success",
                "name": name,
                "voting_place": voting_data,
                "execution_time": execution_time,
                "source": source,
                **nombre_response,
                **puesto_response
            }
        elif voting_data:
            # No se encontró nombre, pero sí puesto de votación
            return {
                "nuip": nuip,
                "status": "partial_success",
                "name": "",
                "voting_place": voting_data,
                "execution_time": execution_time,
                "source": "registraduria_only",
                **puesto_response
            }
        else:
            # No se encontró ni nombre ni puesto de votación
            return {
                "nuip": nuip,
                "status": "not_found",
                "name": "",
                "voting_place": None,
                "execution_time": execution_time
            }
        
    except Exception as e:
        response_time_seconds, execution_time = calculate_response_time(start_time)
        
        return {
            "nuip": nuip,
            "status": "error",
            "name": "",
            "execution_time": execution_time,
            "error": str(e)
        }

@app.post("/consultar-nombres")
async def get_name_sequential(request: ConsultaNombreRequest):
    """
    Endpoint que busca nombres para múltiples NUIPs secuencialmente en:
    1. Sisben
    2. Procuraduría (si no se encontró en Sisben)
    3. Registraduría (consulta puesto de votación solo si consultarpuesto=True)
    
    Si encuentra el nombre, lo envía automáticamente al endpoint externo.
    Si encuentra puesto de votación, también lo envía al endpoint externo.
    
    Args:
        request: Lista de NUIPs a consultar, enviarapi (bool), consultarpuesto (bool, default=True), consultarnombre (bool, default=True)
    
    Returns:
        dict: Lista de resultados con status, name, voting_place, execution_time, source para cada NUIP
        Posibles status:
        - "success": Se encontró nombre y/o puesto de votación
        - "partial_success": Solo se encontró puesto de votación (no nombre)
        - "not_found": No se encontró ni nombre ni puesto de votación
        - "error": Error durante el procesamiento
    """
    start_time = time.time()
    results = []
    
    # Imprimir el request recibido
    print(f"\n{'='*60}")
    print(f"📥 REQUEST RECIBIDO:")
    print(f"{'='*60}")
    print(f"NUIPs: {request.nuips}")
    print(f"Total NUIPs: {len(request.nuips)}")
    print(f"Consultar puesto: {request.consultarpuesto}")
    print(f"Consultar nombre: {request.consultarnombre}")
    print(f"{'='*60}\n")
    
    print(f"\n📋 Procesando {len(request.nuips)} NUIPs...")
    
    for idx, nuip in enumerate(request.nuips, 1):
        print(f"\n{'='*60}")
        print(f"📌 Procesando NUIP {idx}/{len(request.nuips)}: {nuip}")
        print(f"{'='*60}")
        
        try:
            # Agregar timeout global por NUIP (6 minutos máximo)
            result = await asyncio.wait_for(
                process_single_nuip(
                    nuip,
                    enviarapi=request.enviarapi,
                    consultarpuesto=request.consultarpuesto,
                    consultarnombre=request.consultarnombre
                ),
                timeout=360.0
            )
            results.append(result)
        except asyncio.TimeoutError:
            print(f"⏱️ TIMEOUT GLOBAL: NUIP {nuip} excedió 6 minutos")
            results.append({
                "nuip": nuip,
                "status": "error",
                "name": "",
                "execution_time": "360+ seconds",
                "error": "Timeout global: procesamiento excedió 6 minutos"
            })
        except Exception as e:
            print(f"❌ ERROR CRÍTICO procesando NUIP {nuip}: {e}")
            results.append({
                "nuip": nuip,
                "status": "error",
                "name": "",
                "execution_time": "unknown",
                "error": f"Error crítico: {str(e)}"
            })
        
        # Pequeña pausa entre consultas para no sobrecargar
        if idx < len(request.nuips):
            await asyncio.sleep(1)
    
    total_time_seconds, total_execution_time = calculate_response_time(start_time)
    
    # Estadísticas
    successful = sum(1 for r in results if r["status"] == "success")
    not_found = sum(1 for r in results if r["status"] == "not_found")
    errors = sum(1 for r in results if r["status"] == "error")
    
    return {
        "status": "completed",
        "total_nuips": len(request.nuips),
        "successful": successful,
        "not_found": not_found,
        "errors": errors,
        "total_execution_time": total_execution_time,
        "results": results
    }

@app.post("/consultar-solo-nombres")
async def get_solo_name_sequential(request: PeticionRequest):
    """
    Endpoint que busca nombre para un NUIP en:
    1. Sisben
    2. Procuraduría (si no se encontró en Sisben)
    
    Args:
        nuip: Número de identificación a consultar
    
    Returns:
        dict: Resultado con status y name
    """
    start_time = time.time()
    name = ""
    source = None
    nuip = request.nuip
    
    print(f"\n{'='*60}")
    print(f"📥 Consultando NUIP: {nuip}")
    print(f"{'='*60}\n")
    
    try:
        # 1. Buscar en Sisben primero
        scraper_sisben = None
        try:
            print(f"🔍 Buscando en Sisben...")
            scraper_sisben = SisbenScraperAuto(headless=True)
            
            result_sisben = await asyncio.wait_for(
                asyncio.to_thread(scraper_sisben.scrape_name_by_nuip, request.nuip),
                timeout=60.0
            )
            
            if result_sisben.get("status") == "success":
                extracted_name = result_sisben.get("name")
                if extracted_name and extracted_name.strip():
                    name = extracted_name.strip()
                    source = "sisben"
                    print(f"✅ Nombre encontrado en Sisben: {name}")
        except asyncio.TimeoutError:
            print(f"⏱️ Timeout en Sisben (60s excedidos)")
        except Exception as e:
            print(f"⚠️ Error en Sisben: {e}")
        finally:
            if scraper_sisben:
                try:
                    scraper_sisben.close()
                except Exception as close_error:
                    print(f"⚠️ Error al cerrar Sisben: {close_error}")
        
        # 2. Si no se encontró en Sisben, buscar en Procuraduría
        if not name:
            scraper_procuraduria = None
            try:
                print(f"🔍 Buscando en Procuraduría...")
                scraper_procuraduria = ProcuraduriaScraperAuto(API_KEY)
                
                result_procuraduria = await asyncio.wait_for(
                    asyncio.to_thread(scraper_procuraduria.scrape_nuip, request.nuip),
                    timeout=60.0
                )
                
                if result_procuraduria.get("status") == "success":
                    extracted_name = result_procuraduria.get("name")
                    if extracted_name and extracted_name.strip():
                        name = extracted_name.strip()
                        source = "procuraduria"
                        print(f"✅ Nombre encontrado en Procuraduría: {name}")
            except asyncio.TimeoutError:
                print(f"⏱️ Timeout en Procuraduría (60s excedidos)")
            except Exception as e:
                print(f"⚠️ Error en Procuraduría: {e}")
            finally:
                if scraper_procuraduria:
                    try:
                        scraper_procuraduria.close()
                    except Exception as close_error:
                        print(f"⚠️ Error al cerrar Procuraduría: {close_error}")
        
        response_time_seconds, execution_time = calculate_response_time(start_time)
        
        if name:
            # Enviar al API externo si está habilitado
            api_response = {}
            if request.enviarapi:
                print(f"📤 Enviando nombre al API externo...")
                api_response = send_name_to_external_api(request.nuip, name)
            
            response_data = {
                "status": "success",
                "name": name,
                "source": source,
                "execution_time": execution_time
            }
            
            # Incluir respuesta del API externo si se envió
            if api_response:
                response_data["api_externa"] = api_response
                
            return response_data
        else:
            return {
                "status": "not_found",
                "name": "",
                "execution_time": execution_time
            }
            
    except Exception as e:
        response_time_seconds, execution_time = calculate_response_time(start_time)
        
        return {
            "status": "error",
            "name": "",
            "execution_time": execution_time,
            "error": str(e)
        }

