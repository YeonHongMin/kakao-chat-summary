"""메인 윈도우 - 카카오톡 스타일 대화 분석기."""
import sys
import re
import logging
from pathlib import Path
from datetime import datetime, timedelta, date
from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QListWidget, QListWidgetItem, QLabel, QPushButton, QTextBrowser,
    QFrame, QScrollArea, QFileDialog, QMessageBox, QProgressBar,
    QStatusBar, QMenuBar, QMenu, QDialog, QSpinBox, QComboBox,
    QFormLayout, QDialogButtonBox, QGroupBox, QGridLayout, QApplication,
    QLineEdit, QRadioButton, QButtonGroup, QCheckBox, QProgressDialog,
    QTabWidget, QDateEdit, QCalendarWidget
)
from PySide6.QtCore import Qt, Signal, Slot, QTimer, QThread, QDate
from PySide6.QtGui import QAction, QFont, QIcon

from .styles import MAIN_STYLESHEET

# 프로젝트 모듈 import
sys.path.insert(0, str(Path(__file__).parent.parent))
from parser import KakaoLogParser
from db import get_db, ChatRoom, Message
from file_storage import get_storage
from url_extractor import extract_urls_from_text, save_urls_to_file, deduplicate_urls

logger = logging.getLogger("KakaoSummarizer")


class MessageParser:
    """카카오톡 메시지 상세 파싱."""
    
    # [닉네임] [오전/오후 00:00] 내용
    MSG_PATTERN = re.compile(r'\[(.*?)\]\s*\[(오전|오후)\s*(\d{1,2}):(\d{2})\]\s*(.*)', re.DOTALL)
    
    @classmethod
    def parse_message(cls, line: str, msg_date: date) -> Optional[Dict[str, Any]]:
        """메시지 라인을 파싱하여 발신자, 시간, 내용 추출."""
        match = cls.MSG_PATTERN.match(line)
        if not match:
            return None
        
        sender = match.group(1)
        am_pm = match.group(2)
        hour = int(match.group(3))
        minute = int(match.group(4))
        content = match.group(5)
        
        # 24시간 형식으로 변환
        if am_pm == "오후" and hour != 12:
            hour += 12
        elif am_pm == "오전" and hour == 12:
            hour = 0
        
        from datetime import time as dt_time
        msg_time = dt_time(hour, minute)
        
        return {
            'sender': sender,
            'content': content,
            'date': msg_date,
            'time': msg_time,
            'raw_line': line
        }


class FileUploadWorker(QThread):
    """파일 업로드 및 파싱 워커."""
    progress = Signal(int, str)  # (progress, message)
    finished = Signal(bool, str, int)  # (success, message, room_id)
    
    def __init__(self, file_path: str, room_name: Optional[str] = None):
        super().__init__()
        self.file_path = Path(file_path)
        self.room_name = room_name
        self.storage = get_storage()
        # Note: DB는 __init__에서 가져오지 않고 run()에서 별도 인스턴스 생성 (스레드 안전)
    
    def run(self):
        try:
            # 스레드 안전을 위해 워커 전용 DB 인스턴스 생성
            from db.database import Database
            worker_db = Database()
            
            self.progress.emit(10, "파일 읽는 중...")
            # 1. 채팅방 이름 (사용자 입력 또는 파일명에서 추출)
            room_name = self.room_name or self._extract_room_name()
            
            # 2. 기존 채팅방 확인 또는 생성
            self.progress.emit(20, "채팅방 생성 중...")
            room = self._get_or_create_room(room_name, worker_db)
            
            # 3. 파일 파싱
            self.progress.emit(30, "대화 파싱 중...")
            parser = KakaoLogParser()
            parse_result = parser.parse(self.file_path)
            
            # 4. 마지막 요약일 기준 cutoff 계산 (이전 날짜는 해시/DB 처리 건너뜀)
            self.progress.emit(35, "기존 데이터 확인 중...")
            summarized_dates = sorted(self.storage.get_summarized_dates(room_name))
            if summarized_dates:
                last_summarized = summarized_dates[-1]
                last_date = datetime.strptime(last_summarized, '%Y-%m-%d').date()
                cutoff_str = (last_date - timedelta(days=1)).strftime('%Y-%m-%d')
            else:
                cutoff_str = None  # 요약 없으면 모든 날짜 처리

            # cutoff 이후 날짜만 해시/개수 계산
            recent_dates = [
                d for d in parse_result.messages_by_date.keys()
                if cutoff_str is None or d >= cutoff_str
            ]
            skipped_dates = len(parse_result.messages_by_date) - len(recent_dates)

            old_content_hashes = {}
            old_message_counts = {}
            for date_str in recent_dates:
                old_content_hashes[date_str] = self.storage.get_original_content_hash(room_name, date_str)
                old_message_counts[date_str] = len(self.storage.load_daily_original(room_name, date_str))

            # 5. 일별 파일 저장 (original) - cutoff 이후만 저장, 과거는 보호
            self.progress.emit(40, "일별 파일 저장 중...")
            saved_files = self.storage.save_all_daily_originals(
                room_name,
                parse_result.messages_by_date,
                cutoff_date=cutoff_str
            )

            # 6. 최근 날짜만 요약 무효화 체크 (임계값: 10개)
            self.progress.emit(50, "요약 상태 확인 중...")
            invalidated_dates = []
            for date_str in recent_dates:
                old_hash = old_content_hashes.get(date_str, "")
                new_hash = self.storage.get_original_content_hash(room_name, date_str)
                old_count = old_message_counts.get(date_str, 0)
                new_count = len(self.storage.load_daily_original(room_name, date_str))

                if self.storage.invalidate_summary_if_content_changed(
                    room_name, date_str, old_hash, new_hash,
                    old_count, new_count
                ):
                    invalidated_dates.append(date_str)

            # 7. 최근 날짜만 DB 저장 (과거 날짜는 파일만 저장됨)
            self.progress.emit(60, f"DB에 저장 중... ({len(recent_dates)}일, {skipped_dates}일 건너뜀)")
            total_messages = 0
            new_messages = 0

            for date_str in recent_dates:
                lines = parse_result.messages_by_date[date_str]
                msg_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                messages = []

                for line in lines:
                    parsed = MessageParser.parse_message(line, msg_date)
                    if parsed:
                        messages.append(parsed)

                if messages:
                    total_messages += len(messages)
                    try:
                        new_count = worker_db.add_messages(room.id, messages)
                        new_messages += new_count
                    except Exception:
                        # DB 오류 시 파일은 이미 저장됨
                        pass
            
            # 8. 동기화 시간 업데이트
            self.progress.emit(90, "마무리 중...")
            try:
                worker_db.update_room_sync_time(room.id)
                worker_db.add_sync_log(
                    room.id, 'success',
                    message_count=total_messages,
                    new_message_count=new_messages
                )
            except Exception:
                pass  # DB 오류 무시
            finally:
                worker_db.engine.dispose()  # 연결 해제
            
            self.progress.emit(100, "완료!")
            
            # 결과 메시지 구성
            result_msg = f"✅ {room_name}\n📁 {len(saved_files)}일 저장됨 ({skipped_dates}일 보호)\n💬 최근 {total_messages:,}개 메시지 DB 반영"
            if invalidated_dates:
                result_msg += f"\n🔄 {len(invalidated_dates)}일 요약 갱신 필요"
            
            self.finished.emit(True, result_msg, room.id if room else -1)
            
        except Exception as e:
            self.finished.emit(False, f"❌ 오류: {str(e)}", -1)
    
    def _extract_room_name(self) -> str:
        """파일명에서 채팅방 이름 추출."""
        name = self.file_path.stem
        # KakaoTalk_20260131_1416_15_783_group 형식에서 앞부분 추출
        if "_KakaoTalk_" in name:
            return name.split("_KakaoTalk_")[0]
        elif "KakaoTalk_" in name:
            return "카카오톡 대화"
        return name
    
    def _get_or_create_room(self, name: str, db) -> ChatRoom:
        """채팅방 조회 또는 생성."""
        room = db.get_room_by_name(name)
        if room is None:
            room = db.create_room(name, str(self.file_path))
        return room


class SyncWorker(QThread):
    """백그라운드 동기화 워커."""
    progress = Signal(int, str)  # (progress, message)
    finished = Signal(bool, str)  # (success, message)
    
    def __init__(self, room_id: int, file_path: str):
        super().__init__()
        self.room_id = room_id
        self.file_path = Path(file_path)
        # Note: DB는 __init__에서 가져오지 않고 run()에서 별도 인스턴스 생성 (스레드 안전)
    
    def run(self):
        try:
            # 스레드 안전을 위해 워커 전용 DB 인스턴스 생성
            from db.database import Database
            worker_db = Database()
            
            self.progress.emit(20, "파싱 중...")
            
            parser = KakaoLogParser()
            parse_result = parser.parse(self.file_path)
            
            self.progress.emit(50, "메시지 저장 중...")
            total_messages = 0
            new_messages = 0
            
            for date_str, lines in parse_result.messages_by_date.items():
                msg_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                messages = []
                
                for line in lines:
                    parsed = MessageParser.parse_message(line, msg_date)
                    if parsed:
                        messages.append(parsed)
                
                if messages:
                    total_messages += len(messages)
                    new_count = worker_db.add_messages(self.room_id, messages)
                    new_messages += new_count
            
            worker_db.update_room_sync_time(self.room_id)
            worker_db.add_sync_log(
                self.room_id, 'success',
                message_count=total_messages,
                new_message_count=new_messages
            )
            worker_db.engine.dispose()  # 연결 해제
            
            self.progress.emit(100, "완료!")
            self.finished.emit(True, f"동기화 완료: {new_messages:,}개 새 메시지")
        except Exception as e:
            self.finished.emit(False, str(e))


class ChatRoomWidget(QFrame):
    """채팅방 아이템 위젯."""
    clicked = Signal(int, str)  # room_id, file_path
    def __init__(self, room_id: int, name: str, message_count: int = 0,
                 new_count: int = 0, last_sync: Optional[datetime] = None,
                 file_path: Optional[str] = None):
        super().__init__()
        self.room_id = room_id
        self.file_path = file_path or ""
        self.setObjectName("chatRoomItem")
        self.setProperty("class", "ChatRoomItem")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(85)
        
        from PySide6.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)
        
        # 아이콘/아바타 영역
        avatar = QLabel("💬")
        avatar.setFixedSize(40, 40)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet("""
            background-color: #FEE500;
            border-radius: 20px;
            font-size: 18px;
        """)
        layout.addWidget(avatar)
        
        # 정보 영역
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)
        
        # 이름 + 새 메시지 배지
        name_layout = QHBoxLayout()
        name_label = QLabel(name)
        name_label.setProperty("class", "ChatRoomName")
        name_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        name_layout.addWidget(name_label)
        
        if new_count > 0:
            badge = QLabel(str(new_count))
            badge.setProperty("class", "NewBadge")
            badge.setStyleSheet("""
                background-color: #FF5252;
                color: white;
                font-size: 10px;
                font-weight: bold;
                padding: 2px 6px;
                border-radius: 10px;
            """)
            badge.setFixedHeight(16)
            name_layout.addWidget(badge)
        
        name_layout.addStretch()

        info_layout.addLayout(name_layout)

        # 메시지 수 및 동기화 시간
        sync_text = "동기화 안됨"
        if last_sync:
            sync_text = last_sync.strftime("%m/%d %H:%M")
        
        info_label = QLabel(f"📊 {message_count:,}개 메시지 · {sync_text}")
        info_label.setProperty("class", "ChatRoomInfo")
        info_label.setStyleSheet("color: #888888; font-size: 11px;")
        info_layout.addWidget(info_label)
        
        layout.addLayout(info_layout, 1)
    
    def mousePressEvent(self, event):
        self.clicked.emit(self.room_id, self.file_path)
        super().mousePressEvent(event)


class DashboardCard(QFrame):
    """대시보드 카드 위젯."""

    def __init__(self, title: str, value: str, subtext: str = "", icon: str = "📊"):
        super().__init__()
        self.setProperty("class", "DashboardCard")
        self.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #E8E8E8;
                border-radius: 10px;
                padding: 8px 12px;
            }
            QFrame:hover {
                border-color: #FEE500;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(2)
        layout.setContentsMargins(4, 4, 4, 4)

        # 아이콘 + 제목 + 값을 한 줄로
        header = QHBoxLayout()
        header.setSpacing(6)
        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 14px;")
        header.addWidget(icon_label)

        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 11px; color: #666666;")
        header.addWidget(title_label)
        header.addStretch()

        self.value_label = QLabel(value)
        self.value_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #3C1E1E;")
        header.addWidget(self.value_label)
        layout.addLayout(header)

        # 서브텍스트
        self.sub_label = QLabel(subtext)
        self.sub_label.setStyleSheet("font-size: 10px; color: #888888;")
        layout.addWidget(self.sub_label)

    def update_card(self, value: str, subtext: str = ""):
        """카드 값과 서브텍스트 업데이트."""
        self.value_label.setText(value)
        if subtext:
            self.sub_label.setText(subtext)


class AllRoomsSummaryOptionsDialog(QDialog):
    """전체 채팅방 요약 옵션 다이얼로그."""

    def __init__(self, parent=None, room_stats: list = None, current_llm: str = "glm"):
        super().__init__(parent)
        self.setWindowTitle("🌐 전체 채팅방 LLM 요약 생성")
        self.setMinimumWidth(520)
        self.summary_type = "pending"
        self.skip_existing = True
        self.selected_llm = current_llm
        room_stats = room_stats or []

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 전체 채팅방 현황
        total_rooms = len(room_stats)
        total_pending = sum(s.get('pending', 0) for s in room_stats)
        total_days = sum(s.get('total', 0) for s in room_stats)
        total_done = sum(s.get('done', 0) for s in room_stats)

        status_label = QLabel(
            f"🏠 채팅방 {total_rooms}개 | 📅 총 {total_days}일 | "
            f"✅ 완료 {total_done}일 | 🔄 요약필요 {total_pending}일"
        )
        status_label.setStyleSheet("""
            font-size: 11px; color: #666;
            padding: 10px; background-color: #F8F8F8;
            border-radius: 6px;
        """)
        layout.addWidget(status_label)

        # 채팅방별 현황 리스트
        if room_stats:
            detail_group = QGroupBox("📋 채팅방별 현황")
            detail_layout = QVBoxLayout(detail_group)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setMaximumHeight(150)
            scroll_content = QWidget()
            scroll_layout = QVBoxLayout(scroll_content)
            scroll_layout.setSpacing(2)

            for stat in room_stats:
                pending = stat.get('pending', 0)
                icon = "🔴" if pending > 0 else "🟢"
                lbl = QLabel(
                    f"{icon} {stat['name']}: "
                    f"{stat.get('done', 0)}/{stat.get('total', 0)}일 완료"
                    + (f" (🔄 {pending}일 필요)" if pending > 0 else "")
                )
                lbl.setStyleSheet("font-size: 11px; padding: 2px 4px;")
                scroll_layout.addWidget(lbl)

            scroll_layout.addStretch()
            scroll.setWidget(scroll_content)
            detail_layout.addWidget(scroll)
            layout.addWidget(detail_group)

        # LLM 선택
        llm_group = QGroupBox("🤖 LLM 선택")
        llm_layout = QHBoxLayout(llm_group)

        self.llm_combo = QComboBox()
        self.llm_combo.setStyleSheet("""
            QComboBox {
                padding: 8px 12px; font-size: 13px;
                border: 2px solid #E0E0E0; border-radius: 6px;
            }
            QComboBox:focus { border-color: #FEE500; }
        """)

        from full_config import LLM_PROVIDERS, config
        llm_flags = {"glm": "🇨🇳", "chatgpt": "🇺🇸", "minimax": "🇨🇳", "perplexity": "🇺🇸", "grok": "🇺🇸", "qwen-or": "🇨🇳", "qwen-kilo": "🇨🇳", "ollama": "🖥️"}
        default_key = config.DEFAULT_PROVIDER
        current_idx = 0
        for idx, (key, prov) in enumerate(LLM_PROVIDERS.items()):
            suffix = " (기본)" if key == default_key else ""
            flag = llm_flags.get(key, "🌐")
            if key in {"qwen-or", "qwen-kilo"}:
                label = f"{flag} {prov.name}{suffix}"
            else:
                label = f"{flag} {prov.name} {prov.model}{suffix}"
            self.llm_combo.addItem(label, key)
            if key == current_llm:
                current_idx = idx
        self.llm_combo.setCurrentIndex(current_idx)
        llm_layout.addWidget(self.llm_combo, 1)

        self.api_status = QLabel()
        self.api_status.setStyleSheet("font-size: 11px;")
        self._update_api_status()
        llm_layout.addWidget(self.api_status)
        self.llm_combo.currentIndexChanged.connect(self._update_api_status)
        layout.addWidget(llm_group)

        # 요약 범위 선택
        type_group = QGroupBox("📅 요약 범위 선택")
        type_layout = QVBoxLayout(type_group)

        self.type_group = QButtonGroup(self)

        self.radio_pending = QRadioButton(
            f"🎯 요약 필요한 날짜만 ({total_pending}일)"
        )
        self.radio_pending.setChecked(True)
        self.radio_pending.setStyleSheet("font-weight: bold; color: #1976D2;")

        self.radio_today = QRadioButton("📅 오늘 (Today)")
        self.radio_yesterday = QRadioButton("📅 어제~오늘 (Yesterday)")
        self.radio_2days = QRadioButton("📅 엇그제~오늘 (2 Days)")
        self.radio_all = QRadioButton(f"📅 전체 일자 (All - {total_days}일)")

        self.type_group.addButton(self.radio_pending, 0)
        self.type_group.addButton(self.radio_today, 1)
        self.type_group.addButton(self.radio_yesterday, 2)
        self.type_group.addButton(self.radio_2days, 3)
        self.type_group.addButton(self.radio_all, 4)

        type_layout.addWidget(self.radio_pending)
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet("color: #E0E0E0;")
        type_layout.addWidget(separator)
        type_layout.addWidget(self.radio_today)
        type_layout.addWidget(self.radio_yesterday)
        type_layout.addWidget(self.radio_2days)
        type_layout.addWidget(self.radio_all)
        layout.addWidget(type_group)

        # 옵션
        option_group = QGroupBox("⚙️ 옵션")
        option_layout = QVBoxLayout(option_group)
        self.skip_checkbox = QCheckBox("✅ 이미 요약된 날짜 건너뛰기")
        self.skip_checkbox.setChecked(True)
        self.skip_checkbox.setStyleSheet("font-size: 12px;")
        self.skip_checkbox.setToolTip("'요약 필요한 날짜만' 선택 시에는 자동 적용됩니다.")
        option_layout.addWidget(self.skip_checkbox)
        self.radio_pending.toggled.connect(
            lambda checked: self.skip_checkbox.setEnabled(not checked)
        )
        layout.addWidget(option_group)

        # 경고
        warning = QLabel(
            "⚠️ 전체 채팅방 요약은 시간이 오래 걸릴 수 있습니다.\n"
            "진행 중 취소할 수 있으며, 완료된 요약은 보존됩니다."
        )
        warning.setStyleSheet("""
            font-size: 11px; color: #E65100;
            padding: 8px; background-color: #FFF3E0;
            border-radius: 6px; border: 1px solid #FFE0B2;
        """)
        layout.addWidget(warning)

        # 버튼
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        cancel_btn = QPushButton("취소")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        generate_btn = QPushButton("🌐 전체 채팅방 요약 시작")
        generate_btn.setStyleSheet("""
            QPushButton {
                background-color: #1976D2; color: white;
                padding: 10px 20px; border-radius: 6px;
                font-size: 13px; font-weight: bold;
            }
            QPushButton:hover { background-color: #1565C0; }
        """)
        generate_btn.clicked.connect(self._on_generate)
        button_layout.addWidget(generate_btn)
        layout.addLayout(button_layout)

    def _update_api_status(self):
        """API 키 상태 업데이트."""
        from full_config import config
        llm_key = self.llm_combo.currentData()
        api_key = config.get_api_key(llm_key)
        if api_key:
            self.api_status.setText("✅ API 키 설정됨")
            self.api_status.setStyleSheet("font-size: 11px; color: #4CAF50;")
        else:
            self.api_status.setText("⚠️ API 키 필요")
            self.api_status.setStyleSheet("font-size: 11px; color: #FF9800;")

    def _on_generate(self):
        """생성 버튼 클릭."""
        self.selected_llm = self.llm_combo.currentData()
        from full_config import config
        if not config.get_api_key(self.selected_llm):
            QMessageBox.warning(
                self, "API 키 필요",
                f"선택한 LLM ({self.llm_combo.currentText()})의 API 키가 "
                f"설정되어 있지 않습니다.\n\n환경변수를 설정하거나 .env 파일에 추가해주세요."
            )
            return

        selected = self.type_group.checkedId()
        if selected == 0:
            self.summary_type = "pending"
            self.skip_existing = True
        elif selected == 1:
            self.summary_type = "today"
        elif selected == 2:
            self.summary_type = "yesterday"
        elif selected == 3:
            self.summary_type = "2days"
        else:
            self.summary_type = "all"

        if selected != 0:
            self.skip_existing = self.skip_checkbox.isChecked()

        self.accept()


class SummaryOptionsDialog(QDialog):
    """요약 옵션 다이얼로그."""
    
    def __init__(self, parent=None, summarized_count: int = 0, total_count: int = 0,
                 needs_update_count: int = 0, new_count: int = 0, current_llm: str = "glm"):
        super().__init__(parent)
        self.setWindowTitle("📝 LLM 요약 생성")
        self.setMinimumWidth(480)
        self.summary_type = "daily"
        self.skip_existing = True
        self.selected_llm = current_llm
        self.generate_detail = True
        
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # 상태 요약
        status_label = QLabel(
            f"📊 총 {total_count}일 | ✅ 완료 {summarized_count}일 | 🆕 신규 {new_count}일 | 🔄 갱신필요 {needs_update_count}일"
        )
        status_label.setStyleSheet("""
            font-size: 11px; 
            color: #666; 
            padding: 10px; 
            background-color: #F8F8F8; 
            border-radius: 6px;
        """)
        layout.addWidget(status_label)
        
        # LLM 선택
        llm_group = QGroupBox("🤖 LLM 선택")
        llm_layout = QHBoxLayout(llm_group)
        
        self.llm_combo = QComboBox()
        self.llm_combo.setStyleSheet("""
            QComboBox {
                padding: 8px 12px;
                font-size: 13px;
                border: 2px solid #E0E0E0;
                border-radius: 6px;
            }
            QComboBox:focus {
                border-color: #FEE500;
            }
        """)
        
        # LLM 목록 추가
        from full_config import LLM_PROVIDERS, config
        llm_flags = {"glm": "🇨🇳", "chatgpt": "🇺🇸", "minimax": "🇨🇳", "perplexity": "🇺🇸", "grok": "🇺🇸", "qwen-or": "🇨🇳", "qwen-kilo": "🇨🇳", "ollama": "🖥️"}
        default_key = config.DEFAULT_PROVIDER
        current_idx = 0
        for idx, (key, prov) in enumerate(LLM_PROVIDERS.items()):
            suffix = " (기본)" if key == default_key else ""
            flag = llm_flags.get(key, "🌐")
            if key in {"qwen-or", "qwen-kilo"}:
                label = f"{flag} {prov.name}{suffix}"
            else:
                label = f"{flag} {prov.name} {prov.model}{suffix}"
            self.llm_combo.addItem(label, key)
            if key == current_llm:
                current_idx = idx
        
        self.llm_combo.setCurrentIndex(current_idx)
        llm_layout.addWidget(self.llm_combo, 1)
        
        # API 키 상태 표시
        self.api_status = QLabel()
        self.api_status.setStyleSheet("font-size: 11px;")
        self._update_api_status()
        llm_layout.addWidget(self.api_status)
        
        self.llm_combo.currentIndexChanged.connect(self._update_api_status)
        
        layout.addWidget(llm_group)
        
        # 요약 유형 선택
        type_group = QGroupBox("📅 요약 범위 선택")
        type_layout = QVBoxLayout(type_group)
        
        self.type_group = QButtonGroup(self)
        
        pending_total = new_count + needs_update_count
        self.radio_pending = QRadioButton(f"🎯 요약 필요한 날짜만 ({pending_total}일: 신규 {new_count} + 갱신 {needs_update_count})")
        self.radio_pending.setChecked(True)
        self.radio_pending.setStyleSheet("font-weight: bold; color: #1976D2;")
        
        self.radio_today = QRadioButton("📅 오늘 (Today)")
        self.radio_yesterday = QRadioButton("📅 어제~오늘 (Yesterday)")
        self.radio_2days = QRadioButton("📅 엇그제~오늘 (2 Days)")
        self.radio_all = QRadioButton(f"📅 전체 일자 (All - {total_count}일)")
        
        self.type_group.addButton(self.radio_pending, 0)
        self.type_group.addButton(self.radio_today, 1)
        self.type_group.addButton(self.radio_yesterday, 2)
        self.type_group.addButton(self.radio_2days, 3)
        self.type_group.addButton(self.radio_all, 4)
        
        type_layout.addWidget(self.radio_pending)
        
        # 구분선
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet("color: #E0E0E0;")
        type_layout.addWidget(separator)
        
        type_layout.addWidget(self.radio_today)
        type_layout.addWidget(self.radio_yesterday)
        type_layout.addWidget(self.radio_2days)
        type_layout.addWidget(self.radio_all)
        
        layout.addWidget(type_group)
        
        # 옵션
        option_group = QGroupBox("⚙️ 옵션")
        option_layout = QVBoxLayout(option_group)
        
        self.skip_checkbox = QCheckBox(f"✅ 이미 요약된 날짜 건너뛰기")
        self.skip_checkbox.setChecked(True)
        self.skip_checkbox.setStyleSheet("font-size: 12px;")
        self.skip_checkbox.setToolTip("'요약 필요한 날짜만' 선택 시에는 자동 적용됩니다.")
        option_layout.addWidget(self.skip_checkbox)

        self.detail_checkbox = QCheckBox("🔍 상세 분석도 함께 생성 (HTML)")
        self.detail_checkbox.setChecked(True)
        self.detail_checkbox.setStyleSheet("font-size: 12px;")
        self.detail_checkbox.setToolTip("기본 요약 완료 후 상세 분석 HTML을 자동으로 생성합니다.\nLLM API를 추가로 호출하므로 시간이 2배 소요됩니다.")
        option_layout.addWidget(self.detail_checkbox)

        # 옵션 상호작용
        self.radio_pending.toggled.connect(lambda checked: self.skip_checkbox.setEnabled(not checked))

        layout.addWidget(option_group)
        
        # 버튼
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton("취소")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        generate_btn = QPushButton("🤖 LLM 요약 생성")
        generate_btn.clicked.connect(self._on_generate)
        button_layout.addWidget(generate_btn)
        
        layout.addLayout(button_layout)
    
    def _update_api_status(self):
        """API 키 상태 업데이트."""
        from full_config import config
        llm_key = self.llm_combo.currentData()
        api_key = config.get_api_key(llm_key)
        
        if api_key:
            self.api_status.setText("✅ API 키 설정됨")
            self.api_status.setStyleSheet("font-size: 11px; color: #4CAF50;")
        else:
            self.api_status.setText("⚠️ API 키 필요")
            self.api_status.setStyleSheet("font-size: 11px; color: #FF9800;")
    
    def _on_generate(self):
        """생성 버튼 클릭."""
        # LLM 선택
        self.selected_llm = self.llm_combo.currentData()
        
        # API 키 확인
        from full_config import config
        if not config.get_api_key(self.selected_llm):
            QMessageBox.warning(
                self, "API 키 필요",
                f"선택한 LLM ({self.llm_combo.currentText()})의 API 키가 설정되어 있지 않습니다.\n\n"
                f"환경변수를 설정하거나 .env 파일에 추가해주세요."
            )
            return
        
        selected = self.type_group.checkedId()
        if selected == 0:
            self.summary_type = "pending"
            self.skip_existing = True  # pending은 항상 skip
        elif selected == 1:
            self.summary_type = "today"
        elif selected == 2:
            self.summary_type = "yesterday"
        elif selected == 3:
            self.summary_type = "2days"
        else:
            self.summary_type = "all"
        
        if selected != 0:
            self.skip_existing = self.skip_checkbox.isChecked()

        self.generate_detail = self.detail_checkbox.isChecked()

        self.accept()


class SummaryProgressDialog(QDialog):
    """요약 진행 상황 다이얼로그."""
    cancel_requested = Signal()
    
    def __init__(self, parent=None, llm_name: str = "LLM", total_dates: int = 0):
        super().__init__(parent)
        self.setWindowTitle("🤖 요약 생성 중...")
        self.setMinimumWidth(500)
        self.setMinimumHeight(200)
        self.setModal(True)
        self._is_cancelled = False
        
        # 닫기 버튼 비활성화
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 헤더
        header = QLabel(f"🤖 {llm_name}으로 요약 생성 중...")
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #1976D2;")
        layout.addWidget(header)
        
        # 현재 처리 중인 날짜
        self.current_label = QLabel("준비 중...")
        self.current_label.setStyleSheet("""
            font-size: 14px; 
            padding: 10px; 
            background-color: #FFF8E1; 
            border-radius: 6px;
            border: 1px solid #FFE082;
        """)
        layout.addWidget(self.current_label)
        
        # 프로그레스 바
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #E0E0E0;
                border-radius: 8px;
                text-align: center;
                font-size: 12px;
                height: 25px;
            }
            QProgressBar::chunk {
                background-color: #FEE500;
                border-radius: 6px;
            }
        """)
        layout.addWidget(self.progress_bar)
        
        # 상세 정보
        self.detail_label = QLabel(f"📅 총 {total_dates}일 처리 예정")
        self.detail_label.setStyleSheet("font-size: 11px; color: #666;")
        layout.addWidget(self.detail_label)
        
        # 취소 버튼
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.cancel_btn = QPushButton("❌ 취소")
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #F44336;
                color: white;
                padding: 10px 30px;
                border-radius: 6px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #D32F2F;
            }
            QPushButton:disabled {
                background-color: #BDBDBD;
            }
        """)
        self.cancel_btn.clicked.connect(self._on_cancel)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(button_layout)
    
    def _on_cancel(self):
        """취소 버튼 클릭."""
        self._is_cancelled = True
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setText("취소 중...")
        self.current_label.setText("⏳ 현재 작업 완료 후 취소됩니다...")
        self.cancel_requested.emit()
    
    def is_cancelled(self) -> bool:
        """취소 여부 확인."""
        return self._is_cancelled
    
    @Slot(int, str)
    def update_progress(self, progress: int, message: str):
        """진행 상황 업데이트."""
        self.progress_bar.setValue(progress)
        self.current_label.setText(f"📅 {message}")
    
    def set_detail(self, text: str):
        """상세 정보 업데이트."""
        self.detail_label.setText(text)
    
    def complete(self, success: bool):
        """완료 처리."""
        if success:
            self.current_label.setText("✅ 완료!")
            self.current_label.setStyleSheet("""
                font-size: 14px; 
                padding: 10px; 
                background-color: #E8F5E9; 
                border-radius: 6px;
                border: 1px solid #A5D6A7;
            """)
        else:
            self.current_label.setText("❌ 실패")
            self.current_label.setStyleSheet("""
                font-size: 14px; 
                padding: 10px; 
                background-color: #FFEBEE; 
                border-radius: 6px;
                border: 1px solid #EF9A9A;
            """)
        
        self.cancel_btn.setText("닫기")
        self.cancel_btn.setEnabled(True)
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 10px 30px;
                border-radius: 6px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #388E3C;
            }
        """)
        self.cancel_btn.clicked.disconnect()
        self.cancel_btn.clicked.connect(self.accept)


class SummaryProgressWidget(QWidget):
    """상태바 내장 요약 프로그레스 위젯 (비모달)."""
    cancel_requested = Signal()

    def __init__(self, parent=None, llm_name: str = "LLM", room_name: str = ""):
        super().__init__(parent)
        self.room_name = room_name
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)

        self.icon_label = QLabel("🤖")
        self.icon_label.setStyleSheet("font-size: 14px;")
        layout.addWidget(self.icon_label)

        self.message_label = QLabel(f"[{room_name}] {llm_name} 요약 중...")
        self.message_label.setStyleSheet("font-size: 12px; color: #191919;")
        layout.addWidget(self.message_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFixedWidth(120)
        self.progress_bar.setFixedHeight(16)
        self.progress_bar.setObjectName("summaryProgressBar")
        layout.addWidget(self.progress_bar)

        self.cancel_btn = QPushButton("❌")
        self.cancel_btn.setToolTip("요약 취소")
        self.cancel_btn.setFixedSize(24, 24)
        self.cancel_btn.setObjectName("summaryProgressCancelBtn")
        self.cancel_btn.clicked.connect(self._on_cancel)
        layout.addWidget(self.cancel_btn)

        self.setObjectName("summaryProgressWidget")

    def _on_cancel(self):
        """취소 버튼 클릭."""
        self.cancel_btn.setEnabled(False)
        self.message_label.setText(f"[{self.room_name}] 취소 중...")
        self.cancel_requested.emit()

    @Slot(int, str)
    def update_progress(self, progress: int, message: str):
        """진행 상황 업데이트."""
        self.progress_bar.setValue(progress)
        self.message_label.setText(f"[{self.room_name}] {message}")

    def set_completed(self, success: bool, message: str):
        """완료 상태 표시."""
        self.progress_bar.setValue(100)
        self.cancel_btn.setVisible(False)
        icon = "✅" if success else "❌"
        self.icon_label.setText(icon)
        self.message_label.setText(message)


class SummaryGeneratorWorker(QThread):
    """LLM 요약 생성 워커."""
    progress = Signal(int, str)
    finished = Signal(bool, str)  # (success, result_or_error)
    
    def __init__(self, room_id: int, summary_type: str, file_path: Optional[str] = None,
                 room_name: Optional[str] = None, skip_existing: bool = True,
                 llm_provider: str = "glm"):
        super().__init__()
        self.room_id = room_id
        self.summary_type = summary_type
        self.file_path = file_path
        self.room_name = room_name or "Unknown"
        self.skip_existing = skip_existing
        self.llm_provider = llm_provider
        self.storage = get_storage()
        self._cancelled = False
    
    def cancel(self):
        """취소 요청."""
        self._cancelled = True
    
    def is_cancelled(self) -> bool:
        """취소 여부 확인."""
        return self._cancelled
    
    def run(self):
        try:
            from pathlib import Path
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent))
            
            from chat_processor import ChatProcessor
            from full_config import config
            from datetime import datetime, timedelta
            from db import get_db
            
            self.progress.emit(10, "데이터 로드 중...")
            
            # 파일 저장소에서 데이터 로드 (우선)
            messages_by_date = self.storage.load_all_originals(self.room_name)
            
            # 파일 저장소에 없으면 원본 파일에서 파싱
            if not messages_by_date and self.file_path and Path(self.file_path).exists():
                from parser import KakaoLogParser
                parser = KakaoLogParser()
                parse_result = parser.parse(Path(self.file_path))
                messages_by_date = parse_result.messages_by_date
            
            if not messages_by_date:
                self.finished.emit(False, "대화 데이터가 없습니다.")
                return
            
            # "pending" 타입: 마지막 요약일(포함) 이후 날짜만
            if self.summary_type == "pending":
                dates_needing_summary = self.storage.get_dates_needing_summary(self.room_name)
                dates_to_process = list(dates_needing_summary.keys())

                if not dates_to_process:
                    self.finished.emit(True, "✅ 모든 날짜가 이미 요약되어 있습니다.")
                    return

                new_count = sum(1 for r in dates_needing_summary.values() if r == "new")
                resummary_count = sum(1 for r in dates_needing_summary.values() if r == "resummary")
                self.progress.emit(15, f"🎯 신규 {new_count}일 + 재요약 {resummary_count}일 예정")
                skipped_count = len(messages_by_date) - len(dates_to_process)
            else:
                # 날짜 범위 계산
                today = datetime.now().strftime("%Y-%m-%d")
                yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
                day_before = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
                
                if self.summary_type == "today":
                    start_date = today
                elif self.summary_type == "yesterday":
                    start_date = yesterday
                elif self.summary_type == "2days":
                    start_date = day_before
                else:  # all
                    start_date = None  # 모든 날짜
                
                # 날짜 필터링
                if start_date:
                    target_dates = [d for d in messages_by_date.keys() if d >= start_date]
                else:
                    target_dates = list(messages_by_date.keys())
                
                if not target_dates:
                    self.finished.emit(False, "해당 기간의 대화가 없습니다.")
                    return
                
                # 이미 요약된 날짜 확인
                summarized_dates = set(self.storage.get_summarized_dates(self.room_name))
                
                # 건너뛸 날짜 필터링
                if self.skip_existing:
                    dates_to_process = [d for d in target_dates if d not in summarized_dates]
                    skipped_count = len(target_dates) - len(dates_to_process)
                else:
                    dates_to_process = target_dates
                    skipped_count = 0
            
            if not dates_to_process:
                summarized_count = len(self.storage.get_summarized_dates(self.room_name))
                self.finished.emit(True, f"✅ 모든 날짜가 이미 요약되어 있습니다.\n(총 {summarized_count}일)")
                return
            
            # LLM 제공자 설정
            config.set_provider(self.llm_provider)
            llm_provider_info = config.get_provider_info()
            
            self.progress.emit(20, f"🤖 {llm_provider_info.name}으로 요약 중... ({len(dates_to_process)}일, {skipped_count}일 건너뜀)")
            
            # LLM 호출 및 일별 요약 저장
            processor = ChatProcessor()
            llm_provider = llm_provider_info.name
            all_summaries = []
            success_count = 0
            fail_count = 0
            
            for i, date_str in enumerate(sorted(dates_to_process)):
                # 취소 체크
                if self._cancelled:
                    self.progress.emit(100, "취소됨")
                    status_msg = f"⚠️ 취소됨 (완료: {success_count}일 / 취소: {len(dates_to_process) - i}일)"
                    if all_summaries:
                        combined_summary = f"{status_msg}\n\n---\n\n" + "\n\n---\n\n".join(all_summaries)
                        self.finished.emit(True, combined_summary)
                    else:
                        self.finished.emit(True, status_msg)
                    return
                
                progress = 20 + int((i + 1) / len(dates_to_process) * 70)
                self.progress.emit(progress, f"{date_str} 요약 중... ({i+1}/{len(dates_to_process)})")
                
                messages = messages_by_date.get(date_str, [])
                if not messages:
                    fail_count += 1
                    continue
                    
                chat_content = "\n".join(messages)
                
                summary = processor.process_summary(chat_content)
                
                if "[ERROR]" not in summary:
                    # 요약 파일 저장
                    self.storage.save_daily_summary(
                        self.room_name, date_str, summary, llm_provider
                    )
                    # DB에도 저장 (기존 요약 삭제 후 추가) - 스레드 안전을 위해 별도 DB 인스턴스 사용
                    try:
                        from db.database import Database
                        worker_db = Database()  # 워커 전용 인스턴스 (싱글톤 X)
                        summary_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                        worker_db.delete_summary(self.room_id, summary_date)
                        worker_db.add_summary(
                            self.room_id, summary_date, "daily",
                            summary, llm_provider
                        )
                        worker_db.engine.dispose()  # 연결 해제
                    except Exception:
                        pass  # 파일 저장은 성공했으므로 DB 실패는 무시
                    all_summaries.append(f"## 📅 {date_str}\n\n{summary}")
                    success_count += 1
                else:
                    fail_count += 1
            
            self.progress.emit(100, "완료!")
            
            # 결과 메시지
            status_msg = f"✅ {success_count}일 요약 완료"
            if skipped_count > 0:
                status_msg += f" | ⏭️ {skipped_count}일 건너뜀"
            if fail_count > 0:
                status_msg += f" | ❌ {fail_count}일 실패"
            
            if all_summaries:
                combined_summary = f"{status_msg}\n\n---\n\n" + "\n\n---\n\n".join(all_summaries)
                self.finished.emit(True, combined_summary)
            else:
                self.finished.emit(True, status_msg)
                
        except Exception as e:
            self.finished.emit(False, f"오류: {str(e)}")


class DetailSummaryWorker(QThread):
    """단일 날짜 상세 분석 워커."""
    progress = Signal(int, str)
    finished = Signal(bool, str)  # (success, result_html_or_error)

    def __init__(self, room_id: int, room_name: str, date_str: str,
                 llm_provider: str = "glm"):
        super().__init__()
        self.room_id = room_id
        self.room_name = room_name
        self.date_str = date_str
        self.llm_provider = llm_provider
        self.storage = get_storage()
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            import sys
            from pathlib import Path as _Path
            sys.path.insert(0, str(_Path(__file__).parent.parent))

            from detail_prompt import call_detail_llm, wrap_detail_html
            from full_config import LLM_PROVIDERS

            self.progress.emit(10, "원본 대화 로드 중...")

            # 원본 메시지 로드
            messages = self.storage.load_daily_original(self.room_name, self.date_str)
            if not messages:
                self.finished.emit(False, "해당 날짜의 대화 데이터가 없습니다.")
                return

            if self._cancelled:
                self.finished.emit(False, "취소됨")
                return

            llm_name = LLM_PROVIDERS.get(self.llm_provider, None)
            llm_display = llm_name.name if llm_name else self.llm_provider

            self.progress.emit(30, f"🔍 {llm_display}으로 상세 분석 중...")

            chat_content = "\n".join(messages)
            result = call_detail_llm(
                chat_content, self.room_name, self.date_str, self.llm_provider
            )

            if self._cancelled:
                self.finished.emit(False, "취소됨")
                return

            if not result["success"]:
                self.finished.emit(False, f"상세 분석 실패: {result['error']}")
                return

            self.progress.emit(80, "HTML 파일 저장 중...")

            # 다크 테마 HTML로 래핑
            html_content = wrap_detail_html(
                result["content"], self.room_name, self.date_str, llm_display
            )

            # 파일 저장
            filepath = self.storage.save_detail_summary(
                self.room_name, self.date_str, html_content, llm_display
            )

            self.progress.emit(100, "완료!")
            self.finished.emit(True, str(filepath))

        except Exception as e:
            self.finished.emit(False, f"오류: {str(e)}")


class DetailBatchWorker(QThread):
    """여러 날짜의 상세 분석을 일괄 생성하는 워커."""
    progress = Signal(int, str)
    finished = Signal(bool, str)  # (success, result_message)

    def __init__(self, room_id: int, room_name: str, dates: list,
                 llm_provider: str = "glm"):
        super().__init__()
        self.room_id = room_id
        self.room_name = room_name
        self.dates = dates
        self.llm_provider = llm_provider
        self.storage = get_storage()
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            import sys
            from pathlib import Path as _Path
            sys.path.insert(0, str(_Path(__file__).parent.parent))

            from detail_prompt import call_detail_llm, wrap_detail_html
            from full_config import LLM_PROVIDERS

            llm_name = LLM_PROVIDERS.get(self.llm_provider, None)
            llm_display = llm_name.name if llm_name else self.llm_provider

            success_count = 0
            fail_count = 0
            skip_count = 0

            for i, date_str in enumerate(sorted(self.dates)):
                if self._cancelled:
                    msg = f"⚠️ 상세 분석 취소됨 (완료: {success_count}일 / 남은: {len(self.dates) - i}일)"
                    self.finished.emit(True, msg)
                    return

                # 이미 상세 분석이 있으면 건너뛰기
                if self.storage.has_detail_summary(self.room_name, date_str):
                    skip_count += 1
                    continue

                pct = int((i + 1) / len(self.dates) * 100)
                self.progress.emit(pct, f"🔍 {date_str} 상세 분석 중... ({i+1}/{len(self.dates)})")

                messages = self.storage.load_daily_original(self.room_name, date_str)
                if not messages:
                    fail_count += 1
                    continue

                chat_content = "\n".join(messages)
                result = call_detail_llm(
                    chat_content, self.room_name, date_str, self.llm_provider
                )

                if result["success"]:
                    html_content = wrap_detail_html(
                        result["content"], self.room_name, date_str, llm_display
                    )
                    self.storage.save_detail_summary(
                        self.room_name, date_str, html_content, llm_display
                    )
                    success_count += 1
                else:
                    fail_count += 1

            self.progress.emit(100, "상세 분석 완료!")

            msg = f"🔍 상세 분석: ✅ {success_count}일 완료"
            if skip_count > 0:
                msg += f" | ⏭️ {skip_count}일 건너뜀"
            if fail_count > 0:
                msg += f" | ❌ {fail_count}일 실패"

            self.finished.emit(True, msg)

        except Exception as e:
            self.finished.emit(False, f"상세 분석 오류: {str(e)}")


class AllRoomsSummaryWorker(QThread):
    """전체 채팅방 LLM 요약 생성 워커."""
    progress = Signal(int, str)  # (progress_percent, message)
    finished = Signal(bool, str)  # (success, result_or_error)

    def __init__(self, summary_type: str = "pending", skip_existing: bool = True,
                 llm_provider: str = "glm"):
        super().__init__()
        self.summary_type = summary_type
        self.skip_existing = skip_existing
        self.llm_provider = llm_provider
        self.storage = get_storage()
        self._cancelled = False

    def cancel(self):
        """취소 요청."""
        self._cancelled = True

    def is_cancelled(self) -> bool:
        """취소 여부 확인."""
        return self._cancelled

    def run(self):
        try:
            from pathlib import Path
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent))

            from chat_processor import ChatProcessor
            from full_config import config
            from datetime import datetime, timedelta
            from db.database import Database

            # LLM 제공자 설정
            config.set_provider(self.llm_provider)
            llm_provider_info = config.get_provider_info()
            llm_provider_name = llm_provider_info.name

            self.progress.emit(5, "전체 채팅방 스캔 중...")

            # 워커 전용 DB 인스턴스
            worker_db = Database()

            # DB에서 모든 채팅방 가져오기
            all_rooms = worker_db.get_all_rooms()
            if not all_rooms:
                worker_db.engine.dispose()
                self.finished.emit(False, "등록된 채팅방이 없습니다.")
                return

            processor = ChatProcessor()
            total_rooms = len(all_rooms)
            total_success = 0
            total_fail = 0
            total_skipped_rooms = 0
            room_results = []  # 채팅방별 결과 요약

            for room_idx, room in enumerate(all_rooms):
                if self._cancelled:
                    break

                room_name = room.name
                room_id = room.id
                room_progress_base = int((room_idx / total_rooms) * 90) + 5

                self.progress.emit(
                    room_progress_base,
                    f"[{room_idx+1}/{total_rooms}] {room_name} 처리 중..."
                )

                # 채팅방별 원본 데이터 로드
                messages_by_date = self.storage.load_all_originals(room_name)
                if not messages_by_date:
                    room_results.append(f"⏭️ {room_name}: 데이터 없음")
                    total_skipped_rooms += 1
                    continue

                # 날짜 범위 결정 (기존 SummaryGeneratorWorker와 동일 로직)
                if self.summary_type == "pending":
                    dates_needing = self.storage.get_dates_needing_summary(room_name)
                    dates_to_process = list(dates_needing.keys())
                elif self.summary_type == "all":
                    all_dates = list(messages_by_date.keys())
                    if self.skip_existing:
                        summarized = set(self.storage.get_summarized_dates(room_name))
                        dates_to_process = [d for d in all_dates if d not in summarized]
                    else:
                        dates_to_process = all_dates
                else:
                    # today, yesterday, 2days
                    today = datetime.now().strftime("%Y-%m-%d")
                    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
                    day_before = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")

                    if self.summary_type == "today":
                        start_date = today
                    elif self.summary_type == "yesterday":
                        start_date = yesterday
                    elif self.summary_type == "2days":
                        start_date = day_before
                    else:
                        start_date = None

                    if start_date:
                        target_dates = [d for d in messages_by_date.keys() if d >= start_date]
                    else:
                        target_dates = list(messages_by_date.keys())

                    if self.skip_existing:
                        summarized = set(self.storage.get_summarized_dates(room_name))
                        dates_to_process = [d for d in target_dates if d not in summarized]
                    else:
                        dates_to_process = target_dates

                if not dates_to_process:
                    room_results.append(f"⏭️ {room_name}: 요약 필요 없음")
                    total_skipped_rooms += 1
                    continue

                # 날짜별 요약 생성
                room_success = 0
                room_fail = 0

                for date_idx, date_str in enumerate(sorted(dates_to_process)):
                    if self._cancelled:
                        break

                    # 전체 진행률 계산
                    room_date_progress = room_progress_base + int(
                        ((date_idx + 1) / len(dates_to_process)) *
                        (90 / total_rooms)
                    )
                    self.progress.emit(
                        min(room_date_progress, 95),
                        f"[{room_idx+1}/{total_rooms}] {room_name} - {date_str} ({date_idx+1}/{len(dates_to_process)})"
                    )

                    messages = messages_by_date.get(date_str, [])
                    if not messages:
                        room_fail += 1
                        continue

                    chat_content = "\n".join(messages)
                    summary = processor.process_summary(chat_content)

                    if "[ERROR]" not in summary:
                        # 파일 저장
                        self.storage.save_daily_summary(
                            room_name, date_str, summary, llm_provider_name
                        )
                        # DB 저장
                        try:
                            summary_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                            worker_db.delete_summary(room_id, summary_date)
                            worker_db.add_summary(
                                room_id, summary_date, "daily",
                                summary, llm_provider_name
                            )
                        except Exception:
                            pass  # 파일 저장 성공이면 DB 실패는 무시
                        room_success += 1
                    else:
                        room_fail += 1

                total_success += room_success
                total_fail += room_fail
                room_results.append(
                    f"{'✅' if room_fail == 0 else '⚠️'} {room_name}: "
                    f"{room_success}일 완료" +
                    (f", {room_fail}일 실패" if room_fail > 0 else "")
                )

            worker_db.engine.dispose()

            self.progress.emit(100, "전체 완료!")

            # 결과 메시지 구성
            if self._cancelled:
                status = f"⚠️ 취소됨 | 완료: {total_success}일"
            else:
                status = f"✅ 전체 완료: {total_success}일 요약"

            if total_fail > 0:
                status += f" | ❌ {total_fail}일 실패"
            if total_skipped_rooms > 0:
                status += f" | ⏭️ {total_skipped_rooms}개 채팅방 건너뜀"

            detail = "\n".join(room_results)
            result_msg = f"{status}\n\n--- 채팅방별 결과 ---\n{detail}"
            self.finished.emit(True, result_msg)

        except Exception as e:
            self.finished.emit(False, f"오류: {str(e)}")


class AllRoomsDetailWorker(QThread):
    """전체 채팅방 상세 분석 일괄 생성 워커."""
    progress = Signal(int, str)
    finished = Signal(bool, str)

    def __init__(self, rooms: list, llm_provider: str = "glm"):
        """
        Args:
            rooms: [(room_id, room_name), ...] 리스트
            llm_provider: LLM 제공자 키
        """
        super().__init__()
        self.rooms = rooms
        self.llm_provider = llm_provider
        self.storage = get_storage()
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            import sys
            from pathlib import Path as _Path
            sys.path.insert(0, str(_Path(__file__).parent.parent))

            from detail_prompt import call_detail_llm, wrap_detail_html
            from full_config import LLM_PROVIDERS

            llm_info = LLM_PROVIDERS.get(self.llm_provider)
            llm_display = llm_info.name if llm_info else self.llm_provider

            total_success = 0
            total_fail = 0
            total_skip = 0
            results = []  # (room_name, success, skip, fail)

            for room_idx, (room_id, room_name) in enumerate(self.rooms):
                if self._cancelled:
                    break

                # 이 채팅방에서 상세 분석이 필요한 날짜
                summarized = self.storage.get_summarized_dates(room_name)
                dates_needing = [
                    d for d in summarized
                    if not self.storage.has_detail_summary(room_name, d)
                ]

                if not dates_needing:
                    total_skip += len(summarized)
                    results.append((room_name, 0, len(summarized), 0))
                    continue

                room_success = 0
                room_fail = 0

                for i, date_str in enumerate(sorted(dates_needing)):
                    if self._cancelled:
                        break

                    overall = room_idx * 100 // len(self.rooms)
                    self.progress.emit(
                        overall,
                        f"[{room_idx+1}/{len(self.rooms)}] {room_name} — {date_str} ({i+1}/{len(dates_needing)})"
                    )

                    messages = self.storage.load_daily_original(room_name, date_str)
                    if not messages:
                        room_fail += 1
                        continue

                    chat_content = "\n".join(messages)
                    result = call_detail_llm(
                        chat_content, room_name, date_str, self.llm_provider
                    )

                    if result["success"]:
                        html = wrap_detail_html(
                            result["content"], room_name, date_str, llm_display
                        )
                        self.storage.save_detail_summary(
                            room_name, date_str, html, llm_display
                        )
                        room_success += 1
                    else:
                        room_fail += 1

                total_success += room_success
                total_fail += room_fail
                results.append((room_name, room_success, 0, room_fail))

            self.progress.emit(100, "완료!")

            # 결과 메시지
            lines = [f"🔍 전체 채팅방 상세 분석 완료\n"]
            for rn, s, sk, f in results:
                parts = []
                if s > 0:
                    parts.append(f"✅ {s}일")
                if sk > 0:
                    parts.append(f"⏭️ {sk}일")
                if f > 0:
                    parts.append(f"❌ {f}일")
                if parts:
                    lines.append(f"  • {rn}: {' / '.join(parts)}")

            lines.append(f"\n합계: ✅ {total_success}일 완료 | ⏭️ {total_skip}일 건너뜀 | ❌ {total_fail}일 실패")
            if self._cancelled:
                lines.append("⚠️ 사용자 취소")

            self.finished.emit(True, "\n".join(lines))

        except Exception as e:
            self.finished.emit(False, f"오류: {str(e)}")


class AllRoomsUrlSyncWorker(QThread):
    """전체 채팅방 URL 동기화 워커."""
    progress = Signal(int, str)
    finished = Signal(bool, str)

    def __init__(self):
        super().__init__()
        self.storage = get_storage()
        self._cancelled = False

    def cancel(self):
        """취소 요청."""
        self._cancelled = True

    def run(self):
        try:
            from pathlib import Path
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent))

            from db.database import Database
            from url_extractor import extract_urls_from_text, deduplicate_urls
            from datetime import date, timedelta

            self.progress.emit(5, "전체 채팅방 URL 스캔 중...")

            worker_db = Database()
            all_rooms = worker_db.get_all_rooms()

            if not all_rooms:
                worker_db.engine.dispose()
                self.finished.emit(False, "등록된 채팅방이 없습니다.")
                return

            total_rooms = len(all_rooms)
            total_urls = 0
            room_results = []

            today = date.today()
            three_days_ago = today - timedelta(days=3)
            one_week_ago = today - timedelta(days=7)

            for room_idx, room in enumerate(all_rooms):
                if self._cancelled:
                    break

                room_name = room.name
                room_id = room.id
                progress_pct = int((room_idx / total_rooms) * 90) + 5

                self.progress.emit(
                    progress_pct,
                    f"[{room_idx+1}/{total_rooms}] {room_name} URL 수집 중..."
                )

                # 요약 날짜 목록 로드
                summary_dates = self.storage.get_summarized_dates(room_name)
                if not summary_dates:
                    room_results.append(f"⏭️ {room_name}: 요약 없음")
                    continue

                # 날짜별 URL 추출
                urls_by_date = {}
                for date_str in sorted(summary_dates):
                    summary = self.storage.load_daily_summary(room_name, date_str)
                    if summary:
                        urls = extract_urls_from_text(summary)
                        if urls:
                            urls_by_date[date_str] = urls

                if not urls_by_date:
                    room_results.append(f"⏭️ {room_name}: URL 없음")
                    continue

                # 기간별 URL 분류
                def extract_for_period(start_d):
                    period_urls = {}
                    for ds, urls in urls_by_date.items():
                        try:
                            d = date.fromisoformat(ds)
                            if d >= start_d:
                                for url, descs in urls.items():
                                    if url not in period_urls:
                                        period_urls[url] = []
                                    for desc in descs:
                                        if desc and desc not in period_urls[url]:
                                            period_urls[url].append(desc)
                        except Exception:
                            pass
                    return period_urls

                urls_recent = deduplicate_urls(extract_for_period(three_days_ago))
                urls_weekly = deduplicate_urls(extract_for_period(one_week_ago))
                urls_all = {}
                for ds, urls in urls_by_date.items():
                    for url, descs in urls.items():
                        if url not in urls_all:
                            urls_all[url] = []
                        for desc in descs:
                            if desc and desc not in urls_all[url]:
                                urls_all[url].append(desc)
                urls_all = deduplicate_urls(urls_all)

                if urls_all:
                    # DB 저장
                    try:
                        worker_db.clear_urls_by_room(room_id)
                        worker_db.add_urls_batch(room_id, urls_all)
                    except Exception:
                        pass

                    # 파일 저장
                    self.storage.save_url_lists(
                        room_name, urls_recent, urls_weekly, urls_all
                    )

                    total_urls += len(urls_all)
                    room_results.append(
                        f"✅ {room_name}: {len(urls_all)}개 URL"
                    )
                else:
                    room_results.append(f"⏭️ {room_name}: URL 없음")

            worker_db.engine.dispose()
            self.progress.emit(100, "전체 완료!")

            if self._cancelled:
                status = f"⚠️ 취소됨 | 수집: {total_urls}개 URL"
            else:
                status = f"✅ 전체 완료: {total_urls}개 URL 수집"

            detail = "\n".join(room_results)
            result_msg = f"{status}\n\n--- 채팅방별 결과 ---\n{detail}"
            self.finished.emit(True, result_msg)

        except Exception as e:
            self.finished.emit(False, f"오류: {str(e)}")


class RecoveryWorker(QThread):
    """DB 복구 워커 - 파일 저장소에서 DB 복구."""
    progress = Signal(int, str)
    finished = Signal(bool, str)
    
    def __init__(self):
        super().__init__()
        self.storage = get_storage()
    
    def run(self):
        try:
            from db import get_db, reset_db
            
            self.progress.emit(5, "기존 DB 초기화 중...")
            
            # DB 리셋
            reset_db()
            db = get_db(force_new=True)
            
            # 모든 채팅방 조회
            self.progress.emit(10, "파일 저장소 스캔 중...")
            rooms = self.storage.get_all_rooms()
            
            if not rooms:
                self.finished.emit(False, "복구할 데이터가 없습니다.")
                return
            
            total_messages = 0
            total_summaries = 0
            
            for room_idx, room_name in enumerate(rooms):
                room_progress = 10 + int((room_idx / len(rooms)) * 80)
                self.progress.emit(room_progress, f"'{room_name}' 복구 중...")
                
                # 채팅방 생성
                room = db.create_room(room_name)
                
                # 원본 데이터 로드 및 메시지 복구
                messages_by_date = self.storage.load_all_originals(room_name)
                
                for date_str, lines in messages_by_date.items():
                    from datetime import datetime
                    msg_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                    messages = []
                    
                    for line in lines:
                        parsed = MessageParser.parse_message(line, msg_date)
                        if parsed:
                            messages.append(parsed)
                    
                    if messages:
                        try:
                            db.add_messages(room.id, messages)
                            total_messages += len(messages)
                        except Exception:
                            pass
                
                # 요약 복구
                summary_dates = self.storage.get_summarized_dates(room_name)
                for date_str in summary_dates:
                    summary_content = self.storage.load_daily_summary(room_name, date_str)
                    if summary_content:
                        try:
                            from datetime import datetime as dt_cls
                            summary_date_obj = dt_cls.strptime(date_str, '%Y-%m-%d').date()
                            db.add_summary(
                                room.id,
                                summary_date_obj,
                                "daily",
                                summary_content if summary_content else ""
                            )
                            total_summaries += 1
                        except Exception:
                            pass
            
            self.progress.emit(100, "복구 완료!")
            self.finished.emit(
                True, 
                f"✅ 복구 완료!\n\n"
                f"📁 채팅방: {len(rooms)}개\n"
                f"💬 메시지: {total_messages:,}개\n"
                f"📝 요약: {total_summaries}개"
            )
            
        except Exception as e:
            self.finished.emit(False, f"복구 실패: {str(e)}")


class CreateRoomDialog(QDialog):
    """채팅방 생성 다이얼로그."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("➕ 채팅방 만들기")
        self.setMinimumWidth(400)
        self.room_name = ""
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # 안내 메시지
        info_label = QLabel("새 채팅방을 만듭니다.\n나중에 카카오톡 대화 파일을 업로드할 수 있습니다.")
        info_label.setStyleSheet("color: #666666; font-size: 12px;")
        layout.addWidget(info_label)
        
        # 채팅방 이름 입력
        name_group = QGroupBox("채팅방 이름")
        name_layout = QVBoxLayout(name_group)
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("예: 개발팀, 동아리모임...")
        self.name_input.setStyleSheet("""
            QLineEdit {
                padding: 12px;
                font-size: 14px;
                border: 2px solid #E0E0E0;
                border-radius: 8px;
            }
            QLineEdit:focus {
                border-color: #FEE500;
            }
        """)
        name_layout.addWidget(self.name_input)
        layout.addWidget(name_group)
        
        # 버튼
        layout.addStretch()
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton("취소")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #F5F5F5;
                color: #333333;
                padding: 10px 25px;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        self.create_btn = QPushButton("➕ 만들기")
        self.create_btn.setEnabled(False)
        self.create_btn.clicked.connect(self._on_create)
        self.create_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 25px;
            }
        """)
        button_layout.addWidget(self.create_btn)
        
        layout.addLayout(button_layout)
        
        # 입력 변경 시 버튼 활성화 체크
        self.name_input.textChanged.connect(self._check_input)
        self.name_input.returnPressed.connect(self._on_create)
        self.create_btn.setDefault(True)
    
    def _check_input(self):
        """입력 확인 및 버튼 활성화."""
        has_name = bool(self.name_input.text().strip())
        self.create_btn.setEnabled(has_name)
    
    def _on_create(self):
        """만들기 버튼 클릭."""
        name = self.name_input.text().strip()
        if not name:
            return
        self.room_name = name
        self.accept()


class UploadFileDialog(QDialog):
    """파일 업로드 다이얼로그."""
    
    def __init__(self, room_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📤 파일 업로드")
        self.setMinimumWidth(450)
        self.room_name = room_name
        self.file_path = ""
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # 채팅방 정보
        room_label = QLabel(f"📁 채팅방: <b>{room_name}</b>")
        room_label.setStyleSheet("font-size: 14px; padding: 10px; background-color: #FEE500; border-radius: 8px;")
        layout.addWidget(room_label)
        
        # 파일 선택
        file_group = QGroupBox("카카오톡 대화 파일")
        file_layout = QVBoxLayout(file_group)
        
        file_row = QHBoxLayout()
        self.file_label = QLabel("선택된 파일 없음")
        self.file_label.setStyleSheet("color: #888888;")
        file_row.addWidget(self.file_label, 1)
        
        browse_btn = QPushButton("📂 파일 선택")
        browse_btn.clicked.connect(self._browse_file)
        browse_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 15px;
            }
        """)
        file_row.addWidget(browse_btn)
        file_layout.addLayout(file_row)
        
        hint_label = QLabel("💡 카카오톡 앱에서 '대화 내보내기'로 저장한 .txt 파일을 선택하세요.\n여러 번 업로드하면 기존 데이터와 병합됩니다.")
        hint_label.setStyleSheet("color: #888888; font-size: 11px;")
        hint_label.setWordWrap(True)
        file_layout.addWidget(hint_label)
        
        layout.addWidget(file_group)
        
        # 버튼
        layout.addStretch()
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton("취소")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #F5F5F5;
                color: #333333;
                padding: 10px 25px;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        self.upload_btn = QPushButton("📤 업로드")
        self.upload_btn.setEnabled(False)
        self.upload_btn.clicked.connect(self.accept)
        self.upload_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 25px;
            }
        """)
        button_layout.addWidget(self.upload_btn)
        
        layout.addLayout(button_layout)
    
    def _browse_file(self):
        """파일 선택."""
        # 기본 디렉터리: upload/
        upload_dir = Path(__file__).parent.parent.parent / "upload"
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, "카카오톡 대화 파일 선택",
            str(upload_dir),
            "대화 파일 (*.txt *.csv)"
        )
        if file_path:
            self.file_path = file_path
            filename = Path(file_path).name
            self.file_label.setText(f"✅ {filename}")
            self.file_label.setStyleSheet("color: #333333;")
            self.upload_btn.setEnabled(True)


class SettingsDialog(QDialog):
    """설정 다이얼로그."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ 설정")
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout(self)
        
        # 동기화 설정
        sync_group = QGroupBox("🔄 자동 동기화")
        sync_layout = QFormLayout(sync_group)
        
        self.sync_interval = QSpinBox()
        self.sync_interval.setRange(5, 120)
        self.sync_interval.setValue(30)
        self.sync_interval.setSuffix(" 분")
        sync_layout.addRow("동기화 간격:", self.sync_interval)
        
        self.auto_summary = QComboBox()
        self.auto_summary.addItems(["비활성화", "매일", "2일마다", "매주"])
        sync_layout.addRow("자동 요약:", self.auto_summary)
        
        layout.addWidget(sync_group)
        
        # LLM 설정
        llm_group = QGroupBox("🤖 LLM 설정")
        llm_layout = QFormLayout(llm_group)
        
        self.llm_provider = QComboBox()
        self.llm_provider.addItems(["Z.AI GLM", "OpenAI GPT", "Anthropic Claude", "Google Gemini"])
        llm_layout.addRow("LLM 제공자:", self.llm_provider)
        
        layout.addWidget(llm_group)
        
        # 버튼
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class MainWindow(QMainWindow):
    """메인 윈도우."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🗨️ 카카오톡 대화 분석기")
        self.setMinimumSize(1000, 700)
        self.setStyleSheet(MAIN_STYLESHEET)
        
        self.current_room_id: Optional[int] = None
        self.current_room_file: Optional[str] = None
        self.db = get_db()
        self.storage = get_storage()
        
        # 워커 참조 유지
        self.upload_worker: Optional[FileUploadWorker] = None
        self.sync_worker: Optional[SyncWorker] = None
        self.summary_worker: Optional[SummaryGeneratorWorker] = None
        self.all_rooms_summary_worker: Optional[AllRoomsSummaryWorker] = None
        self.all_rooms_url_worker: Optional[AllRoomsUrlSyncWorker] = None
        self.recovery_worker: Optional[RecoveryWorker] = None
        self.progress_dialog: Optional[SummaryProgressDialog] = None
        self.summary_progress_widget: Optional[SummaryProgressWidget] = None
        self._summary_in_progress: bool = False
        self.summary_source_room_id: Optional[int] = None
        self.detail_worker: Optional[DetailSummaryWorker] = None
        self.detail_batch_worker: Optional[DetailBatchWorker] = None
        self.all_rooms_detail_worker: Optional[AllRoomsDetailWorker] = None
        self._detail_view_active: bool = False
        self._detail_after_summary: bool = False
        self._detail_llm_provider: str = "glm"
        
        self._setup_ui()
        self._setup_menu()
        self._setup_statusbar()
        self._load_rooms()
    
    def _setup_ui(self):
        """UI 구성."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 스플리터
        splitter = QSplitter(Qt.Horizontal)
        
        # ===== 좌측 패널: 채팅방 목록 =====
        left_panel = QWidget()
        left_panel.setObjectName("chatListPanel")
        left_panel.setMinimumWidth(250)
        left_panel.setMaximumWidth(350)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        
        # 헤더
        header = QLabel("💬 채팅방")
        header.setObjectName("chatListTitle")
        header.setStyleSheet("""
            font-size: 18px;
            font-weight: bold;
            color: #191919;
            padding: 15px;
            background-color: #FEE500;
        """)
        left_layout.addWidget(header)
        
        # 채팅방 목록
        self.room_list_widget = QWidget()
        self.room_list_layout = QVBoxLayout(self.room_list_widget)
        self.room_list_layout.setContentsMargins(5, 5, 5, 5)
        self.room_list_layout.setSpacing(5)
        from PySide6.QtWidgets import QLayout
        self.room_list_layout.setSizeConstraint(QLayout.SetMinimumSize)
        self.room_list_layout.addStretch()
        
        scroll = QScrollArea()
        scroll.setWidget(self.room_list_widget)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: #F5F5F5; }")
        left_layout.addWidget(scroll, 1)
        
        # 채팅방 만들기 버튼
        add_btn = QPushButton("➕ 채팅방 만들기")
        add_btn.clicked.connect(self._on_add_room)
        add_btn.setStyleSheet("""
            QPushButton {
                margin: 10px 10px 5px 10px;
                padding: 12px;
            }
        """)
        left_layout.addWidget(add_btn)
        
        splitter.addWidget(left_panel)
        
        # ===== 우측 패널: 탭 =====
        right_panel = QWidget()
        right_panel.setObjectName("mainPanel")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        
        # 헤더
        header_widget = QWidget()
        header_widget.setStyleSheet("background-color: #FEE500;")
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(15, 10, 15, 10)
        
        self.header_label = QLabel("📊 대시보드")
        self.header_label.setObjectName("headerTitle")
        self.header_label.setStyleSheet("""
            font-size: 20px;
            font-weight: bold;
            color: #191919;
            background-color: transparent;
        """)
        header_layout.addWidget(self.header_label)
        
        header_layout.addStretch()
        
        # 업로드 버튼
        self.upload_btn = QPushButton("📤 파일 업로드")
        self.upload_btn.clicked.connect(self._on_upload_file)
        self.upload_btn.setStyleSheet("""
            QPushButton {
                background-color: #3C1E1E;
                color: white;
                padding: 8px 15px;
                border-radius: 6px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #5C3E3E;
            }
        """)
        header_layout.addWidget(self.upload_btn)
        
        right_layout.addWidget(header_widget)
        
        # 탭 위젯
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background-color: #FAFAFA;
            }
            QTabBar::tab {
                background-color: #E0E0E0;
                padding: 10px 25px;
                margin-right: 2px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-size: 13px;
            }
            QTabBar::tab:selected {
                background-color: #FEE500;
                font-weight: bold;
            }
            QTabBar::tab:hover:!selected {
                background-color: #EEEEEE;
            }
        """)
        
        # ===== 탭 1: 대시보드 =====
        dashboard_tab = QWidget()
        dashboard_layout = QVBoxLayout(dashboard_tab)
        dashboard_layout.setContentsMargins(0, 0, 0, 0)
        
        # 대시보드 카드 영역
        cards_widget = QWidget()
        cards_layout = QHBoxLayout(cards_widget)
        cards_layout.setContentsMargins(10, 5, 10, 5)
        
        self.card_messages = DashboardCard("총 메시지", "0", "전체 기간", "💬")
        self.card_participants = DashboardCard("참여자", "0", "명", "👥")
        self.card_summaries = DashboardCard("요약", "0", "개 생성됨", "📝")
        
        cards_layout.addWidget(self.card_messages)
        cards_layout.addWidget(self.card_participants)
        cards_layout.addWidget(self.card_summaries)
        
        dashboard_layout.addWidget(cards_widget)
        
        # 요약 뷰어 (대시보드)
        summary_frame = QFrame()
        summary_frame.setObjectName("summaryViewer")
        summary_frame.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #E8E8E8;
                border-radius: 12px;
                margin: 10px;
            }
        """)
        summary_layout = QVBoxLayout(summary_frame)
        
        summary_header = QHBoxLayout()
        summary_title = QLabel("📅 최근 요약")
        summary_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        summary_header.addWidget(summary_title)
        
        self.generate_btn = QPushButton("🤖 LLM 요약 생성")
        self.generate_btn.clicked.connect(self._on_generate_summary)
        summary_header.addWidget(self.generate_btn)
        
        summary_layout.addLayout(summary_header)
        
        self.summary_browser = QTextBrowser()
        self.summary_browser.setOpenExternalLinks(True)
        self.summary_browser.setStyleSheet("""
            QTextBrowser {
                border: none;
                background-color: transparent;
                font-size: 16px;
            }
        """)
        self.summary_browser.setPlaceholderText("채팅방을 선택하면 요약이 표시됩니다.")
        summary_layout.addWidget(self.summary_browser)
        
        dashboard_layout.addWidget(summary_frame, 1)
        
        self.tab_widget.addTab(dashboard_tab, "📊 대시보드")
        
        # ===== 탭 2: 날짜별 요약 =====
        detail_tab = QWidget()
        detail_layout = QVBoxLayout(detail_tab)
        detail_layout.setContentsMargins(10, 10, 10, 10)
        detail_layout.setSpacing(10)
        
        # 날짜 네비게이션
        nav_widget = QWidget()
        nav_widget.setStyleSheet("""
            QWidget {
                background-color: #FFFFFF;
                border: 1px solid #E8E8E8;
                border-radius: 8px;
            }
        """)
        nav_layout = QHBoxLayout(nav_widget)
        nav_layout.setContentsMargins(15, 10, 15, 10)
        
        # 이전 날짜 버튼
        self.prev_date_btn = QPushButton("◀ 이전")
        self.prev_date_btn.setStyleSheet("""
            QPushButton {
                background-color: #E0E0E0;
                padding: 8px 20px;
                border-radius: 6px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #BDBDBD;
            }
        """)
        self.prev_date_btn.clicked.connect(self._on_prev_date)
        nav_layout.addWidget(self.prev_date_btn)
        
        nav_layout.addStretch()
        
        # 날짜 선택
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setDisplayFormat("yyyy년 MM월 dd일")
        self.date_edit.setStyleSheet("""
            QDateEdit {
                border: 2px solid #FEE500;
                border-radius: 6px;
                padding: 8px 15px;
                font-size: 14px;
                font-weight: bold;
                min-width: 160px;
            }
            QDateEdit::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: center right;
                width: 30px;
                border: none;
            }
            QDateEdit::down-arrow {
                image: none;
                width: 0;
            }
        """)
        
        # QCalendarWidget 스타일링
        calendar = self.date_edit.calendarWidget()
        calendar.setStyleSheet("""
            QCalendarWidget {
                background-color: #FFFFFF;
            }
            QCalendarWidget QToolButton {
                color: #333;
                font-size: 14px;
                font-weight: bold;
                icon-size: 20px;
                padding: 5px;
            }
            QCalendarWidget QToolButton:hover {
                background-color: #FEE500;
                border-radius: 4px;
            }
            QCalendarWidget QMenu {
                background-color: #FFFFFF;
            }
            QCalendarWidget QSpinBox {
                font-size: 14px;
                font-weight: bold;
            }
            QCalendarWidget QWidget#qt_calendar_navigationbar {
                background-color: #FEE500;
            }
            QCalendarWidget QTableView {
                selection-background-color: #FEE500;
                selection-color: #000000;
            }
            QCalendarWidget QTableView::item:hover {
                background-color: #FFF9C4;
            }
        """)
        self.date_edit.dateChanged.connect(self._on_date_changed)
        nav_layout.addWidget(self.date_edit)
        
        # 달력 버튼
        self.calendar_btn = QPushButton("📅")
        self.calendar_btn.setToolTip("달력에서 선택")
        self.calendar_btn.setStyleSheet("""
            QPushButton {
                background-color: #FEE500;
                border: none;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #FFD700;
            }
        """)
        self.calendar_btn.clicked.connect(self._show_calendar_dialog)
        nav_layout.addWidget(self.calendar_btn)
        
        nav_layout.addStretch()
        
        # 다음 날짜 버튼
        self.next_date_btn = QPushButton("다음 ▶")
        self.next_date_btn.setStyleSheet("""
            QPushButton {
                background-color: #E0E0E0;
                padding: 8px 20px;
                border-radius: 6px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #BDBDBD;
            }
        """)
        self.next_date_btn.clicked.connect(self._on_next_date)
        nav_layout.addWidget(self.next_date_btn)
        
        detail_layout.addWidget(nav_widget)
        
        # 날짜 정보
        self.date_info_label = QLabel("📊 날짜를 선택하세요")
        self.date_info_label.setStyleSheet("""
            font-size: 12px;
            color: #666;
            padding: 5px 10px;
        """)
        detail_layout.addWidget(self.date_info_label)

        # ===== 기본/상세 토글 바 =====
        toggle_bar = QWidget()
        toggle_bar.setStyleSheet("QWidget { background: transparent; }")
        toggle_layout = QHBoxLayout(toggle_bar)
        toggle_layout.setContentsMargins(5, 0, 5, 0)
        toggle_layout.setSpacing(6)

        self.basic_view_btn = QPushButton("📝 기본 요약")
        self.basic_view_btn.setStyleSheet("""
            QPushButton {
                background-color: #FEE500; color: #000; font-weight: bold;
                padding: 6px 16px; border-radius: 6px; font-size: 11px; border: none;
            }
        """)
        self.basic_view_btn.clicked.connect(lambda: self._toggle_detail_view(False))
        toggle_layout.addWidget(self.basic_view_btn)

        self.detail_view_btn = QPushButton("🔍 상세 분석")
        self.detail_view_btn.setStyleSheet("""
            QPushButton {
                background-color: #E0E0E0; color: #333;
                padding: 6px 16px; border-radius: 6px; font-size: 11px; border: none;
            }
            QPushButton:hover { background-color: #BDBDBD; }
        """)
        self.detail_view_btn.clicked.connect(lambda: self._toggle_detail_view(True))
        toggle_layout.addWidget(self.detail_view_btn)

        toggle_layout.addStretch()

        # === 기본 요약 뷰 전용 버튼 ===
        self.basic_generate_btn = QPushButton("📝 요약 생성")
        self.basic_generate_btn.setToolTip("현재 채팅방의 LLM 요약 생성 다이얼로그 열기")
        self.basic_generate_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800; color: white;
                padding: 6px 16px; border-radius: 6px; font-size: 11px; border: none;
            }
            QPushButton:hover { background-color: #F57C00; }
        """)
        self.basic_generate_btn.clicked.connect(self._on_generate_summary)
        self.basic_generate_btn.setVisible(False)
        toggle_layout.addWidget(self.basic_generate_btn)

        # === 상세 분석 뷰 전용 버튼 ===
        self.detail_generate_btn = QPushButton("🔍 상세 생성")
        self.detail_generate_btn.setStyleSheet("""
            QPushButton {
                background-color: #1976D2; color: white;
                padding: 6px 16px; border-radius: 6px; font-size: 11px; border: none;
            }
            QPushButton:hover { background-color: #1565C0; }
        """)
        self.detail_generate_btn.clicked.connect(self._on_generate_detail_summary)
        self.detail_generate_btn.setVisible(False)
        toggle_layout.addWidget(self.detail_generate_btn)

        self.detail_open_btn = QPushButton("📂 브라우저")
        self.detail_open_btn.setToolTip("상세 분석을 브라우저에서 열기")
        self.detail_open_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50; color: white;
                padding: 6px 16px; border-radius: 6px; font-size: 11px; border: none;
            }
            QPushButton:hover { background-color: #388E3C; }
        """)
        self.detail_open_btn.clicked.connect(self._on_open_detail_in_browser)
        self.detail_open_btn.setVisible(False)
        toggle_layout.addWidget(self.detail_open_btn)

        self.detail_batch_btn = QPushButton("🔍 일괄 상세")
        self.detail_batch_btn.setToolTip("기본 요약이 있는 모든 날짜의 상세 분석을 일괄 생성")
        self.detail_batch_btn.setStyleSheet("""
            QPushButton {
                background-color: #7B1FA2; color: white;
                padding: 6px 16px; border-radius: 6px; font-size: 11px; border: none;
            }
            QPushButton:hover { background-color: #6A1B9A; }
        """)
        self.detail_batch_btn.clicked.connect(self._on_generate_detail_batch)
        self.detail_batch_btn.setVisible(False)
        toggle_layout.addWidget(self.detail_batch_btn)

        detail_layout.addWidget(toggle_bar)

        # 상세 요약 뷰어
        detail_frame = QFrame()
        detail_frame.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #E8E8E8;
                border-radius: 12px;
            }
        """)
        detail_frame_layout = QVBoxLayout(detail_frame)
        
        self.detail_browser = QTextBrowser()
        self.detail_browser.setOpenExternalLinks(True)
        self.detail_browser.setStyleSheet("""
            QTextBrowser {
                border: none;
                background-color: transparent;
                font-size: 14px;
                line-height: 1.6;
            }
        """)
        self.detail_browser.setPlaceholderText("채팅방과 날짜를 선택하면 상세 요약이 표시됩니다.")
        detail_frame_layout.addWidget(self.detail_browser)
        
        detail_layout.addWidget(detail_frame, 1)
        
        self.tab_widget.addTab(detail_tab, "📅 날짜별 요약")
        
        # ===== 탭 3: URL 정보 =====
        url_tab = QWidget()
        url_layout = QVBoxLayout(url_tab)
        url_layout.setContentsMargins(10, 10, 10, 10)
        url_layout.setSpacing(10)
        
        # URL 탭 헤더
        url_header = QWidget()
        url_header.setStyleSheet("""
            QWidget {
                background-color: #FFFFFF;
                border: 1px solid #E8E8E8;
                border-radius: 12px;
            }
        """)
        url_header_layout = QHBoxLayout(url_header)
        url_header_layout.setContentsMargins(15, 10, 15, 10)
        
        url_title = QLabel("🔗 공유된 URL 목록")
        url_title.setStyleSheet("border: none; font-size: 16px; font-weight: bold;")
        url_header_layout.addWidget(url_title)
        
        url_header_layout.addStretch()
        
        # URL 개수 및 상태 표시
        self.url_count_label = QLabel("0개 URL")
        self.url_count_label.setStyleSheet("border: none; color: #666; font-size: 13px;")
        url_header_layout.addWidget(self.url_count_label)
        
        self.url_status_label = QLabel("")
        self.url_status_label.setStyleSheet("border: none; color: #888; font-size: 11px;")
        url_header_layout.addWidget(self.url_status_label)

        # 동기화 버튼 (요약에서 URL 추출 → DB/파일 저장)
        self.sync_url_btn = QPushButton("🔄 동기화")
        self.sync_url_btn.setToolTip("요약 파일에서 URL을 추출하여 DB와 파일에 저장")
        self.sync_url_btn.setStyleSheet("""
            QPushButton {
                background-color: #43A047;
                color: white;
                padding: 6px 15px;
                border-radius: 6px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #388E3C;
            }
        """)
        self.sync_url_btn.clicked.connect(self._sync_url_from_summaries)
        url_header_layout.addWidget(self.sync_url_btn)

        # 파일에서 복구 버튼
        self.restore_url_btn = QPushButton("📂 파일 복구")
        self.restore_url_btn.setToolTip("파일에서 URL 목록을 DB로 복구")
        self.restore_url_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                padding: 6px 15px;
                border-radius: 6px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
        """)
        self.restore_url_btn.clicked.connect(self._restore_url_from_file)
        url_header_layout.addWidget(self.restore_url_btn)

        url_layout.addWidget(url_header)
        
        # URL 목록 뷰어
        url_frame = QFrame()
        url_frame.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #E8E8E8;
                border-radius: 12px;
            }
        """)
        url_frame_layout = QVBoxLayout(url_frame)
        
        self.url_browser = QTextBrowser()
        self.url_browser.setOpenExternalLinks(True)
        self.url_browser.setStyleSheet("""
            QTextBrowser {
                border: none;
                background-color: transparent;
                font-size: 13px;
                line-height: 1.8;
            }
        """)
        self.url_browser.setPlaceholderText("채팅방을 선택하면 공유된 URL 목록이 표시됩니다.")
        url_frame_layout.addWidget(self.url_browser)
        
        url_layout.addWidget(url_frame, 1)
        
        self.tab_widget.addTab(url_tab, "🔗 URL 정보")

        # === 기타 기능 탭 ===
        etc_tab = QWidget()
        etc_layout = QVBoxLayout(etc_tab)
        etc_layout.setSpacing(12)
        etc_layout.setContentsMargins(10, 10, 10, 10)

        # 통계 갱신 카드
        stats_card = QFrame()
        stats_card.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #E8E8E8;
                border-radius: 12px;
            }
        """)
        stats_card_layout = QVBoxLayout(stats_card)
        stats_card_layout.setContentsMargins(15, 12, 15, 12)

        stats_title = QLabel("📊 통계 정보 갱신")
        stats_title.setStyleSheet("border: none; font-size: 15px; font-weight: bold;")
        stats_card_layout.addWidget(stats_title)

        stats_desc = QLabel("대시보드 통계와 채팅방 목록을 최신 상태로 갱신합니다.")
        stats_desc.setStyleSheet("border: none; color: #666; font-size: 12px;")
        stats_desc.setWordWrap(True)
        stats_card_layout.addWidget(stats_desc)

        stats_btn_layout = QHBoxLayout()
        stats_btn_layout.addStretch()
        self.etc_refresh_btn = QPushButton("🔄 갱신")
        self.etc_refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #1E88E5;
                color: white;
                padding: 6px 18px;
                border-radius: 6px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #1565C0;
            }
        """)
        self.etc_refresh_btn.clicked.connect(self._on_refresh_stats)
        stats_btn_layout.addWidget(self.etc_refresh_btn)
        stats_card_layout.addLayout(stats_btn_layout)

        etc_layout.addWidget(stats_card)

        # 채팅방 백업 카드
        backup_card = QFrame()
        backup_card.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #E8E8E8;
                border-radius: 12px;
            }
        """)
        backup_card_layout = QVBoxLayout(backup_card)
        backup_card_layout.setContentsMargins(15, 12, 15, 12)

        backup_title = QLabel("💾 채팅방 백업")
        backup_title.setStyleSheet("border: none; font-size: 15px; font-weight: bold;")
        backup_card_layout.addWidget(backup_title)

        backup_desc = QLabel("선택된 채팅방의 원본 대화, 요약, URL 파일을 백업합니다.")
        backup_desc.setStyleSheet("border: none; color: #666; font-size: 12px;")
        backup_desc.setWordWrap(True)
        backup_card_layout.addWidget(backup_desc)

        backup_btn_layout = QHBoxLayout()
        backup_btn_layout.addStretch()
        self.etc_backup_room_btn = QPushButton("💾 백업")
        self.etc_backup_room_btn.setStyleSheet("""
            QPushButton {
                background-color: #FB8C00;
                color: white;
                padding: 6px 18px;
                border-radius: 6px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #EF6C00;
            }
        """)
        self.etc_backup_room_btn.clicked.connect(self._on_room_backup)
        backup_btn_layout.addWidget(self.etc_backup_room_btn)
        backup_card_layout.addLayout(backup_btn_layout)

        etc_layout.addWidget(backup_card)

        # 채팅방 복원 카드
        restore_card = QFrame()
        restore_card.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #E8E8E8;
                border-radius: 12px;
            }
        """)
        restore_card_layout = QVBoxLayout(restore_card)
        restore_card_layout.setContentsMargins(15, 12, 15, 12)

        restore_title = QLabel("📂 채팅방 복원")
        restore_title.setStyleSheet("border: none; font-size: 15px; font-weight: bold;")
        restore_card_layout.addWidget(restore_title)

        restore_desc = QLabel("백업에서 특정 채팅방의 데이터를 복원합니다.")
        restore_desc.setStyleSheet("border: none; color: #666; font-size: 12px;")
        restore_desc.setWordWrap(True)
        restore_card_layout.addWidget(restore_desc)

        restore_btn_layout = QHBoxLayout()
        restore_btn_layout.addStretch()
        self.etc_restore_room_btn = QPushButton("📂 복원")
        self.etc_restore_room_btn.setStyleSheet("""
            QPushButton {
                background-color: #43A047;
                color: white;
                padding: 6px 18px;
                border-radius: 6px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #2E7D32;
            }
        """)
        self.etc_restore_room_btn.clicked.connect(self._on_restore_room_from_backup_with_current)
        restore_btn_layout.addWidget(self.etc_restore_room_btn)
        restore_card_layout.addLayout(restore_btn_layout)

        etc_layout.addWidget(restore_card)

        etc_layout.addStretch()

        self.tab_widget.addTab(etc_tab, "🔧 기타")

        right_layout.addWidget(self.tab_widget, 1)
        
        splitter.addWidget(right_panel)
        splitter.setSizes([280, 720])
        
        main_layout.addWidget(splitter)
    
    def _setup_menu(self):
        """메뉴바 구성."""
        menubar = self.menuBar()
        
        # 파일 메뉴
        file_menu = menubar.addMenu("파일")
        
        add_action = QAction("채팅방 추가...", self)
        add_action.setShortcut("Ctrl+O")
        add_action.triggered.connect(self._on_add_room)
        file_menu.addAction(add_action)

        delete_room_action = QAction("채팅방 삭제...", self)
        delete_room_action.triggered.connect(self._on_delete_room)
        file_menu.addAction(delete_room_action)

        file_menu.addSeparator()
        
        exit_action = QAction("종료", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 도구 메뉴
        tools_menu = menubar.addMenu("도구")
        
        sync_action = QAction("지금 동기화", self)
        sync_action.setShortcut("Ctrl+R")
        sync_action.triggered.connect(self._on_manual_sync)
        tools_menu.addAction(sync_action)
        
        summary_action = QAction("LLM 요약 생성", self)
        summary_action.setShortcut("Ctrl+G")
        summary_action.triggered.connect(self._on_generate_summary)
        tools_menu.addAction(summary_action)

        all_rooms_summary_action = QAction("🌐 전체 채팅방 LLM 요약 생성", self)
        all_rooms_summary_action.setShortcut("Ctrl+Shift+G")
        all_rooms_summary_action.setToolTip("등록된 모든 채팅방에 대해 일괄 LLM 요약 생성")
        all_rooms_summary_action.triggered.connect(self._on_generate_all_rooms_summary)
        tools_menu.addAction(all_rooms_summary_action)

        all_rooms_url_action = QAction("🌐 전체 채팅방 URL 동기화", self)
        all_rooms_url_action.setShortcut("Ctrl+Shift+U")
        all_rooms_url_action.setToolTip("등록된 모든 채팅방의 요약에서 URL을 추출하여 DB/파일에 저장")
        all_rooms_url_action.triggered.connect(self._on_sync_all_rooms_urls)
        tools_menu.addAction(all_rooms_url_action)

        all_rooms_detail_action = QAction("🌐 전체 채팅방 상세 분석 생성", self)
        all_rooms_detail_action.setShortcut("Ctrl+Shift+D")
        all_rooms_detail_action.setToolTip("모든 채팅방의 기본 요약이 있는 날짜에 대해 상세 분석 HTML 일괄 생성")
        all_rooms_detail_action.triggered.connect(self._on_generate_all_rooms_detail)
        tools_menu.addAction(all_rooms_detail_action)

        tools_menu.addSeparator()

        # === 백업/복원 (스냅샷 관리) ===
        backup_action = QAction("💾 전체 백업...", self)
        backup_action.setShortcut("Ctrl+B")
        backup_action.setToolTip("DB, 원본 대화, 요약 파일을 타임스탬프 디렉터리에 백업")
        backup_action.triggered.connect(self._on_backup)
        tools_menu.addAction(backup_action)

        room_backup_action = QAction("💾 채팅방 백업...", self)
        room_backup_action.setToolTip("선택된 채팅방의 파일만 백업")
        room_backup_action.triggered.connect(self._on_room_backup)
        tools_menu.addAction(room_backup_action)

        tools_menu.addSeparator()

        restore_action = QAction("📂 전체 백업에서 복원...", self)
        restore_action.setToolTip("백업 디렉터리에서 선택하여 전체 복원")
        restore_action.triggered.connect(self._on_restore_from_backup)
        tools_menu.addAction(restore_action)

        room_restore_action = QAction("📂 채팅방 복원...", self)
        room_restore_action.setToolTip("백업에서 특정 채팅방만 복원")
        room_restore_action.triggered.connect(lambda: self._on_restore_room_from_backup())
        tools_menu.addAction(room_restore_action)

        tools_menu.addSeparator()

        # === 파일↔DB 동기화 ===
        rebuild_action = QAction("🔄 파일에서 DB 재구축...", self)
        rebuild_action.setToolTip("기존 DB를 삭제하고 data/original, data/summary 파일에서 재구축")
        rebuild_action.triggered.connect(self._on_recovery)
        tools_menu.addAction(rebuild_action)

        add_missing_action = QAction("🔄 누락 채팅방 DB 추가...", self)
        add_missing_action.setToolTip("파일 디렉터리에 있지만 DB에 없는 채팅방을 추가 (비파괴적)")
        add_missing_action.triggered.connect(self._on_room_recovery)
        tools_menu.addAction(add_missing_action)

        tools_menu.addSeparator()

        settings_action = QAction("설정...", self)
        settings_action.setShortcut("Ctrl+,")
        settings_action.triggered.connect(self._on_settings)
        tools_menu.addAction(settings_action)
        
        # 도움말 메뉴
        help_menu = menubar.addMenu("도움말")
        
        about_action = QAction("정보", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)
    
    def _setup_statusbar(self):
        """상태바 구성."""
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        
        # 작업 상태 (왼쪽)
        self.task_status = QLabel("✅ 준비")
        self.task_status.setStyleSheet("font-size: 12px; padding: 0 10px;")
        self.statusbar.addWidget(self.task_status)
        
        self.statusbar.addPermanentWidget(QLabel(""))  # 스페이서
        
        # 마지막 작업 시간
        self.last_sync_label = QLabel("")
        self.last_sync_label.setStyleSheet("color: #666; font-size: 11px;")
        self.statusbar.addPermanentWidget(self.last_sync_label)
    
    def _load_rooms(self):
        """채팅방 목록 로드."""
        # 기존 위젯 제거
        while self.room_list_layout.count() > 1:
            item = self.room_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # DB에서 채팅방 목록 로드
        rooms = self.db.get_all_rooms()
        
        if not rooms:
            # 채팅방이 없을 때 안내 메시지
            empty_label = QLabel("📁 채팅방을 추가해주세요")
            empty_label.setAlignment(Qt.AlignCenter)
            empty_label.setStyleSheet("color: #888888; padding: 20px;")
            self.room_list_layout.insertWidget(0, empty_label)
            return
        
        for room in rooms:
            # 메시지 수 조회
            msg_count = self.db.get_message_count_by_room(room.id)
            
            widget = ChatRoomWidget(
                room_id=room.id,
                name=room.name,
                message_count=msg_count,
                new_count=0,  # TODO: 새 메시지 수 계산
                last_sync=room.last_sync_at,
                file_path=room.file_path
            )
            widget.clicked.connect(self._on_room_selected)
            self.room_list_layout.insertWidget(
                self.room_list_layout.count() - 1, widget
            )
    
    @Slot(int, str)
    def _on_room_selected(self, room_id: int, file_path: str):
        """채팅방 선택 시."""
        self.current_room_id = room_id
        self.current_room_file = file_path

        
        # 채팅방 통계 로드
        stats = self.db.get_room_stats(room_id)
        room_name = "채팅방"
        
        if stats:
            room_name = stats.get('room_name', '채팅방')
            self.header_label.setText(f"📊 {room_name}")

            # 대화 기간 서브텍스트
            first_date = stats.get('first_date')
            last_date = stats.get('last_date')
            if first_date and last_date:
                days_span = (last_date - first_date).days + 1
                msg_date_sub = f"{first_date} ~ {last_date} ({days_span}일)"
            else:
                msg_date_sub = "대화 없음"

            # 대시보드 카드 업데이트
            total_msg = stats.get('total_messages', 0)
            self.card_messages.update_card(f"{total_msg:,}", msg_date_sub)
            self.card_participants.update_card(
                f"{stats.get('unique_senders', 0)}",
                "명"
            )

            # 파일 저장소에서 요약 통계 가져오기
            from file_storage import get_storage
            storage = get_storage()
            available_dates = storage.get_available_dates(room_name)
            summarized_dates = storage.get_summarized_dates(room_name)
            total_dates = len(available_dates)
            done_dates = len(summarized_dates)
            if total_dates > 0:
                pct = int(done_dates / total_dates * 100)
                summary_sub = f"{done_dates}/{total_dates}일 ({pct}%)"
            else:
                summary_sub = "대화 데이터 없음"
            self.card_summaries.update_card(f"{done_dates}", summary_sub)
            
            # 요약 목록 조회
            summaries = self.db.get_summaries_by_room(room_id)
            
            if summaries:
                html = "<h3>📅 최근 요약</h3>"
                for s in summaries[:5]:
                    html += f"<p><b>{s.summary_date}</b> ({s.summary_type})</p>"
                    html += f"<p>{s.content[:200]}...</p><hr>"
                self.summary_browser.setHtml(html)
            else:
                date_range = ""
                if stats.get('first_date') and stats.get('last_date'):
                    date_range = f"<p>📅 대화 기간: {stats['first_date']} ~ {stats['last_date']}</p>"
                
                self.summary_browser.setHtml(f"""
                    <h3>📊 채팅방 정보</h3>
                    <p>💬 총 메시지: <b>{stats.get('total_messages', 0):,}개</b></p>
                    <p>👥 참여자: <b>{stats.get('unique_senders', 0)}명</b></p>
                    {date_range}
                    <hr>
                    <p style="color: #888;">요약을 생성하려면 '🤖 LLM 요약 생성' 버튼을 클릭하세요.</p>
                """)
        else:
            self.header_label.setText(f"📊 채팅방 #{room_id}")
            self.summary_browser.setHtml("""
                <h3>🌟 요약</h3>
                <p>채팅방 데이터가 없습니다.</p>
            """)
        
        # 날짜 탭 업데이트
        self._update_date_tab_for_room(room_name)
        
        # URL 탭 자동 로드
        self._current_url_data = {}
        self._refresh_url_list()
    
    @Slot()
    def _on_add_room(self):
        """채팅방 만들기."""
        dialog = CreateRoomDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return
        
        room_name = dialog.room_name
        if not room_name:
            return
        
        # 채팅방 생성 (DB + 파일 저장소)
        try:
            # DB에 채팅방 생성
            room = self.db.get_room_by_name(room_name)
            if room:
                QMessageBox.warning(self, "알림", f"'{room_name}' 채팅방이 이미 존재합니다.")
                return
            
            room = self.db.create_room(room_name)
            
            # 파일 저장소 디렉토리 생성
            from file_storage import get_storage
            storage = get_storage()
            (storage.original_dir / storage._sanitize_name(room_name)).mkdir(parents=True, exist_ok=True)
            (storage.summary_dir / storage._sanitize_name(room_name)).mkdir(parents=True, exist_ok=True)
            
            QMessageBox.information(self, "생성 완료", f"✅ '{room_name}' 채팅방이 생성되었습니다.\n\n이제 파일을 업로드하세요.")
            self._load_rooms()
            
        except Exception as e:
            QMessageBox.warning(self, "오류", f"채팅방 생성 실패: {str(e)}")
    
    @Slot()
    def _on_delete_room(self):
        """채팅방 삭제 (파일 메뉴에서 호출)."""
        if self.current_room_id is None:
            QMessageBox.warning(self, "알림", "먼저 채팅방을 선택하세요.")
            return

        room = self.db.get_room_by_id(self.current_room_id)
        if not room:
            QMessageBox.warning(self, "오류", "선택된 채팅방을 찾을 수 없습니다.")
            return

        room_name = room.name
        reply = QMessageBox.question(
            self, "채팅방 삭제",
            f"'{room_name}' 채팅방을 정말 삭제하시겠습니까?\n\n"
            f"DB의 메시지, 요약, URL 데이터가 모두 삭제됩니다.\n"
            f"(data/ 폴더의 파일은 유지됩니다)",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        try:
            self.db.delete_room(self.current_room_id)
            self.current_room_id = None
            self.current_room_file = None
            self.header_label.setText("📊 대시보드")
            self.summary_browser.setHtml("<p style='color: #888;'>채팅방을 선택하세요.</p>")
            self._load_rooms()
            self._update_status(f"'{room_name}' 채팅방 삭제 완료", "success")
        except Exception as e:
            QMessageBox.warning(self, "오류", f"채팅방 삭제 실패: {str(e)}")

    @Slot()
    def _on_upload_file(self):
        """현재 선택된 채팅방에 파일 업로드."""
        if self.current_room_id is None:
            QMessageBox.warning(self, "알림", "먼저 채팅방을 선택하세요.")
            return
        
        # 현재 채팅방 이름 가져오기
        room = self.db.get_room_by_id(self.current_room_id)
        if not room:
            QMessageBox.warning(self, "오류", "채팅방을 찾을 수 없습니다.")
            return
        
        # 파일 업로드 다이얼로그
        dialog = UploadFileDialog(room.name, self)
        if dialog.exec() != QDialog.Accepted:
            return
        
        file_path = dialog.file_path
        if not file_path:
            return
        
        # 프로그레스 표시
        self._update_status("파일 업로드 중...", "working")
        self.generate_btn.setEnabled(False)
        
        # 백그라운드 워커 시작
        self.upload_worker = FileUploadWorker(file_path, room.name)
        self.upload_worker.progress.connect(self._on_upload_progress)
        self.upload_worker.finished.connect(self._on_upload_finished)
        self.upload_worker.start()
    
    @Slot(int, str)
    def _on_upload_progress(self, progress: int, message: str):
        """업로드 진행 상황."""
        self._update_status(f"{message} ({progress}%)", "working")
    
    @Slot(bool, str, int)
    def _on_upload_finished(self, success: bool, message: str, room_id: int):
        """업로드 완료."""
        self.generate_btn.setEnabled(True)
        
        if success:
            self._update_status("업로드 완료", "success")
            QMessageBox.information(self, "업로드 완료", message)
            self._load_rooms()
            
            # 새로 추가된 채팅방 선택
            if room_id > 0:
                room = self.db.get_room_by_id(room_id)
                if room:
                    self._on_room_selected(room_id, room.file_path or "")
        else:
            self._update_status("업로드 실패", "error")
            QMessageBox.warning(self, "업로드 실패", message)
    
    @Slot()
    def _on_manual_sync(self):
        """수동 동기화."""
        if self.current_room_id is None:
            QMessageBox.warning(self, "알림", "먼저 채팅방을 선택하세요.")
            return
        
        if not self.current_room_file or not Path(self.current_room_file).exists():
            QMessageBox.warning(self, "알림", "파일 경로가 유효하지 않습니다.")
            return
        
        # 백그라운드 동기화 시작
        self._update_status("동기화 중...", "working")
        self.sync_worker = SyncWorker(self.current_room_id, self.current_room_file)
        self.sync_worker.progress.connect(lambda p, m: self._update_status(f"{m} ({p}%)", "working"))
        self.sync_worker.finished.connect(self._on_sync_finished)
        self.sync_worker.start()
    
    @Slot(bool, str)
    def _on_sync_finished(self, success: bool, message: str):
        """동기화 완료."""
        if success:
            self._update_status(message, "success")
            # UI 새로고침
            self._load_rooms()
            if self.current_room_id:
                self._on_room_selected(self.current_room_id, self.current_room_file or "")
        else:
            self._update_status(f"동기화 실패: {message}", "error")
    
    def _update_status(self, message: str, status_type: str = "info"):
        """상태바 업데이트."""
        icons = {
            "info": "ℹ️",
            "working": "⏳",
            "success": "✅",
            "error": "❌",
            "warning": "⚠️"
        }
        icon = icons.get(status_type, "ℹ️")
        self.task_status.setText(f"{icon} {message}")
        
        # 시간 표시
        if status_type in ("success", "error"):
            self.last_sync_label.setText(f"({datetime.now().strftime('%H:%M:%S')})")
    
    @Slot()
    def _on_generate_summary(self):
        """요약 생성."""
        if self._summary_in_progress:
            QMessageBox.warning(self, "알림", "이미 요약이 진행 중입니다.\n완료 후 다시 시도하세요.")
            return

        if self.current_room_id is None:
            QMessageBox.warning(self, "알림", "먼저 채팅방을 선택하세요.")
            return

        # 현재 채팅방 이름 가져오기
        room_name = "Unknown"
        if self.current_room_id:
            room = self.db.get_room_by_id(self.current_room_id)
            if room:
                room_name = room.name

        # 통계 조회
        from file_storage import get_storage
        storage = get_storage()
        available_dates = storage.get_available_dates(room_name)
        summarized_dates = storage.get_summarized_dates(room_name)

        # 요약 필요한 날짜 조회
        dates_needing_summary = storage.get_dates_needing_summary(room_name)
        new_count = sum(1 for r in dates_needing_summary.values() if r == "new")
        needs_update_count = sum(1 for r in dates_needing_summary.values() if r == "resummary")

        # 현재 LLM 설정 가져오기
        from full_config import config
        current_llm = config.current_provider

        # 요약 옵션 다이얼로그 (모달 OK - 옵션 선택은 차단이 자연스럽다)
        dialog = SummaryOptionsDialog(
            self,
            summarized_count=len(summarized_dates),
            total_count=len(available_dates),
            needs_update_count=needs_update_count,
            new_count=new_count,
            current_llm=current_llm
        )
        if dialog.exec() != QDialog.Accepted:
            return

        summary_type = dialog.summary_type
        skip_existing = dialog.skip_existing
        selected_llm = dialog.selected_llm
        llm_display_name = dialog.llm_combo.currentText()

        # 상세 분석 옵션 저장
        self._detail_after_summary = dialog.generate_detail
        self._detail_llm_provider = selected_llm

        # 상태 플래그 설정
        self._summary_in_progress = True
        self.summary_source_room_id = self.current_room_id
        self.generate_btn.setEnabled(False)

        # 상태바에 프로그레스 위젯 삽입
        self.summary_progress_widget = SummaryProgressWidget(
            self, llm_name=llm_display_name, room_name=room_name
        )
        self.statusbar.insertPermanentWidget(0, self.summary_progress_widget)
        self.summary_progress_widget.show()

        self._update_status(f"⏳ {llm_display_name} 요약 생성 중...", "working")

        # 백그라운드 워커 시작
        self.summary_worker = SummaryGeneratorWorker(
            self.current_room_id,
            summary_type,
            self.current_room_file,
            room_name,
            skip_existing,
            selected_llm
        )

        # 시그널 연결
        self.summary_worker.progress.connect(self.summary_progress_widget.update_progress)
        self.summary_worker.progress.connect(lambda p, m: self._update_status(m, "working"))
        self.summary_worker.finished.connect(self._on_summary_finished)
        self.summary_progress_widget.cancel_requested.connect(self.summary_worker.cancel)

        # 워커 시작
        self.summary_worker.start()
    
    @Slot(bool, str)
    def _on_summary_finished(self, success: bool, result: str):
        """요약 생성 완료."""
        self.generate_btn.setEnabled(True)
        self._summary_in_progress = False

        # 요약 대상 채팅방 이름 조회
        summary_room_name = ""
        if self.summary_source_room_id:
            room = self.db.get_room_by_id(self.summary_source_room_id)
            if room:
                summary_room_name = room.name

        # 상태바 프로그레스 위젯 제거
        if self.summary_progress_widget:
            self.statusbar.removeWidget(self.summary_progress_widget)
            self.summary_progress_widget.deleteLater()
            self.summary_progress_widget = None

        if success:
            # 현재 보고 있는 채팅방이 요약 대상 채팅방과 같으면 대시보드 갱신
            if self.current_room_id == self.summary_source_room_id:
                self._update_status("요약 생성 완료", "success")
                self.summary_browser.setHtml(f"""
                    <h3>📝 AI 요약</h3>
                    <div style="line-height: 1.6;">{result.replace(chr(10), '<br>')}</div>
                """)
                # 대시보드 통계도 갱신
                if self.current_room_id:
                    self._on_room_selected(self.current_room_id, self.current_room_file or "")
            else:
                self._update_status(f"✅ [{summary_room_name}] 요약 완료", "success")

            # URL 자동 동기화
            if summary_room_name and self.summary_source_room_id:
                self._auto_sync_urls(self.summary_source_room_id, summary_room_name)

            # 상세 분석 자동 실행 (체크 시)
            if getattr(self, '_detail_after_summary', False) and summary_room_name:
                self._start_detail_batch(
                    self.summary_source_room_id, summary_room_name,
                    getattr(self, '_detail_llm_provider', 'glm')
                )
                self.summary_source_room_id = None
                return
        else:
            self._update_status(f"요약 생성 실패: {summary_room_name}", "error")
            QMessageBox.warning(self, "요약 실패", result)

        self.summary_source_room_id = None
        self._detail_after_summary = False

    @Slot()
    def _on_generate_all_rooms_summary(self):
        """전체 채팅방 LLM 요약 생성."""
        if self._summary_in_progress:
            QMessageBox.warning(
                self, "알림",
                "이미 요약이 진행 중입니다.\n완료 후 다시 시도하세요."
            )
            return

        # 모든 채팅방의 통계 수집
        from file_storage import get_storage
        storage = get_storage()
        rooms = self.db.get_all_rooms()

        if not rooms:
            QMessageBox.warning(self, "알림", "등록된 채팅방이 없습니다.")
            return

        room_stats = []
        for room in rooms:
            available = storage.get_available_dates(room.name)
            summarized = storage.get_summarized_dates(room.name)
            dates_needing = storage.get_dates_needing_summary(room.name)
            room_stats.append({
                'name': room.name,
                'total': len(available),
                'done': len(summarized),
                'pending': len(dates_needing),
            })

        # 현재 LLM 설정
        from full_config import config
        current_llm = config.current_provider

        # 옵션 다이얼로그
        dialog = AllRoomsSummaryOptionsDialog(
            self, room_stats=room_stats, current_llm=current_llm
        )
        if dialog.exec() != QDialog.Accepted:
            return

        summary_type = dialog.summary_type
        skip_existing = dialog.skip_existing
        selected_llm = dialog.selected_llm
        llm_display_name = dialog.llm_combo.currentText()

        # 상태 플래그
        self._summary_in_progress = True
        self.summary_source_room_id = None  # 전체 채팅방이므로 None
        self.generate_btn.setEnabled(False)

        # 상태바 프로그레스 위젯
        self.summary_progress_widget = SummaryProgressWidget(
            self, llm_name=llm_display_name, room_name="전체 채팅방"
        )
        self.statusbar.insertPermanentWidget(0, self.summary_progress_widget)
        self.summary_progress_widget.show()

        self._update_status(f"⏳ {llm_display_name} 전체 채팅방 요약 생성 중...", "working")

        # 워커 시작
        self.all_rooms_summary_worker = AllRoomsSummaryWorker(
            summary_type=summary_type,
            skip_existing=skip_existing,
            llm_provider=selected_llm
        )

        self.all_rooms_summary_worker.progress.connect(
            self.summary_progress_widget.update_progress
        )
        self.all_rooms_summary_worker.progress.connect(
            lambda p, m: self._update_status(m, "working")
        )
        self.all_rooms_summary_worker.finished.connect(
            self._on_all_rooms_summary_finished
        )
        self.summary_progress_widget.cancel_requested.connect(
            self.all_rooms_summary_worker.cancel
        )

        self.all_rooms_summary_worker.start()

    @Slot(bool, str)
    def _on_all_rooms_summary_finished(self, success: bool, result: str):
        """전체 채팅방 요약 완료."""
        self.generate_btn.setEnabled(True)
        self._summary_in_progress = False

        # 프로그레스 위젯 제거
        if self.summary_progress_widget:
            self.statusbar.removeWidget(self.summary_progress_widget)
            self.summary_progress_widget.deleteLater()
            self.summary_progress_widget = None

        if success:
            self._update_status("전체 채팅방 요약 완료", "success")

            # 현재 보고 있는 채팅방 대시보드 갱신
            if self.current_room_id:
                self._on_room_selected(
                    self.current_room_id, self.current_room_file or ""
                )

            # 결과 표시
            QMessageBox.information(
                self, "전체 채팅방 요약 완료",
                result
            )
        else:
            self._update_status("전체 채팅방 요약 실패", "error")
            QMessageBox.warning(self, "요약 실패", result)

    @Slot()
    def _on_sync_all_rooms_urls(self):
        """전체 채팅방 URL 동기화."""
        if self._summary_in_progress:
            QMessageBox.warning(
                self, "알림",
                "요약이 진행 중입니다.\n완료 후 다시 시도하세요."
            )
            return

        rooms = self.db.get_all_rooms()
        if not rooms:
            QMessageBox.warning(self, "알림", "등록된 채팅방이 없습니다.")
            return

        # 확인 다이얼로그
        room_list = "\n".join(f"  • {r.name}" for r in rooms)
        reply = QMessageBox.question(
            self, "전체 채팅방 URL 동기화",
            f"다음 {len(rooms)}개 채팅방의 요약에서 URL을 추출합니다:\n\n"
            f"{room_list}\n\n계속하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        if reply != QMessageBox.Yes:
            return

        self._summary_in_progress = True
        self.generate_btn.setEnabled(False)

        # 상태바 프로그레스
        self.summary_progress_widget = SummaryProgressWidget(
            self, llm_name="URL", room_name="전체 채팅방"
        )
        self.statusbar.insertPermanentWidget(0, self.summary_progress_widget)
        self.summary_progress_widget.show()

        self._update_status("⏳ 전체 채팅방 URL 동기화 중...", "working")

        self.all_rooms_url_worker = AllRoomsUrlSyncWorker()
        self.all_rooms_url_worker.progress.connect(
            self.summary_progress_widget.update_progress
        )
        self.all_rooms_url_worker.progress.connect(
            lambda p, m: self._update_status(m, "working")
        )
        self.all_rooms_url_worker.finished.connect(
            self._on_all_rooms_url_sync_finished
        )
        self.summary_progress_widget.cancel_requested.connect(
            self.all_rooms_url_worker.cancel
        )
        self.all_rooms_url_worker.start()

    @Slot(bool, str)
    def _on_all_rooms_url_sync_finished(self, success: bool, result: str):
        """전체 채팅방 URL 동기화 완료."""
        self.generate_btn.setEnabled(True)
        self._summary_in_progress = False

        if self.summary_progress_widget:
            self.statusbar.removeWidget(self.summary_progress_widget)
            self.summary_progress_widget.deleteLater()
            self.summary_progress_widget = None

        if success:
            self._update_status("전체 채팅방 URL 동기화 완료", "success")

            # 현재 채팅방의 URL 탭 갱신
            if self.current_room_id:
                self._refresh_url_list()

            QMessageBox.information(
                self, "전체 채팅방 URL 동기화 완료", result
            )
        else:
            self._update_status("전체 채팅방 URL 동기화 실패", "error")
            QMessageBox.warning(self, "요약 실패", result)

    def _on_generate_all_rooms_detail(self):
        """전체 채팅방 상세 분석 일괄 생성."""
        if self._summary_in_progress:
            QMessageBox.warning(self, "알림", "이미 작업이 진행 중입니다.")
            return

        rooms = self.db.get_all_rooms()
        if not rooms:
            QMessageBox.warning(self, "알림", "등록된 채팅방이 없습니다.")
            return

        from file_storage import get_storage
        storage = get_storage()

        # 각 채팅방별 상세 분석 필요 날짜 수 집계
        room_info = []
        total_needed = 0
        for r in rooms:
            summarized = storage.get_summarized_dates(r.name)
            needing = sum(1 for d in summarized if not storage.has_detail_summary(r.name, d))
            room_info.append((r.id, r.name, len(summarized), needing))
            total_needed += needing

        if total_needed == 0:
            QMessageBox.information(
                self, "알림", "모든 채팅방의 상세 분석이 이미 완료되어 있습니다."
            )
            return

        # LLM 선택 다이얼로그
        from full_config import config, LLM_PROVIDERS
        llm_items = []
        llm_keys = []
        for key, provider in LLM_PROVIDERS.items():
            api_key = config.get_api_key(key)
            status = "✅" if api_key else "⚠️"
            llm_items.append(f"{status} {provider.name}")
            llm_keys.append(key)

        dialog = QDialog(self)
        dialog.setWindowTitle("🌐 전체 채팅방 상세 분석 생성")
        dialog.setFixedWidth(450)
        dlg_layout = QVBoxLayout(dialog)

        # 채팅방별 현황
        info_lines = []
        for _, rn, total, need in room_info:
            if need > 0:
                info_lines.append(f"  • {rn}: {need}일 필요 (전체 {total}일)")
            else:
                info_lines.append(f"  • {rn}: ✅ 완료")

        dlg_layout.addWidget(QLabel(f"<b>🔍 {len(rooms)}개 채팅방 — 총 {total_needed}일 상세 분석 생성</b>"))

        from PySide6.QtWidgets import QTextEdit
        info_text = QTextEdit()
        info_text.setPlainText("\n".join(info_lines))
        info_text.setReadOnly(True)
        info_text.setMaximumHeight(150)
        dlg_layout.addWidget(info_text)

        llm_combo = QComboBox()
        llm_combo.addItems(llm_items)
        current_idx = llm_keys.index(config.current_provider) if config.current_provider in llm_keys else 0
        llm_combo.setCurrentIndex(current_idx)
        form = QFormLayout()
        form.addRow("LLM:", llm_combo)
        dlg_layout.addLayout(form)

        btn_layout = QHBoxLayout()
        cancel_btn = QPushButton("취소")
        cancel_btn.clicked.connect(dialog.reject)
        ok_btn = QPushButton(f"🔍 {total_needed}일 상세 생성")
        ok_btn.setStyleSheet("QPushButton { background-color: #7B1FA2; color: white; padding: 8px 20px; border-radius: 6px; }")
        ok_btn.clicked.connect(dialog.accept)
        ok_btn.setDefault(True)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(ok_btn)
        dlg_layout.addLayout(btn_layout)

        if dialog.exec() != QDialog.Accepted:
            return

        selected_llm = llm_keys[llm_combo.currentIndex()]
        llm_display_name = llm_combo.currentText()

        # 워커 시작
        self._summary_in_progress = True
        self.generate_btn.setEnabled(False)

        self.summary_progress_widget = SummaryProgressWidget(
            self, llm_name=llm_display_name, room_name="전체 채팅방 상세 분석"
        )
        self.statusbar.insertPermanentWidget(0, self.summary_progress_widget)
        self.summary_progress_widget.show()

        self._update_status("🔍 전체 채팅방 상세 분석 중...", "working")

        target_rooms = [(rid, rn) for rid, rn, _, need in room_info if need > 0]
        self.all_rooms_detail_worker = AllRoomsDetailWorker(target_rooms, selected_llm)
        self.all_rooms_detail_worker.progress.connect(
            self.summary_progress_widget.update_progress
        )
        self.all_rooms_detail_worker.progress.connect(
            lambda p, m: self._update_status(m, "working")
        )
        self.all_rooms_detail_worker.finished.connect(
            self._on_all_rooms_detail_finished
        )
        self.summary_progress_widget.cancel_requested.connect(
            self.all_rooms_detail_worker.cancel
        )
        self.all_rooms_detail_worker.start()

    @Slot(bool, str)
    def _on_all_rooms_detail_finished(self, success: bool, result: str):
        """전체 채팅방 상세 분석 완료."""
        self._summary_in_progress = False
        self.generate_btn.setEnabled(True)

        if self.summary_progress_widget:
            self.statusbar.removeWidget(self.summary_progress_widget)
            self.summary_progress_widget.deleteLater()
            self.summary_progress_widget = None

        if success:
            self._update_status("✅ 전체 채팅방 상세 분석 완료", "success")
            if self.current_room_id:
                self._on_room_selected(self.current_room_id, self.current_room_file or "")
            QMessageBox.information(self, "전체 채팅방 상세 분석 완료", result)
        else:
            self._update_status("❌ 전체 채팅방 상세 분석 실패", "error")
            QMessageBox.warning(self, "실패", result)

    @Slot()
    def _on_recovery(self):
        """DB 복구."""
        # 확인 다이얼로그
        reply = QMessageBox.question(
            self, "DB 복구",
            "⚠️ 주의: 기존 DB를 삭제하고 파일 저장소에서 복구합니다.\n\n"
            "data/original 및 data/summary 폴더의 파일을 기반으로\n"
            "새로운 데이터베이스를 생성합니다.\n\n"
            "계속하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # 프로그레스 표시
        self._update_status("DB 복구 중...", "working")
        self.generate_btn.setEnabled(False)
        
        # 복구 워커 시작
        self.recovery_worker = RecoveryWorker()
        self.recovery_worker.progress.connect(lambda p, m: self._update_status(f"{m} ({p}%)", "working"))
        self.recovery_worker.finished.connect(self._on_recovery_finished)
        self.recovery_worker.start()
    
    @Slot(bool, str)
    def _on_recovery_finished(self, success: bool, message: str):
        """복구 완료."""
        self.generate_btn.setEnabled(True)
        
        if success:
            self._update_status("DB 복구 완료", "success")
            QMessageBox.information(self, "복구 완료", message)
            
            # DB 재연결 및 UI 새로고침
            from db import get_db
            self.db = get_db(force_new=True)
            self._load_rooms()
        else:
            self._update_status("DB 복구 실패", "error")
            QMessageBox.warning(self, "복구 실패", message)
    
    @Slot()
    def _on_room_recovery(self):
        """파일 디렉터리에서 누락된 채팅방 복구 (비파괴적)."""
        self._update_status("채팅방 복구 스캔 중...", "working")

        storage = get_storage()
        file_rooms = storage.get_all_rooms()

        # DB에 이미 있는 채팅방 이름 목록
        db_rooms = self.db.get_all_rooms()
        db_room_names = {r.name for r in db_rooms}

        # 파일에는 있지만 DB에 없는 채팅방
        missing = [name for name in file_rooms if name not in db_room_names]

        if not missing:
            self._update_status("채팅방 복구 불필요", "success")
            QMessageBox.information(
                self, "채팅방 복구",
                "✅ 모든 채팅방이 DB에 존재합니다.\n누락된 채팅방이 없습니다."
            )
            return

        reply = QMessageBox.question(
            self, "채팅방 복구",
            f"📂 파일에는 있지만 DB에 없는 채팅방 {len(missing)}개를 발견했습니다:\n\n"
            + "\n".join(f"  • {name}" for name in missing)
            + "\n\nDB에 추가하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )

        if reply != QMessageBox.Yes:
            self._update_status("채팅방 복구 취소", "info")
            return

        created = 0
        for name in missing:
            try:
                self.db.create_room(name)
                created += 1
            except Exception:
                pass

        self._update_status(f"채팅방 {created}개 복구 완료", "success")
        self._load_rooms()
        QMessageBox.information(
            self, "채팅방 복구 완료",
            f"✅ {created}개 채팅방을 DB에 추가했습니다."
        )

    @Slot()
    def _on_backup(self):
        """전체 백업 생성."""
        # 백업 목록 조회
        backups = self.storage.get_backup_list()
        
        # 확인 다이얼로그
        msg = "다음 항목을 백업합니다:\n\n"
        msg += "• DB (chat_history.db)\n"
        msg += "• 원본 대화 (data/original/)\n"
        msg += "• 요약 파일 (data/summary/)\n"
        msg += "• URL 파일 (data/url/)\n\n"
        
        if backups:
            msg += f"기존 백업: {len(backups)}개\n"
            msg += f"최근: {backups[0]['name']} ({backups[0]['size_mb']} MB)\n"
        
        reply = QMessageBox.question(
            self, "전체 백업",
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        self._update_status("백업 중...", "working")
        
        # 백업 실행
        backup_path = self.storage.create_full_backup()
        
        if backup_path:
            self._update_status("백업 완료", "success")
            QMessageBox.information(
                self, "백업 완료",
                f"✅ 백업이 완료되었습니다.\n\n📁 {backup_path}"
            )
        else:
            self._update_status("백업 실패", "error")
            QMessageBox.warning(
                self, "백업 실패",
                "❌ 백업 중 오류가 발생했습니다."
            )

    @Slot()
    def _on_refresh_stats(self):
        """통계 정보 갱신."""
        self._update_status("통계 갱신 중...", "working")
        self._load_rooms()
        if self.current_room_id:
            self._on_room_selected(self.current_room_id, self.current_room_file)
        self._update_status("통계 갱신 완료", "success")

    @Slot()
    def _on_settings(self):
        """설정 다이얼로그."""
        dialog = SettingsDialog(self)
        if dialog.exec() == QDialog.Accepted:
            # TODO: 설정 저장
            pass

    @Slot()
    def _on_room_backup(self):
        """선택된 채팅방 백업."""
        if not self.current_room_id:
            QMessageBox.warning(self, "채팅방 백업", "먼저 채팅방을 선택하세요.")
            return
        
        # 현재 채팅방 이름 가져오기
        room = self.db.get_room_by_id(self.current_room_id)
        if not room:
            QMessageBox.warning(self, "채팅방 백업", "채팅방 정보를 찾을 수 없습니다.")
            return
        
        room_name = room.name
        
        reply = QMessageBox.question(
            self, "채팅방 백업",
            f"'{room_name}' 채팅방을 백업하시겠습니까?\n\n"
            f"백업 대상:\n"
            f"• 원본 대화 (data/original/{room_name}/)\n"
            f"• 요약 파일 (data/summary/{room_name}/)\n"
            f"• URL 파일 (data/url/{room_name}/)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        self._update_status(f"'{room_name}' 백업 중...", "working")
        
        backup_path = self.storage.backup_room(room_name)
        
        if backup_path:
            self._update_status(f"'{room_name}' 백업 완료", "success")
            QMessageBox.information(
                self, "채팅방 백업 완료",
                f"✅ '{room_name}' 백업이 완료되었습니다.\n\n📁 {backup_path}"
            )
        else:
            self._update_status("백업 실패", "error")
            QMessageBox.warning(self, "백업 실패", "❌ 백업 중 오류가 발생했습니다.")

    @Slot()
    def _on_restore_from_backup(self):
        """전체 백업에서 복원."""
        backups = self.storage.get_backup_list()

        if not backups:
            QMessageBox.information(
                self, "전체 백업에서 복원",
                "사용 가능한 백업이 없습니다.\n\n"
                "먼저 '💾 전체 백업...' 또는 '💾 채팅방 백업...'을 실행하세요."
            )
            return

        # 백업 선택 다이얼로그
        from PySide6.QtWidgets import QInputDialog

        backup_items = [
            f"{b['name']} ({b['size_mb']} MB)" for b in backups
        ]

        selected, ok = QInputDialog.getItem(
            self, "전체 백업에서 복원",
            "복원할 백업을 선택하세요:",
            backup_items, 0, False
        )

        if not ok:
            return

        # 선택된 백업 찾기
        selected_idx = backup_items.index(selected)
        backup = backups[selected_idx]
        backup_path = backup['path']

        reply = QMessageBox.warning(
            self, "전체 복원 확인",
            "⚠️ 전체 복원은 현재 데이터를 덮어씁니다.\n\n"
            "• 현재 DB가 백업 시점의 DB로 교체됩니다\n"
            "• 모든 파일이 백업 시점으로 복원됩니다\n\n"
            "계속하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        self._update_status("전체 복원 중...", "working")
        success = self.storage.restore_from_backup(backup_path)

        if success:
            self._update_status("전체 복원 완료 (재시작 권장)", "success")
            QMessageBox.information(
                self, "복원 완료",
                "✅ 전체 복원이 완료되었습니다.\n\n"
                "⚠️ DB가 변경되었으므로 앱을 재시작하세요."
            )
        else:
            self._update_status("복원 실패", "error")
            QMessageBox.warning(self, "복원 실패", "❌ 복원 중 오류가 발생했습니다.")

    def _on_restore_room_from_backup_with_current(self):
        """기타 탭에서 호출: 현재 선택된 채팅방을 기본값으로 복원."""
        default_room = None
        if self.current_room_id:
            room = self.db.get_room_by_id(self.current_room_id)
            if room:
                default_room = room.name
        self._on_restore_room_from_backup(default_room)

    def _on_restore_room_from_backup(self, default_room=None):
        """백업에서 특정 채팅방 복원.

        Args:
            default_room: 기본 선택할 채팅방 이름 (기타 탭에서 호출 시 현재 채팅방)
        """
        backups = self.storage.get_backup_list()

        if not backups:
            QMessageBox.information(
                self, "채팅방 복원",
                "사용 가능한 백업이 없습니다.\n\n"
                "먼저 '💾 전체 백업...' 또는 '💾 채팅방 백업...'을 실행하세요."
            )
            return

        from PySide6.QtWidgets import QInputDialog

        # 백업 선택
        backup_items = [
            f"{b['name']} ({b['size_mb']} MB)" for b in backups
        ]

        selected, ok = QInputDialog.getItem(
            self, "채팅방 복원",
            "백업을 선택하세요:",
            backup_items, 0, False
        )

        if not ok:
            return

        selected_idx = backup_items.index(selected)
        backup = backups[selected_idx]
        backup_path = backup['path']

        # 백업 내 채팅방 목록 조회
        rooms_in_backup = self.storage.get_rooms_in_backup(backup_path)

        if not rooms_in_backup:
            QMessageBox.information(
                self, "채팅방 복원",
                "선택한 백업에 채팅방 데이터가 없습니다."
            )
            return

        # 기본 선택 인덱스 결정
        default_idx = 0
        if default_room and default_room in rooms_in_backup:
            default_idx = rooms_in_backup.index(default_room)

        # 채팅방 선택
        selected_room, ok = QInputDialog.getItem(
            self, "채팅방 복원",
            f"백업: {backup['name']}\n\n복원할 채팅방을 선택하세요:",
            rooms_in_backup, default_idx, False
        )

        if not ok:
            return

        # 복원 실행
        self._update_status(f"'{selected_room}' 복원 중...", "working")
        success = self.storage.restore_from_backup(backup_path, selected_room)

        if success:
            self._update_status(f"'{selected_room}' 복원 완료", "success")
            self._load_rooms()
            QMessageBox.information(
                self, "복원 완료",
                f"✅ '{selected_room}' 채팅방이 복원되었습니다."
            )
        else:
            self._update_status("복원 실패", "error")
            QMessageBox.warning(self, "복원 실패", "❌ 복원 중 오류가 발생했습니다.")
    
    # ===== 날짜별 요약 탭 메서드 =====
    
    @Slot()
    def _show_calendar_dialog(self):
        """달력 다이얼로그 표시."""
        dialog = QDialog(self)
        dialog.setWindowTitle("📅 날짜 선택")
        dialog.setFixedSize(350, 300)
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 달력 위젯
        calendar = QCalendarWidget()
        calendar.setSelectedDate(self.date_edit.date())
        calendar.setStyleSheet("""
            QCalendarWidget {
                background-color: #FFFFFF;
            }
            QCalendarWidget QToolButton {
                color: #333;
                font-size: 13px;
                font-weight: bold;
                padding: 5px;
            }
            QCalendarWidget QToolButton:hover {
                background-color: #FEE500;
                border-radius: 4px;
            }
            QCalendarWidget QWidget#qt_calendar_navigationbar {
                background-color: #FEE500;
                padding: 5px;
            }
            QCalendarWidget QTableView {
                selection-background-color: #FEE500;
                selection-color: #000000;
                font-size: 12px;
            }
            QCalendarWidget QTableView::item:hover {
                background-color: #FFF9C4;
            }
        """)
        layout.addWidget(calendar)
        
        # 버튼
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        today_btn = QPushButton("오늘")
        today_btn.setStyleSheet("""
            QPushButton {
                background-color: #5B9BD5;
                color: white;
                padding: 8px 20px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #4A8BC4;
            }
        """)
        today_btn.clicked.connect(lambda: calendar.setSelectedDate(QDate.currentDate()))
        btn_layout.addWidget(today_btn)
        
        select_btn = QPushButton("선택")
        select_btn.setStyleSheet("""
            QPushButton {
                background-color: #FEE500;
                padding: 8px 20px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #FFD700;
            }
        """)
        select_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(select_btn)
        
        layout.addLayout(btn_layout)
        
        # 더블클릭으로도 선택 가능
        calendar.activated.connect(dialog.accept)
        
        if dialog.exec() == QDialog.Accepted:
            self.date_edit.setDate(calendar.selectedDate())
    
    @Slot()
    def _on_prev_date(self):
        """이전 날짜로 이동."""
        current = self.date_edit.date()
        self.date_edit.setDate(current.addDays(-1))
    
    @Slot()
    def _on_next_date(self):
        """다음 날짜로 이동."""
        current = self.date_edit.date()
        self.date_edit.setDate(current.addDays(1))
    
    @Slot(QDate)
    def _on_date_changed(self, date: QDate):
        """날짜 변경 시 요약 로드."""
        # 상세 분석 뷰 활성화 상태면 상세 내용 표시
        if getattr(self, '_detail_view_active', False):
            self._show_detail_date_content(date)
            return

        # 기본 뷰에서는 상세 분석 버튼 숨기기, 기본 요약 버튼 표시
        if hasattr(self, 'detail_generate_btn'):
            self.detail_generate_btn.setVisible(False)
        if hasattr(self, 'detail_open_btn'):
            self.detail_open_btn.setVisible(False)
        if hasattr(self, 'detail_batch_btn'):
            self.detail_batch_btn.setVisible(False)
        if hasattr(self, 'basic_generate_btn'):
            self.basic_generate_btn.setVisible(self.current_room_id is not None)

        if self.current_room_id is None:
            self.detail_browser.setHtml("""
                <div style="text-align: center; padding: 50px; color: #888;">
                    <p style="font-size: 48px;">📁</p>
                    <p style="font-size: 16px;">먼저 채팅방을 선택하세요</p>
                </div>
            """)
            return
        
        # 현재 채팅방 이름 가져오기
        room = self.db.get_room_by_id(self.current_room_id)
        if not room:
            return
        
        room_name = room.name
        date_str = date.toString("yyyy-MM-dd")
        
        # 파일 저장소에서 데이터 로드
        from file_storage import get_storage
        storage = get_storage()
        
        # 원본 메시지 로드
        messages = storage.load_daily_original(room_name, date_str)
        
        # 요약 로드
        summary = storage.load_daily_summary(room_name, date_str)
        
        # 사용 가능한 날짜 목록
        available_dates = storage.get_available_dates(room_name)
        summarized_dates = storage.get_summarized_dates(room_name)
        
        # 날짜 정보 업데이트
        has_original = date_str in available_dates
        has_summary = date_str in summarized_dates
        
        status_parts = []
        if has_original:
            status_parts.append(f"💬 {len(messages)}개 메시지")
        if has_summary:
            status_parts.append("✅ 요약 완료")
        else:
            status_parts.append("⚠️ 요약 없음")
        if storage.has_detail_summary(room_name, date_str):
            status_parts.append("🔍 상세 ✅")

        self.date_info_label.setText(f"📅 {date_str} | " + " | ".join(status_parts))
        
        # HTML 생성
        if not has_original and not has_summary:
            self.detail_browser.setHtml(f"""
                <div style="text-align: center; padding: 50px; color: #888;">
                    <p style="font-size: 48px;">📭</p>
                    <p style="font-size: 16px;">{date_str}에는 대화 기록이 없습니다</p>
                    <p style="font-size: 12px; color: #AAA;">다른 날짜를 선택해보세요</p>
                </div>
            """)
            return
        
        html = f"<h2>📅 {room_name} - {date_str}</h2>"
        
        # 요약 표시
        if summary:
            # 메타데이터 제거하고 본문만 추출
            summary_lines = summary.split('\n')
            content_start = 0
            for i, line in enumerate(summary_lines):
                if line.strip() == '---' and i > 0:
                    content_start = i + 1
                    break
            
            # 푸터 제거
            content_lines = []
            for line in summary_lines[content_start:]:
                if line.strip().startswith('_Generated'):
                    break
                content_lines.append(line)
            
            summary_content = '\n'.join(content_lines)
            html += f"""
                <div style="background-color: #FFF8E1; padding: 15px; border-radius: 8px; margin: 10px 0; border-left: 4px solid #FFC107;">
                    <h3 style="margin-top: 0;">📝 AI 요약</h3>
                    <div style="line-height: 1.8;">{summary_content.replace(chr(10), '<br>')}</div>
                </div>
            """
        else:
            html += """
                <div style="background-color: #FFEBEE; padding: 15px; border-radius: 8px; margin: 10px 0; border-left: 4px solid #F44336;">
                    <p style="margin: 0; color: #C62828;">⚠️ 이 날짜의 요약이 아직 생성되지 않았습니다.</p>
                    <p style="margin: 5px 0 0 0; color: #888; font-size: 12px;">대시보드 탭에서 '🤖 LLM 요약 생성' 버튼을 클릭하세요.</p>
                </div>
            """
        
        self.detail_browser.setHtml(html)
    
    def _update_date_tab_for_room(self, room_name: str):
        """채팅방 선택 시 날짜 탭 정보 업데이트."""
        from file_storage import get_storage
        storage = get_storage()
        
        available_dates = storage.get_available_dates(room_name)
        
        if available_dates:
            # 가장 최근 날짜로 설정
            latest_date = available_dates[-1]
            year, month, day = map(int, latest_date.split('-'))
            self.date_edit.setDate(QDate(year, month, day))
        else:
            self.date_edit.setDate(QDate.currentDate())
        
        # 날짜 변경 이벤트 트리거
        self._on_date_changed(self.date_edit.date())
    
    # ===== 상세 분석 메서드 =====

    def _toggle_detail_view(self, detail_active: bool):
        """기본 요약 / 상세 분석 뷰 토글."""
        self._detail_view_active = detail_active

        # 토글 버튼 스타일 업데이트
        active_style = """
            QPushButton {
                background-color: #FEE500; color: #000; font-weight: bold;
                padding: 6px 16px; border-radius: 6px; font-size: 11px; border: none;
            }
        """
        inactive_style = """
            QPushButton {
                background-color: #E0E0E0; color: #333;
                padding: 6px 16px; border-radius: 6px; font-size: 11px; border: none;
            }
            QPushButton:hover { background-color: #BDBDBD; }
        """
        if detail_active:
            self.detail_view_btn.setStyleSheet(active_style)
            self.basic_view_btn.setStyleSheet(inactive_style)
        else:
            self.basic_view_btn.setStyleSheet(active_style)
            self.detail_view_btn.setStyleSheet(inactive_style)

        # 뷰 갱신
        self._on_date_changed(self.date_edit.date())

    def _show_detail_date_content(self, date: QDate):
        """날짜별 상세 분석 표시."""
        if self.current_room_id is None:
            self.detail_browser.setHtml("""
                <div style="text-align: center; padding: 50px; color: #888;">
                    <p style="font-size: 48px;">📁</p>
                    <p style="font-size: 16px;">먼저 채팅방을 선택하세요</p>
                </div>
            """)
            self.detail_generate_btn.setVisible(False)
            self.detail_open_btn.setVisible(False)
            self.detail_batch_btn.setVisible(False)
            self.basic_generate_btn.setVisible(False)
            return

        # 상세 뷰에서는 기본 요약 버튼 숨기기
        self.basic_generate_btn.setVisible(False)

        room = self.db.get_room_by_id(self.current_room_id)
        if not room:
            return

        room_name = room.name
        date_str = date.toString("yyyy-MM-dd")

        from file_storage import get_storage
        storage = get_storage()

        messages = storage.load_daily_original(room_name, date_str)
        has_detail = storage.has_detail_summary(room_name, date_str)
        has_original = len(messages) > 0

        # 상태 라벨 업데이트
        status_parts = []
        if has_original:
            status_parts.append(f"💬 {len(messages)}개 메시지")
        status_parts.append("✅ 상세 분석 완료" if has_detail else "⚠️ 상세 분석 없음")
        self.date_info_label.setText(f"📅 {date_str} | " + " | ".join(status_parts))

        # 버튼 표시 업데이트
        self.detail_generate_btn.setVisible(has_original and not has_detail)
        self.detail_open_btn.setVisible(has_detail)
        self.detail_batch_btn.setVisible(True)  # 상세 뷰에서 항상 표시

        if not has_original:
            self.detail_browser.setHtml(f"""
                <div style="text-align: center; padding: 50px; color: #888;">
                    <p style="font-size: 48px;">📭</p>
                    <p style="font-size: 16px;">{date_str}에는 대화 기록이 없습니다</p>
                </div>
            """)
            return

        if has_detail:
            detail_html = storage.load_detail_summary(room_name, date_str)
            detail_html = self._sanitize_detail_html_for_qt(detail_html)
            # HTML 파일에서 body 콘텐츠만 추출하여 QTextBrowser에 표시
            body_match = re.search(
                r'<div class="container">(.*)</div>\s*</body>',
                detail_html, re.DOTALL
            )
            if body_match:
                content = body_match.group(1)
                # meta/footer 제거
                content = re.sub(r'<p class="meta">.*?</p>', '', content)
                content = re.sub(r'<p class="footer">.*?</p>', '', content)
                self.detail_browser.setHtml(f"""
                    <div style="padding: 10px; line-height: 1.8;">
                        <div style="background-color: #E3F2FD; padding: 12px 15px;
                                    margin-bottom: 15px; border-left: 4px solid #1976D2;">
                            <b style="color: #1565C0;">🔍 상세 분석</b>
                        </div>
                        {content}
                    </div>
                """)
            else:
                self.detail_browser.setHtml(detail_html)
        else:
            self.detail_browser.setHtml("""
                <div style="text-align: center; padding: 50px; color: #888;">
                    <p style="font-size: 48px;">🔍</p>
                    <p style="font-size: 16px;">상세 분석이 아직 생성되지 않았습니다</p>
                    <p style="font-size: 12px; color: #AAA;">'🔍 상세 생성' 버튼을 클릭하세요</p>
                </div>
            """)

    @staticmethod
    def _sanitize_detail_html_for_qt(detail_html: str) -> str:
        """QTextBrowser is stricter than browsers; repair a few common malformed closing tags."""
        if not detail_html:
            return detail_html

        fixed_html = re.sub(r'</h([1-6])p>', r'</h\1>', detail_html, flags=re.IGNORECASE)
        fixed_html = fixed_html.replace("</hp>", "</h2>")
        return fixed_html

    def _on_generate_detail_summary(self):
        """상세 분석 생성."""
        if self._summary_in_progress:
            QMessageBox.warning(self, "알림", "이미 요약이 진행 중입니다.\n완료 후 다시 시도하세요.")
            return

        if self.current_room_id is None:
            QMessageBox.warning(self, "알림", "먼저 채팅방을 선택하세요.")
            return

        room = self.db.get_room_by_id(self.current_room_id)
        if not room:
            return

        room_name = room.name
        date_str = self.date_edit.date().toString("yyyy-MM-dd")

        # LLM 선택 다이얼로그
        from full_config import config, LLM_PROVIDERS
        llm_items = []
        llm_keys = []
        for key, provider in LLM_PROVIDERS.items():
            api_key = config.get_api_key(key)
            status = "✅" if api_key else "⚠️"
            llm_items.append(f"{status} {provider.name}")
            llm_keys.append(key)

        dialog = QDialog(self)
        dialog.setWindowTitle("🔍 상세 분석 생성")
        dialog.setFixedWidth(380)
        dlg_layout = QVBoxLayout(dialog)

        dlg_layout.addWidget(QLabel(f"<b>📅 {room_name} — {date_str}</b>"))
        dlg_layout.addWidget(QLabel("상세 분석 HTML을 생성합니다."))

        llm_combo = QComboBox()
        llm_combo.addItems(llm_items)
        # 현재 기본 LLM 선택
        current_idx = llm_keys.index(config.current_provider) if config.current_provider in llm_keys else 0
        llm_combo.setCurrentIndex(current_idx)
        form = QFormLayout()
        form.addRow("LLM:", llm_combo)
        dlg_layout.addLayout(form)

        btn_layout = QHBoxLayout()
        cancel_btn = QPushButton("취소")
        cancel_btn.clicked.connect(dialog.reject)
        ok_btn = QPushButton("🔍 생성")
        ok_btn.setStyleSheet("QPushButton { background-color: #1976D2; color: white; padding: 8px 20px; border-radius: 6px; }")
        ok_btn.clicked.connect(dialog.accept)
        ok_btn.setDefault(True)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(ok_btn)
        dlg_layout.addLayout(btn_layout)

        if dialog.exec() != QDialog.Accepted:
            return

        selected_llm = llm_keys[llm_combo.currentIndex()]
        llm_display_name = llm_combo.currentText()

        # 상태 플래그 설정
        self._summary_in_progress = True
        self.detail_generate_btn.setEnabled(False)

        # 상태바에 프로그레스 위젯 삽입
        self.summary_progress_widget = SummaryProgressWidget(
            self, llm_name=llm_display_name, room_name=f"{room_name} 상세 분석"
        )
        self.statusbar.insertPermanentWidget(0, self.summary_progress_widget)
        self.summary_progress_widget.show()

        self._update_status(f"⏳ {llm_display_name} 상세 분석 중...", "working")

        # 워커 시작
        self.detail_worker = DetailSummaryWorker(
            self.current_room_id, room_name, date_str, selected_llm
        )
        self.detail_worker.progress.connect(self.summary_progress_widget.update_progress)
        self.detail_worker.progress.connect(lambda p, m: self._update_status(m, "working"))
        self.detail_worker.finished.connect(self._on_detail_summary_finished)
        self.summary_progress_widget.cancel_requested.connect(self.detail_worker.cancel)
        self.detail_worker.start()

    @Slot(bool, str)
    def _on_detail_summary_finished(self, success: bool, result: str):
        """상세 분석 완료."""
        self._summary_in_progress = False
        self.detail_generate_btn.setEnabled(True)

        # 프로그레스 위젯 제거
        if self.summary_progress_widget:
            self.statusbar.removeWidget(self.summary_progress_widget)
            self.summary_progress_widget.deleteLater()
            self.summary_progress_widget = None

        if success:
            self._update_status("✅ 상세 분석 완료", "success")
            # 현재 보고 있는 날짜 뷰를 갱신
            if self._detail_view_active:
                self._show_detail_date_content(self.date_edit.date())
            else:
                # 기본 뷰라도 date_info_label 갱신 (🔍 상세 ✅ 추가)
                self._on_date_changed(self.date_edit.date())
        else:
            self._update_status(f"❌ {result}", "error")
            QMessageBox.warning(self, "상세 분석 실패", result)

    def _on_open_detail_in_browser(self):
        """상세 분석 HTML을 기본 브라우저에서 열기."""
        if self.current_room_id is None:
            return

        room = self.db.get_room_by_id(self.current_room_id)
        if not room:
            return

        date_str = self.date_edit.date().toString("yyyy-MM-dd")
        from file_storage import get_storage
        storage = get_storage()

        filepath = storage.get_detail_summary_path(room.name, date_str)
        if filepath.exists():
            import webbrowser
            webbrowser.open(filepath.as_uri())
        else:
            QMessageBox.information(self, "알림", "상세 분석 파일이 없습니다.")

    def _on_generate_detail_batch(self):
        """일괄 상세 분석 생성 (기본 요약 있는 모든 날짜 대상)."""
        if self._summary_in_progress:
            QMessageBox.warning(self, "알림", "이미 작업이 진행 중입니다.")
            return

        if self.current_room_id is None:
            QMessageBox.warning(self, "알림", "먼저 채팅방을 선택하세요.")
            return

        room = self.db.get_room_by_id(self.current_room_id)
        if not room:
            return

        room_name = room.name
        from file_storage import get_storage
        storage = get_storage()

        # 기본 요약 있지만 상세 분석 없는 날짜
        summarized_dates = storage.get_summarized_dates(room_name)
        dates_needing = [
            d for d in summarized_dates
            if not storage.has_detail_summary(room_name, d)
        ]

        if not dates_needing:
            QMessageBox.information(
                self, "알림",
                f"모든 날짜({len(summarized_dates)}일)에 상세 분석이 이미 존재합니다."
            )
            return

        # LLM 선택 다이얼로그
        from full_config import config, LLM_PROVIDERS
        llm_items = []
        llm_keys = []
        for key, provider in LLM_PROVIDERS.items():
            api_key = config.get_api_key(key)
            status = "✅" if api_key else "⚠️"
            llm_items.append(f"{status} {provider.name}")
            llm_keys.append(key)

        dialog = QDialog(self)
        dialog.setWindowTitle("🔍 일괄 상세 분석 생성")
        dialog.setFixedWidth(400)
        dlg_layout = QVBoxLayout(dialog)

        dlg_layout.addWidget(QLabel(f"<b>{room_name}</b>"))
        dlg_layout.addWidget(QLabel(
            f"📊 기본 요약 {len(summarized_dates)}일 중 "
            f"<b>{len(dates_needing)}일</b>의 상세 분석을 생성합니다."
        ))

        llm_combo = QComboBox()
        llm_combo.addItems(llm_items)
        current_idx = llm_keys.index(config.current_provider) if config.current_provider in llm_keys else 0
        llm_combo.setCurrentIndex(current_idx)
        form = QFormLayout()
        form.addRow("LLM:", llm_combo)
        dlg_layout.addLayout(form)

        btn_layout = QHBoxLayout()
        cancel_btn = QPushButton("취소")
        cancel_btn.clicked.connect(dialog.reject)
        ok_btn = QPushButton(f"🔍 {len(dates_needing)}일 상세 생성")
        ok_btn.setStyleSheet("QPushButton { background-color: #7B1FA2; color: white; padding: 8px 20px; border-radius: 6px; }")
        ok_btn.clicked.connect(dialog.accept)
        ok_btn.setDefault(True)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(ok_btn)
        dlg_layout.addLayout(btn_layout)

        if dialog.exec() != QDialog.Accepted:
            return

        selected_llm = llm_keys[llm_combo.currentIndex()]
        self._start_detail_batch(self.current_room_id, room_name, selected_llm)

    def _start_detail_batch(self, room_id: int, room_name: str, llm_provider: str):
        """기본 요약 완료 후 상세 분석 일괄 생성 시작."""
        from file_storage import get_storage
        storage = get_storage()

        # 기본 요약이 있지만 상세 분석이 없는 날짜 목록
        summarized_dates = storage.get_summarized_dates(room_name)
        dates_needing_detail = [
            d for d in summarized_dates
            if not storage.has_detail_summary(room_name, d)
        ]

        if not dates_needing_detail:
            self._update_status("✅ 모든 날짜에 상세 분석이 이미 존재합니다.", "success")
            self._detail_after_summary = False
            return

        from full_config import LLM_PROVIDERS
        llm_info = LLM_PROVIDERS.get(llm_provider)
        llm_display = llm_info.name if llm_info else llm_provider

        # 상태 플래그
        self._summary_in_progress = True
        self.generate_btn.setEnabled(False)

        # 프로그레스 위젯
        self.summary_progress_widget = SummaryProgressWidget(
            self, llm_name=llm_display, room_name=f"{room_name} 상세 분석"
        )
        self.statusbar.insertPermanentWidget(0, self.summary_progress_widget)
        self.summary_progress_widget.show()

        self._update_status(
            f"🔍 상세 분석 시작 ({len(dates_needing_detail)}일)...", "working"
        )

        self.detail_batch_worker = DetailBatchWorker(
            room_id, room_name, dates_needing_detail, llm_provider
        )
        self.detail_batch_worker.progress.connect(
            self.summary_progress_widget.update_progress
        )
        self.detail_batch_worker.progress.connect(
            lambda p, m: self._update_status(m, "working")
        )
        self.detail_batch_worker.finished.connect(self._on_detail_batch_finished)
        self.summary_progress_widget.cancel_requested.connect(
            self.detail_batch_worker.cancel
        )
        self.detail_batch_worker.start()

    @Slot(bool, str)
    def _on_detail_batch_finished(self, success: bool, result: str):
        """상세 분석 일괄 생성 완료."""
        self._summary_in_progress = False
        self._detail_after_summary = False
        self.generate_btn.setEnabled(True)

        if self.summary_progress_widget:
            self.statusbar.removeWidget(self.summary_progress_widget)
            self.summary_progress_widget.deleteLater()
            self.summary_progress_widget = None

        if success:
            self._update_status(f"✅ {result}", "success")
            # 현재 보고 있는 채팅방이면 뷰 갱신
            if self.current_room_id:
                self._on_room_selected(
                    self.current_room_id, self.current_room_file or ""
                )
        else:
            self._update_status(f"❌ {result}", "error")

        self.summary_source_room_id = None

    def _auto_sync_urls(self, room_id: int, room_name: str):
        """요약 완료 후 자동 URL 동기화."""
        try:
            from file_storage import get_storage
            storage = get_storage()

            today = date.today()
            three_days_ago = today - timedelta(days=3)
            one_week_ago = today - timedelta(days=7)

            urls_by_date = {}
            summary_dates = storage.get_summarized_dates(room_name)

            for date_str in sorted(summary_dates):
                summary = storage.load_daily_summary(room_name, date_str)
                if summary:
                    urls = extract_urls_from_text(summary)
                    if urls:
                        urls_by_date[date_str] = urls

            def extract_urls_for_period(start_date):
                period_urls = {}
                for ds, urls in urls_by_date.items():
                    try:
                        d = date.fromisoformat(ds)
                        if d >= start_date:
                            for url, descs in urls.items():
                                if url not in period_urls:
                                    period_urls[url] = []
                                for desc in descs:
                                    if desc and desc not in period_urls[url]:
                                        period_urls[url].append(desc)
                    except Exception:
                        pass
                return period_urls

            urls_recent = deduplicate_urls(extract_urls_for_period(three_days_ago))
            urls_weekly = deduplicate_urls(extract_urls_for_period(one_week_ago))
            urls_all = {}
            for ds, urls in urls_by_date.items():
                for url, descs in urls.items():
                    if url not in urls_all:
                        urls_all[url] = []
                    for desc in descs:
                        if desc and desc not in urls_all[url]:
                            urls_all[url].append(desc)
            urls_all = deduplicate_urls(urls_all)

            if urls_all:
                self.db.clear_urls_by_room(room_id)
                self.db.add_urls_batch(room_id, urls_all)
                storage.save_url_lists(room_name, urls_recent, urls_weekly, urls_all)
                logger.info(f"[URL 자동 동기화] {room_name}: {len(urls_all)}개 URL 저장")
        except Exception as e:
            logger.warning(f"[URL 자동 동기화] {room_name} 실패: {e}")

    # ===== URL 정보 탭 메서드 =====
    
    def _load_url_from_db(self) -> Dict[str, List[str]]:
        """DB에서 URL 목록 로드."""
        if self.current_room_id is None:
            return {}
        return self.db.get_urls_by_room(self.current_room_id)
    
    def _display_url_list(self, urls_all: Dict[str, List[str]], source: str = "DB",
                          urls_recent: Dict[str, List[str]] = None,
                          urls_weekly: Dict[str, List[str]] = None):
        """URL 목록 표시 (3개 섹션: 3일, 1주, 전체)."""
        MAX_DISPLAY = 50  # 섹션당 최대 표시 개수
        
        # 알파벳순 정렬
        sorted_all = sorted(urls_all.items(), key=lambda x: x[0].lower())
        sorted_recent = sorted(urls_recent.items(), key=lambda x: x[0].lower()) if urls_recent else []
        sorted_weekly = sorted(urls_weekly.items(), key=lambda x: x[0].lower()) if urls_weekly else []
        
        total_urls = len(sorted_all)
        
        # HTML 섹션 생성 헬퍼
        def generate_url_section(title: str, emoji: str, urls: list, color: str, max_items: int = MAX_DISPLAY) -> str:
            if not urls:
                return f"""
                <div style="margin-bottom: 25px;">
                    <h3 style="color: {color}; margin-bottom: 10px;">{emoji} {title}</h3>
                    <p style="color: #999; font-size: 13px; padding: 15px; background: #F5F5F5; border-radius: 8px;">
                        해당 기간에 공유된 URL이 없습니다.
                    </p>
                </div>
                """
            
            total_count = len(urls)
            display_urls = urls[:max_items]
            has_more = total_count > max_items
            
            html = f"""
            <div style="margin-bottom: 25px;">
                <h3 style="color: {color}; margin-bottom: 10px; border-bottom: 2px solid {color}; padding-bottom: 5px;">
                    {emoji} {title} ({total_count}개)
                </h3>
            """
            for i, (url, descriptions) in enumerate(display_urls, 1):
                desc_html = ""
                if descriptions:
                    for desc in descriptions:
                        # 내용/시사점/활용 키워드를 볼드 처리
                        if desc.startswith(('내용 —', '시사점 —', '활용 —', '내용—', '시사점—', '활용—')):
                            key, _, val = desc.partition('—')
                            desc_html += f'<div style="color: #555; font-size: 11px; margin-left: 30px;"><b>{key.strip()}</b> — {val.strip()}</div>'
                        else:
                            desc_html += f'<div style="color: #444; font-size: 12px; margin-left: 30px; margin-top: 3px;">{desc}</div>'
                else:
                    desc_html = '<div style="color: #999; font-size: 11px; margin-left: 30px;">설명 없음</div>'
                html += f"""
                <div style="margin-bottom: 12px; padding: 10px; background-color: #F9F9F9; border-radius: 8px; border-left: 3px solid {color};">
                    <span style="color: #999; font-size: 11px; margin-right: 8px;">&nbsp;&nbsp;#{i}</span>
                    <a href="{url}" style="color: #1E88E5; text-decoration: none; word-break: break-all; font-size: 13px;">
                        {url}
                    </a>
                    {desc_html}
                </div>
                """
            
            # 초과 시 "더 있음" 표시
            if has_more:
                remaining = total_count - max_items
                html += f"""
                <div style="text-align: center; padding: 15px; background: #F0F0F0; border-radius: 8px; color: #666;">
                    <span style="font-size: 14px;">... 외 <b>{remaining}개</b> URL이 더 있습니다</span>
                </div>
                """
            
            html += "</div>"
            return html
        
        # HTML 생성
        if total_urls > 0:
            html = f"""
            <div style="padding: 10px;">
                <div style="background: linear-gradient(135deg, #FEE500, #FFD700); padding: 15px; border-radius: 10px; margin-bottom: 20px;">
                    <p style="color: #333; font-size: 14px; margin: 0;">
                        📊 총 <b>{total_urls}개</b> URL이 공유되었습니다.
                        <span style="font-size: 12px; color: #555;">
                            (출처: {source})
                            | 🔥 3일: {len(sorted_recent)}개
                            | 📅 1주: {len(sorted_weekly)}개
                        </span>
                    </p>
                </div>
            """
            
            # 섹션 1: 최근 3일
            html += generate_url_section("최근 3일", "🔥", sorted_recent, "#E53935", MAX_DISPLAY)
            
            # 섹션 2: 최근 1주 (제한 없이 모두 표시)
            html += generate_url_section("최근 1주", "📅", sorted_weekly, "#1E88E5", len(sorted_weekly))
            
            # 섹션 3: 전체 URL (제한 없이 모두 표시)
            html += generate_url_section("전체 URL", "📚", sorted_all, "#43A047", len(sorted_all))
            
            html += "</div>"
            self.url_browser.setHtml(html)
            self.url_count_label.setText(f"{total_urls}개 URL")
        else:
            self.url_browser.setHtml("""
                <div style="text-align: center; padding: 50px; color: #888;">
                    <p style="font-size: 48px;">🔗</p>
                    <p style="font-size: 16px;">공유된 URL이 없습니다</p>
                    <p style="font-size: 13px;">'🔄 동기화' 버튼을 눌러 요약에서 URL을 추출하세요</p>
                </div>
            """)
            self.url_count_label.setText("0개 URL")
        
        self._current_url_data = urls_all
    
    @Slot()
    def _refresh_url_list(self):
        """URL 목록 새로고침 (DB + 파일에서 로드)."""
        if self.current_room_id is None:
            self.url_browser.setHtml("""
                <div style="text-align: center; padding: 50px; color: #888;">
                    <p style="font-size: 48px;">📁</p>
                    <p style="font-size: 16px;">먼저 채팅방을 선택하세요</p>
                </div>
            """)
            self.url_count_label.setText("0개 URL")
            self.url_status_label.setText("")
            return
        
        self._update_status("URL 로드 중...", "working")
        
        room = self.db.get_room_by_id(self.current_room_id)
        if not room:
            return
        
        # 1. DB에서 전체 URL 로드
        urls_all = self._load_url_from_db()
        
        # 2. 파일에서 기간별 URL 로드
        urls_recent = self.storage.load_url_list(room.name, "recent")
        urls_weekly = self.storage.load_url_list(room.name, "weekly")
        
        if urls_all:
            self._display_url_list(urls_all, "DB", urls_recent, urls_weekly)
            self.url_status_label.setText("(DB)")
            self._update_status("URL 로드 완료", "success")
        else:
            # DB에 없으면 파일에서 전체 로드
            urls_all = self.storage.load_url_list(room.name, "all")
            if urls_all:
                self._display_url_list(urls_all, "파일", urls_recent, urls_weekly)
                self.url_status_label.setText("(파일)")
                self._update_status("URL 로드 완료 (파일)", "success")
            else:
                self._display_url_list({}, "", {}, {})
                self.url_status_label.setText("(동기화 필요)")
                self._update_status("URL 없음", "info")
    
    @Slot()
    def _sync_url_from_summaries(self):
        """요약 파일에서 URL 추출하여 DB와 파일(3개)에 저장."""
        if self.current_room_id is None:
            QMessageBox.warning(self, "알림", "먼저 채팅방을 선택하세요.")
            return
        
        room = self.db.get_room_by_id(self.current_room_id)
        if not room:
            return
        
        room_name = room.name
        self._update_status("URL 동기화 중...", "working")
        
        # 날짜 기준
        today = date.today()
        three_days_ago = today - timedelta(days=3)
        one_week_ago = today - timedelta(days=7)
        
        # 날짜별 URL 추출
        urls_by_date = {}  # {date_str: {url: [descriptions]}}
        summary_dates = self.storage.get_summarized_dates(room_name)
        
        for date_str in sorted(summary_dates):
            summary = self.storage.load_daily_summary(room_name, date_str)
            if summary:
                urls = extract_urls_from_text(summary)
                if urls:
                    urls_by_date[date_str] = urls
        
        # 기간별 URL 분류
        def extract_urls_for_period(start_date: date) -> dict:
            period_urls = {}
            for date_str, urls in urls_by_date.items():
                try:
                    d = date.fromisoformat(date_str)
                    if d >= start_date:
                        for url, descriptions in urls.items():
                            if url not in period_urls:
                                period_urls[url] = []
                            for desc in descriptions:
                                if desc and desc not in period_urls[url]:
                                    period_urls[url].append(desc)
                except:
                    pass
            return period_urls
        
        # 3개 기간별 URL
        urls_recent = deduplicate_urls(extract_urls_for_period(three_days_ago))
        urls_weekly = deduplicate_urls(extract_urls_for_period(one_week_ago))
        urls_all = {}
        for date_str, urls in urls_by_date.items():
            for url, descriptions in urls.items():
                if url not in urls_all:
                    urls_all[url] = []
                for desc in descriptions:
                    if desc and desc not in urls_all[url]:
                        urls_all[url].append(desc)
        
        # 최종 중복 제거 및 정렬
        urls_all = deduplicate_urls(urls_all)
        
        if urls_all:
            # DB에 저장 (기존 삭제 후 새로 추가)
            self.db.clear_urls_by_room(self.current_room_id)
            self.db.add_urls_batch(self.current_room_id, urls_all)
            
            # 파일에 3개로 저장
            paths = self.storage.save_url_lists(room_name, urls_recent, urls_weekly, urls_all)
            
            # 3개 섹션과 함께 표시
            self._display_url_list(urls_all, "동기화됨", urls_recent, urls_weekly)
            self.url_status_label.setText("(동기화됨)")
            self._update_status(f"URL 동기화 완료 ({len(urls_all)}개)", "success")
            
            QMessageBox.information(
                self, "동기화 완료",
                f"✅ URL이 동기화되었습니다.\n\n"
                f"- DB에 저장됨\n"
                f"- 파일 저장:\n"
                f"  📁 {room_name}_urls_recent.md ({len(urls_recent)}개)\n"
                f"  📁 {room_name}_urls_weekly.md ({len(urls_weekly)}개)\n"
                f"  📁 {room_name}_urls_all.md ({len(urls_all)}개)"
            )
        else:
            self._display_url_list({}, "")
            self.url_status_label.setText("(URL 없음)")
            self._update_status("동기화할 URL 없음", "info")
            QMessageBox.information(self, "알림", "요약에서 추출된 URL이 없습니다.")
    
    @Slot()
    def _restore_url_from_file(self):
        """파일에서 URL 목록을 DB로 복구 (_urls_all.md 사용)."""
        if self.current_room_id is None:
            QMessageBox.warning(self, "알림", "먼저 채팅방을 선택하세요.")
            return
        
        room = self.db.get_room_by_id(self.current_room_id)
        if not room:
            return
        
        room_name = room.name
        self._update_status("URL 복구 중...", "working")
        
        # 전체 URL 파일에서 로드
        file_urls = self.storage.load_url_list(room_name, "all")
        
        if file_urls:
            # DB에 저장 (기존 삭제 후 새로 추가)
            self.db.clear_urls_by_room(self.current_room_id)
            self.db.add_urls_batch(self.current_room_id, file_urls)
            
            # 기간별 파일도 로드
            urls_recent = self.storage.load_url_list(room_name, "recent")
            urls_weekly = self.storage.load_url_list(room_name, "weekly")
            
            self._display_url_list(file_urls, "복구됨", urls_recent, urls_weekly)
            self.url_status_label.setText("(복구됨)")
            self._update_status(f"URL 복구 완료 ({len(file_urls)}개)", "success")
            
            QMessageBox.information(
                self, "복구 완료",
                f"✅ {len(file_urls)}개 URL이 파일에서 DB로 복구되었습니다."
            )
        else:
            file_info = self.storage.get_url_file_info(room_name)
            if file_info is None:
                QMessageBox.warning(
                    self, "복구 실패",
                    f"URL 파일을 찾을 수 없습니다.\n\n"
                    f"예상 경로: data/url/{room_name}/{room_name}_urls_all.md\n\n"
                    f"'🔄 동기화' 버튼으로 요약에서 URL을 먼저 추출하세요."
                )
            else:
                QMessageBox.warning(self, "복구 실패", "파일에 URL이 없습니다.")
            self._update_status("URL 복구 실패", "error")
    
    def closeEvent(self, event):
        """앱 종료 시 진행 중인 요약 처리."""
        active_worker = None
        if self._summary_in_progress:
            if self.summary_worker and self.summary_worker.isRunning():
                active_worker = self.summary_worker
            elif self.all_rooms_summary_worker and self.all_rooms_summary_worker.isRunning():
                active_worker = self.all_rooms_summary_worker

        if active_worker:
            reply = QMessageBox.question(
                self, "종료 확인",
                "요약이 진행 중입니다. 취소하고 종료하시겠습니까?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                event.ignore()
                return
            active_worker.cancel()
            active_worker.wait(5000)
        event.accept()

    @Slot()
    def _on_about(self):
        """정보 다이얼로그."""
        QMessageBox.about(
            self, "카카오톡 대화 분석기",
            """<h3>🗨️ 카카오톡 대화 분석기</h3>
            <p>버전 2.8.4</p>
            <p>카카오톡 대화를 분석하고 AI로 요약하는 도구입니다.</p>
            <p>제작자: 민연홍<br>
            <a href="https://github.com/YeonHongMin/kakao-chat-summary">https://github.com/YeonHongMin/kakao-chat-summary</a></p>
            <p>&copy; 2026 KakaoTalk Chat Summary</p>"""
        )
