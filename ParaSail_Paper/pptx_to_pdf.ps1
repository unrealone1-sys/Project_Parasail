param(
  [Parameter(Mandatory=$true)][string]$InputPath,
  [Parameter(Mandatory=$true)][string]$OutputPath
)
$app = New-Object -ComObject PowerPoint.Application
try {
  $pres = $app.Presentations.Open($InputPath, $true, $false, $false)
  $pres.SaveAs($OutputPath, 32)  # 32 = ppSaveAsPDF
  $pres.Close()
  Write-Output "PDF_OK $OutputPath"
} finally {
  $app.Quit()
  [System.Runtime.Interopservices.Marshal]::ReleaseComObject($app) | Out-Null
}
