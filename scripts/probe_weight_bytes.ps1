$ErrorActionPreference = 'Stop'
$outPath = Join-Path (Split-Path -Parent $PSScriptRoot) 'audit/evidence/weight_byte_probes.json'
if (Test-Path -LiteralPath $outPath) { throw 'Evidence already exists.' }
$client = [System.Net.Http.HttpClient]::new()
$client.Timeout = [TimeSpan]::FromSeconds(45)
$results = foreach ($entry in @(@('datasentinel','1B0w5r5udH3I_aiZL0_-2a8WzBAqjuLsn'),@('promptlocate_oracle','1CEaW4M6Y2_w8ca3-76SnoaNgio8x2eQB'))) {
    $response = $null
    try {
        $url = 'https://drive.usercontent.google.com/download?id='+$entry[1]+'&export=download&confirm=t'
        $req = [System.Net.Http.HttpRequestMessage]::new([System.Net.Http.HttpMethod]::Get,$url)
        $req.Headers.Range = [System.Net.Http.Headers.RangeHeaderValue]::new(0,4095)
        $response = $client.SendAsync($req,[System.Net.Http.HttpCompletionOption]::ResponseHeadersRead).GetAwaiter().GetResult()
        $stream = $response.Content.ReadAsStream()
        $buffer = [byte[]]::new(4096)
        $total = 0
        while ($total -lt $buffer.Length) { $n = $stream.Read($buffer,$total,$buffer.Length-$total); if ($n -eq 0) { break }; $total += $n }
        [ordered]@{name=$entry[0];url=$url;status=[int]$response.StatusCode;content_type=[string]$response.Content.Headers.ContentType;content_range=[string]$response.Content.Headers.ContentRange;content_disposition=[string]$response.Content.Headers.ContentDisposition;bytes_probed=$total;first_bytes_hex=[System.Convert]::ToHexString($buffer[0..15]);note='Bounded 4KB probe only. ZIP contents and adapter compatibility not verified.'}
        $stream.Dispose()
        $req.Dispose()
    } catch { [ordered]@{name=$entry[0];error=$_.Exception.Message} }
    finally { if ($null -ne $response) { $response.Dispose() } }
}
$client.Dispose()
$results | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $outPath -Encoding utf8
Get-Content -LiteralPath $outPath
