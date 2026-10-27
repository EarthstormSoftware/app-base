# Copies App Base into a product: .\update-base.ps1 -Product ..\applpi-unicorn\app [-Tag v0.1.0 | -From .]
# The product keeps the copy in <folder>\base, with VERSION: where it came from, and each file's SHA-256, which the
# product's tests check so the copy isn't edited there (a fix goes into App Base first).
#   -Tag   a tagged release of this repo (git archive of the tag)
#   -From  a working copy (default: this one), recorded as such: for developing the base and a product together
param(
    [Parameter(Mandatory)]
    [string]$Product,
    [string]$Tag,
    [string]$From = $PSScriptRoot
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$target = Join-Path (Resolve-Path $Product) 'base'
$work = Join-Path ([IO.Path]::GetTempPath()) "app-base-$PID"
try {
    if ($Tag) {
        New-Item -ItemType Directory $work | Out-Null
        $archive = Join-Path $work 'base.tar'
        git -C $PSScriptRoot archive --format=tar -o $archive $Tag src/base
        if ($LASTEXITCODE -ne 0) { throw "No tag $Tag in $PSScriptRoot" }
        tar -x -f $archive -C $work
        $source = Join-Path $work 'src\base'
        $commit = (git -C $PSScriptRoot rev-list -n 1 $Tag).Substring(0, 7)
        $version = $Tag
    } else {
        $source = Join-Path (Resolve-Path $From) 'src\base'
        $commit = (git -C $From rev-parse --short HEAD)
        $dirty = git -C $From status --porcelain -- src/base
        $version = 'working copy' + $(if ($dirty) { ' (uncommitted changes)' } else { '' })
    }

    if (Test-Path $target) { Remove-Item -Recurse -Force $target }
    New-Item -ItemType Directory $target | Out-Null
    Copy-Item -Recurse (Join-Path $source '*') $target -Exclude '__pycache__'
    Get-ChildItem -Recurse -Directory $target -Filter '__pycache__' | Remove-Item -Recurse -Force

    $lines = @("version: $version", "commit: $commit")
    Get-ChildItem -Recurse -File $target | Sort-Object FullName | ForEach-Object {
        $relative = $_.FullName.Substring($target.Length + 1).Replace('\', '/')
        $lines += "$((Get-FileHash -Algorithm SHA256 $_.FullName).Hash.ToLower())  $relative"
    }
    [IO.File]::WriteAllText((Join-Path $target 'VERSION'), ($lines -join "`n") + "`n")
    Write-Host "App Base ($version, $commit) copied into $target"
}
finally {
    if (Test-Path $work) { Remove-Item -Recurse -Force $work }
}
