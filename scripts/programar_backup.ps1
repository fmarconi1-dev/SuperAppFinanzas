# programar_backup.ps1 - registra la tarea diaria de backup en Windows.
#
# POR QUE EXISTE: la guia del RUNBOOK eran seis clicks en el Programador de
# tareas, y ese paso quedo pendiente semanas. Un comando se corre; una guia de
# clicks se posterga. Ademas, hecho a mano es facil dejar mal una opcion (la
# tipica: la tarea no corre si la notebook esta a bateria, y nunca te enteras).
#
# Uso (hay que abrir PowerShell COMO ADMINISTRADOR):
#   powershell -ExecutionPolicy Bypass -File scripts\programar_backup.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\programar_backup.ps1 -Hora 09:30
#   powershell -ExecutionPolicy Bypass -File scripts\programar_backup.ps1 -Quitar

param(
    [string]$Nombre = "Backup Superapp Finanzas",
    [string]$Hora = "09:00",
    [switch]$Quitar
)

$ErrorActionPreference = "Stop"

$existente = Get-ScheduledTask -TaskName $Nombre -ErrorAction SilentlyContinue

if ($Quitar) {
    if ($existente) {
        Unregister-ScheduledTask -TaskName $Nombre -Confirm:$false
        Write-Host "Tarea '$Nombre' eliminada." -ForegroundColor Green
    } else {
        Write-Host "No existe ninguna tarea llamada '$Nombre'."
    }
    exit 0
}

$script = (Resolve-Path "$PSScriptRoot\backup_remoto.ps1").Path

$accion = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$script`""

$disparador = New-ScheduledTaskTrigger -Daily -At $Hora

# Las opciones que importan, y por que:
#   StartWhenAvailable  -> si la PC estaba apagada a esa hora, corre al prender.
#                          Sin esto el dia que no la usaste no hay backup.
#   DontStopIfGoingOnBatteries / AllowStartIfOnBatteries
#                       -> en una notebook, el default es NO correr con
#                          bateria. Es el motivo mas comun de una tarea que
#                          "esta programada" y nunca corre.
#   ExecutionTimeLimit  -> si se cuelga, que no quede un proceso vivo para
#                          siempre bloqueando las corridas siguientes.
$opciones = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopIfGoingOnBatteries `
    -AllowStartIfOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 20)

if ($existente) {
    Write-Host "Ya existia una tarea '$Nombre': la reemplazo."
    Unregister-ScheduledTask -TaskName $Nombre -Confirm:$false
}

Register-ScheduledTask -TaskName $Nombre -Action $accion -Trigger $disparador `
    -Settings $opciones `
    -Description "Copia externa diaria de la DB de superapp-finanzas (Fly.io). Ver docs/RUNBOOK.md." | Out-Null

Write-Host ""
Write-Host "Tarea '$Nombre' registrada: todos los dias a las $Hora." -ForegroundColor Green
Write-Host "  script : $script"
Write-Host ""
Write-Host "Probala AHORA sin esperar a manana:" -ForegroundColor Cyan
Write-Host "  Start-ScheduledTask -TaskName '$Nombre'"
Write-Host "Y despues revisa como viene:"
Write-Host "  powershell -ExecutionPolicy Bypass -File scripts\estado_backup.ps1"
exit 0
