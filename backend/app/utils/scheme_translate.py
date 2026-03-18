"""Shared helper for translating scheme content across all endpoints.

Translates scheme name, description, and nested category/state/ministry names.
Uses scheme_translations cache first, falls back to batch Google Translate.
Priority: names first (fast), descriptions second (can timeout gracefully).
"""

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.scheme import SchemeDetail, SchemeListItem
from app.services.translate_service import translate_texts_batch
from app.utils.translations import (
    CATEGORY_TRANSLATIONS,
    MINISTRY_TRANSLATIONS,
    STATE_TRANSLATIONS,
    translate_name,
)

logger = logging.getLogger(__name__)

# Languages covered by the static translation maps
_STATIC_LANGS = {"hi", "bn", "ta", "te", "mr", "gu", "kn", "ml", "pa", "or", "ur"}


async def translate_scheme_list_items(
    items: list[SchemeListItem],
    lang: str,
    db: AsyncSession,
) -> list[SchemeListItem]:
    """Translate a list of SchemeListItem objects.

    Priority order:
    1. scheme_translations cache (bulk, instant)
    2. Batch Google Translate for names (fast — batched into 1-2 API calls)
    3. Batch Google Translate for descriptions (with timeout)
    4. Static name translations for categories (instant)
    """
    if lang == "en" or not items:
        return items

    # Step 1: Try scheme_translations cache
    scheme_ids = [item.id for item in items]
    trans_map = {}
    try:
        from app.models.scheme import SchemeTranslation

        trans_q = select(SchemeTranslation).where(
            SchemeTranslation.scheme_id.in_(scheme_ids),
            SchemeTranslation.lang == lang,
        )
        trans_rows = (await db.execute(trans_q)).scalars().all()
        trans_map = {t.scheme_id: t for t in trans_rows}
    except Exception:
        pass  # Table doesn't exist — will use on-demand translation

    # Step 2: Identify items that need on-demand translation
    needs_name = []  # (index, original_name)
    needs_desc = []  # (index, original_desc)
    name_indices = []
    desc_indices = []

    for i, item in enumerate(items):
        cached = trans_map.get(item.id)
        if cached and cached.name:
            item.name = cached.name
        else:
            needs_name.append(item.name or "")
            name_indices.append(i)

        if cached and cached.description:
            item.description = cached.description
        else:
            desc = (item.description or "")[:300]
            if desc.strip():
                needs_desc.append(desc)
                desc_indices.append(i)

    # Step 3: Translate names first (high priority, fast with batching)
    if needs_name:
        try:
            translated_names = await translate_texts_batch(needs_name, lang, db)
            for idx, translated in zip(name_indices, translated_names):
                items[idx].name = translated
        except Exception as e:
            logger.warning("Name translation failed: %s", e)

    # Step 4: Translate descriptions — only if small batch (<=30 items)
    # For large lists, descriptions are deferred to detail view for performance
    if needs_desc and len(needs_desc) <= 30:
        try:
            translated_descs = await translate_texts_batch(needs_desc, lang, db)
            for idx, translated in zip(desc_indices, translated_descs):
                items[idx].description = translated
        except Exception as e:
            logger.warning("Description translation failed: %s", e)

    # Step 5: Translate nested names (categories)
    if lang in _STATIC_LANGS:
        # Use instant static maps for the 11 languages that have them
        for item in items:
            if item.category:
                item.category.name = translate_name(item.category.name, lang, CATEGORY_TRANSLATIONS)
    else:
        # On-demand translation for languages not in static maps
        cat_names = []
        cat_indices = []
        for i, item in enumerate(items):
            if item.category and item.category.name:
                cat_names.append(item.category.name)
                cat_indices.append(i)
        if cat_names:
            try:
                translated_cats = await translate_texts_batch(cat_names, lang, db)
                for idx, translated in zip(cat_indices, translated_cats):
                    items[idx].category.name = translated
            except Exception as e:
                logger.warning("Category translation failed: %s", e)

    return items


async def translate_scheme_detail(
    detail: SchemeDetail,
    lang: str,
    db: AsyncSession,
) -> SchemeDetail:
    """Translate a SchemeDetail object fully.

    1. Checks scheme_translations cache
    2. Falls back to batch Google Translate
    3. Translates all content fields + nested names
    """
    if lang == "en":
        return detail

    # Step 1: Check scheme_translations cache
    cached_trans = None
    try:
        from app.models.scheme import SchemeTranslation

        cached_trans = (
            await db.execute(
                select(SchemeTranslation).where(
                    SchemeTranslation.scheme_id == detail.id,
                    SchemeTranslation.lang == lang,
                )
            )
        ).scalar_one_or_none()
    except Exception:
        pass

    # Step 2: Apply cached translations or identify what needs on-demand
    fields_to_translate = {
        "name": detail.name,
        "description": detail.description,
        "benefits": detail.benefits,
        "eligibility_criteria": detail.eligibility_criteria,
        "application_process": detail.application_process,
        "documents_required": detail.documents_required,
    }

    if cached_trans:
        if cached_trans.name:
            detail.name = cached_trans.name
            del fields_to_translate["name"]
        if cached_trans.description:
            detail.description = cached_trans.description
            del fields_to_translate["description"]
        if getattr(cached_trans, "benefits", None):
            detail.benefits = cached_trans.benefits
            del fields_to_translate["benefits"]
        if getattr(cached_trans, "eligibility_criteria", None):
            detail.eligibility_criteria = cached_trans.eligibility_criteria
            del fields_to_translate["eligibility_criteria"]
        if getattr(cached_trans, "application_process", None):
            detail.application_process = cached_trans.application_process
            del fields_to_translate["application_process"]
        if getattr(cached_trans, "documents_required", None):
            detail.documents_required = cached_trans.documents_required
            del fields_to_translate["documents_required"]

    # On-demand translate remaining fields in batch
    texts_to_translate = []
    field_keys = []
    for key, value in fields_to_translate.items():
        if value and value.strip():
            texts_to_translate.append(value)
            field_keys.append(key)

    if texts_to_translate:
        try:
            translated = await translate_texts_batch(texts_to_translate, lang, db)
            for key, trans_text in zip(field_keys, translated):
                setattr(detail, key, trans_text)
        except Exception as e:
            logger.warning("Detail translation failed: %s", e)

    # Step 3: Translate nested names (category, ministry, states)
    if lang in _STATIC_LANGS:
        if detail.category:
            detail.category.name = translate_name(detail.category.name, lang, CATEGORY_TRANSLATIONS)
        if detail.ministry:
            detail.ministry.name = translate_name(detail.ministry.name, lang, MINISTRY_TRANSLATIONS)
        for s in detail.states:
            s.name = translate_name(s.name, lang, STATE_TRANSLATIONS)
    else:
        # On-demand translation for languages not in static maps
        names_to_translate = []
        name_targets = []  # (object, attribute)
        if detail.category and detail.category.name:
            names_to_translate.append(detail.category.name)
            name_targets.append((detail.category, "name"))
        if detail.ministry and detail.ministry.name:
            names_to_translate.append(detail.ministry.name)
            name_targets.append((detail.ministry, "name"))
        for s in detail.states:
            if s.name:
                names_to_translate.append(s.name)
                name_targets.append((s, "name"))
        if names_to_translate:
            try:
                translated = await translate_texts_batch(names_to_translate, lang, db)
                for (obj, attr), trans in zip(name_targets, translated):
                    setattr(obj, attr, trans)
            except Exception as e:
                logger.warning("Nested name translation failed: %s", e)

    # Step 4: Translate eligibility display values (gender, social category)
    if detail.target_gender:
        gender_texts = [g for g in detail.target_gender]
        try:
            translated_genders = await translate_texts_batch(gender_texts, lang, db)
            detail.target_gender = translated_genders
        except Exception as e:
            logger.warning("Gender translation failed: %s", e)

    if detail.target_social_category:
        cat_texts = [c for c in detail.target_social_category]
        try:
            translated_cats = await translate_texts_batch(cat_texts, lang, db)
            detail.target_social_category = translated_cats
        except Exception as e:
            logger.warning("Social category translation failed: %s", e)

    return detail
