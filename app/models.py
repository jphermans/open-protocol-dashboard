"""SQLAlchemy ORM models for the maintenance / tool-data log.

The schema merges two worlds:

* **Work-order columns** sourced from the 'TMC Herstellingen ASML'
  XLSX template (executor, status, SAP order, SAP status options,
  work date, start time, end time).

* **Open Protocol columns** from MID 0040 (tool data) and MID 0060 (last
  tightening result), used when the controller pull auto-fills a row.

Single table, single natural-key uniqueness rule: one row per
(sap_order, work_date, tool_serial, tightening_id). tightening_id is
nullable because manual entries do not always have one.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Column, Integer, String, Date, DateTime, Float, Text, Index,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MaintenanceLog(Base):
    """One work session by a technician, optionally tied to a tightening."""

    __tablename__ = "maintenance_log"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # ---- Audit ----------------------------------------------------------
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow,
                        onupdate=_utcnow, nullable=False)
    source     = Column(String(16),  default="manual")  # 'manual' / 'controller'
    notes      = Column(Text,        nullable=True)

    # ---- XLSX-derived work-order columns ------------------------------
    executor            = Column(String(64),  nullable=True)
    status              = Column(String(32),  nullable=True)
    sap_order           = Column(String(32),  nullable=True)
    sap_status_options  = Column(String(64),  nullable=True)
    work_date           = Column(Date,        nullable=True)
    start_time          = Column(String(8),   nullable=True)   # HH:MM:SS
    end_time            = Column(String(8),   nullable=True)   # HH:MM:SS

    # ---- Open Protocol MID 0040 ----------------------------------------
    tool_serial             = Column(String(32),  nullable=True)
    tool_type               = Column(String(32),  nullable=True)
    controller_serial       = Column(String(32),  nullable=True)
    total_tightenings       = Column(Integer,     nullable=True)
    tightenings_since_svc   = Column(Integer,     nullable=True)
    last_calibration_date   = Column(String(16),  nullable=True)
    last_service_date       = Column(String(16),  nullable=True)
    calibration_value       = Column(String(16),  nullable=True)
    firmware                = Column(String(32),  nullable=True)

    # ---- Open Protocol MID 0060 (last tightening result) --------------
    tightening_id       = Column(String(32),  nullable=True)
    tightening_status   = Column(String(16),  nullable=True)   # OK / NOK / ...
    torque_status       = Column(String(16),  nullable=True)
    angle_status        = Column(String(16),  nullable=True)
    torque_value        = Column(Float,       nullable=True)
    torque_min          = Column(Float,       nullable=True)
    torque_target       = Column(Float,       nullable=True)
    torque_max          = Column(Float,       nullable=True)
    angle_value         = Column(Float,       nullable=True)
    angle_min           = Column(Float,       nullable=True)
    angle_target        = Column(Float,       nullable=True)
    angle_max           = Column(Float,       nullable=True)
    cell_id             = Column(String(16),  nullable=True)
    job_number          = Column(String(16),  nullable=True)
    batch_status        = Column(String(8),   nullable=True)
    batch_counter       = Column(Integer,     nullable=True)
    tightening_time     = Column(String(32),  nullable=True)   # raw time_stamp from MID 0060

    # ---- Open Protocol MID 0080 (controller / adapter) -----------------
    protocol_version    = Column(String(16),  nullable=True)   # e.g. '5.1.0'
    controller_ip       = Column(String(45),  nullable=True)   # ipv4 / ipv6
    controller_port     = Column(Integer,     nullable=True)

    # ---- Debug ----------------------------------------------------------
    raw_response = Column(Text, nullable=True)                  # last MID 0040 frame

    # ---- Constraints / indexes -----------------------------------------
    __table_args__ = (
        # Dedup: same SAP order + day + tool + tightening ID = no new row.
        UniqueConstraint(
            'sap_order', 'work_date', 'tool_serial', 'tightening_id',
            name='uq_log_natural_key',
        ),
        Index('ix_log_executor',  'executor'),
        Index('ix_log_status',    'status'),
        Index('ix_log_sap_order', 'sap_order'),
        Index('ix_log_work_date', 'work_date'),
        Index('ix_log_tool',      'tool_serial'),
    )

    # ---- Display helpers ------------------------------------------------
    def as_display_dict(self) -> dict:
        """Return the row in human-friendly display order."""
        return {
            'id'                    : self.id,
            'work_date'             : self.work_date.isoformat() if self.work_date else '',
            'executor'              : self.executor or '',
            'status'                : self.status or '',
            'sap_order'             : self.sap_order or '',
            'sap_status_options'    : self.sap_status_options or '',
            'start_time'            : self.start_time or '',
            'end_time'              : self.end_time or '',
            'tool_serial'           : self.tool_serial or '',
            'tool_type'             : self.tool_type or '',
            'controller_serial'     : self.controller_serial or '',
            'firmware'              : self.firmware or '',
            'total_tightenings'     : self.total_tightenings if self.total_tightenings is not None else 0,
            'tightenings_since_svc' : self.tightenings_since_svc if self.tightenings_since_svc is not None else 0,
            'calibration_value'     : self.calibration_value or '',
            'last_calibration_date' : self.last_calibration_date or '',
            'last_service_date'     : self.last_service_date or '',
            'tightening_id'         : self.tightening_id or '',
            'tightening_status'     : self.tightening_status or '',
            'torque_value'          : self.torque_value,
            'angle_value'           : self.angle_value,
            'job_number'            : self.job_number or '',
            'cell_id'               : self.cell_id or '',
            'protocol_version'      : self.protocol_version or '',
            'notes'                 : self.notes or '',
            'source'                : self.source or '',
            'created_at'            : self.created_at.isoformat(timespec='seconds') if self.created_at else '',
            'updated_at'            : self.updated_at.isoformat(timespec='seconds') if self.updated_at else '',
        }

    def __repr__(self) -> str:
        return (f"<MaintenanceLog id={self.id} sap={self.sap_order!r} "
                f"executor={self.executor!r} date={self.work_date} "
                f"tool={self.tool_serial!r}>")
