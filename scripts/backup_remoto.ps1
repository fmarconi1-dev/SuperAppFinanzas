# backup_remoto.ps1 - copia la DB de produccion (Fly.io) a esta PC.
#
# POR QUE EXISTE: la DB y sus backups automaticos viven en UN SOLO volumen de
# Fly (`/app/data`). Si se pierde el volumen, se pierden los dos juntos. Este
# script crea la copia EXTERNA, que es la unica que sobrevive a eso.
#
# Lo irreemplazable son las transacciones de Finanzas Personales: la cartera se
# puede reconstruir del Excel, pero los gastos no existen en ningun otro lado.
#
# Requisitos: flyctl instalado y logueado (fly auth login) + Python en el PATH.
# Uso manual:  powershell -ExecutionPolicy Bypass -File scripts\backup_remoto.ps1
# Programarlo: ver docs\RUNBOOK.md (Programador de tareas de Windows, diario).

param(
    [string]$App = "superapp-finanzas",
    [string]$Destino = "$PSScriptRoot\..\backups-remotos",
    [int]$RetencionDias = 90
)

$ErrorActionPreference = "Stop"
$fecha = Get-Date -Format "yyyyMMdd-HHmmss"
New-Item -ItemType Directory -Force -Path $Destino | Out-Null
$archivo = Join-Path $Destino "superapp-$fecha.db"

# 1. Asegurar que haya una maquina ENCENDIDA. `fly ssh sftp` la necesita.
#
#    POR QUE NO ALCANZA UN REQUEST HTTP (fallo real, 4/8/2026): el fly.toml usa
#    `auto_stop_machines = true` con `min_machines_running = 0`, asi que la
#    maquina se duerme sola. Despertarla con un GET depende del proxy de Fly y
#    de que el health check responda dentro del timeout; si no, el sftp corta
#    con "app has no started VMs" y el backup no se hace.
#
#    Y esto NO es un caso raro: la tarea programada corre de madrugada, cuando
#    la maquina SIEMPRE esta dormida. O sea que el camino de la maquina apagada
#    es el camino normal de este script, no la excepcion.
$maquinas = $null
try {
    $maquinas = fly machines list --json -a $App 2>$null | ConvertFrom-Json
} catch {
    Write-Warning "No se pudo listar las maquinas; sigo con el despertador HTTP."
}

if ($maquinas -and $maquinas.Count -eq 0) {
    Write-Error "La app $App no tiene ninguna maquina. Falta desplegar: fly deploy -a $App"
    exit 1
}

if ($maquinas) {
    $encendida = $maquinas | Where-Object { $_.state -eq "started" } | Select-Object -First 1
    if (-not $encendida) {
        $dormida = $maquinas[0]
        Write-Host "La maquina esta $($dormida.state); la enciendo..."
        fly machine start $dormida.id -a $App | Out-Null
    }
}

# Esperar a que el health responda. El grace_period del arranque es de 30 s.
$listo = $false
foreach ($i in 1..12) {
    try {
        $r = Invoke-WebRequest -Uri "https://$App.fly.dev/_stcore/health" `
            -TimeoutSec 10 -UseBasicParsing
        if ($r.StatusCode -eq 200) { $listo = $true; break }
    } catch {
        Start-Sleep -Seconds 5
    }
}
if (-not $listo) {
    Write-Warning "La app no respondio el health; intento el sftp igual."
} else {
    Start-Sleep -Seconds 3
}

# 2. Descargar la DB.
fly ssh sftp get /app/data/finanzas.db $archivo -a $App
if (-not (Test-Path $archivo) -or (Get-Item $archivo).Length -lt 1024) {
    Write-Error "FALLO: el archivo no se descargo o esta vacio."
    exit 1
}

# 3. Verificar. Un backup corrupto o vacio no es un backup, y el momento de
#    descubrirlo NO es el dia que lo necesites.
#    La verificacion vive en scripts\verificar_backup.py y no en un `python -c`
#    aca adentro: PowerShell se come las comillas al pasar un script multilinea
#    como argumento y Python moria con SyntaxError (paso de verdad, 4/8/2026).
$salida = python "$PSScriptRoot\verificar_backup.py" $archivo
$ok = ($LASTEXITCODE -eq 0)
$partes = $salida.Split("|")
$integridad = $partes[0]
$transacciones = [int]$partes[1]
$movimientos = [int]$partes[2]

if (-not $ok) {
    Write-Error "El backup descargado NO sirve (integridad=$integridad, transacciones=$transacciones). Abortando."
    exit 1
}
if ($movimientos -lt 1) {
    Write-Warning "El backup no tiene movimientos de cartera. Si todavia no importaste, es normal."
}
Write-Host "OK: $archivo"
Write-Host "    integridad=$integridad - transacciones=$transacciones - movimientos de cartera=$movimientos"

# 4. Purga local: las copias viejas se borran, pero SIEMPRE quedan las 3 mas
#    recientes aunque sean todas viejas (si el script dejo de correr hace
#    meses, borrar la ultima copia buena seria el peor resultado posible).
$copias = Get-ChildItem $Destino -Filter "superapp-*.db" | Sort-Object LastWriteTime -Descending
$aSalvo = $copias | Select-Object -First 3
$copias |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-$RetencionDias) } |
    Where-Object { $aSalvo -notcontains $_ } |
    Remove-Item -Force

exit 0
