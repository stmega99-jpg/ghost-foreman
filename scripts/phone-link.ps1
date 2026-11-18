# Builds the one-time sign-in link for the iPhone and copies it to the clipboard (it is NOT printed).
#   .\scripts\phone-link.ps1            -> link valid for 20 hours (default)
#   .\scripts\phone-link.ps1 -Ttl 2h    -> shorter
# The link contains a dashboard access token: treat it like a password. Send it to your own iPhone only
# (AirDrop, Notes via iCloud, or paste it into Safari through Universal Clipboard).
param([string]$Ttl = "20h")

$ErrorActionPreference = "Stop"
$ts = "C:\Program Files\Tailscale\tailscale.exe"
if (-not (Test-Path $ts)) { throw "Tailscale is not installed." }

$status = & $ts status --json | ConvertFrom-Json
if ($status.BackendState -ne "Running") { throw "Tailscale is not connected (state: $($status.BackendState)). Sign in first." }
$dns = ([string]$status.Self.DNSName).TrimEnd(".")
if (-not $dns) { throw "This PC has no Tailscale DNS name. Enable MagicDNS in the Tailscale admin console." }

$serve = (& $ts serve status 2>&1 | Out-String)
if ($serve -notmatch [regex]::Escape($dns)) { throw "Tailscale Serve is not active. Run: tailscale serve --bg 5476" }
if ($serve -match "Funnel on") { throw "Funnel is ON: the dashboard would be reachable from the public internet. Run: tailscale funnel reset" }

$env:PYTHONUTF8 = "1"
$line = (kirocrew token --ttl $Ttl 2>$null | Select-Object -Last 1)
if (-not $line -or $line -notmatch "token=") { throw "kirocrew token failed. Is the gateway running?" }
$tokenPart = ($line -split "\?token=", 2)[1].Trim()
$url = "https://$dns/?token=$tokenPart"
Set-Clipboard -Value $url
Write-Host "Link for the iPhone copied to the clipboard (valid $Ttl)." -ForegroundColor Green
Write-Host "Host: https://$dns/   (reachable only from devices signed in to your tailnet)"
