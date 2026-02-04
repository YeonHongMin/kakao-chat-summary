
import sys
import os
from pathlib import Path
from datetime import datetime

# 프로젝트 경로 설정
sys.path.insert(0, str(Path(__file__).parent))

from db import get_db, ChatRoom, Message
from ui.main_window import MessageParser # Reuse message parsing logic

def recover():
    print("🔄 DB 복구 시작 (from data/original)...")
    
    base_dir = Path(__file__).parent.parent / "data" / "original"
    print(f"📂 Base Dir: {base_dir.resolve()}")
    if not base_dir.exists():
        print("❌ data/original 디렉토리가 없습니다.")
        return

    db = get_db()
    
    # 1. 채팅방 디렉토리 순회
    print("🔍 디렉토리 스캔 중...")
    for room_dir in base_dir.iterdir():
        print(f"  - Found: {room_dir.name} (IsDir: {room_dir.is_dir()})")
        if not room_dir.is_dir():
            continue
            
        room_name = room_dir.name
        print(f"\n📁 채팅방 발견: {room_name}")
        
        # Room 생성/조회
        room = db.get_room_by_name(room_name)
        if not room:
            room = db.create_room(room_name, f"Recovered from {room_name}")
            print(f"  ✨ 채팅방 생성 완료: ID {room.id}")
        else:
            print(f"  ℹ️  기존 채팅방 ID {room.id}")

        # 2. 날짜별 파일 순회
        md_files = sorted(list(room_dir.glob("*_full.md")))
        total_files = len(md_files)
        print(f"  📄 파일 {total_files}개 처리 중...")
        
        total_msgs = 0
        new_msgs = 0
        
        for md_file in md_files:
            # 파일명에서 날짜 추출 (Format: Name_YYYYMMDD_full.md)
            # 안전하게 파싱하기 위해 정규식 사용 권장되지만, 여기선 split 등 활용
            try:
                date_part = md_file.name.split('_')[-2] # YYYYMMDD
                date_str = f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:8]}"
                msg_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except Exception:
                print(f"  ⚠️  파일명 날짜 파싱 실패: {md_file.name}")
                continue

            # 파일 읽기
            content = md_file.read_text(encoding='utf-8')
            lines = content.split('\n')
            
            # 헤더 스킵 (--- 나올 때까지)
            body_lines = []
            header_passed = False
            for line in lines:
                if not header_passed:
                    if line.strip() == '---':
                        header_passed = True
                    continue
                
                # 푸터 스킵
                if line.strip().startswith('_Generated'):
                    break
                
                if line.strip():
                    body_lines.append(line)
            
            # 메시지 파싱
            messages = []
            for line in body_lines:
                parsed = MessageParser.parse_message(line, msg_date)
                if parsed:
                    messages.append(parsed)
            
            # DB 저장
            if messages:
                count = db.add_messages(room.id, messages)
                total_msgs += len(messages)
                new_msgs += count
        
        print(f"  ✅ 복구 완료: {total_msgs}개 메시지 로드됨 (DB 저장: {new_msgs})")
        
        # Sync Log 업데이트
        db.update_room_sync_time(room.id)
        db.add_sync_log(room.id, 'recovery', message_count=total_msgs, new_message_count=new_msgs)

    print("\n🎉 모든 복구 작업 완료!")

if __name__ == "__main__":
    recover()
