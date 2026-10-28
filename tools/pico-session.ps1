# Gets a Pico product's scripts ready to talk to one device. Dot-source it, so its variables stay:
#   . ..\app-base\tools\pico-session.ps1 -Product plasmastick -Device porch
# Sets the product's password variables (PLASMASTICK_* or PICOPIR_*) for this session from the Windows user
# variables: the device's own (PLASMASTICK_WEB_PASSWORD_<DEVICE>) if set, else the product's, else the other product's
# (devices set up alike share them), and $PicoIp, the
# device's IPv4 address: Python's urllib fails on the IPv6 address a .local name gives first. Nothing is printed but
# the product's folder and whether each password was found: never the passwords or the address.
param(
    [Parameter(Mandatory)][ValidateSet('plasmastick', 'picopir')][string]$Product,
    [Parameter(Mandatory)][string]$Device
)

$folders = @{ plasmastick = 'plasmastick-controller'; picopir = 'pico-pir' }
$prefixes = @{ plasmastick = 'PLASMASTICK'; picopir = 'PICOPIR' }
$PicoRepo = Join-Path (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)) $folders[$Product]
$prefix = $prefixes[$Product]

foreach ($kind in 'WEB', 'MQTT') {
    # A device's own first (PLASMASTICK_WEB_PASSWORD_PORCH, say), then the product's, then the other's
    $deviceKey = ($Device -replace '\.local$', '' -replace '[^A-Za-z0-9]', '_').ToUpper()
    $value = [Environment]::GetEnvironmentVariable("${prefix}_${kind}_PASSWORD_${deviceKey}", 'User')
    if (-not $value) {
        $value = [Environment]::GetEnvironmentVariable("${prefix}_${kind}_PASSWORD", 'User')
    }
    if (-not $value) {
        foreach ($other in $prefixes.Values) {
            $value = [Environment]::GetEnvironmentVariable("${other}_${kind}_PASSWORD", 'User')
            if ($value) { break }
        }
    }
    Set-Item -Path "env:${prefix}_${kind}_PASSWORD" -Value $value
    Write-Host ("{0} password: {1}" -f $kind.ToLower(), $(if ($value) { 'found' } else { 'not set' }))
}

$name = if ($Device -match '^\d+\.\d+\.\d+\.\d+$' -or $Device.Contains('.')) { $Device } else { "$Device.local" }
$PicoIp = (Resolve-DnsName $name -Type A -ErrorAction SilentlyContinue | Select-Object -First 1).IPAddress
if (-not $PicoIp -and $Device -match '^\d+\.\d+\.\d+\.\d+$') { $PicoIp = $Device }
Write-Host ("{0}: {1}" -f $Device, $(if ($PicoIp) { 'found' } else { "doesn't resolve (off, or in setup mode)" }))
Write-Host "product: $PicoRepo"
