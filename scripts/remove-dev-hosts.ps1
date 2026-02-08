# Removes DI4D dev hosts block added by add-dev-hosts.ps1 (requires Administrator)
# Usage: Run as Administrator: PowerShell -NoProfile -ExecutionPolicy Bypass -File .\scripts\remove-dev-hosts.ps1

$hosts = "$env:SystemRoot\System32\drivers\etc\hosts"
$start = "# BEGIN DI4D-DEV"
$end   = "#  END DI4D-DEV"
$pattern = [regex]::Escape($start) + ".*?" + [regex]::Escape($end)

$content = Get-Content $hosts -Raw
if ($content -match $pattern) {
  $new = [regex]::Replace($content, $pattern, "", [System.Text.RegularExpressions.RegexOptions]::Singleline)
  Set-Content -Path $hosts -Value $new
  ipconfig /flushdns | Out-Null
  Write-Host "Removed DI4D dev hosts block from $hosts"
} else {
  Write-Host "No DI4D dev hosts block found in $hosts"
}