# guardar_token_fly.ps1 - crea y guarda el token de Fly que usa el backup.
#
# POR QUE EXISTE (27/9/2026): el backup usaba tu sesion de `fly auth login`, y
# esa sesion VENCE. El 23/9 pidio login a mitad de la corrida; en la tarea de
# madrugada nadie contesta, y el backup estuvo un mes sin correr sin que nada
# avisara. Un token de la app no depende de la sesion.
#
# Que token es: un "deploy token" LIMITADO A ESTA APP (superapp-finanzas): no
# sirve para ninguna otra app ni para tu cuenta. Vence en un ano (no en 20,
# que es el default de fly): cuando falte poco, estado_backup.ps1 avisa.
#
# Donde queda: %LOCALAPPDATA%\SuperAppFinanzas\fly_token.txt
#   * FUERA del repo  -> no se puede commitear por error;
#   * FUERA de OneDrive -> no se sube a la nube;
#   * con permisos solo para tu usuario.
# El token NUNCA se muestra en pantalla: va directo de fly al archivo.
#
# Uso (una vez, con tu sesion de fly activa; si vencio, primero `fly auth login`):
#   powershell -ExecutionPolicy Bypass -File scripts\guardar_token_fly.ps1
# Revocarlo (si perdes la PC, por ejemplo):
#   fly tokens list -a superapp-finanzas    y despues    fly tokens revoke <id>

param(
    [string]$App = "superapp-finanzas",
    [string]$Vigencia = "8760h"      # 1 ano
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\_fly_comun.ps1"

New-Item -ItemType Directory -Force -Path $script:DirTokenFly | Out-Null

$nombre = "backup-pc-$($env:COMPUTERNAME)".ToLower()
Write-Host "Creando un token de la app $App (vigencia $Vigencia, nombre '$nombre') ..."
$token = (fly tokens create deploy -a $App -x $Vigencia -n $nombre | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or -not $token.StartsWith("FlyV1")) {
    Write-Error ("fly no devolvio un token. Si tu sesion vencio, corre primero " +
        "'fly auth login' y despues este script de nuevo.")
    exit 1
}

Set-Content -Path $script:ArchivoTokenFly -Value $token -Encoding ASCII -NoNewline
$vence = (Get-Date).AddHours([int]($Vigencia.TrimEnd("h"))).ToString("yyyy-MM-dd")
Set-Content -Path $script:ArchivoVenceTokenFly -Value $vence -Encoding ASCII -NoNewline
Remove-Variable token

# Permisos: solo tu usuario (sin herencia de la carpeta).
foreach ($f in @($script:ArchivoTokenFly, $script:ArchivoVenceTokenFly)) {
    icacls $f /inheritance:r /grant:r "$($env:USERNAME):(R,W)" | Out-Null
}

# Probarlo ya, sin la sesion: si el token no sirve, que se sepa hoy.
Remove-Item Env:\FLY_API_TOKEN -ErrorAction SilentlyContinue
if ((Use-TokenFly) -ne "token" -or $null -eq (Get-MaquinaFly -App $App)) {
    Write-Error "El token se guardo pero no pudo listar las maquinas de $App."
    exit 1
}

Write-Host ""
Write-Host "Listo: token guardado en $($script:ArchivoTokenFly)" -ForegroundColor Green
Write-Host "  vence: $vence (estado_backup.ps1 avisa 30 dias antes)"
Write-Host "  probado: lista las maquinas de $App sin usar tu sesion."
Write-Host ""
Write-Host "Siguiente paso: registrar la tarea diaria:" -ForegroundColor Cyan
Write-Host "  powershell -ExecutionPolicy Bypass -File scripts\programar_backup.ps1"
exit 0
