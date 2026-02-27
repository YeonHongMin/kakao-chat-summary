"""
import_to_db.py - 기존 카카오톡 파일들을 DB에 일괄 저장

사용법:
    python import_to_db.py                    # data 폴더 전체
    python import_to_db.py <filepath>         # 단일 파일
    python import_to_db.py --stats            # DB 통계 확인
    python import_to_db.py --clean            # 중복 제거 및 최적화
"""

import sys
import io
import re
from pathlib import Path

# Windows 콘솔 인코딩 문제 해결
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
from datetime import datetime, date, time as dt_time
from typing import Optional, List, Dict, Any
from collections import defaultdict

# 프로젝트 모듈 경로 추가
sys.path.insert(0, str(Path(__file__).parent))

from parser import KakaoLogParser
from db import get_db, reset_db, ChatRoom, Message, Summary


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
        
        msg_time = dt_time(hour, minute)
        
        return {
            'sender': sender,
            'content': content,
            'date': msg_date,
            'time': msg_time,
            'raw_line': line
        }


class DataImporter:
    """데이터 일괄 가져오기 클래스."""
    
    def __init__(self):
        self.db = get_db()
        self.parser = KakaoLogParser()
    
    def import_file(self, filepath: Path, room_name: Optional[str] = None) -> Dict[str, Any]:
        """단일 파일을 DB에 저장."""
        result = {
            'file': filepath.name,
            'room_name': None,
            'total_messages': 0,
            'new_messages': 0,
            'duplicates': 0,
            'dates': [],
            'success': False,
            'error': None
        }
        
        try:
            # 1. 채팅방 이름 추출
            if room_name is None:
                room_name = self._extract_room_name(filepath)
            result['room_name'] = room_name
            
            # 2. 채팅방 조회/생성
            room = self.db.get_room_by_name(room_name)
            if room is None:
                room = self.db.create_room(room_name, str(filepath))
                print(f"  📁 새 채팅방 생성: {room_name}")
            else:
                print(f"  📁 기존 채팅방 사용: {room_name}")
            
            # 3. 파일 파싱
            parse_result = self.parser.parse(filepath)
            result['dates'] = sorted(parse_result.messages_by_date.keys())
            
            # 4. 일별로 메시지 저장
            for date_str, lines in parse_result.messages_by_date.items():
                msg_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                messages = []
                
                for line in lines:
                    parsed = MessageParser.parse_message(line, msg_date)
                    if parsed:
                        messages.append(parsed)
                
                if messages:
                    result['total_messages'] += len(messages)
                    new_count = self.db.add_messages(room.id, messages)
                    result['new_messages'] += new_count
                    result['duplicates'] += len(messages) - new_count
            
            # 5. 동기화 시간 업데이트
            self.db.update_room_sync_time(room.id)
            self.db.add_sync_log(
                room.id, 'success',
                message_count=result['total_messages'],
                new_message_count=result['new_messages']
            )
            
            result['success'] = True
            
        except Exception as e:
            result['error'] = str(e)
            print(f"  ❌ 오류: {e}")
        
        return result
    
    def import_directory(self, directory: Path) -> List[Dict[str, Any]]:
        """디렉토리 내 모든 txt 파일을 DB에 저장."""
        results = []
        
        # txt, csv 파일 필터링 (요약 파일 제외)
        chat_files = [
            f for f in directory.iterdir()
            if f.is_file() and f.suffix.lower() in ['.txt', '.csv']
            and "_summary" not in f.name 
            and "_url" not in f.name
            and "_summaries" not in f.name
        ]
        
        if not chat_files:
            print("❌ 처리할 파일이 없습니다.")
            return results
        
        print("="*60)
        print("📥 데이터 일괄 가져오기")
        print("="*60)
        print(f"📂 디렉토리: {directory}")
        print(f"📄 파일 수: {len(chat_files)}개")
        print("="*60 + "\n")
        
        for filepath in sorted(chat_files):
            print(f"📄 처리 중: {filepath.name}")
            result = self.import_file(filepath)
            results.append(result)
            
            if result['success']:
                print(f"  ✅ 완료: {result['new_messages']:,}개 새 메시지 / {result['duplicates']:,}개 중복")
                print(f"  📅 기간: {result['dates'][0]} ~ {result['dates'][-1]}" if result['dates'] else "")
            print()
        
        return results
    
    def show_stats(self):
        """DB 통계 출력."""
        print("="*60)
        print("📊 데이터베이스 통계")
        print("="*60)
        
        rooms = self.db.get_all_rooms()
        
        if not rooms:
            print("📭 저장된 채팅방이 없습니다.")
            return
        
        total_messages = 0
        
        for room in rooms:
            stats = self.db.get_room_stats(room.id)
            msg_count = stats.get('total_messages', 0)
            total_messages += msg_count
            
            print(f"\n📁 {room.name}")
            print(f"   💬 메시지: {msg_count:,}개")
            print(f"   👥 참여자: {stats.get('unique_senders', 0)}명")
            if stats.get('first_date') and stats.get('last_date'):
                print(f"   📅 기간: {stats['first_date']} ~ {stats['last_date']}")
            if room.last_sync_at:
                print(f"   🔄 마지막 동기화: {room.last_sync_at.strftime('%Y-%m-%d %H:%M:%S')}")
        
        print("\n" + "-"*60)
        print(f"📊 총계: {len(rooms)}개 채팅방, {total_messages:,}개 메시지")
    
    def show_daily_stats(self, room_name: Optional[str] = None):
        """일별 메시지 통계 출력."""
        print("="*60)
        print("📅 일별 메시지 통계")
        print("="*60)
        
        rooms = self.db.get_all_rooms()
        
        if room_name:
            rooms = [r for r in rooms if r.name == room_name]
        
        for room in rooms:
            print(f"\n📁 {room.name}")
            print("-"*40)
            
            # 일별 통계 쿼리
            with self.db.get_session() as session:
                from sqlalchemy import func
                daily_stats = session.query(
                    Message.message_date,
                    func.count(Message.id).label('count'),
                    func.count(func.distinct(Message.sender)).label('senders')
                ).filter(
                    Message.room_id == room.id
                ).group_by(
                    Message.message_date
                ).order_by(
                    Message.message_date.desc()
                ).limit(30).all()
            
            if not daily_stats:
                print("   (데이터 없음)")
                continue
            
            print(f"{'날짜':<12} {'메시지':<10} {'참여자':<8}")
            print("-"*40)
            for stat in daily_stats:
                print(f"{stat.message_date}   {stat.count:>6,}개    {stat.senders:>4}명")
    
    def _extract_room_name(self, filepath: Path) -> str:
        """파일명에서 채팅방 이름 추출."""
        name = filepath.stem
        # 코드팩터리_KakaoTalk_20260131... 형식
        if "_KakaoTalk_" in name:
            return name.split("_KakaoTalk_")[0]
        elif "KakaoTalk_" in name:
            return "카카오톡 대화"
        return name


def main():
    """메인 함수."""
    importer = DataImporter()
    
    args = sys.argv[1:]
    
    # 통계 모드
    if "--stats" in args:
        importer.show_stats()
        return
    
    # 일별 통계 모드
    if "--daily" in args:
        room_name = None
        if len(args) > 1 and not args[1].startswith("--"):
            room_name = args[1]
        importer.show_daily_stats(room_name)
        return
    
    # 경로 지정
    if args and not args[0].startswith("--"):
        target = Path(args[0]).resolve()
    else:
        # 기본: data 디렉토리
        target = Path(__file__).parent.parent / "data"
    
    if target.is_file():
        print(f"📄 단일 파일 처리: {target.name}")
        result = importer.import_file(target)
        if result['success']:
            print(f"✅ 완료: {result['new_messages']:,}개 새 메시지")
        else:
            print(f"❌ 실패: {result['error']}")
    elif target.is_dir():
        results = importer.import_directory(target)
        
        # 요약 출력
        print("="*60)
        print("📋 처리 결과")
        print("="*60)
        
        success_count = sum(1 for r in results if r['success'])
        total_new = sum(r['new_messages'] for r in results)
        total_dup = sum(r['duplicates'] for r in results)
        
        print(f"✅ 성공: {success_count}/{len(results)}개 파일")
        print(f"💬 새 메시지: {total_new:,}개")
        print(f"🔄 중복 제거: {total_dup:,}개")
        
        # DB 통계 출력
        print()
        importer.show_stats()
    else:
        print(f"❌ 유효하지 않은 경로: {target}")


if __name__ == "__main__":
    main()
