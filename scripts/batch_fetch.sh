#!/bin/bash
# 一键批量预拉落盘数据（幂等：只补缺失/不完整期间，可反复运行）
#
# 用法：
#   ./scripts/batch_fetch.sh            # 拉取全部清单
#   ./scripts/batch_fetch.sh stocks     # 只拉个股清单（stocks-core + stocks-watch）
#   ./scripts/batch_fetch.sh funds      # 只拉基金清单
#
# 说明：
#   - 稳定性（限流/重试/断点续传）由 fundamental_fetcher / fund_data_fetcher 内建，
#     本脚本只负责遍历清单并选择对应工具，不重复实现。
#   - 断网中断后重跑本脚本即可，只补缺失期间。
#   - 耗时可能较长（几十只 × 每只多期间），建议 tmux / nohup 后台运行。

set -euo pipefail

# 仓库根 = 脚本所在目录的上级
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_DIR="$ROOT/local/config"
PY="python"

# Windows 下若 python 不可用尝试 python3
command -v "$PY" >/dev/null 2>&1 || PY="python3"

fetch_stocks() {
  local f
  for f in "$CONFIG_DIR"/stocks-*.txt; do
    [ -f "$f" ] || continue
    echo "===== 批量拉取个股: $(basename "$f") ====="
    "$PY" "$ROOT/tools/fundamental_fetcher.py" batch "$f"
  done
}

fetch_funds() {
  local f
  for f in "$CONFIG_DIR"/funds-*.txt; do
    [ -f "$f" ] || continue
    echo "===== 批量拉取基金: $(basename "$f") ====="
    "$PY" "$ROOT/tools/fund_data_fetcher.py" batch "$f"
  done
}

case "${1:-all}" in
  stocks) fetch_stocks ;;
  funds)  fetch_funds ;;
  all|*)  fetch_stocks; fetch_funds ;;
esac

echo "完成。清单文件: $CONFIG_DIR/"
