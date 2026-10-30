# Copies App Base into a product: .\update-base.ps1 -Product ..\juggle-unicorn\app [-Tag v0.1.0 | -From .]
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
        # Windows' own tar: another on the PATH (Git's) takes C: for a host name
        & "$env:SystemRoot\System32\tar.exe" -x -f $archive -C $work
        if ($LASTEXITCODE -ne 0) { throw "Couldn't unpack $Tag" }
        $source = Join-Path $work 'src\base'
        $commit = (git -C $PSScriptRoot rev-list -n 1 $Tag).Substring(0, 7)
        $version = $Tag
    } else {
        $source = Join-Path (Resolve-Path $From) 'src\base'
        $commit = (git -C $From rev-parse --short HEAD)
        $dirty = git -C $From status --porcelain -- src/base
        $version = 'working copy' + $(if ($dirty) { ' (uncommitted changes)' } else { '' })
    }

    # The new copy is made beside the old, which it replaces only once it's whole
    $new = "$target.new"
    if (Test-Path $new) { Remove-Item -Recurse -Force $new }
    New-Item -ItemType Directory $new | Out-Null
    Copy-Item -Recurse (Join-Path $source '*') $new -Exclude '__pycache__'
    Get-ChildItem -Recurse -Directory $new -Filter '__pycache__' | Remove-Item -Recurse -Force
    if (-not (Test-Path (Join-Path $new '__init__.py'))) { throw "No App Base in $source" }

    $lines = @("version: $version", "commit: $commit")
    Get-ChildItem -Recurse -File $new | Sort-Object FullName | ForEach-Object {
        $relative = $_.FullName.Substring($new.Length + 1).Replace('\', '/')
        $lines += "$((Get-FileHash -Algorithm SHA256 $_.FullName).Hash.ToLower())  $relative"
    }
    [IO.File]::WriteAllText((Join-Path $new 'VERSION'), ($lines -join "`n") + "`n")
    if (Test-Path $target) { Remove-Item -Recurse -Force $target }
    Move-Item $new $target
    Write-Host "App Base ($version, $commit) copied into $target"
}
finally {
    if (Test-Path $work) { Remove-Item -Recurse -Force $work }
}
