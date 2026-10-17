<# Read-only Windows host inventory. No installers, login, model download or inference. #>
param(
    [string]$ExpectedComputerName = 'DESKTOP-B5PNBNC'
)
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT' -or $env:COMPUTERNAME -ine $ExpectedComputerName) {
    [Console]::Error.WriteLine("Wrong execution host. Expected Windows $ExpectedComputerName; observed $env:COMPUTERNAME / $env:OS. Run on the actual 5090 desktop.")
    exit 2
}

function Invoke-ReadOnlyProbe {
    param([string]$Name, [string[]]$Arguments)
    $command = Get-Command -Name $Name -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -eq $command) { return [ordered]@{name=$Name; status='NOT_FOUND'} }
    if ($command.CommandType -ne 'Application') {
        return [ordered]@{name=$Name; status='NOT_RUN_NON_APPLICATION'; command_type=[string]$command.CommandType; source=$command.Source}
    }
    try {
        # Probes are an explicit allow-list of version/inventory commands below.
        $probeText = & $command.Source @Arguments 2>&1 | Out-String
        $probeCode = $LASTEXITCODE
        return [ordered]@{name=$Name; arguments=$Arguments; source=$command.Source; exit_code=$probeCode; output=$probeText}
    } catch {
        return [ordered]@{name=$Name; arguments=$Arguments; source=$command.Source; error=$_.Exception.Message}
    }
}

$rootDir = Split-Path -Parent $PSScriptRoot
$toolNames = @('python','python3','py','conda','git','wsl','nvidia-smi')
$tools = foreach ($name in $toolNames) {
    foreach ($entry in @(Get-Command -Name $name -All -ErrorAction SilentlyContinue)) {
        if ($null -ne $entry) {
            [ordered]@{name=$name; command_type=[string]$entry.CommandType; source=$entry.Source; store_alias=([string]$entry.Source -like '*\Microsoft\WindowsApps\python*')}
        }
    }
}
$inventory = [ordered]@{
    schema_version=1
    task_id='R0-5090-003'
    timestamp_utc=[DateTime]::UtcNow.ToString('o')
    hostname=$env:COMPUTERNAME
    powershell_version=$PSVersionTable.PSVersion.ToString()
    evidence_kind='HOST_SCRIPT_INVENTORY'
    formal_inference_executed=$false
    cuda_nf4_verified=$false
    tool_paths=@($tools)
    gpu=(Invoke-ReadOnlyProbe -Name 'nvidia-smi' -Arguments @('--query-gpu=name,memory.total,driver_version','--format=csv'))
    python_launchers=(Invoke-ReadOnlyProbe -Name 'py' -Arguments @('-0p'))
    conda_environments=(Invoke-ReadOnlyProbe -Name 'conda' -Arguments @('env','list','--json'))
    wsl_distributions=(Invoke-ReadOnlyProbe -Name 'wsl' -Arguments @('--list','--verbose'))
    git=(Invoke-ReadOnlyProbe -Name 'git' -Arguments @('--version'))
    notes=@('No python.exe is invoked: Windows Store aliases cannot launch an installer.','Candidate environment paths only; no credentials or environment-variable dump.','Non-zero probe codes are evidence to review, not permission to install.','Host and driver inventory does not verify CUDA, NF4 or model loading.')
}
try {
    $osInfo = Get-CimInstance -ClassName Win32_OperatingSystem
    $inventory['windows'] = [ordered]@{caption=$osInfo.Caption; version=$osInfo.Version; total_memory_kib=$osInfo.TotalVisibleMemorySize}
} catch { $inventory['windows_query_error']=$_.Exception.Message }

$runId = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')+'-windows-inventory-'+[Guid]::NewGuid().ToString('N').Substring(0,8)
$returnDir = Join-Path $rootDir ('coordination/returns/'+$runId)
New-Item -ItemType Directory -Path $returnDir -ErrorAction Stop | Out-Null
$outputPath = Join-Path $returnDir 'windows_inventory.json'
if (Test-Path -LiteralPath $outputPath) { throw 'Refusing to overwrite existing evidence' }
$inventory | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $outputPath -Encoding UTF8
Write-Output ('Inventory written: '+$outputPath)
Write-Output 'This is inventory only; no installation or CUDA/NF4/model acceptance is asserted.'
