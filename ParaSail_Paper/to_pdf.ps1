param(
  [Parameter(Mandatory=$true)][string]$InputPath,
  [Parameter(Mandatory=$true)][string]$OutputPath
)
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
  $doc = $word.Documents.Open($InputPath, $false, $true)
  $doc.ExportAsFixedFormat($OutputPath, 17)  # 17 = wdExportFormatPDF
  $doc.Close($false)
  Write-Output "PDF_OK $OutputPath"
} finally {
  $word.Quit()
  [System.Runtime.Interopservices.Marshal]::ReleaseComObject($word) | Out-Null
}
