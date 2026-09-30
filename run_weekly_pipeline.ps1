param(
  [ValidateSet('dry-run','prepare','stage','refresh-base','publish','verify-pages','notion-plan','complete')]
  [string]$Action = 'dry-run',
  [string]$Context,
  [string]$Run,
  [string]$Snapshot,
  [string]$TargetWeek,
  [ValidateSet('codex','work')][string]$Backend = 'codex',
  [switch]$Dry,
  [switch]$AcceptRevision
)
$ErrorActionPreference = 'Stop'
$taskPython = Get-Command python -ErrorAction SilentlyContinue
if ($taskPython) { $taskExecutable = $taskPython.Source }
else { $taskExecutable = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' }
if (-not (Test-Path -LiteralPath $taskExecutable)) { throw 'Python 3.12+ required; bundled Codex Python not found.' }
$taskArguments = @('-B', (Join-Path $PSScriptRoot 'generator\weekly_orchestrator.py'), $Action, '--backend', $Backend)
if ($Context) { $taskArguments += @('--context', $Context) }
if ($Run) { $taskArguments += @('--run', $Run) }
if ($Snapshot) { $taskArguments += @('--snapshot', $Snapshot) }
if ($TargetWeek) { $taskArguments += @('--target-week', $TargetWeek) }
if ($Dry) { $taskArguments += '--dry' }
if ($AcceptRevision) { $taskArguments += '--accept-revision' }
Push-Location -LiteralPath $PSScriptRoot
try {
  & $taskExecutable @taskArguments
  $taskExit = $LASTEXITCODE
} finally { Pop-Location }
exit $taskExit
