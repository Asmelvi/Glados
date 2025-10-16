param(
  [Parameter(Mandatory=$true, Position=0)][string]$Prompt,
  [switch]$Yes
)

function Write-NoBom([string]$path, [string[]]$lines) {
  $enc = New-Object System.Text.UTF8Encoding($false)
  [IO.File]::WriteAllLines($path, $lines, $enc)
}

# 1) Detectar skill con router
$routerJson = python .\tools\router.py $Prompt
try { $skill = (ConvertFrom-Json $routerJson).skill } catch { $skill = "web_titles_hard" }

# 2) Resolver entry/task_dir/expected/net desde registry (fallback si falta)
$entry   = ""
$taskDir = ""
$expected = ""
$net = $false
try {
  $reg = Get-Content -Raw ".\examples\tools_registry.json" | ConvertFrom-Json
  $s = $reg.skills | Where-Object { $_.id -eq $skill } | Select-Object -First 1
  if ($s) { $entry=$s.entry; $taskDir=$s.task_dir; $expected=$s.expected; $net=[bool]$s.net }
} catch {}

if (-not $entry -or -not $taskDir) {
  switch ($skill) {
    'web_titles_hard' { $entry='winners/web_titles_hard/main.py'; $taskDir='tasks/web_titles_hard/input'; $net=$true }
    'web_links'       { $entry='winners/web_links/main.py';       $taskDir='tasks/web_links/input';       $net=$true }
    'web_meta'        { $entry='winners/web_meta/main.py';        $taskDir='tasks/web_meta/input';        $net=$true }
    'web_h1_texts'    { $entry='winners/web_h1_texts/main.py';    $taskDir='tasks/web_h1_texts/input';    $net=$true }
    'web_fetch_text'  { $entry='winners/web_fetch_text/main.py';  $taskDir='tasks/web_fetch_text/input';  $net=$true }
    'web_fetch_text_clean' { $entry='winners/web_fetch_text_clean/main.py'; $taskDir='tasks/web_fetch_text/input'; $net=$true }
    'forge_skill'     { $entry='winners/forge_skill/main.py';     $taskDir='workspace/forge/INPUT';       $net=$false }
    'custom_quiero_una_nueva_skill_que_convie' { $entry='winners/custom_quiero_una_nueva_skill_que_convie/main.py'; $taskDir='tasks/custom_quiero_una_nueva_skill_que_convie/input'; $net=$false }
    default           { $entry='winners/web_titles_hard/main.py'; $taskDir='tasks/web_titles_hard/input'; $net=$true }
  }
}

# 3) Workdir por orden
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$workdir = "workspace/orders/$ts/$skill"
New-Item -ItemType Directory -Force $workdir     | Out-Null
New-Item -ItemType Directory -Force (Join-Path $workdir 'logs') | Out-Null

# 4) Inputs efÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â­meros segÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Âºn skill

# 4.1) Skills con URLs -> crear urls.txt si hay URLs en el prompt
$needsUrls = $skill -in @('web_status_codes','web_titles_hard','web_h1_texts','web_links','web_meta','web_fetch_text','web_fetch_text_clean')
if ($needsUrls) {
  $matches = [regex]::Matches($Prompt, '(https?://[^\s,;]+)') | ForEach-Object { $_.Groups[1].Value.TrimEnd('.,)') }
  $urls = @($matches | Where-Object { $_ } | Select-Object -Unique)
  if ($urls.Count -gt 0) {
    $epIn = Join-Path $workdir 'input'
    New-Item -ItemType Directory -Force $epIn | Out-Null
    $urls | Set-Content -Encoding utf8 (Join-Path $epIn 'urls.txt')
    $taskDir = $epIn
  }
}

# 4.1.b) Si la skill es web_fetch_text_clean y el prompt contiene "a N" (chars/caracteres), crear limit.txt
if ($skill -eq 'web_fetch_text_clean') {
  $m = [regex]::Match($Prompt, '(?i)\ba\s+(\d{2,6})\s*(?:chars?|caracteres?)\b')
  if ($m.Success -and $taskDir) {
    $limitPath = Join-Path $taskDir 'limit.txt'
    [IO.File]::WriteAllText($limitPath, $m.Groups[1].Value, (New-Object System.Text.UTF8Encoding($false)))
  }
}

# 4.2) Tu skill html->texto: crear input/html.txt con el HTML del prompt
if ($skill -eq 'custom_quiero_una_nueva_skill_que_convie') {
  $epIn = Join-Path $workdir 'input'
  New-Item -ItemType Directory -Force $epIn | Out-Null
  $html = $Prompt
  if ($Prompt -match ':\s*(.*)$') { $html = $Matches[1] }
  [IO.File]::WriteAllText((Join-Path $epIn 'html.txt'), $html, (New-Object System.Text.UTF8Encoding($false)))
  $taskDir = $epIn
}

# 5) Ejecutar
$stdoutPath = Join-Path $workdir 'logs\stdout.txt'
$stderrPath = Join-Path $workdir 'logs\stderr.txt'

if ($skill -eq 'forge_skill') {
  # Ejecutar en host
  New-Item -ItemType Directory -Force (Split-Path $stdoutPath) | Out-Null
  & python $entry $taskDir 1> $stdoutPath 2> $stderrPath
  $rc = $LASTEXITCODE
  Write-Host ("{0}" -f (@{ rc=$rc; stdout=$stdoutPath; stderr=$stderrPath } | ConvertTo-Json -Compress))
} else {
  # Ejecutar dentro de safe_runner (crea logs en $workdir\logs)
  $args = @(".\tools\safe_runner.py","--entry",$entry,"--task-dir",$taskDir,"--timeout","60","--workdir",$workdir)
  if ($net) { $args += "--allow-net" }
  $json = & python @args
  Write-Host $json
}

# 6) Mostrar resultado
Write-Host ""
Write-Host ("--- RESULTADO ({0}) ---" -f $skill)
if (Test-Path $stdoutPath) { Get-Content -Raw $stdoutPath }
Write-Host ""
Write-Host "Logs:"
Write-Host ("  stdout: {0}" -f $stdoutPath)
Write-Host ("  stderr: {0}" -f $stderrPath)
# 7) Guardar copia CSV bonita
try {
  \ = Join-Path \ 'results.csv'
  if (Test-Path \) { Copy-Item \ \ -Force }
} catch {}
# 7b) Ensure results.csv (robusto y verboso)
try {
  if ($workdir -and $stdoutPath) {
    $resultsPath = Join-Path $workdir 'results.csv'
    New-Item -ItemType Directory -Force (Split-Path $resultsPath) | Out-Null
    if (Test-Path $stdoutPath) {
      Copy-Item $stdoutPath $resultsPath -Force
      Write-Host ("results.csv: {0}" -f $resultsPath)
    } else {
      Write-Host ("(warn) stdout no encontrado: {0}" -f $stdoutPath)
    }
  } else {
    Write-Host "(warn) workdir/stdoutPath no definidos cuando se intentó guardar results.csv"
  }
} catch { Write-Warning $_ }
# 7c) Add CSV header if missing (idempotente)
try {
  if ($resultsPath -and (Test-Path $resultsPath)) {
    $header = 'url,texto'
    $first  = Get-Content -LiteralPath $resultsPath -TotalCount 1
    if ($first -ne $header) {
      $tmp = "$resultsPath.tmp"
      $header | Out-File -LiteralPath $tmp -Encoding utf8
      Get-Content -LiteralPath $resultsPath | Add-Content -LiteralPath $tmp -Encoding utf8
      Move-Item -LiteralPath $tmp -Destination $resultsPath -Force
      Write-Host "header añadido a results.csv"
    } else {
      Write-Host "header ya presente en results.csv"
    }
  }
} catch { Write-Warning $_ }
