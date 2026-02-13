#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Test the processor locally by creating and uploading a test zip file

.DESCRIPTION
    Creates a test submission with manifest.json and uploads to blob storage
    to trigger the processor workflow

.EXAMPLE
    .\test-processor.ps1
#>

param(
    [Parameter(Mandatory=$false)]
    [string]$SubmissionId = "test-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
)

$ErrorActionPreference = "Stop"

# Configuration
$STORAGE_ACCOUNT = "strfpo5kn5bsg47vvac"
$CONTAINER = "usabc-uploads-stage"
$PROCESSED_CONTAINER = "usabc-uploads-processed"

Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "Processor Test Script" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""

# Step 1: Create test files
Write-Host "[1/6] Creating test files..." -ForegroundColor Green

$testDir = Join-Path $env:TEMP "processor-test-$SubmissionId"
New-Item -ItemType Directory -Path $testDir -Force | Out-Null

# Create test document
$testFile = Join-Path $testDir "document.txt"
@"
USABC Upload Test Document
Submission ID: $SubmissionId
Created: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')

This is a test document for the processor service.
"@ | Out-File -FilePath $testFile -Encoding utf8

# Create manifest.json
$manifestFile = Join-Path $testDir "manifest.json"
$manifest = @{
    submissionId = $SubmissionId
    submitterEmail = "test@example.com"
    uploadTimestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    fileCount = 2
    files = @("document.txt", "manifest.json")
} | ConvertTo-Json -Depth 10

$manifest | Out-File -FilePath $manifestFile -Encoding utf8

Write-Host "  ✓ Test files created in: $testDir" -ForegroundColor Gray

# Step 2: Create zip file
Write-Host ""
Write-Host "[2/6] Creating zip archive..." -ForegroundColor Green

$zipFile = Join-Path $env:TEMP "test-upload-$SubmissionId.zip"
Compress-Archive -Path "$testDir\*" -DestinationPath $zipFile -Force

Write-Host "  ✓ Zip created: $zipFile" -ForegroundColor Gray
Write-Host "  ✓ Size: $((Get-Item $zipFile).Length) bytes" -ForegroundColor Gray

# Step 3: Upload to blob storage
Write-Host ""
Write-Host "[3/6] Uploading to blob storage..." -ForegroundColor Green

$blobName = "test/$SubmissionId.zip"

try {
    az storage blob upload `
        --account-name $STORAGE_ACCOUNT `
        --container-name $CONTAINER `
        --name $blobName `
        --file $zipFile `
        --auth-mode login `
        --overwrite | Out-Null
    
    Write-Host "  ✓ Uploaded to: $CONTAINER/$blobName" -ForegroundColor Gray
} catch {
    Write-Host "  ✗ Upload failed: $_" -ForegroundColor Red
    exit 1
}

# Step 4: Check Service Bus queue
Write-Host ""
Write-Host "[4/6] Checking Service Bus queue..." -ForegroundColor Green
Start-Sleep -Seconds 3

$queueStatus = az servicebus queue show `
    --namespace-name usabc-servicebus `
    --queue-name blob-upload-events `
    --resource-group rg-rfpo-e108977f `
    --query "countDetails" | ConvertFrom-Json

Write-Host "  Active messages: $($queueStatus.activeMessageCount)" -ForegroundColor Gray
Write-Host "  Dead letter messages: $($queueStatus.deadLetterMessageCount)" -ForegroundColor Gray

if ($queueStatus.activeMessageCount -gt 0) {
    Write-Host "  ✓ Event queued for processing" -ForegroundColor Gray
} else {
    Write-Host "  ⚠️  No messages in queue - event may have been processed already" -ForegroundColor Yellow
}

# Step 5: Wait for processing
Write-Host ""
Write-Host "[5/6] Waiting for processor to complete..." -ForegroundColor Green
Write-Host "  Checking processed container every 5 seconds..." -ForegroundColor Gray

$maxWait = 60
$elapsed = 0

while ($elapsed -lt $maxWait) {
    Start-Sleep -Seconds 5
    $elapsed += 5
    
    # Check if files appear in processed container
    $processedFiles = az storage blob list `
        --account-name $STORAGE_ACCOUNT `
        --container-name $PROCESSED_CONTAINER `
        --prefix "processed/$SubmissionId/" `
        --auth-mode login `
        --query "[].name" -o tsv
    
    if ($processedFiles) {
        Write-Host "  ✓ Processing complete! ($elapsed seconds)" -ForegroundColor Gray
        break
    }
    
    Write-Host "  ⏳ Still waiting... ($elapsed/$maxWait seconds)" -ForegroundColor Gray
}

# Step 6: Verify results
Write-Host ""
Write-Host "[6/6] Verifying processed files..." -ForegroundColor Green

$processedFiles = az storage blob list `
    --account-name $STORAGE_ACCOUNT `
    --container-name $PROCESSED_CONTAINER `
    --prefix "processed/$SubmissionId/" `
    --auth-mode login `
    -o json | ConvertFrom-Json

if ($processedFiles) {
    Write-Host "  ✓ Found $($processedFiles.Count) processed file(s):" -ForegroundColor Green
    foreach ($file in $processedFiles) {
        Write-Host "    - $($file.name)" -ForegroundColor Gray
    }
} else {
    Write-Host "  ✗ No processed files found" -ForegroundColor Red
    Write-Host ""
    Write-Host "Troubleshooting steps:" -ForegroundColor Yellow
    Write-Host "  1. Check if processor is running:" -ForegroundColor Gray
    Write-Host "     docker-compose ps" -ForegroundColor Gray
    Write-Host "  2. View processor logs:" -ForegroundColor Gray
    Write-Host "     docker-compose logs -f" -ForegroundColor Gray
    Write-Host "  3. Check Service Bus queue:" -ForegroundColor Gray
    Write-Host "     az servicebus queue show --namespace-name usabc-servicebus --queue-name blob-upload-events --resource-group rg-rfpo-e108977f" -ForegroundColor Gray
    exit 1
}

# Cleanup
Write-Host ""
Write-Host "Cleaning up temporary files..." -ForegroundColor Yellow
Remove-Item -Path $testDir -Recurse -Force
Remove-Item -Path $zipFile -Force
Write-Host "  ✓ Cleanup complete" -ForegroundColor Gray

# Summary
Write-Host ""
Write-Host "=" * 80 -ForegroundColor Green
Write-Host "Test Complete!" -ForegroundColor Green
Write-Host "=" * 80 -ForegroundColor Green
Write-Host ""
Write-Host "Submission ID: $SubmissionId" -ForegroundColor Cyan
Write-Host "Original blob: $CONTAINER/$blobName" -ForegroundColor Cyan
Write-Host "Processed files: $PROCESSED_CONTAINER/processed/$SubmissionId/" -ForegroundColor Cyan
Write-Host ""
Write-Host "View processed files:" -ForegroundColor Yellow
Write-Host "  az storage blob list --account-name $STORAGE_ACCOUNT --container-name $PROCESSED_CONTAINER --prefix 'processed/$SubmissionId/' --auth-mode login -o table" -ForegroundColor Gray
Write-Host ""
