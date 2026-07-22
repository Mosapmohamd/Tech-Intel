"""Domain enumerations shared across the pipeline."""

from __future__ import annotations

from enum import StrEnum


class CategorySlug(StrEnum):
    """The fixed taxonomy used by the Classification Agent."""

    AI = "ai"
    PROGRAMMING = "programming"
    CYBERSECURITY = "cybersecurity"
    CLOUD = "cloud"
    DEVOPS = "devops"
    OPEN_SOURCE = "open-source"
    DATABASES = "databases"
    WEB_DEVELOPMENT = "web-development"
    MOBILE = "mobile"
    HARDWARE = "hardware"
    BIG_TECH = "big-tech"
    STARTUPS = "startups"
    RESEARCH = "research"
    CRYPTO = "crypto"
    OTHER = "other"


#: Display names for each category (English, Arabic).
CATEGORY_LABELS: dict[CategorySlug, tuple[str, str]] = {
    CategorySlug.AI: ("AI", "الذكاء الاصطناعي"),
    CategorySlug.PROGRAMMING: ("Programming", "البرمجة"),
    CategorySlug.CYBERSECURITY: ("Cybersecurity", "الأمن السيبراني"),
    CategorySlug.CLOUD: ("Cloud", "الحوسبة السحابية"),
    CategorySlug.DEVOPS: ("DevOps", "هندسة التشغيل"),
    CategorySlug.OPEN_SOURCE: ("Open Source", "المصادر المفتوحة"),
    CategorySlug.DATABASES: ("Databases", "قواعد البيانات"),
    CategorySlug.WEB_DEVELOPMENT: ("Web Development", "تطوير الويب"),
    CategorySlug.MOBILE: ("Mobile", "تطبيقات الموبايل"),
    CategorySlug.HARDWARE: ("Hardware", "العتاد"),
    CategorySlug.BIG_TECH: ("Big Tech", "شركات التقنية الكبرى"),
    CategorySlug.STARTUPS: ("Startups", "الشركات الناشئة"),
    CategorySlug.RESEARCH: ("Research", "الأبحاث"),
    CategorySlug.CRYPTO: ("Crypto", "العملات الرقمية"),
    CategorySlug.OTHER: ("Other", "أخرى"),
}


class ArticleStatus(StrEnum):
    """Lifecycle of an article as it moves through the daily pipeline."""

    COLLECTED = "collected"
    EXTRACTED = "extracted"
    DUPLICATE = "duplicate"
    SCORED = "scored"
    ANALYZED = "analyzed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ReportSection(StrEnum):
    """Where an article appears inside a weekly report."""

    TOP_STORY = "top_story"
    WORTH_WATCHING = "worth_watching"
    PROFESSIONAL_PICK = "professional_pick"


class ReportStatus(StrEnum):
    """Lifecycle of a weekly report."""

    DRAFT = "draft"
    GENERATED = "generated"
    SENT = "sent"
    FAILED = "failed"


class DeliveryStatus(StrEnum):
    """Outcome of an email delivery attempt."""

    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class JobStatus(StrEnum):
    """Outcome of a scheduled or manual job run."""

    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
