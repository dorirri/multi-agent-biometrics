param([string]$LogDirectory = 'results/local_server')
$ErrorActionPreference = 'Stop'
$projectDirectory = Split-Path -Parent $PSScriptRoot
$serverPath = Join-Path $projectDirectory '.runtime/llama-b12032/llama-server.exe'
$modelPath = Join-Path $projectDirectory 'models/qwen2.5-1.5b-instruct-q4_k_m.gguf'
if (!(Test-Path -LiteralPath $serverPath) -or !(Test-Path -LiteralPath $modelPath)) {
    throw 'Run node scripts/bootstrap_local.cjs and expand the CPU runtime archive first.'
}
$logsPath = Join-Path $projectDirectory $LogDirectory
New-Item -ItemType Directory -Path $logsPath -Force | Out-Null
$serverProcess = Start-Process -FilePath $serverPath -ArgumentList @('-m',$modelPath,'--host','127.0.0.1','--port','8080','--alias','qwen2.5-1.5b-instruct-q4_k_m','-c','8192','-np','1','-t','6','-tb','6','-ngl','0','--seed','8217') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logsPath 'stdout.log') -RedirectStandardError (Join-Path $logsPath 'stderr.log')
$serverProcess.Id | Set-Content (Join-Path $logsPath 'pid.txt')
Write-Output "Local CPU LLM server PID: $($serverProcess.Id), endpoint http://127.0.0.1:8080/v1"
