<#
.SYNOPSIS
    Build a self-signed TEST MSIX for local install.
.DESCRIPTION
    Run as admin. Signs the output msix with a self-signed cert and
    adds the cert to Trusted Root + Trusted People so the TEST package
    can be double-click installed. NOT for the Store.
#>

$ErrorActionPreference = "Stop"
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Definition
$OUTPUT_DIR = Join-Path $SCRIPT_DIR "output"
$SIGNTOOL = "C:\Program Files (x86)\Windows Kits\10\bin\10.0.26100.0\x64\signtool.exe"

if (-not (Test-Path $SIGNTOOL)) {
    Write-Host "[ERR] signtool not found: $SIGNTOOL" -ForegroundColor Red
    exit 1
}

# Test cert CN MUST equal manifest <Identity Publisher> CN,
# otherwise signtool fails with 0x8007000b on MSIX/Appx.
$PUBLISHER_CN = "2F4AE534-61FA-4616-9EDE-128FE5A6F25E"
$CERT_SUBJECT = "CN=$PUBLISHER_CN"
$PFX_PATH = Join-Path $SCRIPT_DIR "test_sign.pfx"
$CER_PATH  = Join-Path $SCRIPT_DIR "test_sign.cer"
$CERT_PWD  = ConvertTo-SecureString -String "Test2026" -Force -AsPlainText

Write-Host "=== Build signed TEST MSIX ===" -ForegroundColor Cyan

# 1. Admin check
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "[ERR] Must run as Administrator!" -ForegroundColor Red
    exit 1
}

# 2. Create a fresh plain end-entity code-signing cert (NO CA=true!
#    MSIX signing with signtool fails with 0x8007000b when the cert
#    carries the CA basic-constraint. Use the official MSIX pattern.)
Write-Host "[1/4] Create test code-signing cert..." -ForegroundColor Green
Get-ChildItem "Cert:\CurrentUser\My" -ErrorAction SilentlyContinue | Where-Object { $_.Subject -eq $CERT_SUBJECT } | Remove-Item -ErrorAction SilentlyContinue
$cert = New-SelfSignedCertificate -Type Custom -Subject $CERT_SUBJECT `
    -CertStoreLocation "Cert:\CurrentUser\My" -KeyUsage DigitalSignature `
    -TextExtension @("2.5.29.37={text}1.3.6.1.5.5.7.3.3") `
    -KeyExportPolicy Exportable -KeyAlgorithm RSA -KeyLength 2048 `
    -FriendlyName "BiliDownTestRoot" `
    -NotAfter (Get-Date).AddYears(3)
Write-Host "   created: $($cert.Thumbprint)" -ForegroundColor Green

Export-PfxCertificate -Cert $cert -FilePath $PFX_PATH -Password $CERT_PWD -Force | Out-Null
Export-Certificate -Cert $cert -FilePath $CER_PATH -Force | Out-Null
Write-Host "   exported: test_sign.pfx / test_sign.cer" -ForegroundColor Green

# 3. Trusted Root + Trusted People
Write-Host "[2/4] Add to Trusted Root / Trusted People..." -ForegroundColor Green
certutil -addstore -f Root $CER_PATH | Out-Null
Write-Host "   root exit=$LASTEXITCODE" -ForegroundColor Yellow
certutil -addstore -f TrustedPeople $CER_PATH | Out-Null
Write-Host "   trustedpeople exit=$LASTEXITCODE" -ForegroundColor Yellow

# 4. Copy + sign the msix
Write-Host "[3/4] Sign MSIX..." -ForegroundColor Green
$srcMsix = Get-ChildItem $OUTPUT_DIR -Filter "*.msix" | Where-Object { $_.Name -notlike '*TEST*' } | Select-Object -First 1
if (-not $srcMsix) {
    Write-Host "[ERR] No msix found in output/. Run build_msix.py first." -ForegroundColor Red
    exit 1
}
$testMsix = Join-Path $OUTPUT_DIR ($srcMsix.BaseName + "_TEST.msix")
Copy-Item $srcMsix.FullName $testMsix -Force

& $SIGNTOOL sign /fd SHA256 /a /f $PFX_PATH /p Test2026 $testMsix 2>&1
Write-Host "   sign exit=$LASTEXITCODE" -ForegroundColor Yellow

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERR] Sign failed" -ForegroundColor Red
    exit 1
}

# 5. Verify
Write-Host "[4/4] Verify..." -ForegroundColor Green
& $SIGNTOOL verify /pa /v $testMsix 2>&1 | Select-Object -Last 8

Write-Host ""
Write-Host "=== DONE ===" -ForegroundColor Cyan
Write-Host "TEST package: $testMsix" -ForegroundColor White
Write-Host "Self-signed cert is trusted on THIS machine only. NOT for the Store." -ForegroundColor Yellow