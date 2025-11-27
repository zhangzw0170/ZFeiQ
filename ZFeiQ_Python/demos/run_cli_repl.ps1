# PowerShell helper to run the CLI REPL demo
$root = (Resolve-Path "$PSScriptRoot\..").Path
$env:PYTHONPATH = $root
python (Join-Path $PSScriptRoot 'run_cli_repl.py')
