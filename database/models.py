from sqlalchemy import Column, Integer, String, Text, Boolean, BigInteger, ForeignKey, DECIMAL, Float, Date, TIMESTAMP, FetchedValue, Table
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime, timezone
from database.config import Base

# --- BẢNG TRUNG GIAN (Association Tables) ---

video_hashtags = Table(
    "video_hashtags",
    Base.metadata,
    Column("video_id", Integer, ForeignKey("videos.video_id", ondelete="CASCADE"), primary_key=True),
    Column("hashtag_id", Integer, ForeignKey("hashtags.hashtag_id", ondelete="CASCADE"), primary_key=True),
)


# --- MODELS ---
class Role(Base):
    __tablename__ = "roles"

    role_id = Column(Integer, primary_key=True)
    role_name = Column(String(50), unique=True, nullable=False)

    users = relationship("User", back_populates="role")

class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True)

    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(Text, nullable=False)
    full_name = Column(String(100))

    avatar_url = Column(Text)

    role_id = Column(Integer, ForeignKey("roles.role_id"))
    is_active = Column(Boolean, default=True)

    is_email_verified = Column(Boolean, default=False)
    email_verified_at = Column(TIMESTAMP(timezone=True))

    created_at = Column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    updated_at = Column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    last_login = Column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    refresh_token = Column(Text)

    token_expires_at = Column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    role = relationship("Role", back_populates="users")

class EmailOTP(Base):
    __tablename__ = "email_otps"

    otp_id = Column(Integer, primary_key=True)

    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"))
    email = Column(String(100), nullable=False)

    purpose = Column(String(30), nullable=False)
    # verify_email | forgot_password | change_email

    otp_hash = Column(Text, nullable=False)

    expires_at = Column(TIMESTAMP(timezone=True), nullable=False)
    used_at = Column(TIMESTAMP(timezone=True))

    attempts = Column(Integer, default=0)

    created_at = Column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

class TikTokUser(Base):
    __tablename__ = "tiktok_users"
    tiktok_user_id = Column(Integer, primary_key=True)
    unique_id = Column(String(100), unique=True, nullable=False)
    nickname = Column(String(100))
    avatar_url = Column(Text)
    follower_count = Column(BigInteger, default=0)
    bio = Column(Text)
    verified = Column(Boolean, default=False)
    created_at = Column(
        TIMESTAMP(timezone=True), 
        default=lambda: datetime.now(timezone.utc)
    )
    last_updated = Column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    videos = relationship("Video", back_populates="author")

class Video(Base):
    __tablename__ = "videos"
    video_id = Column(Integer, primary_key=True)
    tiktok_video_id = Column(String(50), unique=True, nullable=False)
    tiktok_user_id = Column(Integer, ForeignKey("tiktok_users.tiktok_user_id", ondelete="CASCADE"))
    description = Column(Text)
    video_url = Column(Text)
    cover_url = Column(Text)
    duration_seconds = Column(Integer)
    created_date = Column(TIMESTAMP(timezone=True))

    # Ngày đăng thực tế trên TikTok và phạm vi dữ liệu dùng cho phân tích xu hướng.
    # created_date giữ lại để tương thích code cũ; published_at dùng làm mốc lọc chính.
    published_at = Column(TIMESTAMP(timezone=True))
    published_text = Column(String(50))
    date_confidence = Column(String(20), default="unknown")  # high | medium | unknown
    is_in_scope = Column(Boolean, default=False)
    exclude_reason = Column(String(100))

    collected_date = Column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))
    is_analyzed = Column(Boolean, default=False)
    processing_status = Column(String(30), default='pending')

    author = relationship("TikTokUser", back_populates="videos")
    stats = relationship("VideoStat", back_populates="video")
    analyses = relationship("AIAnalysis", back_populates="video")
    hashtags = relationship("Hashtag", secondary=video_hashtags, back_populates="videos")
    fashion_items = relationship("FashionItem", back_populates="video")

class VideoStat(Base):
    __tablename__ = "video_stats"
    stat_id = Column(Integer, primary_key=True)
    video_id = Column(Integer, ForeignKey("videos.video_id", ondelete="CASCADE"), nullable=False)
    view_count = Column(BigInteger, default=0)
    like_count = Column(BigInteger, default=0)
    comment_count = Column(BigInteger, default=0)
    share_count = Column(BigInteger, default=0)
    
    # Sử dụng FetchedValue() cho cột GENERATED ALWAYS AS ... STORED
    total_engagement = Column(BigInteger, server_default=FetchedValue())
    
    collected_at = Column(
        TIMESTAMP(timezone=True), 
        default=lambda: datetime.now(timezone.utc)
    )
    video = relationship("Video", back_populates="stats")

class Hashtag(Base):
    __tablename__ = "hashtags"
    hashtag_id = Column(Integer, primary_key=True)
    tag_name = Column(String(100), unique=True, nullable=False)
    category = Column(String(50))
    trending_score = Column(Float, default=0)
    video_count = Column(Integer, default=0)
    total_views = Column(BigInteger, default=0)
    first_seen = Column(
        TIMESTAMP(timezone=True), 
        default=lambda: datetime.now(timezone.utc)
    )
    last_seen = Column(
        TIMESTAMP(timezone=True), 
        default=lambda: datetime.now(timezone.utc)
    )

    videos = relationship("Video", secondary=video_hashtags, back_populates="hashtags")

class Comment(Base):
    __tablename__ = "comments"
    comment_id = Column(Integer, primary_key=True) # Khóa chính (Integer)
    video_id = Column(Integer, ForeignKey("videos.video_id", ondelete="CASCADE"), nullable=False)
    content = Column(Text)
    like_count = Column(Integer, default=0)
    created_date = Column(
        TIMESTAMP(timezone=True), 
        default=lambda: datetime.now(timezone.utc)
    )
    collected_date = Column(
        TIMESTAMP(timezone=True), 
        default=lambda: datetime.now(timezone.utc)
    )
    sentiment = Column(String(20))
    commenter_id = Column(String(100))

class AIModel(Base):
    __tablename__ = "ai_models"
    model_id = Column(Integer, primary_key=True)
    model_name = Column(String(100), nullable=False)
    version = Column(String(50), nullable=False)
    accuracy = Column(Float)
    created_at = Column(
        TIMESTAMP(timezone=True), 
        default=lambda: datetime.now(timezone.utc)
    )

class AIAnalysis(Base):
    __tablename__ = "ai_analysis"
    analysis_id = Column(Integer, primary_key=True)
    video_id = Column(Integer, ForeignKey("videos.video_id", ondelete="CASCADE"), nullable=False)
    model_id = Column(Integer, ForeignKey("ai_models.model_id"))
    analysis_type = Column(String(50), nullable=False)
    result_json = Column(JSONB)
    confidence_score = Column(Float)
    processing_time_ms = Column(Integer)
    analyzed_at = Column(
        TIMESTAMP(timezone=True), 
        default=lambda: datetime.now(timezone.utc)
    )
    video = relationship("Video", back_populates="analyses")

class FashionItem(Base):
    __tablename__ = "fashion_items"
    item_id = Column(Integer, primary_key=True)
    video_id = Column(Integer, ForeignKey("videos.video_id", ondelete="CASCADE"), nullable=False)
    item_type = Column(String(50), nullable=False)
    confidence = Column(Float)
    bbox = Column(JSONB)
    detected_at = Column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))
    video = relationship("Video", back_populates="fashion_items")

class Trend(Base):
    __tablename__ = "trends"
    trend_id = Column(Integer, primary_key=True)
    trend_name = Column(String(200), nullable=False)
    trend_category = Column(String(50))
    description = Column(Text)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date)
    confidence_score = Column(Float)
    video_count = Column(Integer, default=0)
    total_views = Column(BigInteger, default=0)
    total_engagement = Column(BigInteger, default=0)
    growth_rate = Column(Float, default=0)
    status = Column(String(20), default='emerging')
    created_at = Column(
        TIMESTAMP(timezone=True), 
        default=lambda: datetime.now(timezone.utc)
    )
class TrendHistory(Base):
    __tablename__ = 'trend_history'
 
    history_id = Column(Integer, primary_key=True)

    hashtag_id = Column(
        Integer,
        ForeignKey('hashtags.hashtag_id', ondelete="CASCADE"),
        nullable=False
    )
 
    date = Column(
        Date,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).date()
    )
 
    view_count = Column(BigInteger, default=0)
    like_count = Column(BigInteger, default=0)
    comment_count = Column(BigInteger, default=0)
    share_count = Column(BigInteger, default=0)
    video_count = Column(Integer, default=0)
    engagement_rate = Column(Float, default=0)

    # thêm các field phục vụ LSTM/growth
    view_growth = Column(Float, default=0)
    like_growth = Column(Float, default=0)
    engagement_growth = Column(Float, default=0)
    trend_score = Column(Float, default=0)

    is_imputed = Column(Boolean, default=False)
    imputation_method = Column(String(100))
    data_quality_score = Column(Float, default=1.0)

    hashtag = relationship("Hashtag")

class Prediction(Base):
    __tablename__ = "predictions"
    prediction_id = Column(Integer, primary_key=True)
    trend_id = Column(Integer, ForeignKey("trends.trend_id"))
    hashtag_id = Column(Integer, ForeignKey("hashtags.hashtag_id"))
    prediction_type = Column(String(50), nullable=False)
    prediction_date = Column(Date, nullable=False)
    predicted_for_date = Column(Date)
    predicted_value = Column(Float)
    actual_value = Column(Float)
    accuracy_score = Column(Float)
    model_version = Column(String(50))
    created_at = Column(
        TIMESTAMP(timezone=True), 
        default=lambda: datetime.now(timezone.utc)
    )

class CrawlerJob(Base):
    __tablename__ = "crawler_jobs"
    job_id = Column(Integer, primary_key=True)
    job_name = Column(String(100))
    job_type = Column(String(50))
    parameters = Column(JSONB)
    status = Column(String(20), default='pending')
    videos_collected = Column(Integer, default=0)
    started_at = Column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at = Column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))
    error_message = Column(Text)
    created_by = Column(Integer, ForeignKey("users.user_id"))
    created_at = Column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))

class AdminTask(Base):
    __tablename__ = "admin_tasks"

    task_id = Column(Integer, primary_key=True)
    task_type = Column(String(100), nullable=False)
    title = Column(String(200), nullable=False)

    status = Column(String(30), default="pending")
    # pending | running | completed | failed

    parameters = Column(JSONB)
    result = Column(JSONB)
    logs = Column(JSONB)

    error_message = Column(Text)

    started_at = Column(TIMESTAMP(timezone=True))
    completed_at = Column(TIMESTAMP(timezone=True))

    created_at = Column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )