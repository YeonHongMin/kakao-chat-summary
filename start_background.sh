#!/bin/bash

# ==========================================
# 카카오톡 대화 분석기 (Mac 백그라운드 기동 스크립트)
# 터미널에서 `chmod +x start_background.sh` 로 실행 권한을 먼저 주신 후
# `./start_background.sh` 로 실행하세요.
# (또는 확장자를 .command 로 변경하면 더블클릭 실행 지원도 가능합니다)
# ==========================================

# 스크립트가 있는 프로젝트 최상위 디렉토리로 이동
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "🚀 카카오톡 대화 분석기 백그라운드 실행을 준비합니다..."

# 이미 실행 중인 프로세스가 있는지 확인하여 종료 (선택 사항)
PIDS=$(pgrep -f "python3 src/app.py" || pgrep -f "python src/app.py")
if [ -n "$PIDS" ]; then
    echo "이미 앱이 실행 중입니다. 기존 프로세스를 종료하고 다시 시작합니다."
    kill $PIDS
    sleep 1
fi

# nohup을 이용하여 완전한 백그라운드로 실행되도록 명령어 실행
# 출력되는 에러 및 로그는 버림처리 (로그 파일 기능이 따로 있으므로)
nohup python3 src/app.py > /dev/null 2>&1 &

echo "✅ 실행이 완료되었습니다! Mac 환경의 팝업 창이나 상단 메뉴바를 확인해 주세요."
sleep 2
