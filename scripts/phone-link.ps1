# Builds the sign-in link for the iPhone and copies it to the clipboard (it is NOT printed).
# By default the link opens Ghost Foreman's own phone page (/api/apps/ghost-foreman/m/), which can be added to the
# Home Screen as its own app. -Dashboard opens the Kiro Crew dashboard instead.
# The link can be used more than once until it expires (-Ttl): the installed Home Screen app signs in with it once,
# then keeps itself signed in with a 30-day refresh cookie. Use a short -Ttl (e.g. 1h) when installing.
#   .\scripts\phone-link.ps1            -> link valid for 20 hours (default)
#   .\scripts\phone-link.ps1 -Ttl 2h    -> shorter
#   .\scripts\phone-link.ps1 -Qr        -> show a QR code in a window on this PC instead of using the clipboard
#                                          (needs `pip install segno`; nothing is written to disk; closes after 5 min / Esc)
# The link contains a dashboard access token: treat it like a password. Send it to your own iPhone only
# (AirDrop, Notes via iCloud, or paste it into Safari through Universal Clipboard).
param([string]$Ttl = "20h", [switch]$Qr, [int]$QrSeconds = 300, [switch]$Dashboard)

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
$path = if ($Dashboard) { "/" } else { "/api/apps/ghost-foreman/m/" }
$url = "https://$dns$path" + "?token=$tokenPart"
if ($Qr) {
    # The link goes to the viewer through an environment variable (not the command line) and is cleared right after.
    $env:GF_QR_TEXT = $url
    $env:GF_QR_SECONDS = "$QrSeconds"
    $env:GF_QR_TITLE = "Ghost Foreman - iPhoneのカメラで読み取り"
    $env:GF_QR_CAPTION = "iPhoneのカメラで読み取り → Safariで開く`n（この画面は他人に見せないでください。ログイン用のリンクです）"
    try {
        $pyw = (Get-Command pythonw -ErrorAction Stop).Source
        Start-Process -FilePath $pyw -ArgumentList ("`"" + (Join-Path $PSScriptRoot "show_qr.py") + "`"")
    } finally {
        Remove-Item Env:GF_QR_TEXT, Env:GF_QR_SECONDS, Env:GF_QR_TITLE, Env:GF_QR_CAPTION -ErrorAction SilentlyContinue
    }
    Write-Host "QR code window opened on this PC (valid $Ttl, closes in $QrSeconds s)." -ForegroundColor Green
} else {
    Set-Clipboard -Value $url
    Write-Host "Link for the iPhone copied to the clipboard (valid $Ttl)." -ForegroundColor Green
}
Write-Host "Host: https://$dns/   (reachable only from devices signed in to your tailnet)"
