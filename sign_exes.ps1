<#
.SYNOPSIS
    对 output 目录下所有 exe 创建自签名证书并签名（兼容所有 Windows 版本）
.DESCRIPTION
    需以管理员身份运行
#>

$ErrorActionPreference = "Stop"
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Definition
$OUTPUT_DIR = Join-Path $SCRIPT_DIR "output"
$CERT_SUBJECT = "CN=寒烟似雪"
$CERT_PWD = ConvertTo-SecureString -String "BiliDown2026" -Force -AsPlainText
$PFX_PATH = Join-Path $SCRIPT_DIR "BilibiliDownloader_dev.pfx"
$CER_PATH = Join-Path $SCRIPT_DIR "BilibiliDownloader_dev.cer"

Write-Host "=== BilibiliDownloader exe 签名脚本 ===" -ForegroundColor Cyan
Write-Host ""

# 检查管理员权限
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "[错误] 请以管理员身份运行此脚本" -ForegroundColor Red
    exit 1
}

# 步骤1: 创建/复用自签名代码签名证书
Write-Host "[1/5] 创建自签名代码签名证书..." -ForegroundColor Green
$existingCert = Get-ChildItem "Cert:\CurrentUser\My" -CodeSigningCert -ErrorAction SilentlyContinue | Where-Object { $_.Subject -eq $CERT_SUBJECT } | Select-Object -First 1
if ($existingCert) {
    Write-Host "  已存在相同主题的证书，复用: $($existingCert.Thumbprint)" -ForegroundColor Yellow
    $cert = $existingCert
} else {
    try {
        $cert = New-SelfSignedCertificate -Type CodeSigningCert `
            -Subject $CERT_SUBJECT `
            -KeyUsage DigitalSignature `
            -FriendlyName "寒烟似雪" `
            -CertStoreLocation "Cert:\CurrentUser\My" `
            -KeyAlgorithm RSA -KeyLength 2048 `
            -NotAfter (Get-Date).AddYears(3) `
            -TextExtension @("2.5.29.37={text}1.3.6.1.5.5.7.3.3","2.5.29.19={text}")
        Write-Host "  证书创建成功: $($cert.Thumbprint)" -ForegroundColor Green
    } catch {
        Write-Host "[错误] 证书创建失败: $_" -ForegroundColor Red
        exit 1
    }
}

$thumbprint = $cert.Thumbprint
Write-Host "  指纹: $thumbprint" -ForegroundColor Green

# 导出 cer 和 pfx
Write-Host "[2/5] 导出证书文件..." -ForegroundColor Green
try {
    Export-Certificate -Cert $cert -FilePath $CER_PATH -Force | Out-Null
    Write-Host "  已导出 cer: BilibiliDownloader_dev.cer" -ForegroundColor Green
} catch {
    # 用 certutil 导出
    certutil -store CurrentUser My $thumbprint $CER_PATH 2>&1 | Out-Null
    if (Test-Path $CER_PATH) {
        Write-Host "  已导出 cer (certutil)" -ForegroundColor Green
    } else {
        Write-Host "[错误] 无法导出证书" -ForegroundColor Red
        exit 1
    }
}

try {
    Export-PfxCertificate -Cert $cert -FilePath $PFX_PATH -Password $CERT_PWD -Force | Out-Null
    Write-Host "  已导出 pfx: BilibiliDownloader_dev.pfx" -ForegroundColor Green
} catch {
    Write-Host "[警告] pfx 导出失败（不影响签名）: $_" -ForegroundColor Yellow
}

# 步骤3: 用 certutil 添加到受信任根证书颁发机构（兼容所有 Windows 版本）
Write-Host "[3/5] 添加到受信任根证书颁发机构..." -ForegroundColor Green
$rootResult = certutil -addstore -f Root $CER_PATH 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  已添加到受信任根证书" -ForegroundColor Green
} else {
    Write-Host "[警告] 添加到受信任根失败: $rootResult" -ForegroundColor Yellow
}

# 步骤4: 添加到受信任发布者
Write-Host "[4/5] 添加到受信任发布者..." -ForegroundColor Green
$pubResult = certutil -addstore -f TrustedPublisher $CER_PATH 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  已添加到受信任发布者" -ForegroundColor Green
} else {
    Write-Host "[警告] 添加到受信任发布者失败: $pubResult" -ForegroundColor Yellow
}

# 步骤5: 签名所有 exe
Write-Host "[5/5] 签名 exe 文件..." -ForegroundColor Green
$exeFiles = @()

$mainExe = Join-Path $SCRIPT_DIR "dist\BilibiliDownloader\BilibiliDownloader.exe"
$uninstExe = Join-Path $SCRIPT_DIR "dist\BilibiliDownloader\uninstaller.exe"
if (Test-Path $mainExe) { $exeFiles += $mainExe }
if (Test-Path $uninstExe) { $exeFiles += $uninstExe }

if (Test-Path $OUTPUT_DIR) {
    $exeFiles += Get-ChildItem $OUTPUT_DIR -Filter "*.exe" -File | ForEach-Object { $_.FullName }
}

if ($exeFiles.Count -eq 0) {
    Write-Host "[错误] 未找到任何 exe 文件，请先运行 python build.py" -ForegroundColor Red
    exit 1
}

$success = 0
$failed = 0
foreach ($exe in $exeFiles) {
    $name = Split-Path $exe -Leaf
    # 检查文件是否被占用
    try {
        $stream = [System.IO.File]::Open($exe, 'Open', 'ReadWrite', 'None')
        $stream.Close()
    } catch {
        Write-Host "  [跳过] $name : 文件被占用，请关闭正在运行的程序" -ForegroundColor Yellow
        $failed++
        continue
    }

    try {
        $result = Set-AuthenticodeSignature -FilePath $exe -Certificate $cert -HashAlgorithm SHA256 -TimestampServer "http://timestamp.digicert.com"
        if ($result.Status -eq "Valid") {
            $size = [math]::Round((Get-Item $exe).Length / 1MB, 1)
            Write-Host "  [OK] $name ($size MB)" -ForegroundColor Green
            $success++
        } elseif ($result.Status -eq "HashMismatch") {
            # 已签名但 hash 不匹配，先移除旧签名再签
            Write-Host "  [重签] $name : 移除旧签名..." -ForegroundColor Yellow
            $removeResult = & certutil -delsignature $exe 2>&1
            $result2 = Set-AuthenticodeSignature -FilePath $exe -Certificate $cert -HashAlgorithm SHA256 -TimestampServer "http://timestamp.digicert.com"
            if ($result2.Status -eq "Valid") {
                $size = [math]::Round((Get-Item $exe).Length / 1MB, 1)
                Write-Host "  [OK] $name ($size MB)" -ForegroundColor Green
                $success++
            } else {
                Write-Host "  [失败] $name : $($result2.Status) - $($result2.StatusMessage)" -ForegroundColor Red
                $failed++
            }
        } else {
            Write-Host "  [失败] $name : $($result.Status) - $($result.StatusMessage)" -ForegroundColor Red
            $failed++
        }
    } catch {
        Write-Host "  [异常] $name : $_" -ForegroundColor Red
        $failed++
    }
}

Write-Host ""
Write-Host "=== 签名完成 ===" -ForegroundColor Cyan
Write-Host "成功: $success, 失败: $failed" -ForegroundColor $(if ($failed -eq 0) { "Green" } else { "Yellow" })
Write-Host ""
Write-Host "证书已安装到本机:" -ForegroundColor Green
Write-Host "  - 受信任根证书颁发机构（本机信任此证书）" -ForegroundColor White
Write-Host "  - 受信任发布者（本机运行不再弹窗）" -ForegroundColor White
Write-Host ""
Write-Host "注意:" -ForegroundColor Yellow
Write-Host "  - 自签名证书仅在本机有效" -ForegroundColor White
Write-Host "  - 分发给新设备时需让对方先运行 cert_installer.exe 安装证书" -ForegroundColor White
Write-Host "  - 360等行为检测类报毒需单独添加信任" -ForegroundColor White
