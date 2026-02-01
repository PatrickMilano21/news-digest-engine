@echo off
REM Overnight Local Agent Review Script
REM Runs 4 code review agents + summary using Claude CLI (uses subscription, not API credits)
REM
REM Usage:
REM   scripts\overnight_local.bat           (run all steps: agents + summary + codex + implement)
REM   scripts\overnight_local.bat cost      (run only cost-risk agent)
REM   scripts\overnight_local.bat user      (run only user-isolation agent)
REM   scripts\overnight_local.bat scoring   (run only scoring-integrity agent)
REM   scripts\overnight_local.bat test      (run only test-gap agent)
REM   scripts\overnight_local.bat summary   (run only summary step)
REM   scripts\overnight_local.bat codex     (run only codex review step)
REM   scripts\overnight_local.bat implement (run only implementation step)

setlocal enabledelayedexpansion

REM Change to repo root
cd /d "%~dp0.."

REM Get today's date in YYYY-MM-DD format
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
set TODAY=%datetime:~0,4%-%datetime:~4,2%-%datetime:~6,2%

echo ========================================
echo Overnight Local Agent Review
echo Started: %date% %time%
echo ========================================
echo.

REM Check if claude CLI is available
where claude >nul 2>nul
if errorlevel 1 (
    echo ERROR: claude CLI not found in PATH
    echo Install: npm install -g @anthropic-ai/claude-code
    exit /b 1
)

REM Single agent mode
if not "%1"=="" (
    if "%1"=="cost" goto :run_cost
    if "%1"=="user" goto :run_user
    if "%1"=="scoring" goto :run_scoring
    if "%1"=="test" goto :run_test
    if "%1"=="summary" goto :run_summary
    if "%1"=="codex" goto :run_codex
    if "%1"=="implement" goto :run_implement
    echo Unknown agent: %1
    echo Valid options: cost, user, scoring, test, summary, codex, implement
    exit /b 1
)

REM Run all agents sequentially (serial execution per best practices)
:run_cost
echo [1/7] Running Cost Risk Reviewer...
echo ----------------------------------------
claude -p "You are the cost-risk-reviewer agent. Read your instructions from .claude/agents/cost-risk-reviewer.md. Follow those instructions to scan src/, jobs/, tests/ for cost-related patterns. Write findings to artifacts/agent-findings.md (cost-risk section, max 50 lines). Update .claude/rules/cost-risk-reviewer/learned-patterns.md. Append run entry to .claude/rules/cost-risk-reviewer/run-history.md (keep last 10 entries)." --max-turns 50 --allowedTools "Edit,Read,Write,Glob,Grep"
if errorlevel 1 (
    echo WARNING: Cost Risk Reviewer failed, continuing...
)
echo.
if not "%1"=="" goto :done

:run_user
echo [2/7] Running User Isolation Reviewer...
echo ----------------------------------------
claude -p "You are the user-isolation-reviewer agent. Read your instructions from .claude/agents/user-isolation-reviewer.md. Follow those instructions to review user data isolation. Write findings to artifacts/agent-findings.md (user-isolation section, max 50 lines). Update learned-patterns.md. Keep run-history.md to last 10 entries." --max-turns 50 --allowedTools "Edit,Read,Write,Glob,Grep"
if errorlevel 1 (
    echo WARNING: User Isolation Reviewer failed, continuing...
)
echo.
if not "%1"=="" goto :done

:run_scoring
echo [3/7] Running Scoring Integrity Reviewer...
echo ----------------------------------------
claude -p "You are the scoring-integrity-reviewer agent. Read your instructions from .claude/agents/scoring-integrity-reviewer.md. Follow those instructions to review scoring/ranking logic. Write findings to artifacts/agent-findings.md (scoring-integrity section, max 50 lines). Update learned-patterns.md. Keep run-history.md to last 10 entries." --max-turns 50 --allowedTools "Edit,Read,Write,Glob,Grep"
if errorlevel 1 (
    echo WARNING: Scoring Integrity Reviewer failed, continuing...
)
echo.
if not "%1"=="" goto :done

:run_test
echo [4/7] Running Test Gap Reviewer...
echo ----------------------------------------
claude -p "You are the test-gap-reviewer agent. Read your instructions from .claude/agents/test-gap-reviewer.md. Follow those instructions to identify untested code paths. Write findings to artifacts/agent-findings.md (test-gap section, max 50 lines). Update learned-patterns.md. Keep run-history.md to last 10 entries." --max-turns 50 --allowedTools "Edit,Read,Write,Glob,Grep"
if errorlevel 1 (
    echo WARNING: Test Gap Reviewer failed, continuing...
)
echo.
if not "%1"=="" goto :done

:run_summary
echo [5/7] Running Summary Generator...
echo ----------------------------------------
claude -p "You are the overnight summary generator. Read your instructions from scripts/summary-prompt.txt. Read artifacts/agent-findings.md, verify each finding against actual code, then write a prioritized fix plan to artifacts/fix-tasks.md with Critical, Medium, and Low priority sections. Include specific How to Fix instructions for each issue." --max-turns 30 --allowedTools "Read,Write,Glob,Grep"
if errorlevel 1 (
    echo WARNING: Summary Generator failed
)
echo.
if not "%1"=="" goto :done

:run_codex
echo [6/7] Running Codex Review...
echo ----------------------------------------
python scripts/codex_review.py
if errorlevel 1 (
    echo WARNING: Codex Review failed
)
echo.
if not "%1"=="" goto :done

:run_implement
echo [7/7] Running Implementation Agent...
echo ----------------------------------------
claude -p "You are the implementation agent. Read your instructions from scripts/implement-prompt.txt. Follow those instructions to: 1) Read artifacts/fix-tasks.md with proposals and Codex commentary, 2) Write Claude's Final Plan section to fix-tasks.md, 3) Implement each fix by reading source files and using Edit tool, 4) Run make test, 5) Write artifacts/FinalCodeFixes.md with summary of changes." --max-turns 75 --allowedTools "Read,Edit,Write,Bash,Glob,Grep"
if errorlevel 1 (
    echo WARNING: Implementation Agent failed
)
echo.

:done
echo ========================================
echo Overnight Review Complete
echo Finished: %date% %time%
echo ========================================
echo.
echo Results written to:
echo   - artifacts/agent-findings.md
echo   - artifacts/fix-tasks.md (proposals + Codex + Claude plan)
echo   - artifacts/FinalCodeFixes.md (implementation summary)
echo   - .claude/rules/*/learned-patterns.md
echo   - .claude/rules/*/run-history.md
echo.
echo Next: Review FinalCodeFixes.md on agent/milestone1 branch
echo   If satisfied: git add . and commit
echo   If not: request changes or reject

endlocal
