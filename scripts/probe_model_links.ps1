$ErrorActionPreference = 'Stop'
$rootDir = Split-Path -Parent $PSScriptRoot
$outPath = Join-Path $rootDir 'audit/evidence/model_link_probes.json'
if (Test-Path -LiteralPath $outPath) { throw 'Evidence already exists; choose a new output before repeating.' }
$links = @(
    @{name='datasentinel'; url='https://drive.google.com/uc?export=download&id=1B0w5r5udH3I_aiZL0_-2a8WzBAqjuLsn'},
    @{name='promptlocate_oracle'; url='https://drive.google.com/uc?export=download&id=1CEaW4M6Y2_w8ca3-76SnoaNgio8x2eQB'},
    @{name='llama_config_unauthenticated'; url='https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct/resolve/0e9e39f249a16976918f6564b8830bc894c89659/config.json'}
)
$client = [System.Net.Http.HttpClient]::new()
$client.Timeout = [TimeSpan]::FromSeconds(45)
$results = foreach ($link in $links) {
    $response = $null
    try {
        $req = [System.Net.Http.HttpRequestMessage]::new([System.Net.Http.HttpMethod]::Get, $link.url)
        $req.Headers.Range = [System.Net.Http.Headers.RangeHeaderValue]::new(0,4095)
        $response = $client.SendAsync($req,[System.Net.Http.HttpCompletionOption]::ResponseHeadersRead).GetAwaiter().GetResult()
        $stream = $response.Content.ReadAsStream()
        $buffer = [byte[]]::new(4096)
        $n = $stream.Read($buffer,0,$buffer.Length)
        $prefix = [System.Text.Encoding]::UTF8.GetString($buffer,0,$n)
        $preview = if ($response.Content.Headers.ContentType.MediaType -match 'text|json') { $prefix } else { $null }
        [ordered]@{name=$link.name; url=$link.url; status=[int]$response.StatusCode; content_type=$response.Content.Headers.ContentType.ToString(); content_length=$response.Content.Headers.ContentLength; content_disposition=[string]$response.Content.Headers.ContentDisposition; bytes_probed=$n; first_bytes_hex=[System.Convert]::ToHexString($buffer[0..([Math]::Min(15,$n-1))]); text_preview=$preview}
        $stream.Dispose()
        $req.Dispose()
    } catch { [ordered]@{name=$link.name; url=$link.url; error=$_.Exception.Message} }
    finally { if ($null -ne $response) { $response.Dispose() } }
}
$client.Dispose()
[ordered]@{timestamp_utc=[DateTime]::UtcNow.ToString('o'); authenticated=$false; results=@($results)} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $outPath -Encoding utf8
$results | Select-Object name,status,content_type,content_length,bytes_probed,error | Format-Table -AutoSize
