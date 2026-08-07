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
. "$PSScriptRoot\_fly_comun.ps1"

$fecha = Get-Date -Format "yyyyMMdd-HHmmss"
New-Item -ItemType Directory -Force -Path $Destino | Out-Null
$archivo = Join-Path $Destino "superapp-$fecha.db"

# Bitacora de corridas. POR QUE: cuando esto lo dispare el Programador de
# tareas a las 3 de la manana, nadie va a estar mirando la consola. Un backup
# que dejo de funcionar y no avisa es PEOR que no tener backup, porque da una
# sensacion de proteccion que no existe. El log deja el rastro y
# `estado_backup.ps1` lo resume en un comando.
$log = Join-Path $Destino "backup.log"
function Escribir-Log {
    param([string]$Estado, [string]$Detalle)
    $linea = "{0}`t{1}`t{2}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Estado, $Detalle
    Add-Content -Path $log -Value $linea -Encoding UTF8
}

trap {
    Escribir-Log "ERROR" $_.Exception.Message
    break
}

# 1. Asegurar que haya una maquina ENCENDIDA. `fly ssh sftp` la necesita.
#    La logica vive en `_fly_comun.ps1` para que este script y el de restore
#    no puedan divergir (paso: se arreglo aca y el restore quedo sin arreglar).
Start-AppFly -App $App | Out-Null

# 2. Descargar la DB.
fly ssh sftp get /app/data/finanzas.db $archivo -a $App
if (-not (Test-Path $archivo) -or (Get-Item $archivo).Length -lt 1024) {
    Escribir-Log "ERROR" "el archivo no se descargo o esta vacio"
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
    Escribir-Log "ERROR" "copia invalida: integridad=$integridad transacciones=$transacciones"
    Write-Error "El backup descargado NO sirve (integridad=$integridad, transacciones=$transacciones). Abortando."
    exit 1
}
if ($movimientos -lt 1) {
    Write-Warning "El backup no tiene movimientos de cartera. Si todavia no importaste, es normal."
}
Escribir-Log "OK" "$([System.IO.Path]::GetFileName($archivo))  transacciones=$transacciones  movimientos=$movimientos"
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
