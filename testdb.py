from database.config import SessionLocal
from database.models import Video

db = SessionLocal()
video = db.query(Video).first()
if video:
    # In ra tất cả các thuộc tính của object Video
    print("Cấu trúc các cột hiện có:")
    print(video.__dict__.keys())
db.close()