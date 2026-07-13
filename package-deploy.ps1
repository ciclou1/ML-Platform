param(
    [string]$OutputDir = ".",
    [string]$Prefix = "ai-platform-deploy"
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$dateTag = Get-Date -Format "yyyyMMdd"
$packageName = "$Prefix-$dateTag.zip"
$outputRoot = [System.IO.Path]::GetFullPath(
    (Join-Path $projectRoot $OutputDir)
)
$packagePath = Join-Path $outputRoot $packageName
$stagingRoot = Join-Path (
    [System.IO.Path]::GetTempPath()
) ("ai-platform-package-" + [System.Guid]::NewGuid().ToString("N"))
$stagingProject = Join-Path $stagingRoot "ai-platform"

$excludeRelativeDirPaths = @(
    ".git",
    ".agents",
    ".claude",
    ".codex",
    ".uv-cache",
    ".idea",
    ".vscode",
    "storage",
    "frontend/dist",
    "YOLOconstructionSiteSeftyDetector-main"
)

$globalExcludeDirNames = @(
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache"
)

$excludeFileNames = @(
    ".env",
    ".env.local",
    ".DS_Store",
    "Thumbs.db"
)

$excludeExtensions = @(
    ".log",
    ".pyc",
    ".pyo",
    ".pyd",
    ".tsbuildinfo"
)

$excludeNamePatterns = @(
    "ai-platform-deploy-*.zip"
)

function Test-ExcludedPath {
    param(
        [System.IO.FileSystemInfo]$Item,
        [string]$RelativePath = ""
    )

    $normalizedRelativePath = $RelativePath.Replace("\", "/")

    if (
        $Item.PSIsContainer -and
        $globalExcludeDirNames -contains $Item.Name
    ) {
        return $true
    }

    if (
        $Item.PSIsContainer -and
        $excludeRelativeDirPaths -contains $normalizedRelativePath
    ) {
        return $true
    }

    if ($excludeFileNames -contains $Item.Name) {
        return $true
    }

    if ($excludeExtensions -contains $Item.Extension) {
        return $true
    }

    foreach ($pattern in $excludeNamePatterns) {
        if ($Item.Name -like $pattern) {
            return $true
        }
    }

    return $false
}

function Copy-ProjectItem {
    param(
        [string]$SourcePath,
        [string]$TargetPath,
        [string]$RelativePath = ""
    )

    $item = Get-Item -LiteralPath $SourcePath -Force
    if (Test-ExcludedPath -Item $item -RelativePath $RelativePath) {
        return
    }

    if ($item.PSIsContainer) {
        New-Item -ItemType Directory -Path $TargetPath -Force | Out-Null
        foreach ($child in Get-ChildItem -LiteralPath $item.FullName -Force) {
            $childRelativePath = if ([string]::IsNullOrEmpty($RelativePath)) {
                $child.Name
            }
            else {
                Join-Path $RelativePath $child.Name
            }

            Copy-ProjectItem `
                -SourcePath $child.FullName `
                -TargetPath (Join-Path $TargetPath $child.Name) `
                -RelativePath $childRelativePath
        }
        return
    }

    $targetDir = Split-Path -Parent $TargetPath
    if (-not (Test-Path -LiteralPath $targetDir)) {
        New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
    }

    Copy-Item -LiteralPath $item.FullName -Destination $TargetPath -Force
}

if (-not (Test-Path -LiteralPath $outputRoot)) {
    New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null
}

Get-ChildItem `
    -LiteralPath $outputRoot `
    -Filter "$Prefix-*.zip" `
    -File `
    -ErrorAction SilentlyContinue | Remove-Item -Force

New-Item -ItemType Directory -Path $stagingProject -Force | Out-Null

try {
    foreach ($child in Get-ChildItem -LiteralPath $projectRoot -Force) {
        Copy-ProjectItem `
            -SourcePath $child.FullName `
            -TargetPath (Join-Path $stagingProject $child.Name) `
            -RelativePath $child.Name
    }

    if (Test-Path -LiteralPath $packagePath) {
        Remove-Item -LiteralPath $packagePath -Force
    }

    Compress-Archive `
        -Path (Join-Path $stagingProject "*") `
        -DestinationPath $packagePath `
        -CompressionLevel Optimal

    Write-Host "Package created: $packagePath"
    Write-Host "Next steps:"
    Write-Host "1. Upload $packageName to the server"
    Write-Host "2. Extract it into the target directory"
    Write-Host "3. Copy docker.env.example to .env and update values"
    Write-Host "4. Run: docker compose --env-file .env up -d --build"
}
finally {
    if (Test-Path -LiteralPath $stagingRoot) {
        Remove-Item -LiteralPath $stagingRoot -Recurse -Force
    }
}
