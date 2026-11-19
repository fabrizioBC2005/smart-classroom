<#
    Arranque unico de Smart Classroom en Windows.

    Backend (mosquitto, db, redis, api, worker, simulator) va en Docker.
    El frontend (web/) corre NATIVO con "npm run dev": en Docker Desktop con
    volumenes montados desde Windows el hot-reload de Next.js va lentisimo,
    asi que el servicio "web" del docker-compose queda en el profile
    "docker-web" y no se usa aqui a proposito.

    Uso:
      .\start.ps1               levanta backend + abre el frontend en otra ventana
      .\start.ps1 -NoFrontend   levanta solo el backend (tu corres npm run dev)
#>

param(
    [switch]$NoFrontend
)

$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $raiz

function Fallar([string]$mensaje) {
    Write-Host ""
    Write-Host "ERROR: $mensaje" -ForegroundColor Red
    exit 1
}

Write-Host "== Smart Classroom - arranque ==" -ForegroundColor Cyan

# 1) Docker Desktop tiene que estar corriendo. Si no lo esta, "docker compose up"
#    falla con un stack trace de conexion que no dice nada util, asi que lo
#    detectamos antes y avisamos en espanol.
docker info 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Fallar "Docker Desktop no esta corriendo (o no responde). Abrelo, espera a que el icono de la ballena este listo, y vuelve a ejecutar .\start.ps1"
}
Write-Host "-- Docker Desktop: OK"

# 2) Validar el docker-compose.yml antes de tocar nada, para no levantar
#    servicios a medias si alguien lo edito y quedo con un error de sintaxis.
docker compose config 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Fallar "docker-compose.yml tiene un error de configuracion. Corre 'docker compose config' para ver el detalle completo."
}

# 3) Levantar el backend con el profile "sim" (simulador de telemetria,
#    no hace falta hardware conectado).
Write-Host "-- Levantando backend (mosquitto, db, redis, api, worker, simulator)..."
docker compose --profile sim up -d --build
if ($LASTEXITCODE -ne 0) {
    Fallar "docker compose no pudo levantar los servicios. Revisa el detalle con: docker compose logs"
}

# 4) El servicio "web" vive en el profile "docker-web" y NO se usa: si alguien
#    lo encendio a mano en otra sesion ("docker compose --profile docker-web up"),
#    lo apagamos aca para que no choque con el "npm run dev" nativo en el puerto 3000.
docker compose stop web 2>$null | Out-Null

# 5) Esperar a que la API responda en /salud (hasta 60s).
Write-Host "-- Esperando a que la API responda en http://localhost:8001/salud ..."
$listo = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        $resp = Invoke-RestMethod -Uri "http://localhost:8001/salud" -TimeoutSec 2
        if ($resp.ok) { $listo = $true; break }
    } catch {
        Start-Sleep -Seconds 2
    }
}
if (-not $listo) {
    Fallar "La API no respondio en http://localhost:8001/salud tras 60s. Revisa: docker compose logs api"
}
Write-Host "-- API lista." -ForegroundColor Green

# 6) Sembrar datos de ejemplo solo si la base esta vacia. app/seed.py ya es
#    idempotente (revisa cada fila antes de insertar), pero igual evitamos
#    correrlo -y su print- en cada arranque cuando ya hay datos cargados.
try {
    $sedes = Invoke-RestMethod -Uri "http://localhost:8001/api/sedes" -TimeoutSec 5
} catch {
    Fallar "La API respondio /salud pero no /api/sedes. Revisa: docker compose logs api"
}
if (-not $sedes -or $sedes.Count -eq 0) {
    Write-Host "-- Base de datos vacia, cargando datos de ejemplo (seed)..."
    docker compose exec api python -m app.seed
    if ($LASTEXITCODE -ne 0) {
        Fallar "El seed fallo. Revisa: docker compose logs api"
    }
} else {
    Write-Host "-- Base de datos ya tiene datos ($($sedes.Count) sede[s]), se omite el seed."
}

# 7) Frontend nativo. web/.env.local ya trae NEXT_PUBLIC_API_URL y
#    NEXT_PUBLIC_WS_URL apuntando al puerto 8001, asi que "npm run dev" no
#    necesita variables exportadas a mano en la sesion de PowerShell.
if (-not $NoFrontend) {
    if (-not (Test-Path "$raiz\web\node_modules")) {
        Write-Host "-- Instalando dependencias del frontend (primera vez, puede tardar)..."
        Push-Location "$raiz\web"
        npm install
        $npmExit = $LASTEXITCODE
        Pop-Location
        if ($npmExit -ne 0) {
            Fallar "npm install fallo en web/. Revisa el mensaje de npm de arriba."
        }
    }
    Write-Host "-- Abriendo el frontend en una nueva ventana de PowerShell (npm run dev)..."
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$raiz\web'; npm run dev"
} else {
    Write-Host "-- Frontend omitido (-NoFrontend)."
}

Write-Host ""
Write-Host "== Smart Classroom listo ==" -ForegroundColor Cyan
Write-Host "  Dashboard    : http://localhost:3000   (nativo, fuera de Docker)"
Write-Host "  API + docs   : http://localhost:8001/docs"
Write-Host "  Salud API    : http://localhost:8001/salud"
Write-Host "  MQTT         : localhost:1883"
Write-Host "  Redis        : localhost:6380"
Write-Host ""
if ($NoFrontend) {
    Write-Host "Para el frontend, abre otra terminal y ejecuta:"
    Write-Host "  cd web"
    Write-Host "  npm run dev"
    Write-Host ""
}
Write-Host "Otros comandos utiles:"
Write-Host "  docker compose logs -f api worker simulator   # ver que decide el worker"
Write-Host "  docker compose ps                             # estado de los contenedores"
Write-Host "  docker compose down                           # apagar backend"
Write-Host "  docker compose down -v                         # apagar y borrar la base de datos"
