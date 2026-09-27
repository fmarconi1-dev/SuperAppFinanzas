# _fly_comun.ps1 - helpers compartidos por los scripts que hablan con Fly.
#
# Se cargan con dot-sourcing:  . "$PSScriptRoot\_fly_comun.ps1"
#
# POR QUE EXISTE: el fly.toml usa `auto_stop_machines = true` con
# `min_machines_running = 0`, asi que la maquina se duerme sola. Todo lo que
# use `fly ssh` necesita una maquina ENCENDIDA, y una maquina dormida corta con
# "app has no started VMs". Como la tarea programada corre de madrugada, el
# camino de la maquina apagada es el camino NORMAL, no la excepcion.
#
# Tener la logica en un solo lugar evita que un script la tenga y el otro no
# (fue exactamente lo que paso: el de backup se arreglo y el de restore quedo
# sin arreglar).
#
# AUTENTICACION (27/9/2026). La sesion de `fly auth login` VENCE. El 23/9 el
# backup pidio login a mitad de la corrida; en una tarea de madrugada nadie
# contesta, y el backup dejo de existir un mes sin que nada avisara. Por eso:
#   * si hay un TOKEN de la app guardado (lo crea `guardar_token_fly.ps1`,
#     fuera del repo y fuera de OneDrive), se usa ese: no depende de la sesion;
#   * toda consulta de prueba corre con la entrada desde NUL, asi flyctl NO
#     puede quedarse esperando un login que nadie va a hacer: falla al toque.

#: Donde vive el token. Fuera del repo (no se commitea) y fuera de OneDrive
#: (no se sincroniza a la nube).
$script:DirTokenFly = Join-Path $env:LOCALAPPDATA "SuperAppFinanzas"
$script:ArchivoTokenFly = Join-Path $script:DirTokenFly "fly_token.txt"
$script:ArchivoVenceTokenFly = Join-Path $script:DirTokenFly "fly_token_vence.txt"

function Use-TokenFly {
    <#
    .SYNOPSIS
        Carga el token de la app en FLY_API_TOKEN si existe. Devuelve con que
        se va a autenticar: "token" o "sesion".
    #>
    if ($env:FLY_API_TOKEN) { return "token" }
    if (Test-Path $script:ArchivoTokenFly) {
        $t = (Get-Content $script:ArchivoTokenFly -Raw).Trim()
        if ($t) {
            $env:FLY_API_TOKEN = $t
            return "token"
        }
    }
    return "sesion"
}

function Get-MaquinaFly {
    param([Parameter(Mandatory = $true)][string]$App)
    # `< NUL`: sin una consola que conteste, flyctl no puede pedir login y
    # quedarse colgado hasta el timeout de la tarea; falla y lo sabemos.
    $crudo = cmd /c "fly machines list --json -a $App < NUL 2>NUL"
    if ($LASTEXITCODE -ne 0 -or -not $crudo) { return $null }
    try {
        return ($crudo | Out-String) | ConvertFrom-Json
    } catch {
        return $null
    }
}

function Start-AppFly {
    <#
    .SYNOPSIS
        Deja la app encendida y respondiendo. Devuelve el id de la maquina.
    .DESCRIPTION
        Enciende la maquina si hace falta y espera al health check (el
        grace_period del arranque son 30 s). Corta con error si la app no
        tiene ninguna maquina: ahi el problema es otro (falta desplegar) y
        conviene decirlo en vez de dejar un error de sftp criptico.
    #>
    param(
        [Parameter(Mandatory = $true)][string]$App,
        [int]$IntentosHealth = 12
    )

    $maquinas = Get-MaquinaFly -App $App
    if ($null -eq $maquinas) {
        # Antes: "sigo igual" -> y el sftp moria despues con un error que no
        # decia nada ("no started VMs"). Si no podemos ni listar, lo mas
        # probable es la autenticacion: se dice eso, y se corta aca.
        $causa = if ($env:FLY_API_TOKEN) {
            "el token guardado no sirve (vencido o revocado)"
        } else {
            "la sesion de fly vencio y no hay token guardado"
        }
        Write-Error ("No se pudo hablar con Fly para $App. Lo mas probable: $causa " +
            "(o no hay internet). Solucion: " +
            "powershell -ExecutionPolicy Bypass -File scripts\guardar_token_fly.ps1")
        exit 1
    }
    if ($maquinas.Count -eq 0) {
        Write-Error "La app $App no tiene ninguna maquina. Falta desplegar: fly deploy -a $App"
        exit 1
    }

    $encendida = $maquinas | Where-Object { $_.state -eq "started" } | Select-Object -First 1
    $maquina = if ($encendida) { $encendida } else { $maquinas[0] }

    if (-not $encendida) {
        Write-Host "La maquina esta $($maquina.state); la enciendo ..."
        fly machine start $maquina.id -a $App | Out-Null
    }

    foreach ($i in 1..$IntentosHealth) {
        try {
            $r = Invoke-WebRequest -Uri "https://$App.fly.dev/_stcore/health" `
                -TimeoutSec 10 -UseBasicParsing
            if ($r.StatusCode -eq 200) {
                Start-Sleep -Seconds 3
                return $maquina.id
            }
        } catch {
            Start-Sleep -Seconds 5
        }
    }
    Write-Warning "La app no respondio el health; sigo igual."
    return $maquina.id
}
