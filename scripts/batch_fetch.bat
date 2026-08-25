@echo off
REM 一键批量预拉落盘数据（幂等：只补缺失/不完整期间，可反复运行）
REM
REM 用法：
REM   batch_fetch.bat            拉取全部清单
REM   batch_fetch.bat stocks     只拉个股清单（stocks-core + stocks-watch）
REM   batch_fetch.bat funds      只拉基金清单
REM
REM 说明：
REM   - 稳定性（限流/重试/断点续传）由 fundamental_fetcher / fund_data_fetcher 内建，
REM     本脚本只负责遍历清单并选择对应工具，不重复实现。
REM   - 断网中断后重跑本脚本即可，只补缺失期间。
REM   - 耗时可能较长（几十只 x 每只多期间），可另开 cmd 窗口后台运行。

setlocal enabledelayedexpansion

REM 仓库根 = 脚本所在目录的上级
set "ROOT=%~dp0.."
set "ROOT=%ROOT:~0,-1%"
set "CONFIG_DIR=%ROOT%\local\config"
set "PY=python"

REM 验证 Python 可用
where %PY% >nul 2>&1 || set "PY=python3"

REM 默认拉取全部
set "MODE=%~1"
if "%MODE%"=="" set "MODE=all"

if /I "%MODE%"=="stocks" goto :fetch_stocks
if /I "%MODE%"=="funds" goto :fetch_funds
if /I "%MODE%"=="all" goto :fetch_all
echo 未知模式: %MODE%
echo 用法: %~nx0 [stocks^|funds^|all]
exit /b 1

:fetch_all
call :fetch_stocks
call :fetch_funds
goto :done

:fetch_stocks
for %%F in ("%CONFIG_DIR%\stocks-*.txt") do (
    if exist "%%F" (
        echo ===== 批量拉取个股: %%~nxF =====
        %PY% "%ROOT%\tools\fundamental_fetcher.py" batch "%%F"
    )
)
goto :eof

:fetch_funds
for %%F in ("%CONFIG_DIR%\funds-*.txt") do (
    if exist "%%F" (
        echo ===== 批量拉取基金: %%~nxF =====
        %PY% "%ROOT%\tools\fund_data_fetcher.py" batch "%%F"
    )
)
goto :eof

:done
echo 完成。清单文件: %CONFIG_DIR%\
endlocal