"""카카오톡 스타일 QSS 정의."""

# 카카오톡 색상 팔레트
KAKAO_YELLOW = "#FEE500"
KAKAO_BROWN = "#3C1E1E"
KAKAO_BLACK = "#191919"
KAKAO_GRAY = "#B2B2B2"
KAKAO_LIGHT_GRAY = "#F5F5F5"
KAKAO_WHITE = "#FFFFFF"
KAKAO_BLUE = "#5B9BD5"

# 메인 스타일시트
MAIN_STYLESHEET = """
/* 전체 배경 */
QMainWindow {
    background-color: #FFFFFF;
}

/* 좌측 채팅방 목록 패널 */
#chatListPanel {
    background-color: #F5F5F5;
    border-right: 1px solid #E0E0E0;
}

#chatListTitle {
    font-size: 18px;
    font-weight: bold;
    color: #191919;
    padding: 15px;
    background-color: #FEE500;
}

/* 채팅방 아이템 */
.ChatRoomItem {
    background-color: #FFFFFF;
    border-bottom: 1px solid #E8E8E8;
    padding: 12px;
    margin: 2px 5px;
    border-radius: 8px;
}

.ChatRoomItem:hover {
    background-color: #FEE500;
}

.ChatRoomItem[selected="true"] {
    background-color: #FEE500;
    border-left: 4px solid #3C1E1E;
}

.ChatRoomName {
    font-size: 14px;
    font-weight: bold;
    color: #191919;
}

.ChatRoomInfo {
    font-size: 11px;
    color: #888888;
}

.NewBadge {
    background-color: #FF5252;
    color: white;
    font-size: 10px;
    font-weight: bold;
    padding: 2px 6px;
    border-radius: 10px;
}

/* 우측 메인 패널 */
#mainPanel {
    background-color: #FFFFFF;
}

#headerBar {
    background-color: #FEE500;
    padding: 15px;
    border-bottom: 1px solid #E0E0E0;
}

#headerTitle {
    font-size: 20px;
    font-weight: bold;
    color: #191919;
}

/* 대시보드 카드 */
.DashboardCard {
    background-color: #FFFFFF;
    border: 1px solid #E8E8E8;
    border-radius: 12px;
    padding: 15px;
    margin: 10px;
}

.DashboardCard:hover {
    border-color: #FEE500;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.CardTitle {
    font-size: 14px;
    font-weight: bold;
    color: #191919;
    margin-bottom: 10px;
}

.CardValue {
    font-size: 24px;
    font-weight: bold;
    color: #3C1E1E;
}

.CardSubtext {
    font-size: 11px;
    color: #888888;
}

/* 요약 뷰어 */
#summaryViewer {
    background-color: #FFFFFF;
    border: 1px solid #E8E8E8;
    border-radius: 12px;
    padding: 20px;
    margin: 10px;
}

#summaryViewer QTextBrowser {
    border: none;
    background-color: transparent;
    font-size: 13px;
    line-height: 1.6;
}

/* 버튼 스타일 */
QPushButton {
    background-color: #FEE500;
    color: #191919;
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
    font-size: 13px;
    font-weight: bold;
}

QPushButton:hover {
    background-color: #FFD700;
}

QPushButton:pressed {
    background-color: #E6CE00;
}

QPushButton:disabled {
    background-color: #E0E0E0;
    color: #A0A0A0;
}

/* 세컨더리 버튼 */
QPushButton.secondary {
    background-color: #FFFFFF;
    border: 1px solid #E0E0E0;
    color: #191919;
}

QPushButton.secondary:hover {
    background-color: #F5F5F5;
    border-color: #FEE500;
}

/* 상태바 */
#statusBar {
    background-color: #F5F5F5;
    border-top: 1px solid #E0E0E0;
    padding: 8px 15px;
}

#syncStatus {
    font-size: 12px;
    color: #666666;
}

#syncButton {
    background-color: #5B9BD5;
    color: white;
    padding: 5px 15px;
    border-radius: 15px;
}

#syncButton:hover {
    background-color: #4A8BC4;
}

/* 설정 다이얼로그 */
QDialog {
    background-color: #FFFFFF;
}

QLabel {
    color: #191919;
}

QLineEdit, QComboBox, QSpinBox {
    border: 1px solid #E0E0E0;
    border-radius: 6px;
    padding: 8px 12px;
    background-color: #FFFFFF;
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
    border-color: #FEE500;
}

/* 리스트 위젯 */
QListWidget {
    background-color: #FFFFFF;
    border: none;
    outline: none;
}

QListWidget::item {
    padding: 10px;
    border-bottom: 1px solid #F0F0F0;
}

QListWidget::item:selected {
    background-color: #FEE500;
    color: #191919;
}

QListWidget::item:hover {
    background-color: #FFFACD;
}

/* 스크롤바 */
QScrollBar:vertical {
    background-color: #F5F5F5;
    width: 8px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background-color: #C0C0C0;
    border-radius: 4px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background-color: #A0A0A0;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

/* 탭 위젯 */
QTabWidget::pane {
    border: 1px solid #E0E0E0;
    border-radius: 8px;
    background-color: #FFFFFF;
}

QTabBar::tab {
    background-color: #F5F5F5;
    border: 1px solid #E0E0E0;
    border-bottom: none;
    padding: 10px 20px;
    margin-right: 2px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
}

QTabBar::tab:selected {
    background-color: #FEE500;
    border-color: #FEE500;
}

QTabBar::tab:hover:!selected {
    background-color: #FFFACD;
}

/* 툴팁 */
QToolTip {
    background-color: #3C1E1E;
    color: #FFFFFF;
    border: none;
    padding: 5px 10px;
    border-radius: 4px;
    font-size: 12px;
}

/* 메뉴바 */
QMenuBar {
    background-color: #FFFFFF;
    border-bottom: 1px solid #E0E0E0;
}

QMenuBar::item {
    padding: 8px 15px;
}

QMenuBar::item:selected {
    background-color: #FEE500;
}

QMenu {
    background-color: #FFFFFF;
    border: 1px solid #E0E0E0;
}

QMenu::item {
    padding: 8px 30px;
}

QMenu::item:selected {
    background-color: #FEE500;
}

/* 프로그레스바 */
QProgressBar {
    border: 1px solid #E0E0E0;
    border-radius: 4px;
    background-color: #F5F5F5;
    text-align: center;
}

QProgressBar::chunk {
    background-color: #FEE500;
    border-radius: 3px;
}

/* 상태바 요약 프로그레스 위젯 */
#summaryProgressWidget {
    background-color: #FFF8E1;
    border: 1px solid #FFE082;
    border-radius: 6px;
    padding: 2px 4px;
}

#summaryProgressBar {
    border: 1px solid #FFE082;
    border-radius: 3px;
    background-color: #FFFDE7;
    font-size: 10px;
}

#summaryProgressBar::chunk {
    background-color: #FEE500;
    border-radius: 2px;
}

#summaryProgressCancelBtn {
    background-color: transparent;
    border: none;
    padding: 0;
    font-size: 12px;
    min-width: 24px;
    max-width: 24px;
}

#summaryProgressCancelBtn:hover {
    background-color: #FFCDD2;
    border-radius: 4px;
}
"""

# 다크 모드 스타일시트 (옵션)
DARK_STYLESHEET = """
QMainWindow {
    background-color: #1E1E1E;
}

#chatListPanel {
    background-color: #252525;
    border-right: 1px solid #333333;
}

#chatListTitle {
    background-color: #FEE500;
    color: #191919;
}

.ChatRoomItem {
    background-color: #2D2D2D;
    border-bottom: 1px solid #333333;
}

.ChatRoomItem:hover {
    background-color: #3D3D3D;
}

.ChatRoomName {
    color: #FFFFFF;
}

.ChatRoomInfo {
    color: #888888;
}

#mainPanel {
    background-color: #1E1E1E;
}

#headerBar {
    background-color: #FEE500;
}

.DashboardCard {
    background-color: #2D2D2D;
    border-color: #333333;
}

.CardTitle {
    color: #FFFFFF;
}

.CardValue {
    color: #FEE500;
}

QLabel {
    color: #FFFFFF;
}
"""
