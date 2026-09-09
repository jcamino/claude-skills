@echo off
title Claude Code remote+bypass
cd /d C:\Users\jcamino\Code
rem Same scrub as launch.ps1: a bare `claude` inherits the launching session's
rem markers and comes up child-marked (transcripts off). Vars must be ABSENT.
set CLAUDECODE=
set CLAUDE_CODE_CHILD_SESSION=
set CLAUDE_CODE_SESSION_ID=
set CLAUDE_PID=
set CLAUDE_CODE_BRIDGE_SESSION_ID=
set CLAUDE_CODE_MESSAGING_SOCKET=
set CLAUDE_CODE_MESSAGING_TOKEN=
set CLAUDE_CODE_CHROME_MCP_ORG_DENIED=
set CLAUDE_CODE_EVAL_INTERVIEW_SESSION=
set CLAUDE_CODE_ENTRYPOINT=
set CLAUDE_CODE_EXECPATH=
set CLAUDE_EFFORT=
set AI_AGENT=
set TRACEPARENT=
set CLAUDE_CODE_FORCE_SESSION_PERSISTENCE=1
echo Starting Claude in %CD%
echo Flags: --remote-control win-0903-one --permission-mode bypassPermissions
where claude
claude --remote-control win-0903-one --permission-mode bypassPermissions
echo.
echo claude exited %ERRORLEVEL%
pause
