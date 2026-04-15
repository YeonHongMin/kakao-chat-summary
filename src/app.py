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

from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QStyle, QMessageBox
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QAction, QIcon

from ui import MainWindow
from db import get_db


def main():
    """애플리케이션 메인 함수."""
    # High DPI 지원
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False) # 백그라운드 실행을 위해 마지막 창이 닫혀도 계속 실행
    
    # 앱 정보 설정
    app.setApplicationName("카카오톡 대화 분석기")
    app.setApplicationVersion("2.9.1")
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
    
    # 메인 윈도우 생성
    window = MainWindow()
    
    # 시스템 트레이 아이콘 추가
    if QSystemTrayIcon.isSystemTrayAvailable():
        # 트레이 아이콘 생성
        tray_icon = QSystemTrayIcon(app)
        
        # 아이콘 이미지 설정 (기본 아이콘 사용)
        icon = app.style().standardIcon(QStyle.SP_ComputerIcon)
        tray_icon.setIcon(icon)
        tray_icon.setToolTip("카카오톡 대화 분석기 (백그라운드 실행 중)")
        
        # 트레이 메뉴
        tray_menu = QMenu()
        
        # 열기 액션
        show_action = QAction("창 열기", app)
        show_action.triggered.connect(window.show)
        show_action.triggered.connect(window.activateWindow)
        tray_menu.addAction(show_action)
        
        # 구분선 지정
        tray_menu.addSeparator()
        
        # 종료 액션
        quit_action = QAction("종료", app)
        quit_action.triggered.connect(app.quit)
        tray_menu.addAction(quit_action)
        
        # 메뉴 할당 및 트레이에 표시
        tray_icon.setContextMenu(tray_menu)
        tray_icon.show()
        
        # 더블클릭 이벤트 연결 (트레이 아이콘 더블클릭시 창 열기)
        def on_tray_activated(reason):
            if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
                window.show()
                window.activateWindow()
        tray_icon.activated.connect(on_tray_activated)

    # 윈도우 표시 (원하시면 숨길수도 있으나 기본으로 보여줍니다)
    window.show()
    
    # 이벤트 루프 시작
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
