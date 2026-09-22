# Start the ParaSail stack as detached background processes (survives the agent session).
$ErrorActionPreference = "Stop"
$root = "C:\Users\ignun\.zcode\workspace\default\parasail"

# 1. Ollama, with the bundled model store
$env:OLLAMA_MODELS = Join-Path $root "models"
Start-Process -FilePath "C:\Users\ignun\AppData\Local\Programs\Ollama\ollama.exe" `
    -ArgumentList "serve" -WindowStyle Hidden
Start-Sleep -Seconds 6

# 2. API + dashboard on the host (containers serve only db + qdrant)
Start-Process -FilePath "python" `
    -ArgumentList "-m", "uvicorn", "parasail.api:app", "--host", "0.0.0.0", "--port", "8000" `
    -WorkingDirectory $root -WindowStyle Hidden
Start-Sleep -Seconds 10

$ok = $true
try { $null = Invoke-RestMethod "http://localhost:11434/api/tags" -TimeoutSec 5 } catch { $ok = $false }
Write-Output ("ollama tags: " + $(if ($ok) { "ok" } else { "FAILED" }))
try {
    $h = Invoke-RestMethod "http://127.0.0.1:8000/health" -TimeoutSec 8
    Write-Output ("health: " + ($h | ConvertTo-Json -Compress))
    $s = Invoke-RestMethod "http://127.0.0.1:8000/assistant/status" -TimeoutSec 15
    Write-Output ("assistant: backend=" + $s.backend + " model=" + $s.model + " available=" + $s.available)
} catch {
    Write-Output ("api check failed: " + $_.Exception.Message)
}
