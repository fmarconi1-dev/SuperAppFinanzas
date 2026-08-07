# restaurar_backup.ps1 - sube una copia local y la deja como DB de produccion.
#
# ESTE SCRIPT PISA LA BASE DE PRODUCCION. Por eso no hace nada sin -Confirmar.
#
# ============================================================================
# REESCRITO EL 4/8/2026. La version anterior NO PODIA FUNCIONAR.
# ============================================================================
# Hacia `fly scale count 0` para parar la app y despues `fly ssh sftp shell`
# para subir el archivo. **No se puede entrar por SSH a una maquina que no
# existe**: `scale count 0` no la para, la DESTRUYE. El restore se colgaba ahi,
# con la app caida y la base sin reemplazar -- el peor estado posible.
#
# Ademas `scale count 1` tiene que CREAR una maquina nueva, y eso puede fallar
# (`cpu_overcommit_exceeded` le paso a Franco el 4/8/2026 en un deploy comun).
# O sea que el camino de vuelta tampoco estaba garantizado.
#
# Nunca se detecto porque el ensayo end-to-end quedo siempre pendiente. Es la
# demostracion de la frase del RUNBOOK: un backup que nunca se restauro no es
# un backup, es un archivo.
#
# ORDEN NUEVO, y cada paso esta donde esta por un motivo:
#   1. verificar la copia          -> restaurar una copia rota encima de una
#                                     base viva convierte un problema en un
#                                     desastre
#   2. encender la maquina         -> todo lo que sigue usa SSH
#   3. bajar la base actual        -> es lo unico que permite volver atras
#   4. subir la copia a un TEMPORAL-> subir directo sobre la base viva la deja
#                                     inconsistente si algo corta a mitad
#   5. swap + borrar wal/shm       -> en UN solo comando, pegado al reinicio
#   6. reiniciar la maquina        -> la app reabre la base nueva
#
# ⚠️ SOBRE EL PASO 5. SQLite en modo WAL guarda las escrituras recientes en
# `-wal`/`-shm`. Si se reemplaza el .db sin borrarlos, al arrancar SQLite mezcla
# la base restaurada con el diario de la vieja y el resultado es una base
# corrupta. Y como no se puede entrar por SSH a una maquina apagada, el swap se
# hace con la app viva: queda una ventana de ~1 segundo entre el swap y el
# reinicio en la que una escritura tuya volveria a crear el `-wal`.
# **No uses la app mientras corre el restore.** Es una app de un solo usuario;
# la ventana es teorica si vos no estas tocandola.
#
# Uso:
#   powershell -ExecutionPolicy Bypass -File scripts\restaurar_backup.ps1 `
#       -Archivo backups-remotos\superapp-20260730-2200.db          # simulacro
#   powershell -ExecutionPolicy Bypass -File scripts\restaurar_backup.ps1 `
#       -Archivo backups-remotos\superapp-20260730-2200.db -Confirmar

param(
    [Parameter(Mandatory = $true)][string]$Archivo,
    [string]$App = "superapp-finanzas",
    [switch]$Confirmar
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\_fly_comun.ps1"

if (-not (Test-Path $Archivo)) {
    Write-Error "No existe el archivo: $Archivo"
    exit 1
}
$Archivo = (Resolve-Path $Archivo).Path

# 1. Verificar la copia ANTES de tocar produccion.
#    (La verificacion vive en un archivo aparte: ver el comentario de
#    backup_remoto.ps1 sobre PowerShell comiendose las comillas.)
$salida = python "$PSScriptRoot\verificar_backup.py" $Archivo
if ($LASTEXITCODE -ne 0) {
    Write-Error "La copia NO sirve ($salida). No se restaura nada."
    exit 1
}
$partes = $salida.Split("|")

Write-Host ""
Write-Host "Vas a REEMPLAZAR la base de $App con:" -ForegroundColor Yellow
Write-Host "  archivo      : $Archivo"
Write-Host "  fecha        : $((Get-Item $Archivo).LastWriteTime)"
Write-Host "  integridad   : $($partes[0])"
Write-Host "  usuarios     : $($partes[3])"
Write-Host "  transacciones: $($partes[1])"
Write-Host "  movimientos  : $($partes[2])"
Write-Host ""

if (-not $Confirmar) {
    Write-Host "Simulacro: no se toco nada. Volve a correrlo con -Confirmar." -ForegroundColor Cyan
    exit 0
}

Write-Host "NO uses la app hasta que termine este script." -ForegroundColor Yellow

# 2. La maquina tiene que estar encendida: todo lo que sigue va por SSH.
$maquina = Start-AppFly -App $App

# 3. Copia de resguardo de lo que hay AHORA. Si el restore sale mal, esto es
#    lo unico que permite volver atras.
$previo = Join-Path (Split-Path $Archivo -Parent) `
    ("pre-restore-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".db")
Write-Host "Guardando el estado actual de produccion en $previo ..."
fly ssh sftp get /app/data/finanzas.db $previo -a $App
if (-not (Test-Path $previo) -or (Get-Item $previo).Length -lt 1024) {
    Write-Error "No se pudo respaldar la base actual. Abortando el restore."
    exit 1
}

# 4. Subir la copia a un TEMPORAL, no sobre la base viva.
#    `fly ssh sftp` no tiene subcomando `put`: hay que abrir su shell y
#    mandarle el comando por la entrada estandar. En PowerShell eso es un pipe
#    (el `<<<` de bash NO existe aca).
Write-Host "Subiendo la copia ..."
"put $Archivo /app/data/restore-pendiente.db" | fly ssh sftp shell -a $App

$tam = fly ssh console -a $App -C "stat -c %s /app/data/restore-pendiente.db"
if (-not $tam -or [int]($tam -replace '\D', '') -lt 1024) {
    Write-Error "La copia no llego entera al servidor. No se toco la base."
    exit 1
}

# 5. Swap + limpieza del diario, en UN solo comando y pegado al reinicio.
Write-Host "Reemplazando la base ..."
fly ssh console -a $App -C "sh -c 'mv -f /app/data/restore-pendiente.db /app/data/finanzas.db && rm -f /app/data/finanzas.db-wal /app/data/finanzas.db-shm'"

# 6. Reiniciar la maquina (NO `scale count`: eso la destruye y puede no volver).
Write-Host "Reiniciando $App ..."
if ($maquina) {
    fly machine restart $maquina -a $App | Out-Null
} else {
    fly apps restart $App | Out-Null
}

Start-Sleep -Seconds 15
$ok = $false
foreach ($i in 1..12) {
    try {
        $r = Invoke-WebRequest -Uri "https://$App.fly.dev/_stcore/health" `
            -TimeoutSec 10 -UseBasicParsing
        if ($r.StatusCode -eq 200) { $ok = $true; break }
    } catch {
        Start-Sleep -Seconds 5
    }
}

Write-Host ""
if ($ok) {
    Write-Host "OK: la app responde. Entra y verifica los numeros a mano." -ForegroundColor Green
} else {
    Write-Warning "La app no responde todavia. Revisa: fly status -a $App"
}
Write-Host "Si algo quedo mal, la base previa al restore esta en: $previo"
Write-Host "  powershell -ExecutionPolicy Bypass -File scripts\restaurar_backup.ps1 -Archivo $previo -Confirmar"
exit 0
