"""Seed reference data: categories, states/UTs, ministries, tags."""

import asyncio
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.database import Base
from app.models import Category, Ministry, State, Tag
from app.utils.slug import slugify

CATEGORIES = [
    ("Agriculture, Rural & Environment", "leaf"),
    ("Banking, Financial Services and Insurance", "banknotes"),
    ("Business & Entrepreneurship", "briefcase"),
    ("Education & Learning", "academic-cap"),
    ("Health & Wellness", "heart"),
    ("Housing & Shelter", "home"),
    ("Public Safety, Law & Justice", "shield-check"),
    ("Science, IT & Communications", "cpu-chip"),
    ("Skills & Employment", "wrench-screwdriver"),
    ("Social Welfare & Empowerment", "users"),
    ("Sports & Culture", "trophy"),
    ("Transport & Infrastructure", "truck"),
    ("Travel & Tourism", "globe-alt"),
    ("Utility & Sanitation", "bolt"),
    ("Women and Child", "user-group"),
    ("Youth Affairs", "fire"),
    ("Disability & Accessibility", "eye"),
    ("Minority Affairs", "sparkles"),
]

STATES = [
    ("Andhra Pradesh", "AP", False),
    ("Arunachal Pradesh", "AR", False),
    ("Assam", "AS", False),
    ("Bihar", "BR", False),
    ("Chhattisgarh", "CG", False),
    ("Goa", "GA", False),
    ("Gujarat", "GJ", False),
    ("Haryana", "HR", False),
    ("Himachal Pradesh", "HP", False),
    ("Jharkhand", "JH", False),
    ("Karnataka", "KA", False),
    ("Kerala", "KL", False),
    ("Madhya Pradesh", "MP", False),
    ("Maharashtra", "MH", False),
    ("Manipur", "MN", False),
    ("Meghalaya", "ML", False),
    ("Mizoram", "MZ", False),
    ("Nagaland", "NL", False),
    ("Odisha", "OD", False),
    ("Punjab", "PB", False),
    ("Rajasthan", "RJ", False),
    ("Sikkim", "SK", False),
    ("Tamil Nadu", "TN", False),
    ("Telangana", "TS", False),
    ("Tripura", "TR", False),
    ("Uttar Pradesh", "UP", False),
    ("Uttarakhand", "UK", False),
    ("West Bengal", "WB", False),
    ("Andaman and Nicobar Islands", "AN", True),
    ("Chandigarh", "CH", True),
    ("Dadra and Nagar Haveli and Daman and Diu", "DD", True),
    ("Delhi", "DL", True),
    ("Jammu and Kashmir", "JK", True),
    ("Ladakh", "LA", True),
    ("Lakshadweep", "LD", True),
    ("Puducherry", "PY", True),
]

MINISTRIES = [
    "Ministry of Agriculture & Farmers Welfare",
    "Ministry of Chemicals and Fertilizers",
    "Ministry of Civil Aviation",
    "Ministry of Coal",
    "Ministry of Commerce and Industry",
    "Ministry of Communications",
    "Ministry of Consumer Affairs, Food and Public Distribution",
    "Ministry of Corporate Affairs",
    "Ministry of Culture",
    "Ministry of Defence",
    "Ministry of Development of North Eastern Region",
    "Ministry of Earth Sciences",
    "Ministry of Education",
    "Ministry of Electronics and Information Technology",
    "Ministry of Environment, Forest and Climate Change",
    "Ministry of External Affairs",
    "Ministry of Finance",
    "Ministry of Fisheries, Animal Husbandry and Dairying",
    "Ministry of Food Processing Industries",
    "Ministry of Health and Family Welfare",
    "Ministry of Heavy Industries",
    "Ministry of Home Affairs",
    "Ministry of Housing and Urban Affairs",
    "Ministry of Information and Broadcasting",
    "Ministry of Jal Shakti",
    "Ministry of Labour and Employment",
    "Ministry of Law and Justice",
    "Ministry of Micro, Small and Medium Enterprises",
    "Ministry of Mines",
    "Ministry of Minority Affairs",
    "Ministry of New and Renewable Energy",
    "Ministry of Panchayati Raj",
    "Ministry of Parliamentary Affairs",
    "Ministry of Personnel, Public Grievances and Pensions",
    "Ministry of Petroleum and Natural Gas",
    "Ministry of Ports, Shipping and Waterways",
    "Ministry of Power",
    "Ministry of Railways",
    "Ministry of Road Transport and Highways",
    "Ministry of Rural Development",
    "Ministry of Science and Technology",
    "Ministry of Skill Development and Entrepreneurship",
    "Ministry of Social Justice and Empowerment",
    "Ministry of Statistics and Programme Implementation",
    "Ministry of Steel",
    "Ministry of Textiles",
    "Ministry of Tourism",
    "Ministry of Tribal Affairs",
    "Ministry of Women and Child Development",
    "Ministry of Youth Affairs and Sports",
    "NITI Aayog",
]

TAGS = [
    "Scholarship",
    "Loan",
    "Subsidy",
    "Pension",
    "Insurance",
    "Training",
    "Grant",
    "Housing",
    "Employment",
    "Healthcare",
    "Cash Transfer",
    "Equipment",
    "Skill Development",
    "Infrastructure",
]


async def seed_all():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    # Create pgvector extension and ensure all tables exist
    async with engine.begin() as conn:
        await conn.execute(
            __import__("sqlalchemy").text("CREATE EXTENSION IF NOT EXISTS vector")
        )
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        # Categories
        existing = (await session.execute(select(Category))).scalars().all()
        if not existing:
            for i, (name, icon) in enumerate(CATEGORIES):
                session.add(Category(id=uuid.uuid4(), name=name, slug=slugify(name), icon=icon, display_order=i))
            await session.commit()
            print(f"Seeded {len(CATEGORIES)} categories")
        else:
            print(f"Categories already seeded ({len(existing)})")

        # States
        existing = (await session.execute(select(State))).scalars().all()
        if not existing:
            for name, code, is_ut in STATES:
                session.add(State(id=uuid.uuid4(), name=name, slug=slugify(name), code=code, is_ut=is_ut))
            await session.commit()
            print(f"Seeded {len(STATES)} states/UTs")
        else:
            print(f"States already seeded ({len(existing)})")

        # Ministries
        existing = (await session.execute(select(Ministry))).scalars().all()
        if not existing:
            for name in MINISTRIES:
                session.add(Ministry(id=uuid.uuid4(), name=name, slug=slugify(name), level="central"))
            await session.commit()
            print(f"Seeded {len(MINISTRIES)} ministries")
        else:
            print(f"Ministries already seeded ({len(existing)})")

        # Tags
        existing = (await session.execute(select(Tag))).scalars().all()
        if not existing:
            for name in TAGS:
                session.add(Tag(id=uuid.uuid4(), name=name, slug=slugify(name)))
            await session.commit()
            print(f"Seeded {len(TAGS)} tags")
        else:
            print(f"Tags already seeded ({len(existing)})")

    await engine.dispose()
    print("Seed complete!")


if __name__ == "__main__":
    asyncio.run(seed_all())
