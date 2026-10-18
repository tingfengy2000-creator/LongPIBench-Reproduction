param([switch]$Persist)

# User preference: large payloads, caches and download temporary files on D/E.
# Authentication files are small and are neither read nor relocated here.
$pilotCacheRoot = 'E:\Caches'
$pilotCacheVariables = [ordered]@{
    HF_HUB_CACHE = "$pilotCacheRoot\huggingface\hub"
    HF_ASSETS_CACHE = "$pilotCacheRoot\huggingface\assets"
    HF_XET_CACHE = "$pilotCacheRoot\huggingface\xet"
    HF_DATASETS_CACHE = "$pilotCacheRoot\huggingface\datasets"
    TRANSFORMERS_CACHE = "$pilotCacheRoot\huggingface\hub"
    TORCH_HOME = "$pilotCacheRoot\torch"
    PIP_CACHE_DIR = "$pilotCacheRoot\pip"
}
foreach ($pilotVariable in $pilotCacheVariables.GetEnumerator()) {
    $pilotResolved = [System.IO.Path]::GetFullPath($pilotVariable.Value)
    if ($pilotResolved.Substring(0, 2) -notin @('D:', 'E:')) { throw 'Large-file path must be on D: or E:' }
    New-Item -ItemType Directory -Path $pilotResolved -Force | Out-Null
    [Environment]::SetEnvironmentVariable($pilotVariable.Key, $pilotResolved, 'Process')
    if ($Persist) { [Environment]::SetEnvironmentVariable($pilotVariable.Key, $pilotResolved, 'User') }
}
$pilotDownloadTemp = "$pilotCacheRoot\download-temp"
New-Item -ItemType Directory -Path $pilotDownloadTemp -Force | Out-Null
$env:TEMP = $pilotDownloadTemp
$env:TMP = $pilotDownloadTemp
# TEMP/TMP are process-scoped: do not silently change every Windows app's temp.
Write-Output 'Large-file caches: E:\Caches; this download process TEMP/TMP: E:\Caches\download-temp'
