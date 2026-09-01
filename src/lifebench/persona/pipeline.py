"""Stage-oriented persona generation pipeline."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from datetime import date
from typing import Any, Callable, Dict, List, Optional

from src.lifebench.utils.structured_llm import StructuredLLMCaller

from .constraints import apply_derived_values
from .internal_models import BatchResult, PersonaResult
from .grounding import (
    build_employer_anchor,
    enrich_grounding_context,
    extract_mobility_profile,
)
from .normalization import normalize_persona_input
from .output_adapter import to_legacy_output
from .stages import (
    GenerationContext,
    generate_base_profile,
    generate_contact_group,
    generate_enrich,
    generate_narratives,
    generate_persona_consistency,
    generate_profile_enrich,
    generate_relation_slots,
    group_relation_slots,
)
from .validation import validate_internal_persona


class PersonaPipeline:
    def __init__(
        self,
        as_of_date: date,
        caller: StructuredLLMCaller,
        references_factory: Callable[[int], Dict[str, List[str]]],
        min_contacts: int = 16,
        max_contacts: int = 28,
        address_service=None,
    ):
        self.as_of_date = as_of_date
        self.caller = caller
        self.references_factory = references_factory
        self.min_contacts = min_contacts
        self.max_contacts = max_contacts
        self.address_service = address_service

    def generate_one(
        self,
        seed_person: Dict[str, Any],
        source_index: int,
        variant_instruction: Optional[str] = None,
        references: Optional[Dict[str, List[str]]] = None,
        locked_facts: Optional[Dict[str, Any]] = None,
        soft_clues: Optional[Dict[str, Any]] = None,
        source_description: str = "",
        variant_blueprint: Optional[Dict[str, Any]] = None,
        diversity: str = "low",
        variant_index: int = 0,
        run_seed: Optional[int] = None,
    ) -> PersonaResult:
        stage = "input"
        try:
            expected_keys = list(seed_person.keys())
            if "relation" not in expected_keys:
                raise ValueError("输入画像缺少 relation 字段，无法保持现有输出契约")
            context = GenerationContext(
                as_of_date=self.as_of_date,
                caller=self.caller,
                references=references or self.references_factory(source_index),
                variant_instruction=variant_instruction,
                min_contacts=self.min_contacts,
                max_contacts=self.max_contacts,
                locked_facts=locked_facts or {},
                soft_clues=soft_clues or {},
                source_description=source_description,
                variant_blueprint=variant_blueprint or {},
                diversity=diversity,
                variant_index=variant_index,
                run_seed=run_seed,
            )
            stage = "base"
            base, _ = generate_base_profile(seed_person, context)
            persona = normalize_persona_input(base, source_index)
            apply_derived_values(persona, self.as_of_date)

            stage = "profile_enrich"
            enriched_profile, _ = generate_profile_enrich(persona.data, context)
            persona.data.update(enriched_profile)
            apply_derived_values(persona, self.as_of_date)

            context.mobility_profile = extract_mobility_profile(
                persona.data, context.soft_clues, context.source_description,
            )
            context.employer_anchor = build_employer_anchor(persona.data, context.run_seed)

            core_locations = []
            if self.address_service is not None:
                stage = "address_grounding"
                ground = self.address_service.ground_core_addresses
                kwargs = {"seed": context.run_seed if context.run_seed is not None else source_index}
                try:
                    import inspect
                    if "mobility_profile" in inspect.signature(ground).parameters:
                        kwargs["mobility_profile"] = context.mobility_profile
                except (TypeError, ValueError):
                    pass
                grounded, core_locations = ground(persona.data, context.locked_facts, **kwargs)
                persona = normalize_persona_input(grounded, source_index)
                apply_derived_values(persona, self.as_of_date)

            context.grounding_context = enrich_grounding_context(
                core_locations,
                getattr(self.address_service, "last_assignment_metrics", {}) if self.address_service else {},
                context.employer_anchor,
                context.mobility_profile,
            )

            stage = "narrative"
            narratives, _ = generate_narratives(persona.data, context)
            persona.data.update(narratives)
            apply_derived_values(persona, self.as_of_date)

            stage = "relation_plan"
            slots, _ = generate_relation_slots(persona, context)
            fixed_circle_pois = []
            if self.address_service is not None and hasattr(self.address_service, "ground_circle_anchors"):
                stage = "circle_address_grounding"
                grounded_anchors, fixed_circle_pois = self.address_service.ground_circle_anchors(
                    context.circle_anchors, persona.data, core_locations,
                    seed=context.run_seed if context.run_seed is not None else source_index,
                )
                context.circle_anchors = grounded_anchors
                context.grounding_context["circle_anchors"] = deepcopy(grounded_anchors)
                context.grounding_context["circle_fixed_pois"] = [
                    {
                        "circle_id": item.get("_circle_id", ""),
                        "name": item.get("name", ""),
                        "location": item.get("location", ""),
                        "structured_address": item.get("structured_address", ""),
                    }
                    for item in fixed_circle_pois
                ]
                anchors_by_id = {item.get("circle_id"): item for item in grounded_anchors}
                for slot in slots:
                    grounded_anchor = anchors_by_id.get(slot.circle_id)
                    if grounded_anchor:
                        slot.parent_anchor_id = grounded_anchor.get("parent_anchor_id", slot.parent_anchor_id)
                        slot.shared_facts = deepcopy(grounded_anchor.get("shared_facts") or {})
            stage = "enrich"
            enriched, _ = generate_enrich(persona.data, context)
            persona.data.update(enriched)
            apply_derived_values(persona, self.as_of_date)
            persona.relation_groups = []
            contact_address_audit = []
            for group_index, group_slots in enumerate(group_relation_slots(slots).values()):
                stage = "contact_group_%d" % group_index
                contacts, _ = generate_contact_group(persona, group_slots, context, group_index)
                if self.address_service is not None and hasattr(self.address_service, "ground_contact_addresses"):
                    stage = "contact_address_grounding_%d" % group_index
                    anchor = next(
                        (item for item in context.circle_anchors if item.get("circle_id") == group_slots[0].circle_id),
                        {},
                    )
                    contact_address_audit.extend(self.address_service.ground_contact_addresses(
                        persona.data, contacts, anchor, core_locations, fixed_circle_pois,
                        seed=(context.run_seed if context.run_seed is not None else source_index) + group_index,
                    ))
                persona.relation_groups.append(contacts)
            if self.address_service is not None and hasattr(self.address_service, "ground_contact_addresses"):
                context.grounding_context["contact_address_audit"] = contact_address_audit

            stage = "persona_consistency"
            generate_persona_consistency(persona, context)

            stage = "final_validation"
            apply_derived_values(persona, self.as_of_date)
            report = validate_internal_persona(persona, self.as_of_date)
            if not report.valid:
                raise ValueError("; ".join(report.messages()))
            output = to_legacy_output(persona, expected_keys)
            locations = []
            if self.address_service is not None:
                stage = "address_surroundings"
                surrounding = self.address_service.generate_surrounding_locations
                surrounding_kwargs = {"seed": context.run_seed or source_index}
                try:
                    import inspect
                    if "fixed_pois" in inspect.signature(surrounding).parameters:
                        surrounding_kwargs["fixed_pois"] = fixed_circle_pois
                except (TypeError, ValueError):
                    pass
                locations = surrounding(output, core_locations, **surrounding_kwargs)
                consistency_errors = self.address_service.consistency_errors(output, locations)
                if consistency_errors:
                    raise ValueError("; ".join(consistency_errors))
            return PersonaResult(
                source_index=source_index, output=output, stage="complete",
                locations=locations, quality_context=deepcopy(context.grounding_context),
            )
        except Exception as exc:
            return PersonaResult(source_index=source_index, errors=[str(exc)], stage=stage)

    def generate_many(
        self,
        seeds: List[Dict[str, Any]],
        source_indices: Optional[List[int]] = None,
        max_workers: Optional[int] = None,
        variant_instruction_factory: Optional[Callable[[int], Optional[str]]] = None,
    ) -> BatchResult:
        indices = source_indices or list(range(len(seeds)))
        if len(indices) != len(seeds):
            raise ValueError("source_indices 与 seeds 数量不一致")
        results = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {}
            for seed_person, source_index in zip(seeds, indices):
                instruction = variant_instruction_factory(source_index) if variant_instruction_factory else None
                future = executor.submit(self.generate_one, deepcopy(seed_person), source_index, instruction)
                future_map[future] = source_index
            for future in as_completed(future_map):
                results.append(future.result())
        results.sort(key=lambda item: item.source_index)
        return BatchResult(results)
