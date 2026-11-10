param(
    [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA 'Programs\Celvo'),
    [string]$DataRoot = (Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'Celvo'),
    [string]$WhisperRuntimeUrl = 'https://github.com/ggml-org/whisper.cpp/releases/download/b5454/whisper-bin-x64.zip',
    [string]$WhisperRuntimeSha256 = '6ba69e3482d7826214f90a6a9c84ca07782aec1e1d0c6a7c30c994fd5d816ccb',
    [switch]$BuildWhisper
)

$ErrorActionPreference = 'Stop'
$WhisperVersion = 'v1.9.5'
$WhisperCommit = 'd1be6fde11ac6e0407606b4e42fe72d34add8037'
$ModelName = 'ggml-large-v3.bin'
$ModelUrl = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/$ModelName"
$ModelSha256 = '64d182b440b98d5203c4f9bd541544d84c605196c4f7b845dfa11fb23594d1e2'

function Invoke-Checked([string]$Program, [string[]]$Arguments, [switch]$Quiet) {
    if ($Quiet) {
        $previousPreference = $ErrorActionPreference
        try {
            # Windows PowerShell 5.1 promotes native stderr lines to errors, even
            # for commands such as whisper-cli --help that legitimately use stderr.
            $ErrorActionPreference = 'Continue'
            & $Program @Arguments 1> $null 2> $null
            $exitCode = $LASTEXITCODE
        } finally { $ErrorActionPreference = $previousPreference }
    } else {
        & $Program @Arguments
        $exitCode = $LASTEXITCODE
    }
    if ($exitCode -ne 0) { throw "Command failed ($exitCode): $Program $($Arguments -join ' ')" }
}

function Get-Python {
    $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
    if (-not $launcher) { throw 'Python 3.10–3.13 was not found. Install 64-bit Python and its py launcher, then rerun install.ps1.' }
    foreach ($minor in 13..10) {
        $tag = "-3.$minor"
        & $launcher.Source $tag -c "import sys, struct; print(sys.version_info[:2])" *> $null
        if ($LASTEXITCODE -eq 0) {
            $bits = (& $launcher.Source $tag -c "import struct; print(struct.calcsize('P') * 8)").Trim()
            if ($bits -ne '64') { continue }
            $version = (& $launcher.Source $tag -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')").Trim()
            return @{ Program = $launcher.Source; Args = @($tag); Version = $version }
        }
    }
    throw 'A compatible CPython 3.10, 3.11, 3.12, or 3.13 installation is required.'
}

function Receive-VerifiedFile([string]$Url, [string]$Destination, [string]$ExpectedHash, [long]$MinimumBytes) {
    $partial = "$Destination.download"
    New-Item -ItemType Directory -Force (Split-Path -Parent $Destination) | Out-Null
    if ((Test-Path $Destination) -and (Get-FileHash $Destination -Algorithm SHA256).Hash.ToLowerInvariant() -eq $ExpectedHash) {
        Write-Host "Verified existing file: $Destination"
        return
    }
    Add-Type -AssemblyName System.Net.Http
    $handler = New-Object System.Net.Http.HttpClientHandler
    $handler.AllowAutoRedirect = $true
    $client = New-Object System.Net.Http.HttpClient($handler)
    $client.Timeout = [System.Threading.Timeout]::InfiniteTimeSpan
    $stream = $null
    $response = $null
    try {
        $existingLength = if (Test-Path $partial) { (Get-Item $partial).Length } else { [long]0 }
        $request = New-Object System.Net.Http.HttpRequestMessage([System.Net.Http.HttpMethod]::Get, $Url)
        if ($existingLength -gt 0) {
            $request.Headers.Range = New-Object System.Net.Http.Headers.RangeHeaderValue($existingLength, $null)
            Write-Host "Resuming download at $([math]::Round($existingLength / 1MB, 1)) MB."
        } else { Write-Host "Downloading $Url" }
        $response = $client.SendAsync($request, [System.Net.Http.HttpCompletionOption]::ResponseHeadersRead).GetAwaiter().GetResult()
        $null = $response.EnsureSuccessStatusCode()
        $append = $existingLength -gt 0 -and $response.StatusCode -eq [System.Net.HttpStatusCode]::PartialContent
        if ($existingLength -gt 0 -and -not $append) {
            Write-Warning 'The server did not accept the resume range; restarting the download.'
            $existingLength = 0
        }
        $streamMode = if ($append) { [System.IO.FileMode]::Append } else { [System.IO.FileMode]::Create }
        $stream = New-Object System.IO.FileStream($partial, $streamMode, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None, 1048576, [System.IO.FileOptions]::SequentialScan)
        $input = $response.Content.ReadAsStreamAsync().GetAwaiter().GetResult()
        $buffer = New-Object byte[] 1048576
        $received = $existingLength
        $contentLength = $response.Content.Headers.ContentLength
        $total = if ($contentLength) { $contentLength + $existingLength } else { 0 }
        $lastProgress = [datetime]::UtcNow
        while (($read = $input.Read($buffer, 0, $buffer.Length)) -gt 0) {
            $stream.Write($buffer, 0, $read)
            $received += $read
            if (([datetime]::UtcNow - $lastProgress).TotalMilliseconds -ge 500) {
                if ($total -gt 0) {
                    $percent = [math]::Min(100, [math]::Floor(100 * $received / $total))
                    Write-Progress -Activity 'Downloading Celvo model' -Status "$([math]::Round($received / 1GB, 2)) / $([math]::Round($total / 1GB, 2)) GB" -PercentComplete $percent
                } else { Write-Progress -Activity 'Downloading Celvo model' -Status "$([math]::Round($received / 1GB, 2)) GB received" }
                $lastProgress = [datetime]::UtcNow
            }
        }
        $stream.Flush($true)
        Write-Progress -Activity 'Downloading Celvo model' -Completed
    } catch {
        throw "Download failed or was interrupted. The partial file was preserved so a rerun can resume it. $($_.Exception.Message)"
    } finally {
        if ($stream) { $stream.Dispose() }
        if ($response) { $response.Dispose() }
        if ($client) { $client.Dispose() }
        if ($handler) { $handler.Dispose() }
    }
    $file = Get-Item $partial
    if ($file.Length -lt $MinimumBytes) { throw "Downloaded file is too small ($($file.Length) bytes); partial data was preserved for retry." }
    $actualHash = (Get-FileHash $partial -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -ne $ExpectedHash) {
        $bad = "$partial.invalid-$(Get-Date -Format yyyyMMddHHmmss)"
        Move-Item -LiteralPath $partial -Destination $bad
        throw "SHA-256 verification failed. The invalid download was preserved at $bad; rerun to download again."
    }
    if (Test-Path $Destination) {
        $backup = "$Destination.invalid-$(Get-Date -Format yyyyMMddHHmmss)"
        Move-Item -LiteralPath $Destination -Destination $backup
        Write-Warning "Preserved the previous invalid file at $backup"
    }
    Move-Item -LiteralPath $partial -Destination $Destination
}

function Install-WhisperRuntime([string]$Destination, [string]$Scratch) {
    if ($BuildWhisper) {
        $cmake = Get-Command cmake.exe -ErrorAction SilentlyContinue
        $git = Get-Command git.exe -ErrorAction SilentlyContinue
        $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
        $vsInstall = if (Test-Path $vswhere) {
            & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
        }
        if (-not $cmake -or -not $git -or -not $vsInstall) {
            throw 'Building whisper.cpp requires Git, CMake, and Visual Studio C++ x64 build tools. Install them or use the pinned prebuilt runtime.'
        }
        $source = Join-Path $Scratch 'whisper.cpp'
        Invoke-Checked $git.Source @('clone', '--depth', '1', '--branch', $WhisperVersion, 'https://github.com/ggml-org/whisper.cpp.git', $source)
        $actualCommit = (& $git.Source -C $source rev-parse HEAD).Trim()
        if ($actualCommit -ne $WhisperCommit) { throw "whisper.cpp tag did not resolve to the pinned commit ($actualCommit)." }
        Invoke-Checked $cmake.Source @(
            '-S', $source, '-B', "$source\build", '-DWHISPER_BUILD_TESTS=OFF',
            '-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreaded'
        )
        Invoke-Checked $cmake.Source @('--build', "$source\build", '--config', 'Release', '--target', 'whisper-cli', '--parallel')
        $exe = Get-ChildItem "$source\build" -Filter whisper-cli.exe -Recurse | Select-Object -First 1
        if (-not $exe) { throw 'CMake completed without producing whisper-cli.exe.' }
        New-Item -ItemType Directory -Force $Destination | Out-Null
        Copy-Item $exe.FullName $Destination
        Get-ChildItem "$source\build" -Filter *.dll -Recurse | ForEach-Object { Copy-Item $_.FullName $Destination -Force }
        Invoke-Checked (Join-Path $Destination 'whisper-cli.exe') @('--help') -Quiet
        Invoke-Checked (Join-Path $Destination 'whisper-cli.exe') @('--version') -Quiet
        return
    }

    $zip = Join-Path (Join-Path $InstallRoot 'downloads') 'whisper-windows-x64.zip'
    $expected = $WhisperRuntimeSha256.ToLowerInvariant()
    if ($expected -notmatch '^[a-f0-9]{64}$') {
        throw 'The pinned whisper.cpp runtime SHA-256 value is invalid.'
    }
    Receive-VerifiedFile $WhisperRuntimeUrl $zip $expected 1000000
    $extract = Join-Path $Scratch 'whisper-runtime'
    Expand-Archive -LiteralPath $zip -DestinationPath $extract -Force
    $exe = Get-ChildItem $extract -Filter whisper-cli.exe -Recurse | Select-Object -First 1
    if (-not $exe) { throw 'The downloaded whisper.cpp package does not contain whisper-cli.exe.' }
    New-Item -ItemType Directory -Force $Destination | Out-Null
    Copy-Item "$($exe.Directory.FullName)\*" $Destination -Recurse -Force
    Invoke-Checked (Join-Path $Destination 'whisper-cli.exe') @('--help') -Quiet
    Invoke-Checked (Join-Path $Destination 'whisper-cli.exe') @('--version') -Quiet
}

$os = Get-CimInstance Win32_OperatingSystem
if ([int]$os.BuildNumber -lt 22000) { throw "Celvo's native installer requires Windows 11 (build 22000+); detected build $($os.BuildNumber)." }
if ($env:PROCESSOR_ARCHITECTURE -ne 'AMD64') { throw 'Celvo currently supports x64 Windows 11. Windows ARM64 is not supported by the current audio dependency.' }
$python = Get-Python
Invoke-Checked $python.Program (@($python.Args) + @('-c', 'import tkinter'))
$repoRoot = $PSScriptRoot
if (-not (Test-Path (Join-Path $repoRoot 'pyproject.toml'))) { throw 'Run install.ps1 from a Celvo source checkout.' }
foreach ($target in @($InstallRoot, $DataRoot, [IO.Path]::GetTempPath())) {
    $drive = [IO.Path]::GetPathRoot([IO.Path]::GetFullPath($target))
    $free = (Get-PSDrive -Name $drive.Substring(0, 1) -ErrorAction SilentlyContinue).Free
    if ($free -and $free -lt 7GB) { throw "At least 7 GB of free space is required on drive $drive for the full-precision model and installation files." }
}

$version = (Get-Content (Join-Path $repoRoot 'pyproject.toml') | Select-String '^version\s*=\s*"([^"]+)"').Matches.Groups[1].Value
if (-not $version) { throw 'Could not read Celvo version from pyproject.toml.' }
$guid = [guid]::NewGuid().ToString('N').Substring(0, 8)
$versionDir = Join-Path (Join-Path $InstallRoot 'versions') "$version-$guid"
$scratch = Join-Path ([IO.Path]::GetTempPath()) "celvo-install-$guid"
$dataModels = Join-Path $DataRoot 'models'
$model = Join-Path $dataModels $ModelName
$runtime = Join-Path $versionDir 'venv\Lib\site-packages\bin'

New-Item -ItemType Directory -Force $scratch, $InstallRoot, (Split-Path -Parent $versionDir), $dataModels | Out-Null
try {
    $runtimeStage = Join-Path $scratch 'runtime-ready'
    Install-WhisperRuntime $runtimeStage $scratch
    Receive-VerifiedFile $ModelUrl $model $ModelSha256 3000000000
    $source = Join-Path $versionDir 'source'
    New-Item -ItemType Directory -Force $source | Out-Null
    Get-ChildItem -LiteralPath $repoRoot -Force |
        Where-Object Name -notin @('.git', '.venv', '.pytest_cache', '.ruff_cache', '__pycache__', 'models', 'work') |
        ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $source -Recurse -Force }
    $venv = Join-Path $versionDir 'venv'
    Invoke-Checked $python.Program (@($python.Args) + @('-m', 'venv', $venv))
    $pip = Join-Path $venv 'Scripts\python.exe'
    Invoke-Checked $pip @('-m', 'pip', 'install', '--upgrade', 'pip')
    Invoke-Checked $pip @('-m', 'pip', 'install', $source)
    New-Item -ItemType Directory -Force $runtime | Out-Null
    Copy-Item "$runtimeStage\*" $runtime -Recurse -Force
    $celvoExe = Join-Path $venv 'Scripts\celvo.exe'
    if (-not (Test-Path $celvoExe)) { throw 'Python package installation did not create celvo.exe.' }
    $previousDataRoot = $env:CELVO_DATA_DIR
    $env:CELVO_DATA_DIR = $DataRoot
    try {
        Invoke-Checked $celvoExe @('--version')
        Invoke-Checked $celvoExe @('diagnose')
    } finally {
        $env:CELVO_DATA_DIR = $previousDataRoot
    }

    $bin = Join-Path $InstallRoot 'bin'
    New-Item -ItemType Directory -Force $bin | Out-Null
    $shim = Join-Path $bin 'celvo.cmd'
    $shimLines = @(
        '@echo off',
        "if not defined CELVO_DATA_DIR set `"CELVO_DATA_DIR=$DataRoot`"",
        "`"$celvoExe`" %*"
    )
    $shimText = $shimLines -join "`r`n"
    $shimTemp = "$shim.new"
    Set-Content -LiteralPath $shimTemp -Value $shimText -Encoding ascii
    Move-Item -LiteralPath $shimTemp -Destination $shim -Force
    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    $entries = @($userPath -split ';' | Where-Object { $_ })
    $alreadyPresent = $entries | Where-Object { $_.TrimEnd('\') -ieq $bin.TrimEnd('\') }
    if (-not $alreadyPresent) {
        [Environment]::SetEnvironmentVariable('Path', (($entries + $bin) -join ';'), 'User')
    }
    $startMenu = Join-Path ([Environment]::GetFolderPath('Programs')) 'Celvo'
    New-Item -ItemType Directory -Force $startMenu | Out-Null
    $pythonw = Join-Path $venv 'Scripts\pythonw.exe'
    if (-not (Test-Path $pythonw)) { throw 'The virtual environment did not provide pythonw.exe for the desktop shortcut.' }
    $shortcutPath = Join-Path $startMenu 'Celvo.lnk'
    $uiBootstrapPath = Join-Path $bin 'celvo-ui.pyw'
    $dataRootLiteral = ConvertTo-Json -InputObject $DataRoot -Compress
    $uiBootstrap = @"
import os
os.environ.setdefault("CELVO_DATA_DIR", $dataRootLiteral)
from celvo.ui.app import launch_ui
launch_ui()
"@
    Set-Content -LiteralPath $uiBootstrapPath -Value $uiBootstrap -Encoding UTF8
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $pythonw
    $shortcut.Arguments = "`"$uiBootstrapPath`""
    $shortcut.WorkingDirectory = $DataRoot
    $shortcut.Description = 'Private, offline audio recording and transcription'
    $shortcut.Save()
    Write-Host "Celvo $version installed for Python $($python.Version)."
    Write-Host "Start menu shortcut: $shortcutPath"
    Write-Host "Open a new terminal, then run: celvo --help"
    Write-Host "Record: celvo record"
    Write-Host "Transcribe: celvo process"
} catch {
    throw "Installation failed. The previous Celvo installations and user recordings were left in place. $($_.Exception.Message)"
} finally {
    Remove-Item -LiteralPath $scratch -Recurse -Force -ErrorAction SilentlyContinue
}
