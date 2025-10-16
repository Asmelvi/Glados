#!/usr/bin/env python3
import argparse, os, sys, subprocess, datetime, json, re, pathlib
from agents.memory import log_event, add_goal

def nowstamp():
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

def guess_skill(prompt:str)->str:
    kw = prompt.lower()
    if any(k in kw for k in ["lÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â­mpialo", "limpialo", "texto limpio", "recÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â³rtalo", "recortalo", "trim to", "clean to"]):
        return "web_fetch_text_clean"
    return "web_titles_hard"

def extract_urls(prompt:str):
    return re.findall(r'(https?://[^\s,;]+)', prompt)

def write_chat(base:str, role:str, text:str):
    chat = os.path.join(base, "chat.txt")
    with open(chat, "a", encoding="utf-8") as f:
        ts = datetime.datetime.now().isoformat(timespec="seconds")
        f.write(f"[{ts}] {role.upper()}: {text}\n")

def main():
    ap = argparse.ArgumentParser(description="Supervisor no autÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â³nomo (requiere aprobaciÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â³n).")
    ap.add_argument("prompt", help="InstrucciÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â³n en lenguaje natural")
    ap.add_argument("-y","--approve", action="store_true", help="Ejecutar sin pedir confirmaciÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â³n (aprobado)")
    args = ap.parse_args()

    session_root = os.path.join("workspace", "sessions", nowstamp())
    os.makedirs(session_root, exist_ok=True)

    skill = guess_skill(args.prompt)
    urls  = extract_urls(args.prompt)

    plan = [
        f"Skill sugerida: {skill}",
        "Acciones:",
        "  1) Extraer URLs del prompt.",
        "  2) Preparar inputs efÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â­meros (order.ps1 ya lo hace).",
        "  3) Ejecutar en sandbox con lÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â­mites.",
        "  4) Guardar resultados y hacer resumen corto.",
    ]
    plan_txt = "\n".join(plan)

    log_event("plan", "Propuesta de plan generado por supervisor.")
    write_chat(session_root, "supervisor", "Propuesta de plan:\n" + plan_txt)
    print("=== PLAN PROPUESTO ===")
    print(plan_txt)
    if urls:
        print("URLs detectadas:", ", ".join(urls))
    else:
        print("URLs detectadas: (ninguna)")

    if not args.approve:
        msg = "Plan listo. Para ejecutar aÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â±ade --approve (o -y)."
        print(msg)
        write_chat(session_root, "supervisor", msg)
        return 0

    # Ejecutar usando el orquestador (aprovecha router e inputs)
    run_cmd = [
        "powershell", "-ExecutionPolicy", "Bypass",
        "-File", ".\\order.ps1", args.prompt, "-Yes"
    ]
    print("=== EJECUTANDO ===")
    write_chat(session_root, "supervisor", "Ejecutando plan con aprobaciÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â³nÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â¦")
    proc = subprocess.run(run_cmd, capture_output=True, text=True)
    out = proc.stdout.strip()
    err = proc.stderr.strip()

    # Guardar logs de ejecuciÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â³n en la sesiÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â³n
    with open(os.path.join(session_root, "orchestrator_stdout.txt"), "w", encoding="utf-8") as f:
        f.write(out)
    with open(os.path.join(session_root, "orchestrator_stderr.txt"), "w", encoding="utf-8") as f:
        f.write(err)

    # Localizar ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Âºltimo results.csv para ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã¢â‚¬Å“lo que aprendÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â­ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â
    orders = sorted(pathlib.Path("workspace/orders").glob("*"), key=os.path.getmtime, reverse=True)
    learned = "EjecuciÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â³n completada."
    if orders:
        last = orders[0]
        skills = sorted([p for p in last.glob("*") if p.is_dir()], key=os.path.getmtime, reverse=True)
        if skills:
            sdir = skills[0]
            csv  = sdir / "results.csv"
            if csv.exists():
                try:
                    # lee primeras dos filas para el ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã¢â‚¬Å“resumenÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â
                    with open(csv, "r", encoding="utf-8") as f:
                        lines = [next(f,"").strip() for _ in range(3)]
                    learned = "He generado un CSV con texto limpio. Muestra:\n" + "\n".join([l for l in lines if l])
                except Exception as ex:
                    learned = f"Resultados listos, pero no pude previsualizar CSV: {ex}"
            else:
                learned = "No encontrÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â© results.csv; revisa logs del orquestador."
    print("=== RESUMEN APRENDIZAJE (ES) ===")
    print(learned)
    log_event("learned", learned)
    write_chat(session_root, "worker", learned)
    return proc.returncode

if __name__ == "__main__":
    sys.exit(main())
    # 7c.0) Strip BOM si existe
    try {
      $bytes = [IO.File]::ReadAllBytes($resultsPath)
      if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
        [IO.File]::WriteAllBytes($resultsPath, $bytes[3..($bytes.Length-1)])
        Write-Host "BOM eliminado de results.csv"
      }
    } catch { Write-Warning $_ }

    $lines = Get-Content -LiteralPath $resultsPath
    if ($lines.Count -gt 0) {
      $first  = $lines[0].Trim()
      $cols   = $first -split '\s*,\s*'

      $newHdr = 'url,title,h1,meta_description,texto'
      $hdrOk  = $first -match '^\s*url,title,h1,meta_description,texto\s*$'
      $hdr2   = $first -match '^\s*url,\s*texto\s*$'
      $startsUrl = $first -match '^\s*url,'

      if ($hdrOk) {
        Write-Host "header OK en results.csv"
      }
      elseif ($hdr2 -or ($startsUrl -and $cols.Count -eq 2)) {
        # Actualizar cabecera 2 columnas -> 5 columnas
        $lines[0] = $newHdr
        $lines | Set-Content -LiteralPath $resultsPath -Encoding utf8
        Write-Host "header actualizado a 5 columnas en results.csv"
      }
      elseif (-not $startsUrl) {
        # No empieza por "url," -> preprender cabecera nueva
        $tmp = "$resultsPath.tmp"
        $newHdr | Out-File -LiteralPath $tmp -Encoding utf8
        $lines | Add-Content -LiteralPath $tmp -Encoding utf8
        Move-Item -LiteralPath $tmp -Destination $resultsPath -Force
        Write-Host "header añadido a results.csv"
      } else {
        Write-Host "header no reconocido, pero empieza por 'url,' → lo dejo como está"
      }
    } else {
      # Archivo vacío: escribir cabecera nueva
      'url,title,h1,meta_description,texto' | Set-Content -LiteralPath $resultsPath -Encoding utf8
      Write-Host "header escrito en results.csv (archivo vacío)"
    }
  }
} catch { Write-Warning $_ }
# 7c) Header CSV idempotente (no tocar si ya empieza por "url,")
try {
  if ($resultsPath -and (Test-Path $resultsPath)) {
    # lee primera línea sin BOM
    $raw = [System.IO.File]::ReadAllBytes($resultsPath)
    if ($raw.Length -ge 3 -and $raw[0] -eq 0xEF -and $raw[1] -eq 0xBB -and $raw[2] -eq 0xBF) {
      $raw = $raw[3..($raw.Length-1)]
    }
    $first = [System.Text.Encoding]::UTF8.GetString($raw)
    $first = $first.Split("`n")[0].Trim()

    if ($first -match '^\s*url\s*,') {
      Write-Host "header OK/detectado (empieza por 'url,'), no se toca"
    } elseif ($first -match '^\s*url\s*,\s*texto\s*$') {
      $tmp = "$resultsPath.tmp"
      $newHeader = 'url,title,h1,meta_description,texto'
      $newHeader | Out-File -LiteralPath $tmp -Encoding utf8
      Get-Content -LiteralPath $resultsPath -Encoding UTF8 | Select-Object -Skip 1 | Add-Content -LiteralPath $tmp -Encoding utf8
      Move-Item -LiteralPath $tmp -Destination $resultsPath -Force
      Write-Host "header legacy (2 col) -> actualizado a 5 columnas"
    } else {
      Write-Host "header no reconocido, no se toca: $first"
    }
  } else {
    Write-Host "(warn) results.csv no encontrado para revisar cabecera"
  }
} catch { Write-Warning $_ }
# 7d) Re-generar results.csv (5 columnas) para web_fetch_text_clean (autodetect task_dir)
try {
  if ($skill -eq 'web_fetch_text_clean' -and $workdir) {
    $cand1 = Join-Path $workdir 'urls.txt'
    $cand2 = Join-Path (Join-Path $workdir 'input') 'urls.txt'
    $taskDir = $null
    if (Test-Path $cand1)      { $taskDir = $workdir; Write-Host ("7d -> task_dir: {0}" -f $taskDir) -ForegroundColor DarkGray }
    elseif (Test-Path $cand2)  { $taskDir = (Join-Path $workdir 'input'); Write-Host ("7d -> task_dir: {0}" -f $taskDir) -ForegroundColor DarkGray }
    else {
      Write-Host ("(warn) 7d: no encontré urls.txt en {0} ni en {0}\input" -f $workdir) -ForegroundColor Yellow
      throw "urls_not_found"
    }

    $entryPy = Join-Path $PSScriptRoot 'winners\web_fetch_text_clean\main.py'
    if (-not (Test-Path $entryPy)) { Write-Host ("(warn) 7d: no existe {0}" -f $entryPy) -ForegroundColor Yellow; throw "entryPy_not_found" }

    $py = (Get-Command python -ErrorAction SilentlyContinue)?.Source
    if (-not $py) { $py = "python" }

    $resultsPath = Join-Path (Split-Path $taskDir -Parent) 'results.csv'   # -> ...\web_fetch_text_clean\results.csv

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName  = $py
    $psi.Arguments = "`"$entryPy`" `"$taskDir`""
    $psi.RedirectStandardOutput = $true
    $psi.UseShellExecute        = $false
    $psi.CreateNoWindow         = $true

    $p = [System.Diagnostics.Process]::Start($psi)
    $stdout = $p.StandardOutput.ReadToEnd()
    $p.WaitForExit()

    if ($p.ExitCode -ne 0 -or -not $stdout) {
      Write-Host ("(warn) 7d: main.py devolvió vacío o error (ExitCode={0})" -f $p.ExitCode) -ForegroundColor Yellow
      throw "runner_failed"
    }

    # Escribir sin BOM
    $bytes = [System.Text.UTF8Encoding]::new($false).GetBytes($stdout)
    [System.IO.File]::WriteAllBytes($resultsPath, $bytes)

    $first = Get-Content -LiteralPath $resultsPath -TotalCount 1 -Encoding UTF8
    if ($first -match '^url,title,h1,meta_description,texto
try {
  if ($skill -eq 'web_fetch_text_clean' -and $workdir -and (Test-Path $workdir)) {
    $urlsFile  = Join-Path $workdir 'urls.txt'
    if (Test-Path $urlsFile) {
      $entryPy = Join-Path $PSScriptRoot 'winners\web_fetch_text_clean\main.py'
      if (-not (Test-Path $entryPy)) { Write-Host ("(warn) 7d: no existe {0}" -f $entryPy) -ForegroundColor Yellow; throw "entryPy_not_found" }

      $py = (Get-Command python -ErrorAction SilentlyContinue)?.Source
      if (-not $py) { $py = "python" }

      # results.csv siempre en el directorio de skill (padre de input)
      $resultsPath = Join-Path (Split-Path $workdir -Parent) 'results.csv'

      # Ejecutar main.py con task-dir = $workdir y capturar STDOUT
      $psi = New-Object System.Diagnostics.ProcessStartInfo
      $psi.FileName  = $py
      $psi.Arguments = "`"$entryPy`" `"$workdir`""
      $psi.RedirectStandardOutput = $true
      $psi.UseShellExecute        = $false
      $psi.CreateNoWindow         = $true
      $p = [System.Diagnostics.Process]::Start($psi)
      $stdout = $p.StandardOutput.ReadToEnd()
      $p.WaitForExit()

      if ($p.ExitCode -ne 0 -or -not $stdout) {
        Write-Host ("(warn) 7d: main.py devolvió vacío o error (ExitCode={0})" -f $p.ExitCode) -ForegroundColor Yellow
      }

      # Guardar CSV en UTF-8 sin BOM
      $bytes = [System.Text.UTF8Encoding]::new($false).GetBytes($stdout)
      [System.IO.File]::WriteAllBytes($resultsPath, $bytes)

      # Verificar cabecera
      $first = Get-Content -LiteralPath $resultsPath -TotalCount 1 -Encoding UTF8
      if ($first -match '^url,title,h1,meta_description,texto$') {
        Write-Host ("7d -> results.csv (5 columnas) escrito en: {0}" -f $resultsPath) -ForegroundColor Green
      } else {
        Write-Host ("(warn) 7d: cabecera inesperada: {0}" -f $first) -ForegroundColor Yellow
      }
    } else {
      Write-Host "(warn) 7d: no existe urls.txt en workdir; no se regenera CSV" -ForegroundColor Yellow
    }
  }
} catch { Write-Warning $_ }
# 7b) Ensure preview.csv (no pisa results.csv real)
try {
  if ($workdir -and $stdoutPath) {
    $resultsPath = Join-Path $workdir 'preview.csv'
    New-Item -ItemType Directory -Force (Split-Path $resultsPath) | Out-Null
    if (Test-Path $stdoutPath) {
      Copy-Item $stdoutPath $resultsPath -Force
    } else {
      Set-Content -LiteralPath $resultsPath -Value "url,texto" -Encoding utf8
    }
    Write-Host ("7b -> preview.csv escrito en: {0}" -f $resultsPath)
  } else {
    Write-Host "(warn) 7b: workdir/stdoutPath no definidos"
  }
} catch { Write-Warning $_ }
) {
      Write-Host ("7d -> results.csv (5 columnas) escrito en: {0}" -f $resultsPath) -ForegroundColor Green
    } else {
      Write-Host ("(warn) 7d: cabecera inesperada: {0}" -f $first) -ForegroundColor Yellow
    }
  }
} catch { Write-Warning #!/usr/bin/env python3
import argparse, os, sys, subprocess, datetime, json, re, pathlib
from agents.memory import log_event, add_goal

def nowstamp():
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

def guess_skill(prompt:str)->str:
    kw = prompt.lower()
    if any(k in kw for k in ["lÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â­mpialo", "limpialo", "texto limpio", "recÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â³rtalo", "recortalo", "trim to", "clean to"]):
        return "web_fetch_text_clean"
    return "web_titles_hard"

def extract_urls(prompt:str):
    return re.findall(r'(https?://[^\s,;]+)', prompt)

def write_chat(base:str, role:str, text:str):
    chat = os.path.join(base, "chat.txt")
    with open(chat, "a", encoding="utf-8") as f:
        ts = datetime.datetime.now().isoformat(timespec="seconds")
        f.write(f"[{ts}] {role.upper()}: {text}\n")

def main():
    ap = argparse.ArgumentParser(description="Supervisor no autÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â³nomo (requiere aprobaciÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â³n).")
    ap.add_argument("prompt", help="InstrucciÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â³n en lenguaje natural")
    ap.add_argument("-y","--approve", action="store_true", help="Ejecutar sin pedir confirmaciÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â³n (aprobado)")
    args = ap.parse_args()

    session_root = os.path.join("workspace", "sessions", nowstamp())
    os.makedirs(session_root, exist_ok=True)

    skill = guess_skill(args.prompt)
    urls  = extract_urls(args.prompt)

    plan = [
        f"Skill sugerida: {skill}",
        "Acciones:",
        "  1) Extraer URLs del prompt.",
        "  2) Preparar inputs efÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â­meros (order.ps1 ya lo hace).",
        "  3) Ejecutar en sandbox con lÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â­mites.",
        "  4) Guardar resultados y hacer resumen corto.",
    ]
    plan_txt = "\n".join(plan)

    log_event("plan", "Propuesta de plan generado por supervisor.")
    write_chat(session_root, "supervisor", "Propuesta de plan:\n" + plan_txt)
    print("=== PLAN PROPUESTO ===")
    print(plan_txt)
    if urls:
        print("URLs detectadas:", ", ".join(urls))
    else:
        print("URLs detectadas: (ninguna)")

    if not args.approve:
        msg = "Plan listo. Para ejecutar aÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â±ade --approve (o -y)."
        print(msg)
        write_chat(session_root, "supervisor", msg)
        return 0

    # Ejecutar usando el orquestador (aprovecha router e inputs)
    run_cmd = [
        "powershell", "-ExecutionPolicy", "Bypass",
        "-File", ".\\order.ps1", args.prompt, "-Yes"
    ]
    print("=== EJECUTANDO ===")
    write_chat(session_root, "supervisor", "Ejecutando plan con aprobaciÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â³nÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â¦")
    proc = subprocess.run(run_cmd, capture_output=True, text=True)
    out = proc.stdout.strip()
    err = proc.stderr.strip()

    # Guardar logs de ejecuciÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â³n en la sesiÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â³n
    with open(os.path.join(session_root, "orchestrator_stdout.txt"), "w", encoding="utf-8") as f:
        f.write(out)
    with open(os.path.join(session_root, "orchestrator_stderr.txt"), "w", encoding="utf-8") as f:
        f.write(err)

    # Localizar ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Âºltimo results.csv para ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã¢â‚¬Å“lo que aprendÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â­ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â
    orders = sorted(pathlib.Path("workspace/orders").glob("*"), key=os.path.getmtime, reverse=True)
    learned = "EjecuciÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â³n completada."
    if orders:
        last = orders[0]
        skills = sorted([p for p in last.glob("*") if p.is_dir()], key=os.path.getmtime, reverse=True)
        if skills:
            sdir = skills[0]
            csv  = sdir / "results.csv"
            if csv.exists():
                try:
                    # lee primeras dos filas para el ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã¢â‚¬Å“resumenÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â
                    with open(csv, "r", encoding="utf-8") as f:
                        lines = [next(f,"").strip() for _ in range(3)]
                    learned = "He generado un CSV con texto limpio. Muestra:\n" + "\n".join([l for l in lines if l])
                except Exception as ex:
                    learned = f"Resultados listos, pero no pude previsualizar CSV: {ex}"
            else:
                learned = "No encontrÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â© results.csv; revisa logs del orquestador."
    print("=== RESUMEN APRENDIZAJE (ES) ===")
    print(learned)
    log_event("learned", learned)
    write_chat(session_root, "worker", learned)
    return proc.returncode

if __name__ == "__main__":
    sys.exit(main())
    # 7c.0) Strip BOM si existe
    try {
      $bytes = [IO.File]::ReadAllBytes($resultsPath)
      if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
        [IO.File]::WriteAllBytes($resultsPath, $bytes[3..($bytes.Length-1)])
        Write-Host "BOM eliminado de results.csv"
      }
    } catch { Write-Warning $_ }

    $lines = Get-Content -LiteralPath $resultsPath
    if ($lines.Count -gt 0) {
      $first  = $lines[0].Trim()
      $cols   = $first -split '\s*,\s*'

      $newHdr = 'url,title,h1,meta_description,texto'
      $hdrOk  = $first -match '^\s*url,title,h1,meta_description,texto\s*$'
      $hdr2   = $first -match '^\s*url,\s*texto\s*$'
      $startsUrl = $first -match '^\s*url,'

      if ($hdrOk) {
        Write-Host "header OK en results.csv"
      }
      elseif ($hdr2 -or ($startsUrl -and $cols.Count -eq 2)) {
        # Actualizar cabecera 2 columnas -> 5 columnas
        $lines[0] = $newHdr
        $lines | Set-Content -LiteralPath $resultsPath -Encoding utf8
        Write-Host "header actualizado a 5 columnas en results.csv"
      }
      elseif (-not $startsUrl) {
        # No empieza por "url," -> preprender cabecera nueva
        $tmp = "$resultsPath.tmp"
        $newHdr | Out-File -LiteralPath $tmp -Encoding utf8
        $lines | Add-Content -LiteralPath $tmp -Encoding utf8
        Move-Item -LiteralPath $tmp -Destination $resultsPath -Force
        Write-Host "header añadido a results.csv"
      } else {
        Write-Host "header no reconocido, pero empieza por 'url,' → lo dejo como está"
      }
    } else {
      # Archivo vacío: escribir cabecera nueva
      'url,title,h1,meta_description,texto' | Set-Content -LiteralPath $resultsPath -Encoding utf8
      Write-Host "header escrito en results.csv (archivo vacío)"
    }
  }
} catch { Write-Warning $_ }
# 7c) Header CSV idempotente (no tocar si ya empieza por "url,")
try {
  if ($resultsPath -and (Test-Path $resultsPath)) {
    # lee primera línea sin BOM
    $raw = [System.IO.File]::ReadAllBytes($resultsPath)
    if ($raw.Length -ge 3 -and $raw[0] -eq 0xEF -and $raw[1] -eq 0xBB -and $raw[2] -eq 0xBF) {
      $raw = $raw[3..($raw.Length-1)]
    }
    $first = [System.Text.Encoding]::UTF8.GetString($raw)
    $first = $first.Split("`n")[0].Trim()

    if ($first -match '^\s*url\s*,') {
      Write-Host "header OK/detectado (empieza por 'url,'), no se toca"
    } elseif ($first -match '^\s*url\s*,\s*texto\s*$') {
      $tmp = "$resultsPath.tmp"
      $newHeader = 'url,title,h1,meta_description,texto'
      $newHeader | Out-File -LiteralPath $tmp -Encoding utf8
      Get-Content -LiteralPath $resultsPath -Encoding UTF8 | Select-Object -Skip 1 | Add-Content -LiteralPath $tmp -Encoding utf8
      Move-Item -LiteralPath $tmp -Destination $resultsPath -Force
      Write-Host "header legacy (2 col) -> actualizado a 5 columnas"
    } else {
      Write-Host "header no reconocido, no se toca: $first"
    }
  } else {
    Write-Host "(warn) results.csv no encontrado para revisar cabecera"
  }
} catch { Write-Warning $_ }
# 7d) Re-generar results.csv (5 columnas) para web_fetch_text_clean (robusto)
try {
  if ($skill -eq 'web_fetch_text_clean' -and $workdir -and (Test-Path $workdir)) {
    $urlsFile  = Join-Path $workdir 'urls.txt'
    if (Test-Path $urlsFile) {
      $entryPy = Join-Path $PSScriptRoot 'winners\web_fetch_text_clean\main.py'
      if (-not (Test-Path $entryPy)) { Write-Host ("(warn) 7d: no existe {0}" -f $entryPy) -ForegroundColor Yellow; throw "entryPy_not_found" }

      $py = (Get-Command python -ErrorAction SilentlyContinue)?.Source
      if (-not $py) { $py = "python" }

      # results.csv siempre en el directorio de skill (padre de input)
      $resultsPath = Join-Path (Split-Path $workdir -Parent) 'results.csv'

      # Ejecutar main.py con task-dir = $workdir y capturar STDOUT
      $psi = New-Object System.Diagnostics.ProcessStartInfo
      $psi.FileName  = $py
      $psi.Arguments = "`"$entryPy`" `"$workdir`""
      $psi.RedirectStandardOutput = $true
      $psi.UseShellExecute        = $false
      $psi.CreateNoWindow         = $true
      $p = [System.Diagnostics.Process]::Start($psi)
      $stdout = $p.StandardOutput.ReadToEnd()
      $p.WaitForExit()

      if ($p.ExitCode -ne 0 -or -not $stdout) {
        Write-Host ("(warn) 7d: main.py devolvió vacío o error (ExitCode={0})" -f $p.ExitCode) -ForegroundColor Yellow
      }

      # Guardar CSV en UTF-8 sin BOM
      $bytes = [System.Text.UTF8Encoding]::new($false).GetBytes($stdout)
      [System.IO.File]::WriteAllBytes($resultsPath, $bytes)

      # Verificar cabecera
      $first = Get-Content -LiteralPath $resultsPath -TotalCount 1 -Encoding UTF8
      if ($first -match '^url,title,h1,meta_description,texto$') {
        Write-Host ("7d -> results.csv (5 columnas) escrito en: {0}" -f $resultsPath) -ForegroundColor Green
      } else {
        Write-Host ("(warn) 7d: cabecera inesperada: {0}" -f $first) -ForegroundColor Yellow
      }
    } else {
      Write-Host "(warn) 7d: no existe urls.txt en workdir; no se regenera CSV" -ForegroundColor Yellow
    }
  }
} catch { Write-Warning $_ }
# 7b) Ensure preview.csv (no pisa results.csv real)
try {
  if ($workdir -and $stdoutPath) {
    $resultsPath = Join-Path $workdir 'preview.csv'
    New-Item -ItemType Directory -Force (Split-Path $resultsPath) | Out-Null
    if (Test-Path $stdoutPath) {
      Copy-Item $stdoutPath $resultsPath -Force
    } else {
      Set-Content -LiteralPath $resultsPath -Value "url,texto" -Encoding utf8
    }
    Write-Host ("7b -> preview.csv escrito en: {0}" -f $resultsPath)
  } else {
    Write-Host "(warn) 7b: workdir/stdoutPath no definidos"
  }
} catch { Write-Warning $_ }
 }
try {
  if ($skill -eq 'web_fetch_text_clean' -and $workdir -and (Test-Path $workdir)) {
    $urlsFile  = Join-Path $workdir 'urls.txt'
    if (Test-Path $urlsFile) {
      $entryPy = Join-Path $PSScriptRoot 'winners\web_fetch_text_clean\main.py'
      if (-not (Test-Path $entryPy)) { Write-Host ("(warn) 7d: no existe {0}" -f $entryPy) -ForegroundColor Yellow; throw "entryPy_not_found" }

      $py = (Get-Command python -ErrorAction SilentlyContinue)?.Source
      if (-not $py) { $py = "python" }

      # results.csv siempre en el directorio de skill (padre de input)
      $resultsPath = Join-Path (Split-Path $workdir -Parent) 'results.csv'

      # Ejecutar main.py con task-dir = $workdir y capturar STDOUT
      $psi = New-Object System.Diagnostics.ProcessStartInfo
      $psi.FileName  = $py
      $psi.Arguments = "`"$entryPy`" `"$workdir`""
      $psi.RedirectStandardOutput = $true
      $psi.UseShellExecute        = $false
      $psi.CreateNoWindow         = $true
      $p = [System.Diagnostics.Process]::Start($psi)
      $stdout = $p.StandardOutput.ReadToEnd()
      $p.WaitForExit()

      if ($p.ExitCode -ne 0 -or -not $stdout) {
        Write-Host ("(warn) 7d: main.py devolvió vacío o error (ExitCode={0})" -f $p.ExitCode) -ForegroundColor Yellow
      }

      # Guardar CSV en UTF-8 sin BOM
      $bytes = [System.Text.UTF8Encoding]::new($false).GetBytes($stdout)
      [System.IO.File]::WriteAllBytes($resultsPath, $bytes)

      # Verificar cabecera
      $first = Get-Content -LiteralPath $resultsPath -TotalCount 1 -Encoding UTF8
      if ($first -match '^url,title,h1,meta_description,texto$') {
        Write-Host ("7d -> results.csv (5 columnas) escrito en: {0}" -f $resultsPath) -ForegroundColor Green
      } else {
        Write-Host ("(warn) 7d: cabecera inesperada: {0}" -f $first) -ForegroundColor Yellow
      }
    } else {
      Write-Host "(warn) 7d: no existe urls.txt en workdir; no se regenera CSV" -ForegroundColor Yellow
    }
  }
} catch { Write-Warning $_ }
# 7b) Ensure preview.csv (no pisa results.csv real)
try {
  if ($workdir -and $stdoutPath) {
    $resultsPath = Join-Path $workdir 'preview.csv'
    New-Item -ItemType Directory -Force (Split-Path $resultsPath) | Out-Null
    if (Test-Path $stdoutPath) {
      Copy-Item $stdoutPath $resultsPath -Force
    } else {
      Set-Content -LiteralPath $resultsPath -Value "url,texto" -Encoding utf8
    }
    Write-Host ("7b -> preview.csv escrito en: {0}" -f $resultsPath)
  } else {
    Write-Host "(warn) 7b: workdir/stdoutPath no definidos"
  }
} catch { Write-Warning $_ }
# 7d-final) Force 5-col results.csv
try {
  if ($skill -eq 'web_fetch_text_clean' -and $workdir) {
    $entryPy = Join-Path $PSScriptRoot 'winners\web_fetch_text_clean\main.py'
    $cand1   = Join-Path $workdir 'urls.txt'
    $cand2   = Join-Path (Join-Path $workdir 'input') 'urls.txt'
    $taskDir = $null
    if (Test-Path $cand1)     { $taskDir = $workdir }
    elseif (Test-Path $cand2) { $taskDir = (Join-Path $workdir 'input') }

    $resultsPath = Join-Path $workdir 'results.csv'
    $needs = $true
    if (Test-Path $resultsPath) {
      $first = Get-Content -LiteralPath $resultsPath -TotalCount 1 -Encoding UTF8
      if ($first -match '^url,title,h1,meta_description,texto$') { $needs = $false }
    }

    if ($needs -and $taskDir -and (Test-Path $entryPy)) {
      $py  = (Get-Command python -ErrorAction SilentlyContinue)?.Source; if (-not $py) { $py = 'python' }
      $out = & $py $entryPy $taskDir 2>$null
      if ($LASTEXITCODE -eq 0 -and $out) {
        [IO.File]::WriteAllText($resultsPath, $out, [Text.UTF8Encoding]::new($false))
        Write-Host ("7d-final -> results.csv (5 columnas) escrito: {0}" -f $resultsPath) -ForegroundColor Green
      } else {
        Write-Host ("(warn) 7d-final: main.py no devolvió salida (ExitCode={0})" -f $LASTEXITCODE) -ForegroundColor Yellow
      }
    } else {
      Write-Host "7d-final -> ya estaba con 5 columnas o faltan prerequisitos" -ForegroundColor DarkGray
    }
  }
} catch { Write-Warning $_ }
