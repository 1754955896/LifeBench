"""Persona generation facade with staged validation and legacy-compatible output."""

import json
import os
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy

from src.lifebench.utils.structured_llm import StructuredLLMCaller

from .constraints import apply_derived_values, parse_date
from .canonicalizer import canonicalize_source
from .address_generation import PersonaAddressService
from .diversity import (
    create_run_seed,
    diversity_directive,
    minimum_distance,
    persona_distance,
    stage_seed,
)
from .eval.quality_gate import evaluate_output_batch
from .internal_models import INTERNAL_KEYS
from .grounding import build_employer_anchor, enrich_grounding_context, extract_mobility_profile
from .local_io import append_failure, atomic_write_json
from .normalization import (
    normalize_persona_input,
    normalize_profile_response,
    normalize_relation_plan,
    parse_json_response,
)
from .output_adapter import contact_to_output, to_legacy_output
from .pipeline import PersonaPipeline
from .prompts import build_base_profile_prompt
from .sampling import PersonaReferenceSampler, derived_variant_seed, sample_from_reference_pool
from .source_io import load_source_records
from .source_normalizer import SourceNormalizer
from .stages import (
    GenerationContext,
    generate_base_profile,
    generate_contact_group,
    generate_enrich,
    generate_narratives,
    generate_persona_consistency,
    generate_profile_enrich,
    generate_relation_slots,
    generate_variant_blueprint,
    group_relation_slots,
)
from .validation import validate_internal_persona, validate_profile_keys


class PersonaGenerator:
    """Generate personas while preserving the repository's legacy JSON contract."""

    def __init__(
        self,
        ref_json_file_path="../persona/persona_file/refer.json",
        as_of_date="2021-12-31",
        seed=None,
        max_stage_retries=2,
        keep_checkpoints=False,
        caller=None,
        generate_locations=False,
        address_service=None,
    ):
        self.ref_json_file_path = ref_json_file_path
        with open(ref_json_file_path, "r", encoding="utf-8") as stream:
            refer_data = json.load(stream)
        self.as_of_date = parse_date(as_of_date, "as_of_date")
        self.seed = seed
        self.max_stage_retries = int(max_stage_retries)
        self.keep_checkpoints = bool(keep_checkpoints)
        self.reference_sampler = PersonaReferenceSampler(refer_data, seed=seed)
        self.caller = caller or StructuredLLMCaller(max_retries=self.max_stage_retries)
        self.generate_locations = bool(generate_locations or address_service is not None)
        self.address_service = address_service
        if self.generate_locations and self.address_service is None:
            self.address_service = PersonaAddressService(self.caller)
        self.pipeline = PersonaPipeline(
            as_of_date=self.as_of_date,
            caller=self.caller,
            references_factory=self.reference_sampler.references_for_person,
            address_service=self.address_service,
        )
        self.source_normalizer = SourceNormalizer(self.caller, self.as_of_text)
        self.last_run_seed = None

    @property
    def as_of_text(self):
        return self.as_of_date.strftime("%Y-%m-%d")

    def _context(self, source_index=0, variant_instruction=None):
        return GenerationContext(
            as_of_date=self.as_of_date,
            caller=self.caller,
            references=self.reference_sampler.references_for_person(source_index),
            variant_instruction=variant_instruction,
        )

    def _variant_context(
        self, canonical, source_index, variant_index, run_seed, diversity,
        previous_blueprints=None, attempt=0,
    ):
        references = self.reference_sampler.references_for_variant(
            source_index, variant_index + attempt * 1000, run_seed,
        )
        return GenerationContext(
            as_of_date=self.as_of_date,
            caller=self.caller,
            references=references,
            variant_instruction=diversity_directive(diversity),
            locked_facts=canonical.locked_facts,
            soft_clues=canonical.soft_clues,
            source_description=canonical.source_description,
            diversity=diversity,
            variant_index=variant_index,
            run_seed=stage_seed(run_seed, source_index, variant_index, "blueprint-attempt-%d" % attempt),
        )

    def normalize_source(self, source):
        """Normalize one arbitrary source record into internal sparse facts."""
        return self.source_normalizer.normalize(source)

    def generate_from_any(
        self, source, out_file_path=None, input_format="auto",
        variants_per_input=1, diversity="high", seed=None,
        start_id=0, end_id=None, location_out_file_path=None,
    ):
        """Generate fixed-schema personas from arbitrary structured or text input."""
        if int(variants_per_input) < 1:
            raise ValueError("variants_per_input 必须大于 0")
        records = load_source_records(source, input_format)
        if start_id < 0 or (end_id is not None and end_id < start_id):
            raise ValueError("start_id/end_id 范围非法")
        records = records[start_id:end_id]
        if not records:
            return []
        run_seed = create_run_seed(self.seed if seed is None else seed)
        self.last_run_seed = run_seed
        all_outputs = []
        all_location_batches = []
        all_quality_contexts = []
        expected_orders = []
        failures = []

        for source_index, record in enumerate(records):
            try:
                normalized = self.normalize_source(record)
                canonical = canonicalize_source(normalized)
            except Exception as exc:
                failures.append({"source_index": source_index, "stage": "input_normalization", "error": str(exc)})
                continue

            source_outputs = []
            accepted_blueprints = []
            for variant_index in range(int(variants_per_input)):
                best_output = None
                best_distance = -1.0
                best_blueprint = None
                best_locations = []
                best_quality_context = {}
                variant_errors = []
                attempts = max(2, self.max_stage_retries + 1)
                rejected_blueprints = []
                for attempt in range(attempts):
                    context = self._variant_context(
                        canonical, source_index, variant_index, run_seed,
                        diversity, accepted_blueprints + rejected_blueprints, attempt,
                    )
                    try:
                        blueprint = generate_variant_blueprint(
                            context, accepted_blueprints + rejected_blueprints,
                        )
                        context.variant_blueprint = blueprint.to_dict()
                        result = self.pipeline.generate_one(
                            canonical.data,
                            source_index * int(variants_per_input) + variant_index,
                            variant_instruction=context.variant_instruction,
                            references=context.references,
                            locked_facts=canonical.locked_facts,
                            soft_clues=canonical.soft_clues,
                            source_description=canonical.source_description,
                            variant_blueprint=context.variant_blueprint,
                            diversity=diversity,
                            variant_index=variant_index,
                            run_seed=context.run_seed,
                        )
                        if not result.succeeded:
                            variant_errors.extend(result.errors)
                            rejected_blueprints.append(blueprint.to_dict())
                            continue
                        distance = min(
                            (persona_distance(result.output, prior, canonical.locked_facts.keys()) for prior in source_outputs),
                            default=1.0,
                        )
                        if distance > best_distance:
                            best_output = result.output
                            best_distance = distance
                            best_blueprint = blueprint.to_dict()
                            best_locations = result.locations
                            best_quality_context = result.quality_context
                        if distance >= minimum_distance(diversity):
                            break
                        rejected_blueprints.append(blueprint.to_dict())
                    except Exception as exc:
                        variant_errors.append(str(exc))
                if best_output is None:
                    failures.append({
                        "source_index": source_index,
                        "variant_index": variant_index,
                        "stage": "variant_generation",
                        "error": "; ".join(variant_errors[-10:]),
                    })
                    continue
                if best_distance < minimum_distance(diversity):
                    print(
                        "警告：输入 %d 的变体 %d 多样性距离 %.3f 低于目标 %.3f，已保留重试中的最佳结果"
                        % (source_index, variant_index, best_distance, minimum_distance(diversity))
                    )
                source_outputs.append(best_output)
                all_location_batches.append(best_locations)
                all_quality_contexts.append(best_quality_context)
                accepted_blueprints.append(best_blueprint)

            all_outputs.extend(source_outputs)
            expected_orders.extend([list(canonical.data.keys())] * len(source_outputs))

        expected_count = len(records) * int(variants_per_input)
        if failures or len(all_outputs) != expected_count:
            if out_file_path:
                failure_path = out_file_path + ".failures.jsonl"
                for failure in failures:
                    append_failure(failure_path, failure)
            raise RuntimeError(
                "任意输入画像生成未完整成功：期望 %d，实际 %d；%s"
                % (expected_count, len(all_outputs), failures[-3:])
            )
        gate = evaluate_output_batch(
            all_outputs, expected_orders,
            location_batches=all_location_batches if self.address_service is not None else None,
            semantic_contexts=all_quality_contexts,
        )
        if not gate.valid:
            raise ValueError("任意输入输出质量门禁失败: %s" % "; ".join(gate.errors))
        if out_file_path:
            atomic_write_json(out_file_path, all_outputs)
            if self.address_service is not None:
                location_out_file_path = location_out_file_path or self._default_location_sidecar(out_file_path)
                atomic_write_json(location_out_file_path, all_location_batches)
                print("画像地址 sidecar 已保存到 %s" % location_out_file_path)
            print("任意输入画像已保存到 %s；run_seed=%s" % (out_file_path, run_seed))
        return all_outputs

    def refer_const(self, source_index=0):
        """Return legacy prompt text for callers that still inspect references."""
        return json.dumps(
            self.reference_sampler.references_for_person(source_index),
            ensure_ascii=False,
            indent=2,
        )

    def generate_profile(self, profile_str, variant_instruction=None, source_index=0):
        """Compatibility API: generate one base profile and return a JSON string."""
        raw = parse_json_response(profile_str)
        expected = list(raw.keys())
        prompt = build_base_profile_prompt(
            raw,
            self.reference_sampler.references_for_person(source_index),
            self.as_of_text,
            variant_instruction,
        )
        result = self.caller.call_json_object(
            prompt,
            validator=lambda data: validate_profile_keys(data, expected, "base"),
        )
        normalized = normalize_profile_response(result.data, expected)
        return json.dumps(normalized, ensure_ascii=False)

    def generate_refine(self, profile, source_index=0):
        """Compatibility API: refine narratives without rewriting structure."""
        raw = parse_json_response(profile)
        narratives, _ = generate_narratives(raw, self._context(source_index))
        result = deepcopy(raw)
        result.update(narratives)
        internal = normalize_persona_input(result, 0)
        apply_derived_values(internal, self.as_of_date)
        return json.dumps(to_legacy_output(internal, list(raw.keys())), ensure_ascii=False)

    def generate_relation(self, profile, source_index=0):
        """Compatibility API: return the legacy relation-plan array JSON."""
        raw = parse_json_response(profile)
        internal = normalize_persona_input(raw, source_index)
        slots, _ = generate_relation_slots(internal, self._context(source_index))
        result = [
            {"name": slot.name_hint, "relation": slot.relation, "social circle": slot.social_circle}
            for slot in slots
        ]
        return json.dumps(result, ensure_ascii=False)

    def generate_people(self, profile, circle, source_index=0):
        """Compatibility API: fill one relation group and return an array JSON."""
        raw_profile = parse_json_response(profile)
        slots = normalize_relation_plan(parse_json_response(circle))
        internal = normalize_persona_input(raw_profile, source_index)
        contacts, _ = generate_contact_group(internal, slots, self._context(source_index), 0)
        return json.dumps([contact_to_output(contact) for contact in contacts], ensure_ascii=False)

    def group_by_social_circle(self, data):
        groups = {}
        for person in data:
            circle = person.get("social circle") or person.get("social_circle")
            if not circle:
                raise ValueError("联系人缺少 social circle")
            groups.setdefault(circle, []).append(person)
        return groups

    def generate_person(self, profile, profile_rl, index):
        relation_list = parse_json_response(profile_rl)
        result = []
        for people in self.group_by_social_circle(relation_list).values():
            response = self.generate_people(profile, json.dumps(people, ensure_ascii=False), source_index=index)
            result.append(parse_json_response(response))
        return result

    def parse_llm_json_response(self, llm_response):
        return parse_json_response(llm_response)

    @staticmethod
    def _build_variant_instruction(variant_strength):
        strength = float(variant_strength)
        if not 0 <= strength <= 1:
            raise ValueError("variant_strength 必须在 0.0～1.0 之间")
        if strength == 0:
            return None
        if strength >= 0.7:
            return "大幅变体：在不破坏输入硬事实和字段契约的前提下，显著调整可变职业细节、兴趣和生活叙事。"
        if strength >= 0.4:
            return "中等变体：保持核心人口属性，适度调整职业细节、兴趣和同省生活地点。"
        return "轻度变体：保持主体框架，只微调非核心细节和描述措辞。"

    @staticmethod
    def _standard_address_locks(person):
        """Keep input administrative regions while allowing fictional streets to be grounded."""
        result = {}
        for field in ("home_address", "workplace"):
            address = person.get(field)
            if isinstance(address, dict):
                region = {
                    key: deepcopy(address[key])
                    for key in ("province", "city", "district")
                    if address.get(key) not in (None, "")
                }
                if region:
                    result[field] = region
        return result

    def _generate_basic_one(self, person, index, variant_strength=0.3):
        context = self._context(index, self._build_variant_instruction(variant_strength))
        base, _ = generate_base_profile(person, context)
        internal = normalize_persona_input(base, index)
        apply_derived_values(internal, self.as_of_date)
        enriched_profile, _ = generate_profile_enrich(internal.data, context)
        internal.data.update(enriched_profile)
        apply_derived_values(internal, self.as_of_date)
        context.mobility_profile = extract_mobility_profile(internal.data)
        context.employer_anchor = build_employer_anchor(internal.data, self.seed)
        core_locations = []
        if self.address_service is not None:
            grounded, core_locations = self.address_service.ground_core_addresses(
                internal.data, self._standard_address_locks(person),
                seed=derived_variant_seed(self.seed, index, 0, "core_location") or index,
                mobility_profile=context.mobility_profile,
            )
            internal = normalize_persona_input(grounded, index)
            apply_derived_values(internal, self.as_of_date)
        context.grounding_context = enrich_grounding_context(
            core_locations,
            getattr(self.address_service, "last_assignment_metrics", {}) if self.address_service else {},
            context.employer_anchor, context.mobility_profile,
        )
        narratives, _ = generate_narratives(internal.data, context)
        internal.data.update(narratives)
        apply_derived_values(internal, self.as_of_date)
        output = to_legacy_output(internal, list(person.keys()))
        output["_index"] = index
        if core_locations:
            output["_core_locations"] = core_locations
        output["_quality_context"] = context.grounding_context
        return output

    def _process_single_person(self, person, index, variant_strength=0.3):
        result = self._generate_basic_one(person, index, variant_strength)
        print("已生成第%d条基础画像" % (index + 1))
        return result

    @staticmethod
    def _selected_people(people_list, start_id, end_id):
        if start_id < 0 or end_id < start_id:
            raise ValueError("start_id/end_id 范围非法")
        return [(people_list[index], index) for index in range(start_id, min(end_id, len(people_list)))]

    def generate_basic_profile(
        self, start_id, end_id, in_file_path, basic_out_file_path,
        max_workers=None, variant_strength=0.3,
    ):
        with open(in_file_path, "r", encoding="utf-8") as stream:
            people_list = json.load(stream)
        selected = self._selected_people(people_list, start_id, end_id)
        if not selected:
            return []
        results, failures = [], []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {
                executor.submit(self._process_single_person, person, index, variant_strength): index
                for person, index in selected
            }
            for future in as_completed(future_map):
                index = future_map[future]
                try:
                    results.append(future.result())
                except Exception as exc:
                    failures.append({"source_index": index, "stage": "basic", "error": str(exc)})
        if failures:
            failure_path = basic_out_file_path + ".failures.jsonl"
            for failure in failures:
                append_failure(failure_path, failure)
            print("基础画像生成失败 %d 条，未写入中间结果；详见 %s" % (len(failures), failure_path))
            return None
        results.sort(key=lambda item: item["_index"])
        atomic_write_json(basic_out_file_path, results)
        print("基础画像数据已保存到 %s" % basic_out_file_path)
        return results

    def _generate_relations_for_basic(self, basic_data, fallback_index=0):
        index = int(basic_data.get("_index", fallback_index))
        core_locations = deepcopy(basic_data.get("_core_locations") or [])
        saved_quality_context = deepcopy(basic_data.get("_quality_context") or {})
        clean = {
            key: deepcopy(value)
            for key, value in basic_data.items()
            if key not in INTERNAL_KEYS and not key.startswith("_")
        }
        expected_keys = list(clean.keys())
        internal = normalize_persona_input(clean, index)
        apply_derived_values(internal, self.as_of_date)
        context = self._context(index)
        context.mobility_profile = deepcopy(saved_quality_context.get("mobility_profile") or extract_mobility_profile(internal.data))
        context.employer_anchor = deepcopy(saved_quality_context.get("employer_anchor") or build_employer_anchor(internal.data, self.seed))
        context.grounding_context = saved_quality_context or enrich_grounding_context(
            core_locations, {}, context.employer_anchor, context.mobility_profile,
        )
        slots, _ = generate_relation_slots(internal, context)
        fixed_circle_pois = []
        if self.address_service is not None and hasattr(self.address_service, "ground_circle_anchors"):
            grounded_anchors, fixed_circle_pois = self.address_service.ground_circle_anchors(
                context.circle_anchors, internal.data, core_locations,
                seed=derived_variant_seed(self.seed, index, 0, "circle_location") or index,
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
        context.run_seed = derived_variant_seed(self.seed, index, 0, "enrich") or index
        enriched, _ = generate_enrich(internal.data, context)
        internal.data.update(enriched)
        apply_derived_values(internal, self.as_of_date)
        internal.relation_groups = []
        contact_address_audit = []
        for group_index, slot_group in enumerate(group_relation_slots(slots).values()):
            contacts, _ = generate_contact_group(internal, slot_group, context, group_index)
            if self.address_service is not None and hasattr(self.address_service, "ground_contact_addresses"):
                anchor = next(
                    (item for item in context.circle_anchors if item.get("circle_id") == slot_group[0].circle_id),
                    {},
                )
                contact_address_audit.extend(self.address_service.ground_contact_addresses(
                    internal.data, contacts, anchor, core_locations, fixed_circle_pois,
                    seed=(derived_variant_seed(self.seed, index, 0, "contact_location") or index) + group_index,
                ))
            internal.relation_groups.append(contacts)
        if self.address_service is not None and hasattr(self.address_service, "ground_contact_addresses"):
            context.grounding_context["contact_address_audit"] = contact_address_audit
        generate_persona_consistency(internal, context)
        apply_derived_values(internal, self.as_of_date)
        report = validate_internal_persona(internal, self.as_of_date)
        if not report.valid:
            raise ValueError("; ".join(report.messages()))
        output = to_legacy_output(internal, expected_keys)
        locations = []
        if self.address_service is not None:
            if not core_locations:
                grounded, core_locations = self.address_service.ground_core_addresses(
                    output, self._standard_address_locks(output),
                    seed=derived_variant_seed(self.seed, index, 0, "core_location") or index,
                    mobility_profile=context.mobility_profile,
                )
                internal = normalize_persona_input(grounded, index)
                apply_derived_values(internal, self.as_of_date)
                output = to_legacy_output(internal, expected_keys)
                context.grounding_context = enrich_grounding_context(
                    core_locations, getattr(self.address_service, "last_assignment_metrics", {}),
                    context.employer_anchor, context.mobility_profile,
                )
            locations = self.address_service.generate_surrounding_locations(
                output, core_locations,
                seed=derived_variant_seed(self.seed, index, 0, "location") or index,
                fixed_pois=fixed_circle_pois,
            )
            consistency_errors = self.address_service.consistency_errors(output, locations)
            if consistency_errors:
                raise ValueError("; ".join(consistency_errors))
        return index, output, locations, context.grounding_context

    def _process_single_relation(self, basic_data):
        index, output, locations, quality_context = self._generate_relations_for_basic(basic_data)
        print("已完成第%d条完整画像" % (index + 1))
        return index, output, locations, quality_context

    def generate_relation_and_complete(
        self, basic_profile_file, final_out_file_path, max_workers=None,
        location_out_file_path=None,
    ):
        with open(basic_profile_file, "r", encoding="utf-8") as stream:
            basic_profiles = json.load(stream)
        if not basic_profiles:
            return []
        results, failures = [], []
        expected_keys_by_index = {
            int(item.get("_index", index)): [
                key for key in item if key not in INTERNAL_KEYS and not key.startswith("_")
            ]
            for index, item in enumerate(basic_profiles)
        }
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {
                executor.submit(self._process_single_relation, item): int(item.get("_index", index))
                for index, item in enumerate(basic_profiles)
            }
            for future in as_completed(future_map):
                index = future_map[future]
                try:
                    results.append(future.result())
                except Exception as exc:
                    failures.append({"source_index": index, "stage": "relation", "error": str(exc)})
        if failures:
            failure_path = final_out_file_path + ".failures.jsonl"
            for failure in failures:
                append_failure(failure_path, failure)
            print("关系生成失败 %d 条，正式输出未更新；详见 %s" % (len(failures), failure_path))
            return None
        results.sort(key=lambda item: item[0])
        outputs = [item[1] for item in results]
        gate = evaluate_output_batch(
            outputs,
            [expected_keys_by_index[item[0]] for item in results],
            location_batches=[item[2] for item in results] if self.address_service is not None else None,
            semantic_contexts=[item[3] for item in results],
        )
        if not gate.valid:
            raise ValueError("批量输出质量门禁失败: %s" % "; ".join(gate.errors))
        atomic_write_json(final_out_file_path, outputs)
        if self.address_service is not None:
            location_batches = [item[2] for item in results]
            location_out_file_path = location_out_file_path or self._default_location_sidecar(final_out_file_path)
            atomic_write_json(location_out_file_path, location_batches)
            print("画像地址 sidecar 已保存到 %s" % location_out_file_path)
        print("完整画像数据已保存到 %s" % final_out_file_path)
        return outputs

    @staticmethod
    def _default_location_sidecar(persona_path):
        stem, _ = os.path.splitext(persona_path)
        return stem + "_locations.json"

    def gen_profile(
        self, start_id, end_id, in_file_path, out_file_path, median_path=None,
        max_workers=None, location_out_file_path=None,
    ):
        if median_path is None:
            median_path = out_file_path.replace(".json", "_basic_temp.json")
        basic_profiles = self.generate_basic_profile(
            start_id, end_id, in_file_path, median_path, max_workers=max_workers,
        )
        if not basic_profiles:
            print("生成基础画像失败，无法继续")
            return None
        outputs = self.generate_relation_and_complete(
            median_path, out_file_path, max_workers=max_workers,
            location_out_file_path=location_out_file_path,
        )
        if outputs is not None and not self.keep_checkpoints:
            try:
                os.remove(median_path)
            except OSError:
                pass
        return outputs

    def sample_from_ref(self, ref_file_path, target_count, required_indices=None, exclude_indices=None):
        if not os.path.exists(ref_file_path):
            raise FileNotFoundError("参考文件不存在: %s" % ref_file_path)
        with open(ref_file_path, "r", encoding="utf-8") as stream:
            pool = json.load(stream)
        sampled = sample_from_reference_pool(
            pool, target_count,
            required_indices=required_indices,
            exclude_indices=exclude_indices,
            seed=self.seed,
        )
        return [{"person": item.person, "ref_index": item.ref_index} for item in sampled]

    def generate_from_ref(
        self, ref_file_path, target_count, out_file_path,
        required_indices=None, exclude_indices=None,
        variant_strength=0.3, max_workers=None,
    ):
        sampled = self.sample_from_ref(ref_file_path, target_count, required_indices, exclude_indices)
        temp_dir = tempfile.mkdtemp(prefix="lifebench-persona-")
        sampled_path = os.path.join(temp_dir, "sampled_input.json")
        basic_path = os.path.join(temp_dir, "basic_temp.json")
        try:
            atomic_write_json(sampled_path, [item["person"] for item in sampled])
            basic = self.generate_basic_profile(
                0, len(sampled), sampled_path, basic_path,
                max_workers=max_workers, variant_strength=variant_strength,
            )
            if not basic:
                return None
            outputs = self.generate_relation_and_complete(basic_path, out_file_path, max_workers=max_workers)
            if outputs:
                print("共生成 %d 个完整画像，已保存到: %s" % (len(outputs), out_file_path))
            return outputs
        finally:
            if self.keep_checkpoints:
                print("已保留 persona checkpoint: %s" % temp_dir)
            else:
                shutil.rmtree(temp_dir, ignore_errors=True)
