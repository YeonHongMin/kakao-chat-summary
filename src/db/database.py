"""Database connection and session management."""
import logging
import os
import sys
from pathlib import Path
from datetime import datetime, date, time
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker, Session

from .models import Base, ChatRoom, Message, Summary, SyncLog, URL

_logger = logging.getLogger("KakaoSummarizer")
_env_loaded = False


def _load_env_local_once() -> None:
    """`.env.local`을 한 번만 로드합니다 (`CHAT_DB_PATH` 등 DB 설정용)."""
    global _env_loaded
    if _env_loaded:
        return
    _env_loaded = True
    try:
        from dotenv import load_dotenv

        project_root = Path(__file__).parent.parent.parent
        env_local = project_root / ".env.local"
        env_file = project_root / ".env"
        if env_local.exists():
            load_dotenv(env_local, override=True)
        elif env_file.exists():
            load_dotenv(env_file, override=True)
    except ImportError:
        pass


def _is_network_path(path: Path) -> bool:
    """UNC·매핑된 네트워크 드라이브 등 NFS/SMB 경로 여부."""
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path

    path_str = str(resolved)
    if path_str.startswith("\\\\") or path_str.startswith("//"):
        return True

    if sys.platform == "win32":
        drive = os.path.splitdrive(path_str)[0]
        if drive:
            import ctypes

            DRIVE_REMOTE = 4
            return ctypes.windll.kernel32.GetDriveTypeW(drive + "\\") == DRIVE_REMOTE
    return False


def resolve_chat_db_path(db_path: Optional[str] = None) -> str:
    """실제 SQLite DB 파일 경로 (공유 NFS 기본값 유지, `CHAT_DB_PATH`로만 개별 변경)."""
    _load_env_local_once()

    if db_path is not None:
        p = Path(db_path).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        return str(p.resolve())

    custom = os.getenv("CHAT_DB_PATH", "").strip()
    if custom:
        p = Path(custom).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        return str(p.resolve())

    project_root = Path(__file__).parent.parent.parent
    db_dir = project_root / "data" / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    return str((db_dir / "chat_history.db").resolve())


def resolve_sqlite_journal_mode(db_path: str) -> str:
    """저널 모드: 네트워크 경로는 DELETE(기본), 로컬은 WAL. `SQLITE_JOURNAL_MODE`로 강제 가능."""
    explicit = os.getenv("SQLITE_JOURNAL_MODE", "").strip().upper()
    allowed = {"WAL", "DELETE", "TRUNCATE", "OFF", "MEMORY", "PERSIST"}
    if explicit in allowed:
        return explicit
    if _is_network_path(Path(db_path)):
        return "DELETE"
    return "WAL"


class Database:
    """SQLite 데이터베이스 관리 클래스."""
    
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = resolve_chat_db_path(db_path)
        self.journal_mode = resolve_sqlite_journal_mode(self.db_path)
        on_network = _is_network_path(Path(self.db_path))

        # SQLite 최적화 설정
        self.engine = create_engine(
            f"sqlite:///{self.db_path}",
            echo=False,
            connect_args={
                "check_same_thread": False,
                "timeout": 30
            }
        )

        journal_mode = self.journal_mode
        synchronous = "FULL" if on_network and journal_mode != "WAL" else "NORMAL"

        from sqlalchemy import event

        @event.listens_for(self.engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute(f"PRAGMA journal_mode={journal_mode}")
            cursor.execute(f"PRAGMA synchronous={synchronous}")
            cursor.execute("PRAGMA cache_size=10000")
            cursor.execute("PRAGMA temp_store=MEMORY")
            cursor.close()

        if on_network and journal_mode == "DELETE":
            _logger.info(
                f"SQLite: 네트워크 경로 감지 → journal_mode=DELETE "
                f"(경로: {self.db_path})"
            )

        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)

        # 테이블 생성
        Base.metadata.create_all(self.engine)
    
    @contextmanager
    def get_session(self):
        """세션 컨텍스트 매니저."""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    # ==================== ChatRoom 관련 ====================
    
    def create_room(self, name: str, file_path: Optional[str] = None) -> ChatRoom:
        """새 채팅방 생성."""
        with self.get_session() as session:
            room = ChatRoom(name=name, file_path=file_path)
            session.add(room)
            session.flush()
            # detached 객체 반환을 위해 속성 복사
            return ChatRoom(
                id=room.id, name=room.name, file_path=room.file_path,
                last_sync_at=room.last_sync_at, created_at=room.created_at
            )
    
    def get_room_by_id(self, room_id: int) -> Optional[ChatRoom]:
        """ID로 채팅방 조회."""
        with self.get_session() as session:
            room = session.query(ChatRoom).filter(ChatRoom.id == room_id).first()
            if room:
                return ChatRoom(
                    id=room.id, name=room.name, file_path=room.file_path,
                    last_sync_at=room.last_sync_at, created_at=room.created_at
                )
            return None
    
    def get_room_by_name(self, name: str) -> Optional[ChatRoom]:
        """이름으로 채팅방 조회."""
        with self.get_session() as session:
            room = session.query(ChatRoom).filter(ChatRoom.name == name).first()
            if room:
                return ChatRoom(
                    id=room.id, name=room.name, file_path=room.file_path,
                    last_sync_at=room.last_sync_at, created_at=room.created_at
                )
            return None
    
    def get_all_rooms(self) -> List[ChatRoom]:
        """모든 채팅방 조회 (메시지 개수 내림차순 정렬)."""
        with self.get_session() as session:
            # 메시지 개수로 정렬하기 위한 서브쿼리
            from sqlalchemy import select
            msg_count_subq = (
                select(Message.room_id, func.count(Message.id).label('msg_count'))
                .group_by(Message.room_id)
                .subquery()
            )
            
            # 채팅방과 메시지 개수를 조인하여 정렬
            rooms = (
                session.query(ChatRoom)
                .outerjoin(msg_count_subq, ChatRoom.id == msg_count_subq.c.room_id)
                .order_by(func.coalesce(msg_count_subq.c.msg_count, 0).desc())
                .all()
            )
            
            return [
                ChatRoom(
                    id=r.id, name=r.name, file_path=r.file_path,
                    last_sync_at=r.last_sync_at, created_at=r.created_at
                ) for r in rooms
            ]

    def get_all_rooms_with_message_counts(self) -> List[tuple]:
        """모든 채팅방과 메시지 수를 한 번의 쿼리로 조회 (기동 N+1 방지)."""
        from sqlalchemy import select
        with self.get_session() as session:
            msg_count_subq = (
                select(Message.room_id, func.count(Message.id).label('msg_count'))
                .group_by(Message.room_id)
                .subquery()
            )
            rows = (
                session.query(
                    ChatRoom,
                    func.coalesce(msg_count_subq.c.msg_count, 0).label('msg_count'),
                )
                .outerjoin(msg_count_subq, ChatRoom.id == msg_count_subq.c.room_id)
                .all()
            )
            return [
                (
                    ChatRoom(
                        id=r.id, name=r.name, file_path=r.file_path,
                        last_sync_at=r.last_sync_at, created_at=r.created_at,
                    ),
                    int(count),
                )
                for r, count in rows
            ]

    def update_room_sync_time(self, room_id: int):
        """채팅방 동기화 시간 업데이트."""
        with self.get_session() as session:
            room = session.query(ChatRoom).filter(ChatRoom.id == room_id).first()
            if room:
                room.last_sync_at = datetime.now()
    
    def update_room_file_path(self, room_id: int, file_path: str):
        """앱 폴더 이동 시 깨진 원본 파일 절대 경로 보정."""
        with self.get_session() as session:
            room = session.query(ChatRoom).filter(ChatRoom.id == room_id).first()
            if room:
                room.file_path = file_path
    
    def delete_room(self, room_id: int):
        """채팅방 삭제 (연관 데이터 포함)."""
        with self.get_session() as session:
            room = session.query(ChatRoom).filter(ChatRoom.id == room_id).first()
            if room:
                session.delete(room)
    
    # ==================== Message 관련 ====================
    
    def add_messages(self, room_id: int, messages: List[Dict[str, Any]], batch_size: int = 500) -> int:
        """메시지 일괄 추가 (중복 무시, 배치 처리)."""
        added_count = 0
        
        # 배치 단위로 처리
        for i in range(0, len(messages), batch_size):
            batch = messages[i:i + batch_size]
            
            with self.get_session() as session:
                for msg_data in batch:
                    try:
                        # 중복 체크
                        existing = session.query(Message).filter(
                            Message.room_id == room_id,
                            Message.sender == msg_data['sender'],
                            Message.message_date == msg_data['date'],
                            Message.message_time == msg_data.get('time'),
                            Message.content == msg_data.get('content')
                        ).first()
                        
                        if existing is None:
                            msg = Message(
                                room_id=room_id,
                                sender=msg_data['sender'],
                                content=msg_data.get('content'),
                                message_date=msg_data['date'],
                                message_time=msg_data.get('time'),
                                raw_line=msg_data.get('raw_line')
                            )
                            session.add(msg)
                            added_count += 1
                    except Exception as e:
                        continue
        
        return added_count
    
    def get_messages_by_room(self, room_id: int, 
                             start_date: Optional[date] = None,
                             end_date: Optional[date] = None) -> List[Message]:
        """채팅방의 메시지 조회."""
        with self.get_session() as session:
            query = session.query(Message).filter(Message.room_id == room_id)
            if start_date:
                query = query.filter(Message.message_date >= start_date)
            if end_date:
                query = query.filter(Message.message_date <= end_date)
            return query.order_by(Message.message_date, Message.message_time).all()
    
    def get_message_count_by_room(self, room_id: int) -> int:
        """채팅방의 메시지 수 조회."""
        with self.get_session() as session:
            return session.query(func.count(Message.id)).filter(
                Message.room_id == room_id
            ).scalar()
    
    def get_message_count_by_date(self, room_id: int, target_date: date) -> int:
        """특정 날짜의 메시지 수 조회."""
        with self.get_session() as session:
            return session.query(func.count(Message.id)).filter(
                Message.room_id == room_id,
                Message.message_date == target_date
            ).scalar()
    
    def get_unique_senders(self, room_id: int) -> List[str]:
        """채팅방의 참여자 목록 조회."""
        with self.get_session() as session:
            results = session.query(Message.sender).filter(
                Message.room_id == room_id
            ).distinct().all()
            return [r[0] for r in results]
    
    # ==================== Summary 관련 ====================
    
    def add_summary(self, room_id: int, summary_date: date, 
                    summary_type: str, content: str,
                    llm_provider: Optional[str] = None) -> Summary:
        """요약 추가."""
        with self.get_session() as session:
            summary = Summary(
                room_id=room_id,
                summary_date=summary_date,
                summary_type=summary_type,
                content=content,
                llm_provider=llm_provider
            )
            session.add(summary)
            session.flush()
            summary_id = summary.id
        return self.get_summary_by_id(summary_id)
    
    def get_summary_by_id(self, summary_id: int) -> Optional[Summary]:
        """ID로 요약 조회."""
        with self.get_session() as session:
            return session.query(Summary).filter(Summary.id == summary_id).first()
    
    def get_summaries_by_room(self, room_id: int, 
                              summary_type: Optional[str] = None) -> List[Summary]:
        """채팅방의 요약 목록 조회."""
        with self.get_session() as session:
            query = session.query(Summary).filter(Summary.room_id == room_id)
            if summary_type:
                query = query.filter(Summary.summary_type == summary_type)
            return query.order_by(Summary.summary_date.desc()).all()
    
    def delete_summary(self, room_id: int, summary_date: date) -> bool:
        """특정 날짜의 요약 삭제."""
        with self.get_session() as session:
            deleted = session.query(Summary).filter(
                Summary.room_id == room_id,
                Summary.summary_date == summary_date
            ).delete()
            return deleted > 0

    # ==================== SyncLog 관련 ====================
    
    def add_sync_log(self, room_id: int, status: str, 
                     message_count: int = 0, new_message_count: int = 0,
                     error_message: Optional[str] = None) -> SyncLog:
        """동기화 로그 추가."""
        try:
            with self.get_session() as session:
                log = SyncLog(
                    room_id=room_id,
                    status=status,
                    message_count=message_count,
                    new_message_count=new_message_count,
                    error_message=error_message
                )
                session.add(log)
                session.flush()
                log_id = log.id
            return log_id
        except Exception as e:
            # 로깅 실패는 치명적이지 않으므로 무시 (DB 손상 방지)
            print(f"⚠️ [DB Warning] Failed to add sync log: {e}")
            return -1
    
    def get_sync_logs_by_room(self, room_id: int, limit: int = 10) -> List[SyncLog]:
        """채팅방의 동기화 로그 조회."""
        with self.get_session() as session:
            return session.query(SyncLog).filter(
                SyncLog.room_id == room_id
            ).order_by(SyncLog.synced_at.desc()).limit(limit).all()
    
    # ==================== URL 관련 ====================
    
    def add_url(self, room_id: int, url: str, descriptions: List[str] = None,
                source_date: Optional[date] = None) -> URL:
        """URL 추가 또는 업데이트."""
        desc_str = " / ".join(descriptions) if descriptions else ""
        
        with self.get_session() as session:
            existing = session.query(URL).filter(
                URL.room_id == room_id,
                URL.url == url
            ).first()
            
            if existing:
                # 기존 설명에 새 설명 추가
                existing_descs = set(existing.descriptions.split(" / ")) if existing.descriptions else set()
                new_descs = set(descriptions) if descriptions else set()
                merged = existing_descs | new_descs
                merged.discard("")
                existing.descriptions = " / ".join(sorted(merged))
                existing.updated_at = datetime.now()
                url_id = existing.id
            else:
                url_obj = URL(
                    room_id=room_id,
                    url=url,
                    descriptions=desc_str,
                    source_date=source_date
                )
                session.add(url_obj)
                session.flush()
                url_id = url_obj.id
        
        return url_id
    
    def add_urls_batch(self, room_id: int, urls: Dict[str, List[str]]) -> int:
        """URL 일괄 추가."""
        added = 0
        for url, descriptions in urls.items():
            self.add_url(room_id, url, descriptions)
            added += 1
        return added
    
    def get_urls_by_room(self, room_id: int) -> Dict[str, List[str]]:
        """채팅방의 URL 목록 조회."""
        with self.get_session() as session:
            urls_list = session.query(URL).filter(URL.room_id == room_id).all()
            result = {}
            for u in urls_list:
                descs = u.descriptions.split(" / ") if u.descriptions else []
                descs = [d for d in descs if d]  # 빈 문자열 제거
                result[u.url] = descs
            return result
    
    def get_url_count_by_room(self, room_id: int) -> int:
        """채팅방의 URL 수 조회."""
        with self.get_session() as session:
            return session.query(func.count(URL.id)).filter(
                URL.room_id == room_id
            ).scalar()
    
    def clear_urls_by_room(self, room_id: int) -> int:
        """채팅방의 모든 URL 삭제."""
        with self.get_session() as session:
            count = session.query(URL).filter(URL.room_id == room_id).delete()
            return count
    
    # ==================== 통계 관련 ====================
    
    def get_room_stats(self, room_id: int) -> Dict[str, Any]:
        """채팅방 통계 조회."""
        with self.get_session() as session:
            room = session.query(ChatRoom).filter(ChatRoom.id == room_id).first()
            if not room:
                return {}
            
            total_messages = session.query(func.count(Message.id)).filter(
                Message.room_id == room_id
            ).scalar()
            
            unique_senders = session.query(func.count(func.distinct(Message.sender))).filter(
                Message.room_id == room_id
            ).scalar()
            
            date_range = session.query(
                func.min(Message.message_date),
                func.max(Message.message_date)
            ).filter(Message.room_id == room_id).first()
            
            return {
                'room_name': room.name,
                'total_messages': total_messages,
                'unique_senders': unique_senders,
                'first_date': date_range[0] if date_range else None,
                'last_date': date_range[1] if date_range else None,
                'last_sync': room.last_sync_at
            }


# 싱글톤 인스턴스
_db_instance: Optional[Database] = None
_db_path: Optional[str] = None


def get_db(db_path: Optional[str] = None, force_new: bool = False) -> Database:
    """데이터베이스 인스턴스 반환."""
    global _db_instance, _db_path

    if force_new:
        _db_instance = Database(db_path)
        _db_path = _db_instance.db_path
        return _db_instance

    resolved = (
        resolve_chat_db_path(db_path)
        if db_path is None
        else str(Path(db_path).expanduser().resolve())
    )

    if db_path is not None and resolved != _db_path:
        _db_instance = Database(db_path)
        _db_path = _db_instance.db_path
        return _db_instance

    if _db_instance is None:
        _db_instance = Database(db_path)
        _db_path = _db_instance.db_path

    return _db_instance


def reset_db():
    """데이터베이스 인스턴스 리셋."""
    global _db_instance, _db_path
    if _db_instance is not None:
        _db_instance.engine.dispose()
    _db_instance = None
    _db_path = None
