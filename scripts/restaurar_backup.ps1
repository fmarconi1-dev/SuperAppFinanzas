# restaurar_backup.ps1 - sube una copia local y la deja como DB de produccion.
#
# ESTE SCRIPT PISA LA BASE DE PRODUCCION. Por eso no hace nada sin -Confirmar.
#
# El orden importa y no es obvio: SQLite en modo WAL guarda escrituras en
# archivos aparte (`-wal` y `-shm`). Si se reemplaza el .db con la app viva o
# sin borrar esos dos, SQLite mezcla la base restaurada con el diario de la
# vieja y el resultado es una base corrupta. Por eso: parar -> subir ->
# borrar wal/shm -> arrancar.
#
# Uso:
#   powershell -ExecutionPolicy Bypass -File scripts\restaurar_backup.ps1 `
#       -Archivo backups-remotos\superapp-20260730-2200.db -Confirmar

param(
    [Parameter(Mandatory = $true)][string]$Archivo,
    [string]$App = "superapp-finanzas",
    [switch]$Confirmar
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $Archivo)) {
    Write-Error "No existe el archivo: $Archivo"
    exit 1
}

# 1. Verificar el backup ANTES de tocar produccion. Restaurar una copia rota
#    encima de una base viva convierte un problema en un desastre.
$py = @'
import sqlite3, sys
c = sqlite3.connect(sys.argv[1])
ok = c.execute("PRAGMA integrity_check").fetchone()[0]
def cuenta(tabla):
    try:
        return c.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]
    except sqlite3.Error:
        return -1
print(f"{ok}|{cuenta('transacciones')}|{cuenta('cartera_movimientos')}|{cuenta('usuarios')}")
'@
$partes = (python -c $py $Archivo).Split("|")
if ($partes[0] -ne "ok") {
    Write-Error "El backup NO pasa integrity_check ($($partes[0])). No se restaura nada."
    exit 1
}
if ([int]$partes[3] -lt 1) {
    Write-Error "El backup no tiene usuarios: no es una base valida de esta app."
    exit 1
}

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

# 2. Copia de resguardo de lo que hay AHORA en produccion. Si el restore sale
#    mal, esto es lo unico que permite volver atras.
$previo = Join-Path (Split-Path $Archivo -Parent) `
    ("pre-restore-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".db")
Write-Host "Guardando el estado actual de produccion en $previo ..."
fly ssh sftp get /app/data/finanzas.db $previo -a $App
if (-not (Test-Path $previo)) {
    Write-Error "No se pudo respaldar la base actual. Abortando el restore."
    exit 1
}

# 3. Parar la app para que nadie escriba durante el reemplazo.
Write-Host "Parando $App ..."
fly scale count 0 -a $App -y
Start-Sleep -Seconds 10

# 4. Subir la copia y limpiar el diario WAL de la base vieja.
#    `fly ssh sftp` no tiene subcomando `put`: hay que abrir su shell y
#    mandarle el comando por la entrada estandar. En PowerShell eso es un
#    pipe (el `<<<` de bash NO existe acá).
Write-Host "Subiendo la copia ..."
"put $Archivo /app/data/finanzas.db" | fly ssh sftp shell -a $App
fly ssh console -a $App -C "rm -f /app/data/finanzas.db-wal /app/data/finanzas.db-shm"

# 5. Levantar y verificar.
Write-Host "Levantando $App ..."
fly scale count 1 -a $App -y
Start-Sleep -Seconds 20
try {
    Invoke-WebRequest -Uri "https://$App.fly.dev/_stcore/health" `
        -TimeoutSec 90 -UseBasicParsing | Out-Null
    Write-Host "OK: la app responde. Entra y verifica los numeros a mano." -ForegroundColor Green
} catch {
    Write-Warning "La app todavia no responde. Revisa: fly status -a $App"
}

Write-Host ""
Write-Host "Si algo quedo mal, la base previa al restore esta en: $previo"
exit 0
