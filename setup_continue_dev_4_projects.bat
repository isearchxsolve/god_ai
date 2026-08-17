@echo off
REM ============================================
REM Continue.dev + NVIDIA NIM Setup & Launcher
REM Installs Continue.dev, configures NIM for 4 projects,
REM each with its own NVIDIA account and model.
REM ============================================

echo ============================================
echo   Continue.dev + NVIDIA NIM Setup ^& Launcher
echo ============================================
echo.

REM --- STEP 0: CHECK VS CODE: ---
echo [0/7] Checking VS Code: installation...
where code >nul 2>&1
if errorlevel 1 (
    echo ERROR: VS Code: is not installed or not in PATH!
    echo Please install VS Code: from https://code.visualstudio.com/
    pause
    exit /b 1
)
echo   VS Code: found.

REM --- STEP 1: INSTALL CONTINUE.DEV EXTENSION ---
echo.
echo [1/7] Installing Continue.dev extension...
code --install-extension Continue.continue
if errorlevel 1 (
    echo WARNING: Continue.dev extension install may have failed.
    echo If it's already installed, this is fine.
)
echo   Continue.dev extension ready.

REM --- STEP 2: CHECK NODE/NPM (for Continue.dev server) ---
echo.
echo [2/7] Checking Node.js for Continue.dev core...
node --version >nul 2>&1
if errorlevel 1 (
    echo WARNING: Node.js not found. Continue.dev may have limited functionality.
    echo Consider installing Node.js from https://nodejs.org/
)

REM --- STEP 3: CONFIGURE API KEYS ---
echo.
echo [3/7] Configuring NVIDIA NIM API keys...
echo.
echo ============================================
echo   EDIT THESE 4 API KEYS BEFORE RUNNING:
echo ============================================

REM --- EDIT THESE 4 API KEYS ---
set "NIM_KEY_1=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"
set "NIM_KEY_2=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"
set "NIM_KEY_3=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"
set "NIM_KEY_4=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"

REM Validate keys are set
if "%NIM_KEY_1%"=="nvapi-account-1-key-here" (
    echo WARNING: You have not edited the API keys in this script!
    echo Please open this file in Notepad and replace the placeholder keys.
    echo.
    echo Press any key to continue anyway...
    pause >nul
)

REM --- STEP 4: CONFIGURE PROJECTS ---
echo.
echo [4/7] Configuring project paths and models...

REM --- EDIT THESE 4 PROJECT PATHS ---
set "PROJECT_1=C:\Users\Admin\Downloads\god_ai\OMEGA"
set "PROJECT_2=C:\dev\antigravity-kandover"
set "PROJECT_3=C:\god_ai\crypto-trader-v1_1"
set "PROJECT_4=C:\god_ai\ases_v3_1"

REM --- EDIT THESE 4 MODELS ---
set "MODEL_1=z-ai/glm-5.2"
set "MODEL_2=nvidia/nemotron-3-ultra-550b-a55b"
set "MODEL_3=deepseek-ai/deepseek-v4-flash"
set "MODEL_4=moonshotai/kimi-k2.6"

REM --- EDIT THESE 4 WINDOW TITLES ---
set "NAME_1=OMEGA-GLM5"
set "NAME_2=Antigravity-Nemotron"
set "NAME_3=Project3-DeepSeek"
set "NAME_4=Project4-Kimi"

REM Validate project paths exist
if not exist "%PROJECT_1%" (
    echo WARNING: Project 1 path does not exist: %PROJECT_1%
    echo Creating directory...
    mkdir "%PROJECT_1%" 2>nul
)
if not exist "%PROJECT_2%" (
    echo WARNING: Project 2 path does not exist: %PROJECT_2%
    echo Creating directory...
    mkdir "%PROJECT_2%" 2>nul
)
if not exist "%PROJECT_3%" (
    echo WARNING: Project 3 path does not exist: %PROJECT_3%
    echo Creating directory...
    mkdir "%PROJECT_3%" 2>nul
)
if not exist "%PROJECT_4%" (
    echo WARNING: Project 4 path does not exist: %PROJECT_4%
    echo Creating directory...
    mkdir "%PROJECT_4%" 2>nul
)

REM --- STEP 5: CREATE CONTINUE.DEV CONFIGS ---
echo.
echo [5/7] Creating Continue.dev project configs...

REM Create .continue directory and config.json for Project 1
if not exist "%PROJECT_1%\.continue" mkdir "%PROJECT_1%\.continue"
(
echo {
echo   "models": [
echo     {
echo       "title": "GLM-5 NIM",
echo       "provider": "openai",
echo       "model": "%MODEL_1%",
echo       "apiBase": "https://integrate.api.nvidia.com/v1",
echo       "apiKey": "%NIM_KEY_1%",
echo       "completionOptions": {
echo         "maxTokens": 131072,
echo         "temperature": 0.2
echo       }
echo     }
echo   ],
echo   "tabAutocompleteModel": {
echo     "title": "GLM-5 Autocomplete",
echo     "provider": "openai",
echo     "model": "%MODEL_1%",
echo     "apiBase": "https://integrate.api.nvidia.com/v1",
echo     "apiKey": "%NIM_KEY_1%"
echo   },
echo   "customCommands": [
echo     {
echo       "name": "fix",
echo       "prompt": "Fix the code in the selected file. Look for bugs, type errors, and logical issues. Return only the corrected code.",
echo       "description": "Fix code issues"
echo     },
echo     {
echo       "name": "refactor",
echo       "prompt": "Refactor the selected code for better readability, performance, and maintainability. Follow best practices.",
echo       "description": "Refactor code"
echo     },
echo     {
echo       "name": "explain",
echo       "prompt": "Explain the selected code in detail. Break down the logic, data flow, and any design patterns used.",
echo       "description": "Explain code"
echo     }
echo   ],
echo   "contextProviders": [
echo     { "name": "diff", "params": {} },
echo     { "name": "folder", "params": {} },
echo     { "name": "codebase", "params": {} }
echo   ],
echo   "slashCommands": [
echo     { "name": "edit", "description": "Edit selected code" },
echo     { "name": "comment", "description": "Add comments" },
echo     { "name": "share", "description": "Export session" }
echo   ]
echo }
) > "%PROJECT_1%\.continue\config.json"
echo   Created config for Project 1: %NAME_1%

REM Create .continue directory and config.json for Project 2
if not exist "%PROJECT_2%\.continue" mkdir "%PROJECT_2%\.continue"
(
echo {
echo   "models": [
echo     {
echo       "title": "Nemotron Ultra NIM",
echo       "provider": "openai",
echo       "model": "%MODEL_2%",
echo       "apiBase": "https://integrate.api.nvidia.com/v1",
echo       "apiKey": "%NIM_KEY_2%",
echo       "completionOptions": {
echo         "maxTokens": 131072,
echo         "temperature": 0.2
echo       }
echo     }
echo   ],
echo   "tabAutocompleteModel": {
echo     "title": "Nemotron Autocomplete",
echo     "provider": "openai",
echo     "model": "%MODEL_2%",
echo     "apiBase": "https://integrate.api.nvidia.com/v1",
echo     "apiKey": "%NIM_KEY_2%"
echo   },
echo   "customCommands": [
echo     {
echo       "name": "fix",
echo       "prompt": "Fix the code in the selected file. Look for bugs, type errors, and logical issues. Return only the corrected code.",
echo       "description": "Fix code issues"
echo     },
echo     {
echo       "name": "refactor",
echo       "prompt": "Refactor the selected code for better readability, performance, and maintainability. Follow best practices.",
echo       "description": "Refactor code"
echo     },
echo     {
echo       "name": "explain",
echo       "prompt": "Explain the selected code in detail. Break down the logic, data flow, and any design patterns used.",
echo       "description": "Explain code"
echo     }
echo   ],
echo   "contextProviders": [
echo     { "name": "diff", "params": {} },
echo     { "name": "folder", "params": {} },
echo     { "name": "codebase", "params": {} }
echo   ],
echo   "slashCommands": [
echo     { "name": "edit", "description": "Edit selected code" },
echo     { "name": "comment", "description": "Add comments" },
echo     { "name": "share", "description": "Export session" }
echo   ]
echo }
) > "%PROJECT_2%\.continue\config.json"
echo   Created config for Project 2: %NAME_2%

REM Create .continue directory and config.json for Project 3
if not exist "%PROJECT_3%\.continue" mkdir "%PROJECT_3%\.continue"
(
echo {
echo   "models": [
echo     {
echo       "title": "DeepSeek V4 NIM",
echo       "provider": "openai",
echo       "model": "%MODEL_3%",
echo       "apiBase": "https://integrate.api.nvidia.com/v1",
echo       "apiKey": "%NIM_KEY_3%",
echo       "completionOptions": {
echo         "maxTokens": 131072,
echo         "temperature": 0.2
echo       }
echo     }
echo   ],
echo   "tabAutocompleteModel": {
echo     "title": "DeepSeek Autocomplete",
echo     "provider": "openai",
echo     "model": "%MODEL_3%",
echo     "apiBase": "https://integrate.api.nvidia.com/v1",
echo     "apiKey": "%NIM_KEY_3%"
echo   },
echo   "customCommands": [
echo     {
echo       "name": "fix",
echo       "prompt": "Fix the code in the selected file. Look for bugs, type errors, and logical issues. Return only the corrected code.",
echo       "description": "Fix code issues"
echo     },
echo     {
echo       "name": "refactor",
echo       "prompt": "Refactor the selected code for better readability, performance, and maintainability. Follow best practices.",
echo       "description": "Refactor code"
echo     },
echo     {
echo       "name": "explain",
echo       "prompt": "Explain the selected code in detail. Break down the logic, data flow, and any design patterns used.",
echo       "description": "Explain code"
echo     }
echo   ],
echo   "contextProviders": [
echo     { "name": "diff", "params": {} },
echo     { "name": "folder", "params": {} },
echo     { "name": "codebase", "params": {} }
echo   ],
echo   "slashCommands": [
echo     { "name": "edit", "description": "Edit selected code" },
echo     { "name": "comment", "description": "Add comments" },
echo     { "name": "share", "description": "Export session" }
echo   ]
echo }
) > "%PROJECT_3%\.continue\config.json"
echo   Created config for Project 3: %NAME_3%

REM Create .continue directory and config.json for Project 4
if not exist "%PROJECT_4%\.continue" mkdir "%PROJECT_4%\.continue"
(
echo {
echo   "models": [
echo     {
echo       "title": "Kimi K2.6 NIM",
echo       "provider": "openai",
echo       "model": "%MODEL_4%",
echo       "apiBase": "https://integrate.api.nvidia.com/v1",
echo       "apiKey": "%NIM_KEY_4%",
echo       "completionOptions": {
echo         "maxTokens": 131072,
echo         "temperature": 0.2
echo       }
echo     }
echo   ],
echo   "tabAutocompleteModel": {
echo     "title": "Kimi Autocomplete",
echo     "provider": "openai",
echo     "model": "%MODEL_4%",
echo     "apiBase": "https://integrate.api.nvidia.com/v1",
echo     "apiKey": "%NIM_KEY_4%"
echo   },
echo   "customCommands": [
echo     {
echo       "name": "fix",
echo       "prompt": "Fix the code in the selected file. Look for bugs, type errors, and logical issues. Return only the corrected code.",
echo       "description": "Fix code issues"
echo     },
echo     {
echo       "name": "refactor",
echo       "prompt": "Refactor the selected code for better readability, performance, and maintainability. Follow best practices.",
echo       "description": "Refactor code"
echo     },
echo     {
echo       "name": "explain",
echo       "prompt": "Explain the selected code in detail. Break down the logic, data flow, and any design patterns used.",
echo       "description": "Explain code"
echo     }
echo   ],
echo   "contextProviders": [
echo     { "name": "diff", "params": {} },
echo     { "name": "folder", "params": {} },
echo     { "name": "codebase", "params": {} }
echo   ],
echo   "slashCommands": [
echo     { "name": "edit", "description": "Edit selected code" },
echo     { "name": "comment", "description": "Add comments" },
echo     { "name": "share", "description": "Export session" }
echo   ]
echo }
) > "%PROJECT_4%\.continue\config.json"
echo   Created config for Project 4: %NAME_4%

REM --- STEP 6: CREATE .VSCODE SETTINGS FOR EACH PROJECT ---
echo.
echo [6/7] Creating VS Code: workspace settings...

REM VS Code: settings for Project 1
if not exist "%PROJECT_1%\.vscode" mkdir "%PROJECT_1%\.vscode"
(
echo {
echo   "continue.enableTabAutocomplete": true,
echo   "continue.allowAnonymousTelemetry": false,
echo   "window.title": "%NAME_1% - ${activeEditorShort}${separator}${rootName}"
echo }
) > "%PROJECT_1%\.vscode\settings.json"

REM VS Code: settings for Project 2
if not exist "%PROJECT_2%\.vscode" mkdir "%PROJECT_2%\.vscode"
(
echo {
echo   "continue.enableTabAutocomplete": true,
echo   "continue.allowAnonymousTelemetry": false,
echo   "window.title": "%NAME_2% - ${activeEditorShort}${separator}${rootName}"
echo }
) > "%PROJECT_2%\.vscode\settings.json"

REM VS Code: settings for Project 3
if not exist "%PROJECT_3%\.vscode" mkdir "%PROJECT_3%\.vscode"
(
echo {
echo   "continue.enableTabAutocomplete": true,
echo   "continue.allowAnonymousTelemetry": false,
echo   "window.title": "%NAME_3% - ${activeEditorShort}${separator}${rootName}"
echo }
) > "%PROJECT_3%\.vscode\settings.json"

REM VS Code: settings for Project 4
if not exist "%PROJECT_4%\.vscode" mkdir "%PROJECT_4%\.vscode"
(
echo {
echo   "continue.enableTabAutocomplete": true,
echo   "continue.allowAnonymousTelemetry": false,
echo   "window.title": "%NAME_4% - ${activeEditorShort}${separator}${rootName}"
echo }
) > "%PROJECT_4%\.vscode\settings.json"

echo   VS Code: workspace settings created.

REM --- STEP 7: LAUNCH ALL 4 VS CODE: INSTANCES ---
echo.
echo [7/7] Launching 4 VS Code: instances with Continue.dev...
echo.

echo Launching Instance 1: %NAME_1%
echo   Project: %PROJECT_1%
echo   Model:   %MODEL_1%
start "%NAME_1%" code "%PROJECT_1%"
timeout /t 3 /nobreak >nul

echo Launching Instance 2: %NAME_2%
echo   Project: %PROJECT_2%
echo   Model:   %MODEL_2%
start "%NAME_2%" code "%PROJECT_2%"
timeout /t 3 /nobreak >nul

echo Launching Instance 3: %NAME_3%
echo   Project: %PROJECT_3%
echo   Model:   %MODEL_3%
start "%NAME_3%" code "%PROJECT_3%"
timeout /t 3 /nobreak >nul

echo Launching Instance 4: %NAME_4%
echo   Project: %PROJECT_4%
echo   Model:   %MODEL_4%
start "%NAME_4%" code "%PROJECT_4%"

echo.
echo ============================================
echo   Setup Complete! All 4 VS Code: instances launched!
echo ============================================
echo.
echo Window 1: %NAME_1%  ^| %PROJECT_1% ^| %MODEL_1%
echo Window 2: %NAME_2%  ^| %PROJECT_2% ^| %MODEL_2%
echo Window 3: %NAME_3%  ^| %PROJECT_3% ^| %MODEL_3%
echo Window 4: %NAME_4%  ^| %PROJECT_4% ^| %MODEL_4%
echo.
echo Each VS Code: window has:
echo   - Its own Continue.dev config with unique NVIDIA API key
echo   - Its own project directory
echo   - Its own AI model (GLM-5, Nemotron, DeepSeek, Kimi)
echo   - Tab autocomplete enabled
echo   - Custom commands: /fix, /refactor, /explain
echo.
echo NO shared 32-worker OpenCode limit.
echo Each instance talks DIRECTLY to NVIDIA NIM.
echo.
echo To use:
echo   1. In any VS Code: window, open the Continue panel (Ctrl+L)
echo   2. Start chatting with your model
echo   3. Use tab autocomplete as you type
echo   4. Select code and use /fix, /refactor, or /explain
echo.
echo To re-launch later, just run this script again.
echo It will skip reinstallation and just launch the windows.
echo.
pause
