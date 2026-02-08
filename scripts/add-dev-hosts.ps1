# Adds dev hosts for OpenCloud (requires Administrator)
# Usage: Run as Administrator: PowerShell -NoProfile -ExecutionPolicy Bypass -File .\scripts\add-dev-hosts.ps1

# Get Minikube IP
$minikubeIp = (& minikube ip).Trim()
if (-not $minikubeIp) {
  Write-Error "Could not determine minikube IP. Ensure minikube is running and 'minikube ip' works."
  exit 1
}

$hosts = "$env:SystemRoot\System32\drivers\etc\hosts"
$start = "# BEGIN DI4D-DEV"
$end   = "#  END DI4D-DEV"

$entries = @(
  "$minikubeIp cloud.opencloud.test opencloud",
  "$minikubeIp keycloak.opencloud.test"
)

$content = Get-Content $hosts -Raw
if ($content -notmatch [regex]::Escape($start)) {
  Add-Content $hosts "`n$start"
  $entries | ForEach-Object { Add-Content $hosts $_ }
  Add-Content $hosts $end
  ipconfig /flushdns | Out-Null
  Write-Host "Added DI4D dev hosts for IP $minikubeIp"
} else {
  Write-Host "DI4D dev hosts block already exists in $hosts"
}