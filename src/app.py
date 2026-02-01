"""
카카오톡 대화 분석기 - GUI 애플리케이션 진입점

사용법:
    python app.py
"""
import sys
import os
import shutil
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
_here = Path(__file__).resolve().parent
sys.path.insert(0, str(_here))
_base = _here.parent

# 앱 기동 시 .env.local이 없으면 env.local.example을 복사하여 생성
_env_local = _base / ".env.local"
_env_example = _base / "env.local.example"
if not _env_local.exists() and _env_example.exists():
    shutil.copy2(_env_example, _env_local)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from ui import MainWindow
from db import get_db


def main():
    """애플리케이션 메인 함수."""
    # High DPI 지원
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    
    app = QApplication(sys.argv)
    
    # 앱 정보 설정
    app.setApplicationName("카카오톡 대화 분석기")
    app.setApplicationVersion("2.0.0")
    app.setOrganizationName("KakaoTalk Chat Summary")
    
    # 기본 폰트 설정 (한글 지원)
    font = QFont()
    if sys.platform == 'win32':
        font.setFamily("맑은 고딕")
    elif sys.platform == 'darwin':
        font.setFamily("Apple SD Gothic Neo")
    else:
        font.setFamily("Noto Sans CJK KR")
    font.setPointSize(10)
    app.setFont(font)
    
    # 데이터베이스 초기화
    db = get_db()
    
    # 메인 윈도우 생성 및 표시
    window = MainWindow()
    window.show()
    
    # 이벤트 루프 시작
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
