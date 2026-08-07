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

function Get-MaquinaFly {
    param([Parameter(Mandatory = $true)][string]$App)
    try {
        return fly machines list --json -a $App 2>$null | ConvertFrom-Json
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
        Write-Warning "No se pudo listar las maquinas de $App; sigo igual."
        return $null
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
