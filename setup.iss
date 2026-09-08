; B站视频解析下载工具 Inno Setup 安装脚本
; 用法：ISCC.exe setup.iss
; 输出：Output\BilibiliDownloader_Setup_V2.1.exe

#define MyAppName "B站视频解析下载工具"
#define MyAppVersion "2.1"
#define MyAppExeName "BilibiliDownloader.exe"
#define MyAppUninstallerName "unins000.exe"
#define MyAppPublisher "BilibiliDownloadTool"
#define MyAppURL "https://www.bilidown.cn"
#define MyAppId "{{B6F8F7E1-2A3B-4C5D-6E7F-8A9B0C1D2E3F}"

[Setup]
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={localappdata}\BilibiliDownloadTool
DefaultGroupName={#MyAppName}
OutputDir=Output
OutputBaseFilename=BilibiliDownloader_Setup_V{#MyAppVersion}
SetupIconFile=logo.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64
DisableProgramGroupPage=yes
Uninstallable=yes
CreateAppDir=yes
CreateUninstallRegKey=yes
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName}
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}
MinVersion=0,6.1

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Messages]
chinesesimp.WelcomeLabel1=欢迎使用 {#MyAppName} V{#MyAppVersion} 安装向导
chinesesimp.SelectDirLabel=请选择安装目录：
chinesesimp.SelectDirBrowseLabel=点击"浏览"选择其他目录，点击"下一步"继续。
chinesesimp.FinishedHeadingLabel=安装完成！
chinesesimp.FinishedLabel2={#MyAppName} 已成功安装到您的计算机。

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加图标："; Flags: unchecked
Name: "startmenuicon"; Description: "创建开始菜单快捷方式"; GroupDescription: "附加图标："; Flags: checkedonce

[Files]
; 主程序所有文件（来自 dist\BilibiliDownloader\ 目录）
Source: "dist\BilibiliDownloader\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\logo.ico"
Name: "{group}\卸载 {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\logo.ico"; Tasks: desktopicon
Name: "{commonprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\logo.ico"; Tasks: startmenuicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "立即启动 {#MyAppName}"; Flags: nowait postinstall skipifsilent unchecked

[UninstallDelete]
Type: filesandordirs; Name: "{app}\log"
Type: filesandordirs; Name: "{app}\cookie.txt"
Type: filesandordirs; Name: "{app}\download_history.json"
Type: dirifempty; Name: "{app}"

[Registry]
Root: HKCU; Subkey: "Software\BilibiliDownloadTool"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\BilibiliDownloadTool"; ValueType: string; ValueName: "Version"; ValueData: "{#MyAppVersion}"; Flags: uninsdeletekey
