# Validate the two ParaSail decks open in real PowerPoint without a repair prompt.
# Exit 0 = both opened cleanly; 1 = at least one failed.
$ErrorActionPreference = "Stop"
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$decks = @(
    (Join-Path $dir "ParaSail_Presentation (Ananthakrishnan AS).pptx"),
    (Join-Path $dir "ParaSail_Presentation_TechnicalBackup (Ananthakrishnan AS).pptx")
)
$app = New-Object -ComObject PowerPoint.Application
$app.DisplayAlerts = 1          # ppAlertsNone: suppress the repair dialog
$failed = 0
try {
    foreach ($d in $decks) {
        if (-not (Test-Path -LiteralPath $d)) { Write-Output "MISSING $d"; $failed++; continue }
        try {
            $pres = $app.Presentations.Open($d, $true, $false, $false)
            $n = $pres.Slides.Count
            $pres.Close()
            Write-Output ("OK   {0} slides  {1}" -f $n, (Split-Path $d -Leaf))
        }
        catch {
            Write-Output ("FAIL needs repair: {0} - {1}" -f (Split-Path $d -Leaf), $_.Exception.Message)
            $failed++
        }
    }
}
finally {
    $app.Quit()
    [System.Runtime.Interopservices.Marshal]::ReleaseComObject($app) | Out-Null
}
if ($failed -gt 0) { exit 1 } else { Write-Output "POWERPOINT VALIDATION PASSED"; exit 0 }
