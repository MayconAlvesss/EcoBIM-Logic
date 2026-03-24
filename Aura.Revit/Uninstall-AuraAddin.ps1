#Requires -Version 5.1
<#
.SYNOPSIS
    Removes the Aura BIM AI add-in from Autodesk Revit 2025.

.DESCRIPTION
    Deletes Aura.Revit.dll and Aura.addin from the Revit 2025 Add-ins folder.
    Revit must be closed before running this script.

.NOTES
    Run from anywhere:
        powershell -ExecutionPolicy Bypass -File .\Uninstall-AuraAddin.ps1
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$REVIT_VERSION = "2025"
$ADDINS_DIR    = Join-Path $env:APPDATA "Autodesk\Revit\Addins\$REVIT_VERSION"

Write-Host ""
Write-Host "═══════════════════════════════════════════════" -ForegroundColor DarkRed
Write-Host "   Aura BIM AI — Revit $REVIT_VERSION Uninstaller       " -ForegroundColor Red
Write-Host "═══════════════════════════════════════════════" -ForegroundColor DarkRed
Write-Host ""

# Ensure Revit is closed before removing files it may have loaded.
$revitProcess = Get-Process -Name "Revit" -ErrorAction SilentlyContinue
if ($revitProcess) {
    Write-Host "  ✘ Revit is currently open. Close it before uninstalling." -ForegroundColor Red
    exit 1
}

$filesToRemove = @(
    "Aura.Revit.dll",
    "Aura.addin",
    "System.Text.Json.dll"  # dependency shipped alongside the add-in
)

$removedAny = $false
foreach ($file in $filesToRemove) {
    $target = Join-Path $ADDINS_DIR $file
    if (Test-Path $target) {
        Remove-Item $target -Force
        Write-Host "  ✔ Removed: $target" -ForegroundColor Green
        $removedAny = $true
    }
}

if (-not $removedAny) {
    Write-Host "  ⚠ No Aura add-in files found in: $ADDINS_DIR" -ForegroundColor Yellow
    Write-Host "    The add-in may not have been installed." -ForegroundColor Gray
} else {
    Write-Host ""
    Write-Host "  Aura BIM AI has been removed from Revit $REVIT_VERSION." -ForegroundColor Green
}

Write-Host ""
