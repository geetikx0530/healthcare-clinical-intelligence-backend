from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Text, Float, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.connection import Base


class MedicalEntity(Base):
    __tablename__ = "medical_entities"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    medical_record_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("medical_records.id", ondelete="SET NULL"), nullable=True, index=True
    )
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_text: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    patient: Mapped["Patient"] = relationship("Patient", back_populates="entities")
    record: Mapped[Optional["MedicalRecord"]] = relationship("MedicalRecord", back_populates="entities")
