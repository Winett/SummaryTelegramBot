from sqlalchemy import Column, Integer, String, BigInteger, Boolean, DateTime, ForeignKey, Text, Index, \
    UniqueConstraint, text, Float
from sqlalchemy.orm import relationship

from .database import Base
from .enums import AdminRole
from app.utils.utils import utc_now

class Chat(Base):
    __tablename__ = "chats"
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    title = Column(String, nullable=False)
    language = Column(String, default="ru")
    is_active = Column(Boolean, nullable=False, default=False)
    is_approved = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    to_send_summary = Column(Boolean, nullable=False, default=False, server_default=text("false"))

    messages = relationship("Message", back_populates="chat", cascade="all, delete-orphan")
    summaries = relationship("Summary", back_populates="chat", cascade="all, delete-orphan")

    @property
    def chat_info(self) -> str:
        return (f"Название чата: {self.title}\n"
                f"Активный: {'✅' if self.is_active else '❌'}\n"
                f"Подтверждённый: {'✅' if self.is_approved else '❌'}\n"
                f"Для отсылки саммари: {'✅' if self.to_send_summary else '❌'}\n")



class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    full_name = Column(String(255), nullable=True)
    is_bot = Column(Boolean, default=False)

    messages = relationship("Message", back_populates="user")

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, ForeignKey("chats.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    telegram_message_id = Column(BigInteger, nullable=True)
    text = Column(Text, nullable=True)

    sent_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    created_at = Column(DateTime(timezone=True), default=utc_now, index=True)

    chat = relationship("Chat", back_populates="messages")
    user = relationship("User", back_populates="messages")

    __table_args__ = (
        Index('ix_messages_chat_created', 'chat_id', 'sent_at'),
    )

    @property
    def message_to_llm(self) -> str:
        return f"[{self.sent_at}] (tg_id:{self.user.telegram_id}) (msg_id:{self.telegram_message_id}): {self.text.strip()}"


class Summary(Base):
    __tablename__ = "summaries"

    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, ForeignKey("chats.id", ondelete="CASCADE"), nullable=False)
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    content = Column(Text, nullable=False) # html content
    model_used = Column(String(50), nullable=True)

    created_at = Column(DateTime(timezone=True), default=utc_now)

    chat = relationship("Chat", back_populates="summaries")

    __table_args__ = (
        UniqueConstraint('chat_id', 'period_start', 'period_end', name='uq_chat_period'),
    )


class Admin(Base):
    __tablename__ = "admins"
    id = Column(Integer, primary_key=True)

    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    full_name = Column(String(255), nullable=True)

    role = Column(String(20), default=AdminRole.ADMIN, nullable=False)

    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    __table_args__ = (
        UniqueConstraint('telegram_id', name='uq_admin_telegram_id'),
    )

class ModelSettings(Base):
    __tablename__ = "model_settings"
    id = Column(Integer, primary_key=True)
    llm_id = Column(String(255), nullable=True)
    name = Column(String(255), nullable=True)
    context_length = Column(Integer, nullable=True)
    price_competition = Column(Float, nullable=True)
    promt = Column(Text, nullable=True)