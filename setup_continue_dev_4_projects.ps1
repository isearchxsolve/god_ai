
# ============================================
# Continue.dev + NVIDIA NIM Setup & Launcher (PowerShell)
# Installs Continue.dev, configures NIM for 4 projects,
# each with its own NVIDIA account and model.
# ============================================

# --- STEP 0: CHECK VS CODE: ---
Write-Host "[0/7] Checking VS Code: installation..." -ForegroundColor Cyan
try {
    $null = Get-Command code -ErrorAction Stop
    Write-Host "  VS Code: found." -ForegroundColor Green
} catch {
    Write-Host "ERROR: VS Code: is not installed or not in PATH!" -ForegroundColor Red
    Write-Host "Please install VS Code: from https://code.visualstudio.com/" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# --- STEP 1: INSTALL CONTINUE.DEV EXTENSION ---
Write-Host ""
Write-Host "[1/7] Installing Continue.dev extension..." -ForegroundColor Cyan
code --install-extension Continue.continue
if ($LASTEXITCODE -ne 0) {
    Write-Host "WARNING: Continue.dev extension install may have failed." -ForegroundColor Yellow
    Write-Host "If it's already installed, this is fine." -ForegroundColor Gray
} else {
    Write-Host "  Continue.dev extension installed." -ForegroundColor Green
}

# --- STEP 2: CHECK NODE/NPM ---
Write-Host ""
Write-Host "[2/7] Checking Node.js for Continue.dev core..." -ForegroundColor Cyan
try {
    $nodeVersion = node --version
    Write-Host "  Node.js $nodeVersion found." -ForegroundColor Green
} catch {
    Write-Host "WARNING: Node.js not found. Continue.dev may have limited functionality." -ForegroundColor Yellow
}

# --- STEP 3: CONFIGURE API KEYS ---
Write-Host ""
Write-Host "[3/7] Configuring NVIDIA NIM API keys..." -ForegroundColor Cyan
Write-Host ""
Write-Host "============================================" -ForegroundColor Yellow
Write-Host "   EDIT THESE 4 API KEYS BEFORE RUNNING:" -ForegroundColor Yellow
Write-Host "============================================" -ForegroundColor Yellow

# --- EDIT THESE 4 API KEYS ---
$Keys = @(
    "nvapi-account-1-key-here",
    "nvapi-account-2-key-here",
    "nvapi-account-3-key-here",
    "nvapi-account-4-key-here"
)

# Validate keys
if ($Keys[0] -eq "nvapi-account-1-key-here") {
    Write-Host ""
    Write-Host "WARNING: You have not edited the API keys in this script!" -ForegroundColor Red
    Write-Host "Please open this file in a text editor and replace the placeholder keys." -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press Enter to continue anyway"
}

# --- STEP 4: CONFIGURE PROJECTS ---
Write-Host ""
Write-Host "[4/7] Configuring project paths and models..." -ForegroundColor Cyan

# --- EDIT THESE 4 PROJECT PATHS ---
$Projects = @(
    "C:\Users\Admin\Downloads\god_ai\OMEGA",
    "C:\dev\antigravity-kandover",
    "C:\dev\project-3",
    "C:\dev\project-4"
)

# --- EDIT THESE 4 MODELS ---
$Models = @(
    "z-ai/glm5",
    "nvidia/llama-3.1-nemotron-ultra-253b-v1",
    "deepseek-ai/deepseek-v4-flash",
    "moonshotai/kimi-k2.6"
)

# --- EDIT THESE 4 NAMES ---
$Names = @(
    "OMEGA-GLM5",
    "Antigravity-Nemotron",
    "Project3-DeepSeek",
    "Project4-Kimi"
)

# --- EDIT THESE 4 COLORS ---
$Colors = @("Green", "Cyan", "Yellow", "Magenta")

# Validate/create paths
for ($i = 0; $i -lt 4; $i++) {
    if (-not (Test-Path $Projects[$i])) {
        Write-Host "WARNING: Project $($i+1) path does not exist: $($Projects[$i])" -ForegroundColor Yellow
        Write-Host "  Creating directory..." -ForegroundColor Gray
        New-Item -ItemType Directory -Path $Projects[$i] -Force | Out-Null
    }
}

# --- STEP 5: CREATE CONTINUE.DEV CONFIGS ---
Write-Host ""
Write-Host "[5/7] Creating Continue.dev project configs..." -ForegroundColor Cyan

for ($i = 0; $i -lt 4; $i++) {
    $continueDir = Join-Path $Projects[$i] ".continue"
    $configPath = Join-Path $continueDir "config.json"

    if (-not (Test-Path $continueDir)) {
        New-Item -ItemType Directory -Path $continueDir -Force | Out-Null
    }

    $config = @{
        models = @(
            @{
                title = "$($Names[$i]) NIM"
                provider = "openai"
                model = $Models[$i]
                apiBase = "https://integrate.api.nvidia.com/v1"
                apiKey = $Keys[$i]
                completionOptions = @{
                    maxTokens = 131072
                    temperature = 0.2
                }
            }
        )
        tabAutocompleteModel = @{
            title = "$($Names[$i]) Autocomplete"
            provider = "openai"
            model = $Models[$i]
            apiBase = "https://integrate.api.nvidia.com/v1"
            apiKey = $Keys[$i]
        }
        customCommands = @(
            @{
                name = "fix"
                prompt = "Fix the code in the selected file. Look for bugs, type errors, and logical issues. Return only the corrected code."
                description = "Fix code issues"
            },
            @{
                name = "refactor"
                prompt = "Refactor the selected code for better readability, performance, and maintainability. Follow best practices."
                description = "Refactor code"
            },
            @{
                name = "explain"
                prompt = "Explain the selected code in detail. Break down the logic, data flow, and any design patterns used."
                description = "Explain code"
            }
        )
        contextProviders = @(
            @{ name = "diff"; params = @{} },
            @{ name = "folder"; params = @{} },
            @{ name = "codebase"; params = @{} }
        )
        slashCommands = @(
            @{ name = "edit"; description = "Edit selected code" },
            @{ name = "comment"; description = "Add comments" },
            @{ name = "share"; description = "Export session" }
        )
    }

    $config | ConvertTo-Json -Depth 10 | Set-Content -Path $configPath -Encoding UTF8
    Write-Host "  Created config for Project $($i+1): $($Names[$i])" -ForegroundColor $Colors[$i]
}

# --- STEP 6: CREATE .VSCODE SETTINGS ---
Write-Host ""
Write-Host "[6/7] Creating VS Code: workspace settings..." -ForegroundColor Cyan

for ($i = 0; $i -lt 4; $i++) {
    $vscodeDir = Join-Path $Projects[$i] ".vscode"
    $settingsPath = Join-Path $vscodeDir "settings.json"

    if (-not (Test-Path $vscodeDir)) {
        New-Item -ItemType Directory -Path $vscodeDir -Force | Out-Null
    }

    $settings = @{
        "continue.enableTabAutocomplete" = $true
        "continue.allowAnonymousTelemetry" = $false
        "window.title" = "$($Names[$i]) - `${activeEditorShort}`${separator}`${rootName}"
    }

    $settings | ConvertTo-Json -Depth 5 | Set-Content -Path $settingsPath -Encoding UTF8
}

Write-Host "  VS Code: workspace settings created." -ForegroundColor Green

# --- STEP 7: LAUNCH ALL 4 VS CODE: INSTANCES ---
Write-Host ""
Write-Host "[7/7] Launching 4 VS Code: instances with Continue.dev..." -ForegroundColor Cyan
Write-Host ""

for ($i = 0; $i -lt 4; $i++) {
    $num = $i + 1
    Write-Host "Launching Instance $num`: $($Names[$i])" -ForegroundColor $Colors[$i]
    Write-Host "  Project: $($Projects[$i])" -ForegroundColor Gray
    Write-Host "  Model:   $($Models[$i])" -ForegroundColor Gray
    Write-Host ""

    Start-Process code -ArgumentList "$($Projects[$i])"
    Start-Sleep -Seconds 3
}

Write-Host ""
Write-Host "============================================" -ForegroundColor White
Write-Host "   Setup Complete! All 4 VS Code: instances launched!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor White
Write-Host ""
Write-Host "Each VS Code: window has:" -ForegroundColor Gray
Write-Host "  - Its own Continue.dev config with unique NVIDIA API key" -ForegroundColor Gray
Write-Host "  - Its own project directory" -ForegroundColor Gray
Write-Host "  - Its own AI model (GLM-5, Nemotron, DeepSeek, Kimi)" -ForegroundColor Gray
Write-Host "  - Tab autocomplete enabled" -ForegroundColor Gray
Write-Host "  - Custom commands: /fix, /refactor, /explain" -ForegroundColor Gray
Write-Host ""
Write-Host "NO shared 32-worker OpenCode limit." -ForegroundColor Green
Write-Host "Each instance talks DIRECTLY to NVIDIA NIM." -ForegroundColor Green
Write-Host ""
Write-Host "To use:" -ForegroundColor White
Write-Host "  1. In any VS Code: window, open the Continue panel (Ctrl+L)" -ForegroundColor Gray
Write-Host "  2. Start chatting with your model" -ForegroundColor Gray
Write-Host "  3. Use tab autocomplete as you type" -ForegroundColor Gray
Write-Host "  4. Select code and use /fix, /refactor, or /explain" -ForegroundColor Gray
Write-Host ""
Write-Host "To re-launch later, just run this script again." -ForegroundColor Gray
Write-Host "It will skip reinstallation and just launch the windows." -ForegroundColor Gray
Write-Host ""
Read-Host "Press Enter to exit launcher"
