#!/usr/bin/env python3
"""
Script para probar proxies y conectividad
Útil para verificar que los proxies configurados funcionan correctamente
"""

import requests
import sys
from typing import List, Optional

def test_proxy(proxy_url: str, max_retries: int = 3) -> dict:
    """
    Prueba un proxy individual
    
    Args:
        proxy_url: URL del proxy (ej: http://proxy.com:8080)
        max_retries: Intentos máximos
    
    Returns:
        Dict con resultado de la prueba
    """
    proxies = {
        'http': proxy_url,
        'https': proxy_url
    }
    
    test_urls = [
        'http://httpbin.org/ip',  # Retorna tu IP
        'http://ifconfig.co',  # También retorna tu IP
    ]
    
    for attempt in range(max_retries):
        for url in test_urls:
            try:
                print(f"  Intento {attempt + 1}/{max_retries}: Probando {url}...")
                response = requests.get(
                    url,
                    proxies=proxies,
                    timeout=5
                )
                
                if response.status_code == 200:
                    print(f"  ✅ Éxito - Status: {response.status_code}")
                    return {
                        'status': 'success',
                        'proxy': proxy_url,
                        'response': response.text[:200],
                        'status_code': response.status_code
                    }
            except requests.exceptions.ProxyError:
                print(f"  ❌ Error de proxy (ProxyError)")
            except requests.exceptions.ConnectionError:
                print(f"  ❌ Error de conexión (ConnectionError)")
            except requests.exceptions.Timeout:
                print(f"  ⏱️  Timeout - Proxy muy lento")
            except Exception as e:
                print(f"  ❌ Erro: {type(e).__name__}: {str(e)[:100]}")
    
    return {
        'status': 'failed',
        'proxy': proxy_url,
        'error': 'No se pudo conectar después de varios intentos'
    }

def test_proxies(proxy_list: List[str]) -> None:
    """
    Prueba una lista de proxies
    
    Args:
        proxy_list: Lista de URLs de proxies
    """
    if not proxy_list:
        print("❌ Lista de proxies vacía")
        return
    
    print(f"\n{'='*60}")
    print(f"🧪 PRUEBA DE PROXIES - {len(proxy_list)} proxies")
    print(f"{'='*60}\n")
    
    results = {
        'success': [],
        'failed': []
    }
    
    for i, proxy in enumerate(proxy_list, 1):
        proxy = proxy.strip()
        print(f"📍 Proxy {i}/{len(proxy_list)}: {proxy}")
        
        result = test_proxy(proxy)
        
        if result['status'] == 'success':
            results['success'].append(result)
        else:
            results['failed'].append(result)
        
        print()
    
    # Resumen
    print(f"{'='*60}")
    print(f"📊 RESUMEN")
    print(f"{'='*60}")
    print(f"✅ Exitosos: {len(results['success'])}/{len(proxy_list)}")
    print(f"❌ Fallidos: {len(results['failed'])}/{len(proxy_list)}")
    
    if results['success']:
        print(f"\n✅ Proxies que funcionan:")
        for result in results['success']:
            print(f"   • {result['proxy']}")
    
    if results['failed']:
        print(f"\n❌ Proxies que no funcionan:")
        for result in results['failed']:
            print(f"   • {result['proxy']} - {result.get('error', 'Desconocido')}")
    
    print()

def test_registraduria_api(proxy_url: Optional[str] = None) -> None:
    """
    Prueba acceso a la API de Registraduría con un proxy específico
    
    Args:
        proxy_url: URL del proxy (None para sin proxy)
    """
    print(f"\n{'='*60}")
    if proxy_url:
        print(f"🔍 Prueba API Registraduría CON proxy: {proxy_url}")
    else:
        print(f"🔍 Prueba API Registraduría SIN proxy")
    print(f"{'='*60}\n")
    
    proxies = None
    if proxy_url:
        proxies = {
            'http': proxy_url,
            'https': proxy_url
        }
    
    try:
        api_url = "https://eleccionescolombia.registraduria.gov.co/identificacion"
        print(f"Conectando a {api_url}...")
        
        response = requests.get(
            api_url,
            proxies=proxies,
            timeout=10,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
            }
        )
        
        print(f"✅ Status: {response.status_code}")
        print(f"   Contenido: {len(response.text)} bytes")
        print(f"   Headers: {dict(response.headers)}")
        
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {str(e)}")

if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    proxy_list = os.getenv('PROXY_LIST', '').split(',') if os.getenv('PROXY_LIST') else []
    proxy_enabled = os.getenv('PROXY_ENABLED', 'false').lower() == 'true'
    
    print(f"\n🔧 CONFIGURACIÓN ACTUAL")
    print(f"   PROXY_ENABLED: {proxy_enabled}")
    print(f"   PROXY_LIST: {len(proxy_list)} proxies")
    
    if not proxy_list or not proxy_enabled:
        print("\n⚠️  Proxies no configurados. Para habilitar:")
        print("   1. Edita tu .env")
        print("   2. Establece: PROXY_ENABLED=true")
        print("   3. Agrega proxies a: PROXY_LIST=http://proxy1:8080,http://proxy2:8080")
        print("\n📖 Ver PROXIES_GUIA.md para más información")
    else:
        print()
        test_proxies(proxy_list)
        
        if proxy_list:
            print("\n--- Prueba sin proxy (para comparación) ---")
            test_registraduria_api(None)
            
            print("\n--- Prueba CON primer proxy ---")
            test_registraduria_api(proxy_list[0].strip())
