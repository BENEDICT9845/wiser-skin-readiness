param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [Parameter(Mandatory = $true)]
    [string]$ApiKey
)

$ErrorActionPreference = "Stop"
$headers = @{ "X-API-Key" = $ApiKey }
$pass = 0
$fail = 0
$results = @()

function Test-Check {
    param([string]$Name, [scriptblock]$Block)
    try {
        $detail = & $Block
        $script:pass++
        $script:results += "PASS  $Name  $detail"
    } catch {
        $script:fail++
        $script:results += "FAIL  $Name  $($_.Exception.Message)"
    }
}

Write-Host "WISeR Skin Readiness - end-to-end smoke" -ForegroundColor Cyan
Write-Host "Base: $BaseUrl"

Test-Check "/health is 200" {
    $body = Invoke-RestMethod -Uri "$BaseUrl/health"
    if ($body.status -ne "ok") { throw "status=$($body.status)" }
    "status=ok"
}

Test-Check "root opens interactive docs" {
    $response = Invoke-WebRequest -Uri "$BaseUrl/" -UseBasicParsing
    if ($response.StatusCode -ne 200) { throw "expected 200 after redirect, got $($response.StatusCode)" }
    if ($response.Content -notmatch "Swagger UI") { throw "Swagger UI not found" }
    "Swagger UI served"
}

Test-Check "/ready loads both packs" {
    $body = Invoke-RestMethod -Uri "$BaseUrl/ready"
    if ($body.status -ne "ready") { throw "status=$($body.status)" }
    if ($body.rule_packs.Count -lt 2) { throw "expected 2 packs, got $($body.rule_packs.Count)" }
    "packs=$($body.rule_packs.Count)"
}

Test-Check "/openapi.json lists 9 paths" {
    $body = Invoke-RestMethod -Uri "$BaseUrl/openapi.json"
    $count = $body.paths.PSObject.Properties.Name.Count
    if ($count -ne 9) { throw "expected 9 paths, got $count" }
    "paths=9"
}

Test-Check "protected v2 endpoint rejects missing key" {
    try {
        Invoke-RestMethod -Uri "$BaseUrl/v2/rule-packs/cms-wiser-skin-l35041-tx-dfu-v0.1"
        throw "expected 401"
    } catch {
        if ($_.Exception.Response.StatusCode.value__ -ne 401) { throw }
        "status=401"
    }
}

Test-Check "protected v2 endpoint accepts key" {
    $body = Invoke-RestMethod `
        -Uri "$BaseUrl/v2/rule-packs/cms-wiser-skin-l35041-tx-dfu-v0.1" `
        -Headers $headers
    "pack=$($body.id)"
}

$fixturePath = Join-Path $PSScriptRoot "tests\golden_cases\cms-wiser-skin-l35041-tx-dfu-v0.1\TX-DFU-01-ready.json"
$texasReady = (Get-Content $fixturePath -Raw | ConvertFrom-Json).request
$texasReady.case_reference = "smoke-tx-ready"

Test-Check "Texas ready case evaluates end-to-end" {
    $body = Invoke-RestMethod `
        -Uri "$BaseUrl/v2/readiness/evaluate" `
        -Method Post `
        -Headers $headers `
        -ContentType "application/json" `
        -Body ($texasReady | ConvertTo-Json -Depth 10)
    if ($body.readiness.status -ne "READY_FOR_QUALIFIED_REVIEW") {
        throw "readiness=$($body.readiness.status)"
    }
    "participant=$($body.applicability.participant) score=$($body.readiness.score)"
}

Test-Check "negative wound size returns validation envelope" {
    $invalid = @{
        case_reference = "smoke-negative"
        state = "TX"
        coverage_type = "ORIGINAL_MEDICARE"
        service_date = "2026-06-01"
        wound_type = "DFU"
        wound_bed = @{ wound_size_cm_sq = -1 }
    }
    try {
        Invoke-RestMethod `
            -Uri "$BaseUrl/v2/readiness/evaluate" `
            -Method Post `
            -Headers $headers `
            -ContentType "application/json" `
            -Body ($invalid | ConvertTo-Json -Depth 5)
        throw "expected 422"
    } catch {
        if ($_.Exception.Response.StatusCode.value__ -ne 422) { throw }
        "status=422"
    }
}

$results | ForEach-Object { Write-Host $_ }
Write-Host "Total: $($pass + $fail)  Pass: $pass  Fail: $fail"
if ($fail -gt 0) { exit 1 }
