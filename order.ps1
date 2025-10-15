param(
  [Parameter(Mandatory=$true, Position=0)]
  [string]$Prompt,
  [switch]$Yes
)

function Write-NoBom($path, [string[]]$lines) {
  $enc = New-Object System.Text.UTF8Encoding($false)
  $sw = [System.IO.StreamWriter]::new($path, $false, $enc)
  foreach($l in $lines){ $sw.WriteLine($l) }
  $sw.Close()
}

# 1) Detecta skill con el router
$routerJson = python .\tools\router.py $Prompt
try { $skill = (ConvertFrom-Json $routerJson).skill } catch { $skill = "web_titles_hard" }

# 2) Mapea skill -> entry / default task_dir
switch ($skill) {
  'web_status_codes' { $entry='winners/web_status_codes/main.py'; $taskDir='tasks/web_status_codes/input' }
  'web_h1_texts'    { $entry='winners/web_h1_texts/main.py';    $taskDir='tasks/web_h1_texts/input' }
  'web_json_api'    { $entry='winners/web_json_api/main.py';    $taskDir='tasks/web_json_api/input' }
  'web_meta'        { \C:\Users\Avalon\Desktop\vscode\Glados\winners\web_titles_hard\main.py='winners/web_meta/main.py';       \C:\Users\Avalon\Desktop\vscode\Glados\tasks\web_titles_hard\input='tasks/web_meta/input' }
  'web_links'      { $entry='winners/web_links/main.py'; $taskDir='tasks/web_links/input' }
  default           { $entry='winners/web_titles_hard/main.py'; $taskDir='tasks/web_titles_hard/input' }
}

# 3) Workdir por orden
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$workdir = "workspace/orders/$ts/$skill"
New-Item -ItemType Directory -Force $workdir | Out-Null

# 4) Extraer URLs del prompt y crear input efÃƒÂ­mero si aplica
$needsUrls = $skill -in @('web_status_codes','web_titles_hard','web_h1_texts','web_meta','web_links')
if ($needsUrls) {
  $matches = [regex]::Matches($Prompt, '(https?://[^\s,;]+)') | ForEach-Object { $_.Groups[1].Value.TrimEnd('.,)') }
  $urls = @($matches | Where-Object { $_ } | Select-Object -Unique)
  if ($urls.Count -gt 0) {
    $epIn = Join-Path $workdir "input"
    New-Item -ItemType Directory -Force $epIn | Out-Null
    Write-NoBom (Join-Path $epIn "urls.txt") $urls
    $taskDir = $epIn
  }
}

# 5) Ejecutar en docker via safe_runner
$cmd = @(
  "python", ".\tools\safe_runner.py",
  "--entry", $entry,
  "--task-dir", $taskDir,
  "--allow-net",
  "--timeout", "60",
  "--cpus", "2",
  "--mem-mb", "512",
  "--workdir", $workdir
)
$proc = Start-Process -FilePath $cmd[0] -ArgumentList $cmd[1..($cmd.Length-1)] -NoNewWindow -PassThru -Wait
$rc = $proc.ExitCode

# 6) Mostrar resultado
$stdoutPath = Join-Path $workdir 'logs\stdout.txt'
$stderrPath = Join-Path $workdir 'logs\stderr.txt'
if ($rc -eq 0) {
  Write-Host ("{0}" -f (@{ rc=$rc; stdout=$stdoutPath; stderr=$stderrPath } | ConvertTo-Json -Compress))
  if ($skill -eq 'web_links') {
  Write-Host "
--- RESULTADO (web_links) ---"
  Get-Content -Raw $stdoutPath | Write-Output
  Write-Host "

Logs:
  stdout: $stdoutPath
  stderr: $stderrPath"
  return
}Write-Host "`n--- RESULTADO ($skill) ---"
  Get-Content -Raw $stdoutPath
  Write-Host "`n`nLogs:`n  stdout: $(Resolve-Path $stdoutPath)`n  stderr: $(Resolve-Path $stderrPath)"
} else {
  Write-Output (@{ rc=$rc; stdout=$stdoutPath; stderr=$stderrPath } | ConvertTo-Json -Compress)
  Write-Error "EjecuciÃƒÂ³n retornÃƒÂ³ cÃƒÂ³digo $rc"
}