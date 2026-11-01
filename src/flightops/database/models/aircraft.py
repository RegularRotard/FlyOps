from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from flightops.database.base import Base, TimestampMixin, UUIDMixin


class Manufacturer(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "manufacturers"

    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)

    families: Mapped[list["AircraftFamily"]] = relationship(
        back_populates="manufacturer"
    )


class AircraftFamily(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "aircraft_families"

    manufacturer_id: Mapped[str] = mapped_column(
        ForeignKey("manufacturers.id"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    manufacturer: Mapped["Manufacturer"] = relationship(
        back_populates="families"
    )
    variants: Mapped[list["AircraftVariant"]] = relationship(
        back_populates="family"
    )

    __table_args__ = (
        UniqueConstraint("manufacturer_id", "name"),
    )


class AircraftVariant(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "aircraft_variants"

    family_id: Mapped[str] = mapped_column(
        ForeignKey("aircraft_families.id"),
        nullable=False,
    )
    designation: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    current_revision_id: Mapped[str | None] = mapped_column(
        ForeignKey("aircraft_variant_revisions.id"),
        nullable=True,
    )

    family: Mapped["AircraftFamily"] = relationship(
        back_populates="variants"
    )
    revisions: Mapped[list["AircraftVariantRevision"]] = relationship(
        back_populates="variant",
        foreign_keys="AircraftVariantRevision.variant_id",
        order_by="AircraftVariantRevision.revision_number",
    )
    current_revision: Mapped["AircraftVariantRevision | None"] = relationship(
        foreign_keys=[current_revision_id],
        post_update=True,
    )
    aircraft: Mapped[list["AircraftProfile"]] = relationship(
        back_populates="variant"
    )

    __table_args__ = (
        UniqueConstraint("family_id", "designation"),
    )


class AircraftVariantRevision(UUIDMixin, Base):
    __tablename__ = "aircraft_variant_revisions"

    variant_id: Mapped[str] = mapped_column(
        ForeignKey("aircraft_variants.id"),
        nullable=False,
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_revision_id: Mapped[str | None] = mapped_column(
        ForeignKey("aircraft_variant_revisions.id"),
        nullable=True,
    )
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    change_description: Mapped[str] = mapped_column(Text, nullable=False)
    changed_by: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    variant: Mapped["AircraftVariant"] = relationship(
        back_populates="revisions",
        foreign_keys=[variant_id],
    )
    changes: Mapped[list["AircraftVariantRevisionChange"]] = relationship(
        back_populates="revision",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("variant_id", "revision_number"),
    )


class AircraftVariantRevisionChange(UUIDMixin, Base):
    __tablename__ = "aircraft_variant_revision_changes"

    revision_id: Mapped[str] = mapped_column(
        ForeignKey("aircraft_variant_revisions.id"),
        nullable=False,
    )
    field_path: Mapped[str] = mapped_column(String(255), nullable=False)
    old_value: Mapped[Any | None] = mapped_column(JSON)
    new_value: Mapped[Any | None] = mapped_column(JSON)

    revision: Mapped["AircraftVariantRevision"] = relationship(
        back_populates="changes"
    )


class AircraftProfile(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "aircraft_profiles"

    variant_id: Mapped[str] = mapped_column(
        ForeignKey("aircraft_variants.id"),
        nullable=False,
    )
    registration: Mapped[str] = mapped_column(
        String(30),
        unique=True,
        nullable=False,
    )
    serial_number: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
    )
    nickname: Mapped[str | None] = mapped_column(String(100))
    engine_configuration: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    equipment_configuration: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    modification_configuration: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    current_revision_id: Mapped[str | None] = mapped_column(
        ForeignKey("aircraft_profile_revisions.id"),
        nullable=True,
    )

    variant: Mapped["AircraftVariant"] = relationship(
        back_populates="aircraft"
    )
    revisions: Mapped[list["AircraftProfileRevision"]] = relationship(
        back_populates="profile",
        foreign_keys="AircraftProfileRevision.profile_id",
        order_by="AircraftProfileRevision.revision_number",
    )
    current_revision: Mapped["AircraftProfileRevision | None"] = relationship(
        foreign_keys=[current_revision_id],
        post_update=True,
    )
    documents: Mapped[list["AircraftDocument"]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
    )


class AircraftProfileRevision(UUIDMixin, Base):
    __tablename__ = "aircraft_profile_revisions"

    profile_id: Mapped[str] = mapped_column(
        ForeignKey("aircraft_profiles.id"),
        nullable=False,
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_revision_id: Mapped[str | None] = mapped_column(
        ForeignKey("aircraft_profile_revisions.id"),
        nullable=True,
    )
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    change_description: Mapped[str] = mapped_column(Text, nullable=False)
    changed_by: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    profile: Mapped["AircraftProfile"] = relationship(
        back_populates="revisions",
        foreign_keys=[profile_id],
    )
    changes: Mapped[list["AircraftRevisionChange"]] = relationship(
        back_populates="revision",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("profile_id", "revision_number"),
    )


class AircraftRevisionChange(UUIDMixin, Base):
    __tablename__ = "aircraft_revision_changes"

    revision_id: Mapped[str] = mapped_column(
        ForeignKey("aircraft_profile_revisions.id"),
        nullable=False,
    )
    field_path: Mapped[str] = mapped_column(String(255), nullable=False)
    old_value: Mapped[Any | None] = mapped_column(JSON)
    new_value: Mapped[Any | None] = mapped_column(JSON)

    revision: Mapped["AircraftProfileRevision"] = relationship(
        back_populates="changes"
    )


class AircraftDocument(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "aircraft_documents"

    profile_id: Mapped[str | None] = mapped_column(
        ForeignKey("aircraft_profiles.id"),
        nullable=True,
    )
    variant_id: Mapped[str | None] = mapped_column(
        ForeignKey("aircraft_variants.id"),
        nullable=True,
    )

    document_type: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    sha256_checksum: Mapped[str | None] = mapped_column(String(64))
    document_reference: Mapped[str | None] = mapped_column(String(120))
    revision_reference: Mapped[str | None] = mapped_column(String(80))
    effective_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)

    profile: Mapped["AircraftProfile | None"] = relationship(
        back_populates="documents"
    )

    __table_args__ = (
    CheckConstraint(
        """
        (profile_id IS NOT NULL AND variant_id IS NULL)
        OR
        (profile_id IS NULL AND variant_id IS NOT NULL)
        """,
        name="ck_aircraft_document_single_owner",
    ),
)
