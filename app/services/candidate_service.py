import logging
import math
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.candidate import Candidate, Skill, candidate_skills
from app.models.application import Application
from app.models.job import Job

logger = logging.getLogger(__name__)


class CandidateService:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_candidate(
        self,
        first_name: str,
        last_name: str,
        email: str,
        phone: Optional[str] = None,
        headline: Optional[str] = None,
        summary: Optional[str] = None,
        location: Optional[str] = None,
        linkedin_url: Optional[str] = None,
        portfolio_url: Optional[str] = None,
        resume_url: Optional[str] = None,
        source: Optional[str] = None,
        skills: Optional[list[dict]] = None,
    ) -> Candidate:
        existing = await self.db.execute(
            select(Candidate).where(Candidate.email == email)
        )
        if existing.scalar_one_or_none() is not None:
            raise ValueError(f"Candidate with email '{email}' already exists.")

        candidate = Candidate(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            headline=headline,
            summary=summary,
            location=location,
            linkedin_url=linkedin_url,
            portfolio_url=portfolio_url,
            resume_url=resume_url,
            source=source,
        )
        self.db.add(candidate)
        await self.db.flush()

        if skills:
            for skill_info in skills:
                skill_name = skill_info.get("name", "").strip()
                if not skill_name:
                    continue
                years_of_experience = skill_info.get("years_of_experience")
                skill_obj = await self._get_or_create_skill(skill_name, years_of_experience)
                if skill_obj not in candidate.skills:
                    candidate.skills.append(skill_obj)

        await self.db.flush()
        await self.db.refresh(candidate)
        return candidate

    async def update_candidate(
        self,
        candidate_id: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        headline: Optional[str] = None,
        summary: Optional[str] = None,
        location: Optional[str] = None,
        linkedin_url: Optional[str] = None,
        portfolio_url: Optional[str] = None,
        resume_url: Optional[str] = None,
        source: Optional[str] = None,
        skills: Optional[list[dict]] = None,
    ) -> Candidate:
        candidate = await self.get_candidate(candidate_id)
        if candidate is None:
            raise ValueError(f"Candidate with id '{candidate_id}' not found.")

        if email is not None and email != candidate.email:
            existing = await self.db.execute(
                select(Candidate).where(
                    Candidate.email == email,
                    Candidate.id != candidate_id,
                )
            )
            if existing.scalar_one_or_none() is not None:
                raise ValueError(f"Candidate with email '{email}' already exists.")

        if first_name is not None:
            candidate.first_name = first_name
        if last_name is not None:
            candidate.last_name = last_name
        if email is not None:
            candidate.email = email
        if phone is not None:
            candidate.phone = phone
        if headline is not None:
            candidate.headline = headline
        if summary is not None:
            candidate.summary = summary
        if location is not None:
            candidate.location = location
        if linkedin_url is not None:
            candidate.linkedin_url = linkedin_url
        if portfolio_url is not None:
            candidate.portfolio_url = portfolio_url
        if resume_url is not None:
            candidate.resume_url = resume_url
        if source is not None:
            candidate.source = source

        if skills is not None:
            candidate.skills.clear()
            for skill_info in skills:
                skill_name = skill_info.get("name", "").strip()
                if not skill_name:
                    continue
                years_of_experience = skill_info.get("years_of_experience")
                skill_obj = await self._get_or_create_skill(skill_name, years_of_experience)
                if skill_obj not in candidate.skills:
                    candidate.skills.append(skill_obj)

        await self.db.flush()
        await self.db.refresh(candidate)
        return candidate

    async def get_candidate(self, candidate_id: str) -> Optional[Candidate]:
        result = await self.db.execute(
            select(Candidate)
            .where(Candidate.id == candidate_id)
            .options(
                selectinload(Candidate.skills),
                selectinload(Candidate.applications).selectinload(Application.job),
            )
        )
        return result.scalar_one_or_none()

    async def list_candidates(
        self,
        search: Optional[str] = None,
        skill: Optional[str] = None,
        location: Optional[str] = None,
        source: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        query = select(Candidate).options(
            selectinload(Candidate.skills),
            selectinload(Candidate.applications),
        )
        count_query = select(func.count(Candidate.id))

        if search:
            search_term = f"%{search}%"
            search_filter = or_(
                Candidate.first_name.ilike(search_term),
                Candidate.last_name.ilike(search_term),
                Candidate.email.ilike(search_term),
                Candidate.headline.ilike(search_term),
            )
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)

        if location:
            location_filter = Candidate.location.ilike(f"%{location}%")
            query = query.where(location_filter)
            count_query = count_query.where(location_filter)

        if source:
            source_filter = Candidate.source == source
            query = query.where(source_filter)
            count_query = count_query.where(source_filter)

        if skill:
            skill_subquery = (
                select(candidate_skills.c.candidate_id)
                .join(Skill, Skill.id == candidate_skills.c.skill_id)
                .where(Skill.name.ilike(f"%{skill}%"))
            )
            skill_filter = Candidate.id.in_(skill_subquery)
            query = query.where(skill_filter)
            count_query = count_query.where(skill_filter)

        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        total_pages = max(1, math.ceil(total / page_size))
        offset = (page - 1) * page_size

        query = query.order_by(Candidate.created_at.desc())
        query = query.offset(offset).limit(page_size)

        result = await self.db.execute(query)
        candidates = result.scalars().unique().all()

        return {
            "items": list(candidates),
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

    async def add_skill(
        self,
        candidate_id: str,
        skill_name: str,
        years_of_experience: Optional[int] = None,
    ) -> Skill:
        candidate = await self.get_candidate(candidate_id)
        if candidate is None:
            raise ValueError(f"Candidate with id '{candidate_id}' not found.")

        skill_name = skill_name.strip()
        if not skill_name:
            raise ValueError("Skill name cannot be empty.")

        for existing_skill in candidate.skills:
            if existing_skill.name.lower() == skill_name.lower():
                if years_of_experience is not None:
                    existing_skill.years_of_experience = years_of_experience
                    await self.db.flush()
                return existing_skill

        skill_obj = await self._get_or_create_skill(skill_name, years_of_experience)
        candidate.skills.append(skill_obj)
        await self.db.flush()
        await self.db.refresh(candidate)
        return skill_obj

    async def remove_skill(self, candidate_id: str, skill_name: str) -> None:
        candidate = await self.get_candidate(candidate_id)
        if candidate is None:
            raise ValueError(f"Candidate with id '{candidate_id}' not found.")

        skill_name = skill_name.strip()
        skill_to_remove = None
        for s in candidate.skills:
            if s.name.lower() == skill_name.lower():
                skill_to_remove = s
                break

        if skill_to_remove is None:
            raise ValueError(
                f"Skill '{skill_name}' not found for candidate '{candidate_id}'."
            )

        candidate.skills.remove(skill_to_remove)
        await self.db.flush()

    async def get_candidate_applications(self, candidate_id: str) -> list:
        candidate = await self.get_candidate(candidate_id)
        if candidate is None:
            raise ValueError(f"Candidate with id '{candidate_id}' not found.")

        applications = []
        for app in candidate.applications:
            job_title = None
            if app.job:
                job_title = app.job.title
            applications.append({
                "id": app.id,
                "job_id": app.job_id,
                "job_title": job_title,
                "status": app.status,
                "source": app.source,
                "notes": app.notes,
                "applied_at": app.applied_at,
                "updated_at": app.updated_at,
            })
        return applications

    async def _get_or_create_skill(
        self,
        name: str,
        years_of_experience: Optional[int] = None,
    ) -> Skill:
        result = await self.db.execute(
            select(Skill).where(func.lower(Skill.name) == name.lower())
        )
        skill = result.scalar_one_or_none()

        if skill is not None:
            if years_of_experience is not None and skill.years_of_experience != years_of_experience:
                skill.years_of_experience = years_of_experience
                await self.db.flush()
            return skill

        skill = Skill(name=name, years_of_experience=years_of_experience)
        self.db.add(skill)
        await self.db.flush()
        await self.db.refresh(skill)
        return skill

    async def get_source_options(self) -> list[str]:
        result = await self.db.execute(
            select(Candidate.source)
            .where(Candidate.source.isnot(None))
            .distinct()
            .order_by(Candidate.source)
        )
        sources = [row[0] for row in result.all() if row[0]]
        default_sources = [
            "Direct", "LinkedIn", "Referral", "Job Board",
            "Career Site", "Agency", "University", "Social Media", "Other",
        ]
        all_sources = list(dict.fromkeys(default_sources + sources))
        return all_sources