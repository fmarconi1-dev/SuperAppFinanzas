# estado_backup.ps1 - responde "¿mi backup viene funcionando?" en un comando.
#
# POR QUE EXISTE: la tarea programada corre de madrugada y nadie mira la
# consola. Un backup que dejo de andar y no avisa es PEOR que no tener backup,
# porque da una sensacion de proteccion que no existe. Este script mira la
# bitacora y las copias reales, y te dice si estas cubierto o no.
#
# Uso:  powershell -ExecutionPolicy Bypass -File scripts\estado_backup.ps1

param(
    [string]$Destino = "$PSScriptRoot\..\backups-remotos",
    [int]$MaxDiasSinBackup = 2,
    [string]$Tarea = "Backup Superapp Finanzas"
)

. "$PSScriptRoot\_fly_comun.ps1"

# Las dos piezas de las que depende que el backup corra SOLO. El 27/9/2026 se
# descubrio que las dos faltaban: la tarea no existia en la PC (aunque ESTADO.md
# decia que estaba confirmada) y la sesion de fly vencida la habria hecho
# fallar igual. Por eso se miran siempre, no solo las copias.
Write-Host ""
Write-Host "=== Lo que hace que corra solo ===" -ForegroundColor Cyan
$problemas = 0
$t = Get-ScheduledTask -TaskName $Tarea -ErrorAction SilentlyContinue
if ($t) {
    $i = $t | Get-ScheduledTaskInfo
    $res = if ($i.LastTaskResult -eq 0) { "ok" } else { "codigo $($i.LastTaskResult)" }
    Write-Host ("  Tarea programada : existe ({0}) - ultima corrida {1:dd/MM HH:mm} ({2}) - proxima {3:dd/MM HH:mm}" -f `
        $t.State, $i.LastRunTime, $res, $i.NextRunTime)
} else {
    Write-Host "  Tarea programada : NO EXISTE. Registrala: scripts\programar_backup.ps1" -ForegroundColor Red
    $problemas++
}
if (Test-Path $script:ArchivoTokenFly) {
    $vence = if (Test-Path $script:ArchivoVenceTokenFly) {
        [datetime]::ParseExact((Get-Content $script:ArchivoVenceTokenFly -Raw).Trim(), "yyyy-MM-dd", $null)
    } else { $null }
    if ($vence -and $vence -lt (Get-Date).AddDays(30)) {
        Write-Host ("  Token de Fly     : VENCE EL {0:dd/MM/yyyy}. Renovalo: scripts\guardar_token_fly.ps1" -f $vence) -ForegroundColor Red
        $problemas++
    } elseif ($vence) {
        Write-Host ("  Token de Fly     : guardado, vence el {0:dd/MM/yyyy}" -f $vence)
    } else {
        Write-Host "  Token de Fly     : guardado (sin fecha de vencimiento registrada)"
    }
} else {
    Write-Host "  Token de Fly     : NO HAY. Sin token, la tarea falla cuando vence tu sesion: scripts\guardar_token_fly.ps1" -ForegroundColor Red
    $problemas++
}
$avisoEscritorio = Join-Path ([Environment]::GetFolderPath("Desktop")) "BACKUP SUPERAPP - FALLO.txt"
if (Test-Path $avisoEscritorio) {
    Write-Host "  Hay un aviso de fallo en el Escritorio: la ultima corrida fallo." -ForegroundColor Red
}

if (-not (Test-Path $Destino)) {
    Write-Host "NO HAY NINGUNA COPIA todavia. Corre backup_remoto.ps1." -ForegroundColor Red
    exit 1
}

$copias = Get-ChildItem $Destino -Filter "superapp-*.db" -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending

Write-Host ""
Write-Host "=== Copias externas en $((Resolve-Path $Destino).Path) ===" -ForegroundColor Cyan
if (-not $copias) {
    Write-Host "NO HAY NINGUNA COPIA. Estas sin respaldo externo." -ForegroundColor Red
    exit 1
}

$copias | Select-Object -First 5 | ForEach-Object {
    $dias = [math]::Round(((Get-Date) - $_.LastWriteTime).TotalDays, 1)
    $mb = [math]::Round($_.Length / 1MB, 2)
    Write-Host ("  {0,-32} {1,8} MB   hace {2} dia(s)" -f $_.Name, $mb, $dias)
}
Write-Host ("  ({0} copias en total)" -f $copias.Count)

# La bitacora: distingue "no corrio" de "corrio y fallo". No es lo mismo.
$log = Join-Path $Destino "backup.log"
if (Test-Path $log) {
    Write-Host ""
    Write-Host "=== Ultimas corridas ===" -ForegroundColor Cyan
    Get-Content $log -Tail 8 | ForEach-Object {
        $color = if ($_ -match "`tERROR`t") { "Red" } else { "Gray" }
        Write-Host "  $_" -ForegroundColor $color
    }
    $fallos = (Get-Content $log -Tail 5 | Where-Object { $_ -match "`tERROR`t" }).Count
    if ($fallos -ge 3) {
        Write-Host ""
        Write-Host "ATENCION: $fallos de las ultimas 5 corridas fallaron." -ForegroundColor Red
    }
} else {
    Write-Host ""
    Write-Host "Sin bitacora todavia (backup.log aparece en la primera corrida)." -ForegroundColor Yellow
}

# El veredicto. Lo que importa no es que existan copias: es que la mas nueva
# sea RECIENTE. Diez copias de hace tres meses no te protegen de nada.
$ultima = $copias[0]
$diasUltima = ((Get-Date) - $ultima.LastWriteTime).TotalDays
Write-Host ""
if ($diasUltima -le $MaxDiasSinBackup) {
    Write-Host ("OK: la copia mas nueva es de hace {0:N1} dia(s)." -f $diasUltima) -ForegroundColor Green
    if ($problemas -gt 0) {
        Write-Host "  ...pero hay $problemas problema(s) arriba: hoy estas cubierto, manana puede que no." -ForegroundColor Yellow
        exit 1
    }
    exit 0
}
Write-Host ("ATENCION: hace {0:N1} dias que no se hace una copia buena." -f $diasUltima) -ForegroundColor Red
Write-Host "  Revisa la tarea programada:  Get-ScheduledTask -TaskName 'Backup Superapp Finanzas'"
Write-Host "  O corre una a mano:          powershell -File scripts\backup_remoto.ps1"
exit 1
