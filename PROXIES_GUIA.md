# Evitar Bloqueos de IP - Guía de Proxies

## 🚨 Problema
En el servidor, la API de la Registraduría bloquea tu IP después de varias consultas, mostrando "Respuesta vacía de la API". Esto es una protección contra scraping.

## ✅ Solución: Usar Proxies

### 1. Configuración Rápida

En tu archivo `.env`, agrega:

```bash
# Activar proxies
PROXY_ENABLED=true

# Lista de proxies (separados por comas)
PROXY_LIST=http://proxy1.com:8080,http://proxy2.com:8080,http://proxy3.com:3128
```

### 2. Proveedores Recomendados

#### **Opción 1: Bright Data (Premium - Recomendado)**
- URL: https://brightdata.com
- Precio: Desde $10.50/GB
- Ventaja: Proxies residenciales (IPs reales de usuarios)
- Configuración:
  ```
  PROXY_LIST=http://usuario:contraseña@proxy.provider.com:puerto
  ```

#### **Opción 2: Oxylabs (Premium)**
- URL: https://oxylabs.io
- Precio: Desde $15/mes
- Ventaja: Muy rápidos y confiables
- Configuración:
  ```
  PROXY_LIST=http://usuario:contraseña@pr.oxylabs.io:7777
  ```

#### **Opción 3: Smartproxy (Económico)**
- URL: https://smartproxy.com
- Precio: Desde $5.50/mes
- Ventaja: Buena relación precio/calidad
- Configuración:
  ```
  PROXY_LIST=http://usuario-pais:contraseña@gate.smartproxy.com:7000
  ```

#### **Opción 4: Proxies Gratuitos (NO recomendados)**
- Servicios: free-proxy-list.net, proxylists.com
- Problema: Lentos, inestables y frecuentemente bloqueados
- Solo para testing

### 3. Cómo Funciona

El sistema de proxies rota entre la lista proporcionada:
- Consulta 1: Usa proxy 1
- Consulta 2: Usa proxy 2
- Consulta 3: Usa proxy 3
- Consulta 4: Vuelve al proxy 1 (rotación)

Esto hace parecer que las consultas vienen de diferentes IPs, evitando bloqueos.

### 4. Verificación

Para verificar que los proxies funcionan:

```bash
# En Linux/Mac
curl -x http://proxy:puerto https://registry.gov.co

# En PowerShell Windows
$proxy = New-Object System.Net.WebProxy("http://proxy:puerto")
$client = New-Object System.Net.WebClient
$client.Proxy = $proxy
$client.DownloadString("https://registry.gov.co")
```

### 5. Logs para Depuración

Cuando uses proxies, verás en los logs:
```
🌐 Usando proxy: http://proxy1.com:8080 (1/3)
🌐 Usando proxy: http://proxy2.com:8080 (2/3)
🌐 Usando proxy: http://proxy3.com:3128 (3/3)
```

Si ves errores, el proxy podría estar:
- Caído
- Bloqueado
- Con credenciales incorrectas
- Sin límite de conexiones disponible

### 6. Mejores Prácticas

1. **Usar Proxies Residenciales**: Son IPs reales de usuarios normales, mucho más difficiles de bloquear
2. **Rotación Automática**: EL sistema ya rota proxies automáticamente
3. **Múltiples Proxies**: Agrega al menos 3-5 proxies para mayor redundancia
4. **Monitoreo**: Revisa logs para detectar proxies fallidos
5. **Limpieza**: Desactiva proxies si no los necesitas (PROXY_ENABLED=false)

### 7. Ejemplo Completo de .env

```bash
APIKEY_2CAPTCHA=abc123def456

# Proxies para evitar bloqueos
PROXY_ENABLED=true
PROXY_LIST=http://usuario:pass@proxy1.smartproxy.com:7000,http://usuario:pass@proxy2.smartproxy.com:7000,http://usuario:pass@proxy3.smartproxy.com:7000
```

### 8. Desactivar Proxies

Si por algún motivo necesitas desactivar los proxies temporalmente:

```bash
PROXY_ENABLED=false
# o simplemente comenta la línea PROXY_LIST
```

## 🔍 Solución de Problemas

| Error | Causa | Solución |
|-------|-------|----------|
| `ProxyError` | Proxy caído o incorrecto | Verifica IP:puerto y credenciales |
| `Connection timeout` | Proxy muy lento | Usa proxies diferentes |
| `407 Proxy-Authenticate` | Credenciales incorrectas | Revisa usuario:contraseña |
| `Respuesta vacía` persiste | IP del proxy también bloqueada | Cambia a proxies más frescos |

## 📊 Monitoreo

Para monitorear qué proxies funcionan mejor, agrega logging:

```python
print(f"Proxy: {proxy} - Tiempo: {response_time}ms - Status: {response.status_code}")
```

---

**Nota**: Los proxies Premium (residenciales) son más caros pero mucho más efectivos para evitar bloqueos de sitios como Registraduría.
