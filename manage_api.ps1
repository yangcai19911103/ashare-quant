#Requires -Version 5.1
<#
.SYNOPSIS
  Start / stop / restart / status for ashare-quant API (Windows PowerShell).

.DESCRIPTION
  Port: env ASHARE_API_PORT > config/settings.yaml api.port > 8000.
  Background start; stdout/stderr -> logs/api-service.*.log; PID -> .run/api-service.pid.

.EXAMPLE
  .\manage_api.ps1 status
  .\manage_api.ps1 start
  .\manage_api.ps1 stop
  .\manage_api.ps1 restart
  .\manage_api.ps1 start -Port 9000
#>
param(
    [Parameter(Position = 0)]
    [ValidateSet('start', 'stop', 'restart', 'status')]
    [string]$Command = 'status',

    [int]$Port = 0
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = $PSScriptRoot
$RunDir = Join-Path $ProjectRoot '.run'
$PidFile = Join-Path $RunDir 'api-service.pid'
$LogDir = Join-Path $ProjectRoot 'logs'

function Get-ConfiguredApiPort {
    if ($env:ASHARE_API_PORT) {
        $p = [int]$env:ASHARE_API_PORT
        if ($p -gt 0) { return $p }
    }
    $yaml = Join-Path $ProjectRoot 'config\settings.yaml'
    if (Test-Path $yaml) {
        $inApi = $false
        foreach ($line in Get-Content -LiteralPath $yaml -Encoding UTF8) {
            if ($line -match '^\s*api:\s*$') {
                $inApi = $true
                continue
            }
            if ($inApi -and $line -match '^\S' -and $line -notmatch '^\s') {
                break
            }
            if ($inApi -and $line -match '^\s+port:\s*(\d+)\s*$') {
                return [int]$Matches[1]
            }
        }
    }
    return 8000
}

function Get-TargetPort {
    if ($Port -gt 0) { return $Port }
    return Get-ConfiguredApiPort
}

function Get-ListenPids([int]$listenPort) {
    $pids = @()
    try {
        $conns = Get-NetTCPConnection -LocalPort $listenPort -State Listen -ErrorAction SilentlyContinue
        if ($conns) {
            foreach ($c in $conns) {
                if ($c.OwningProcess -and $pids -notcontains $c.OwningProcess) {
                    $pids += [int]$c.OwningProcess
                }
            }
        }
    }
    catch {
    }
    return $pids
}

function Stop-ApiByPort([int]$listenPort) {
    $procIds = Get-ListenPids $listenPort
    foreach ($procId in $procIds) {
        try {
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        }
        catch { }
    }
    return $procIds.Count
}

function Remove-PidFile {
    if (Test-Path -LiteralPath $PidFile) {
        Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
    }
}

function Stop-ApiByPidFile {
    if (-not (Test-Path -LiteralPath $PidFile)) { return 0 }
    $raw = (Get-Content -LiteralPath $PidFile -Raw -ErrorAction SilentlyContinue).Trim()
    if (-not $raw) { Remove-PidFile; return 0 }
    $procId = 0
    if (-not [int]::TryParse($raw, [ref]$procId)) { Remove-PidFile; return 0 }
    try {
        $p = Get-Process -Id $procId -ErrorAction SilentlyContinue
        if ($p) {
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
            return 1
        }
    }
    catch { }
    Remove-PidFile
    return 0
}

function Get-PythonExe {
    $venvPy = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
    if (Test-Path -LiteralPath $venvPy) { return $venvPy }
    return 'python'
}

function Invoke-ApiStatus([int]$listenPort) {
    Write-Host "Project root: $ProjectRoot"
    Write-Host "Listen port:  $listenPort (ASHARE_API_PORT / config/settings.yaml / default 8000)"
    $pids = Get-ListenPids $listenPort
    if ($pids.Count -eq 0) {
        Write-Host "Status: not listening on port $listenPort."
        if (Test-Path -LiteralPath $PidFile) {
            Write-Host "Note: PID file exists at $PidFile but port is not listening."
        }
        return
    }
    Write-Host "Status: running"
    foreach ($procId in $pids) {
        try {
            $p = Get-Process -Id $procId -ErrorAction Stop
            Write-Host "  PID $procId  $($p.ProcessName)  started: $($p.StartTime)"
        }
        catch {
            Write-Host "  PID $procId (process details unavailable)"
        }
    }
    $healthUrl = "http://127.0.0.1:$listenPort/api/docs"
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:$listenPort/api/openapi.json" -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
        Write-Host "HTTP check: $($r.StatusCode) (/api/openapi.json OK)"
    }
    catch {
        Write-Host "HTTP check: port listens but request failed: $($_.Exception.Message)"
        Write-Host "Try in browser: $healthUrl"
    }
}

function Start-ApiService([int]$listenPort) {
    $existing = Get-ListenPids $listenPort
    if ($existing.Count -gt 0) {
        $list = $existing -join ', '
        Write-Warning "Port $listenPort is in use (PID: $list). Run stop first or use -Port."
        Invoke-ApiStatus $listenPort
        return
    }
    if (-not (Test-Path -LiteralPath $RunDir)) {
        New-Item -ItemType Directory -Path $RunDir -Force | Out-Null
    }
    if (-not (Test-Path -LiteralPath $LogDir)) {
        New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
    }
    $py = Get-PythonExe
    $stdoutLog = Join-Path $LogDir 'api-service.stdout.log'
    $stderrLog = Join-Path $LogDir 'api-service.stderr.log'
    $env:ASHARE_API_PORT = "$listenPort"
    $proc = Start-Process -FilePath $py `
        -ArgumentList '-m', 'ashare_quant.api.main' `
        -WorkingDirectory $ProjectRoot `
        -WindowStyle Hidden `
        -PassThru `
        -RedirectStandardOutput $stdoutLog `
        -RedirectStandardError $stderrLog
    $procId = $proc.Id
    Set-Content -LiteralPath $PidFile -Value "$procId" -Encoding ascii -NoNewline
    Write-Host "Started API PID $procId on port $listenPort"
    Write-Host "Logs: $stdoutLog , $stderrLog"
    Start-Sleep -Seconds 2
    $pids = Get-ListenPids $listenPort
    if ($pids.Count -eq 0) {
        Write-Warning "Port still not listening; see stderr log."
    }
    else {
        Write-Host "Port is listening."
    }
}

function Stop-ApiService([int]$listenPort) {
    $nPid = Stop-ApiByPidFile
    $nPort = Stop-ApiByPort $listenPort
    Remove-PidFile
    if ($nPid -eq 0 -and $nPort -eq 0) {
        Write-Host "No API process found (no PID file match, no listener on port $listenPort)."
    }
    else {
        Write-Host "Stop issued (by PID file: $nPid, by port: $nPort)."
    }
}

$targetPort = Get-TargetPort

switch ($Command) {
    'status' { Invoke-ApiStatus $targetPort }
    'start' { Start-ApiService $targetPort }
    'stop' { Stop-ApiService $targetPort }
    'restart' {
        Stop-ApiService $targetPort
        Start-Sleep -Seconds 1
        Start-ApiService $targetPort
    }
}
