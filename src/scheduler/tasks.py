"""동기화 스케줄러 및 태스크 정의."""
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable, List
from apscheduler.schedulers.qt import QtScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)


class SyncScheduler:
    """APScheduler 기반 동기화 스케줄러."""
    
    def __init__(self):
        self.scheduler = QtScheduler()
        self._sync_callback: Optional[Callable] = None
        self._summary_callback: Optional[Callable] = None
        self._is_running = False
    
    def set_sync_callback(self, callback: Callable):
        """동기화 콜백 설정."""
        self._sync_callback = callback
    
    def set_summary_callback(self, callback: Callable):
        """요약 생성 콜백 설정."""
        self._summary_callback = callback
    
    def start(self):
        """스케줄러 시작."""
        if not self._is_running:
            self.scheduler.start()
            self._is_running = True
            logger.info("Scheduler started")
    
    def stop(self):
        """스케줄러 중지."""
        if self._is_running:
            self.scheduler.shutdown()
            self._is_running = False
            logger.info("Scheduler stopped")
    
    def add_sync_job(self, interval_minutes: int = 30, job_id: str = "sync_all"):
        """동기화 작업 추가."""
        if self._sync_callback is None:
            logger.warning("Sync callback not set")
            return
        
        # 기존 작업 제거
        self.remove_job(job_id)
        
        # 새 작업 추가
        self.scheduler.add_job(
            self._sync_callback,
            trigger=IntervalTrigger(minutes=interval_minutes),
            id=job_id,
            name="Auto Sync All Rooms",
            replace_existing=True
        )
        logger.info(f"Sync job added: every {interval_minutes} minutes")
    
    def add_summary_job(self, interval_hours: int = 24, job_id: str = "summary_daily"):
        """요약 생성 작업 추가."""
        if self._summary_callback is None:
            logger.warning("Summary callback not set")
            return
        
        # 기존 작업 제거
        self.remove_job(job_id)
        
        # 새 작업 추가
        self.scheduler.add_job(
            self._summary_callback,
            trigger=IntervalTrigger(hours=interval_hours),
            id=job_id,
            name="Auto Generate Summary",
            replace_existing=True
        )
        logger.info(f"Summary job added: every {interval_hours} hours")
    
    def remove_job(self, job_id: str):
        """작업 제거."""
        try:
            self.scheduler.remove_job(job_id)
            logger.info(f"Job removed: {job_id}")
        except Exception:
            pass  # 작업이 없으면 무시
    
    def get_jobs(self) -> List[dict]:
        """현재 등록된 작업 목록."""
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                'id': job.id,
                'name': job.name,
                'next_run': job.next_run_time
            })
        return jobs
    
    @property
    def is_running(self) -> bool:
        return self._is_running


def sync_room_from_file(file_path: Path, room_id: int, db) -> dict:
    """파일에서 채팅방 데이터 동기화."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from parser import KakaoLogParser
    
    result = {
        'success': False,
        'message_count': 0,
        'new_count': 0,
        'error': None
    }
    
    try:
        parser = KakaoLogParser()
        parse_result = parser.parse(file_path)
        
        messages = []
        for date_str, msg_list in parse_result.messages_by_date.items():
            for msg in msg_list:
                # 메시지 파싱 (간단한 구현)
                # TODO: 실제 파서의 상세 메시지 파싱 결과 활용
                messages.append({
                    'sender': 'Unknown',
                    'content': msg,
                    'date': datetime.strptime(date_str, '%Y-%m-%d').date(),
                    'time': None,
                    'raw_line': msg
                })
        
        result['message_count'] = len(messages)
        
        # DB에 저장
        if db:
            new_count = db.add_messages(room_id, messages)
            result['new_count'] = new_count
            db.update_room_sync_time(room_id)
            db.add_sync_log(
                room_id, 'success',
                message_count=result['message_count'],
                new_message_count=result['new_count']
            )
        
        result['success'] = True
        
    except Exception as e:
        result['error'] = str(e)
        logger.error(f"Sync failed: {e}")
        if db:
            db.add_sync_log(room_id, 'failed', error_message=str(e))
    
    return result
