# -*- coding: utf-8 -*-
"""
执行 Agent (Execution Agent)
负责执行具体的增删改查操作，修改对应文件
"""

import json
import os
import copy
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
from utils.llm_call import llm_call_j
from event.edit.planning_agent import OperationPlan, OperationType, DataType


@dataclass
class ExecutionResult:
    """执行结果数据结构"""
    success: bool
    operation_type: str
    data_type: str
    target_path: str
    message: str
    data_before: Optional[Any] = None  # 操作前的数据（用于撤销）
    data_after: Optional[Any] = None   # 操作后的数据
    affected_count: int = 0            # 影响的数据条数
    execution_time_ms: float = 0.0     # 执行耗时
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "success": self.success,
            "operation_type": self.operation_type,
            "data_type": self.data_type,
            "target_path": self.target_path,
            "message": self.message,
            "data_before": self.data_before,
            "data_after": self.data_after,
            "affected_count": self.affected_count,
            "execution_time_ms": self.execution_time_ms
        }


class ExecutionAgent:
    """执行 Agent - 负责执行文件增删改查操作"""
    
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self._cache: Dict[str, Any] = {}
        self._loaded_files: Dict[str, str] = {}
        
        # 文件配置：定义各文件的 ID 字段
        self._file_configs = {
            'daily_event': {
                'id_field': 'event_id',
                'index_method': 'by_id'
            },
            'daily_draft': {
                'id_field': 'date',
                'index_method': 'by_date'
            },
            'phone_data': {
                'id_field': 'phone_id',
                'sub_types': ['call', 'sms', 'calendar', 'note', 'contact', 'fitness_health', 'perception', 'push', 'photo'],
                'index_method': 'by_id'
            }
        }
        
        # 处理器映射：daily_event 和 phone_data 支持完整 CRUD, daily_draft 仅支持查询和更新
        self._handlers = {
            (DataType.DAILY_EVENT, OperationType.ADD): self._add_daily_event_direct,
            (DataType.DAILY_EVENT, OperationType.DELETE): self._delete_daily_event_by_id,
            (DataType.DAILY_EVENT, OperationType.UPDATE): self._update_daily_event_by_id,
            (DataType.DAILY_EVENT, OperationType.QUERY): self._query_daily_event_by_id,
            (DataType.DAILY_EVENT, OperationType.WHOLE_DAY_REWRITE): self._whole_day_rewrite_daily_event,
            
            (DataType.DAILY_DRAFT, OperationType.QUERY): self._query_daily_draft,
            (DataType.DAILY_DRAFT, OperationType.UPDATE): self._update_daily_draft,
            
            (DataType.PHONE_DATA, OperationType.ADD): self._add_phone_data_direct,
            (DataType.PHONE_DATA, OperationType.DELETE): self._delete_phone_data_by_id,
            (DataType.PHONE_DATA, OperationType.UPDATE): self._update_phone_data_by_id,
            (DataType.PHONE_DATA, OperationType.QUERY): self._query_phone_data_by_id,
        }
    
    def execute(self, plan: OperationPlan) -> ExecutionResult:
        """执行单个操作计划"""
        import time
        start_time = time.time()
        
        print(f"[ExecutionAgent] 执行：{plan.operation_type.value} on {plan.data_type.value}")
        
        handler = self._handlers.get((plan.data_type, plan.operation_type))
        if not handler:
            return ExecutionResult(
                success=False, operation_type=plan.operation_type.value,
                data_type=plan.data_type.value, target_path=plan.target_path,
                message=f"不支持的操作",
                execution_time_ms=(time.time() - start_time) * 1000
            )
        
        try:
            result = handler(plan)
            result.execution_time_ms = (time.time() - start_time) * 1000
            return result
        except Exception as e:
            return ExecutionResult(
                success=False, operation_type=plan.operation_type.value,
                data_type=plan.data_type.value, target_path=plan.target_path,
                message=f"执行异常：{str(e)}",
                execution_time_ms=(time.time() - start_time) * 1000
            )
    
    def execute_batch(self, plans: List[OperationPlan]) -> List[ExecutionResult]:
        """批量执行操作计划"""
        results = []
        for plan in plans:
            result = self.execute(plan)
            results.append(result)
            if not result.success and plan.operation_type in [OperationType.DELETE, OperationType.UPDATE]:
                break
        return results
    
    def save_all(self) -> Dict[str, bool]:
        """保存所有修改到文件"""
        results = {}
        
        # 保存 daily_events
        if 'daily_event' in self._cache:
            try:
                file_path = self._loaded_files.get('daily_event', os.path.join(self.base_dir, 'daily_event.json'))
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(self._cache['daily_event'], f, ensure_ascii=False, indent=2)
                results['daily_event'] = True
                print(f"[ExecutionAgent] 已保存 daily_event 到：{file_path}")
            except Exception as e:
                results['daily_event'] = False
                print(f"[ExecutionAgent] 保存 daily_event 失败：{e}")
        
        # 保存 daily_drafts
        if 'daily_draft' in self._cache:
            try:
                file_path = self._loaded_files.get('daily_draft', os.path.join(self.base_dir, 'daily_draft.json'))
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(self._cache['daily_draft'], f, ensure_ascii=False, indent=2)
                results['daily_draft'] = True
                print(f"[ExecutionAgent] 已保存 daily_draft 到：{file_path}")
            except Exception as e:
                results['daily_draft'] = False
                print(f"[ExecutionAgent] 保存 daily_draft 失败：{e}")
        
        # 保存 phone_data
        if 'phone_data' in self._cache:
            try:
                data_dir = self._loaded_files.get('phone_data', os.path.join(self.base_dir, 'phone_data'))
                for data_type, data_list in self._cache['phone_data'].items():
                    file_path = os.path.join(data_dir, f"{data_type}.json")
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(data_list, f, ensure_ascii=False, indent=2)
                results['phone_data'] = True
                print(f"[ExecutionAgent] 已保存 phone_data 到：{data_dir}")
            except Exception as e:
                results['phone_data'] = False
                print(f"[ExecutionAgent] 保存 phone_data 失败：{e}")
        
        return results

    
    # ========== 数据加载方法 ==========
    
    def _load_daily_events(self) -> List[Dict]:
        """加载日常事件数据"""
        if 'daily_event' not in self._cache:
            file_path = os.path.join(self.base_dir, 'daily_event.json')
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    self._cache['daily_event'] = json.load(f)
                self._loaded_files['daily_event'] = file_path
            else:
                self._cache['daily_event'] = []
        return self._cache['daily_event']
    
    def _load_daily_drafts(self) -> Dict:
        """加载草稿数据"""
        if 'daily_draft' not in self._cache:
            file_path = os.path.join(self.base_dir, 'daily_draft.json')
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    self._cache['daily_draft'] = json.load(f)
                self._loaded_files['daily_draft'] = file_path
            else:
                self._cache['daily_draft'] = {}
        return self._cache['daily_draft']
    
    def _load_phone_data(self, data_type: str = None) -> Dict[str, List[Dict]]:
        """加载手机数据"""
        if 'phone_data' not in self._cache:
            data_dir = os.path.join(self.base_dir, 'phone_data')
            self._cache['phone_data'] = {}
            
            if os.path.exists(data_dir):
                for filename in os.listdir(data_dir):
                    if filename.endswith('.json'):
                        file_path = os.path.join(data_dir, filename)
                        dtype = filename.replace('.json', '')
                        with open(file_path, 'r', encoding='utf-8') as f:
                            self._cache['phone_data'][dtype] = json.load(f)
                self._loaded_files['phone_data'] = data_dir
        
        if data_type:
            return {data_type: self._cache['phone_data'].get(data_type, [])}
        return self._cache['phone_data']
    
    # ========== 通用操作方法 (支持所有文件类型) ==========
    
    def _get_file_config(self, data_type: DataType) -> Dict:
        """获取文件配置"""
        config_map = {
            DataType.DAILY_EVENT: self._file_configs['daily_event'],
            DataType.DAILY_DRAFT: self._file_configs['daily_draft'],
            DataType.PHONE_DATA: self._file_configs['phone_data']
        }
        return config_map.get(data_type, self._file_configs['daily_event'])
    
    def _get_data_key(self, data_type: DataType) -> str:
        """获取数据缓存的键名"""
        key_map = {
            DataType.DAILY_EVENT: 'daily_event',
            DataType.DAILY_DRAFT: 'daily_draft',
            DataType.PHONE_DATA: 'phone_data'
        }
        return key_map.get(data_type, 'unknown')
    
    def _load_generic_data(self, data_type: DataType, target_path: str = None) -> Any:
        """通用数据加载方法"""
        data_key = self._get_data_key(data_type)
        
        if data_key not in self._cache:
            if data_type == DataType.PHONE_DATA:
                data_dir = os.path.join(self.base_dir, 'phone_data')
                self._cache[data_key] = {}
                if os.path.exists(data_dir):
                    for filename in os.listdir(data_dir):
                        if filename.endswith('.json'):
                            dtype = filename.replace('.json', '')
                            file_path = os.path.join(data_dir, filename)
                            with open(file_path, 'r', encoding='utf-8') as f:
                                self._cache[data_key][dtype] = json.load(f)
                    self._loaded_files[data_key] = data_dir
            else:
                file_path = os.path.join(self.base_dir, f'{data_key}.json')
                if os.path.exists(file_path):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        self._cache[data_key] = json.load(f)
                    self._loaded_files[data_key] = file_path
                else:
                    self._cache[data_key] = [] if data_type != DataType.DAILY_DRAFT else {}
        
        return self._cache[data_key]
    
    # ========== daily_event 操作方法 ==========
    
    def _add_daily_event_direct(self, plan: OperationPlan) -> ExecutionResult:
        """添加日常事件 (直接添加，无需 LLM)"""
        events = self._load_daily_events()
            
        new_event = plan.params.get('event', {})
        if not new_event:
            return ExecutionResult(
                success=False, operation_type="add",
                data_type="daily_event", target_path=plan.target_path,
                message="未提供要添加的事件数据"
            )
        
        file_config = self._get_file_config(DataType.DAILY_EVENT)
        id_field = file_config['id_field']
        
        if id_field not in new_event:
            new_event[id_field] = self._generate_id(len(events))
        
        events.append(new_event)
        
        return ExecutionResult(
            success=True, operation_type="add",
            data_type="daily_event", target_path=plan.target_path,
            message=f"已添加事件：{new_event.get(id_field)}",
            data_after=new_event,
            affected_count=1
        )
    
    def _delete_daily_event_by_id(self, plan: OperationPlan) -> ExecutionResult:
        """删除日常事件 (按 event_id 定位)"""
        events = self._load_daily_events()
            
        event_id = plan.params.get('event_id')
        if not event_id:
            return ExecutionResult(
                success=False, operation_type="delete",
                data_type="daily_event", target_path=plan.target_path,
                message="删除 daily_event 必须提供 event_id"
            )
        
        found_idx = -1
        for idx, event in enumerate(events):
            if isinstance(event, dict) and event.get('event_id') == event_id:
                found_idx = idx
                break
        
        if found_idx == -1:
            return ExecutionResult(
                success=False, operation_type="delete",
                data_type="daily_event", target_path=plan.target_path,
                message=f"未找到 event_id 为 {event_id} 的事件"
            )
        
        return ExecutionResult(
            success=True, operation_type="delete",
            data_type="daily_event", target_path=plan.target_path,
            message=f"已删除事件：{event_id}",
            affected_count=1
        )
    
    def _update_daily_event_by_id(self, plan: OperationPlan) -> ExecutionResult:
        """更新日常事件（按 event_id 定位）"""
        events = self._load_daily_events()
        
        event_id = plan.params.get('event_id')
        updates = plan.params.get('updates', {})
        
        if not event_id:
            return ExecutionResult(
                success=False, operation_type="update",
                data_type="daily_event", target_path=plan.target_path,
                message="更新 daily_event 必须提供 event_id"
            )
        
        found_idx = -1
        for idx, event in enumerate(events):
            if isinstance(event, dict) and event.get('event_id') == event_id:
                found_idx = idx
                break
        
        if found_idx == -1:
            return ExecutionResult(
                success=False, operation_type="update",
                data_type="daily_event", target_path=plan.target_path,
                message=f"未找到 event_id 为 {event_id} 的事件"
            )
        
        # 直接更新指定字段
        for key, value in updates.items():
            events[found_idx][key] = value
        
        return ExecutionResult(
            success=True, operation_type="update",
            data_type="daily_event", target_path=plan.target_path,
            message=f"已更新事件：{event_id}",
            affected_count=1
        )
    
    def _query_daily_event_by_id(self, plan: OperationPlan) -> ExecutionResult:
        """查询日常事件（按 event_id 定位）"""
        events = self._load_daily_events()
        
        event_id = plan.params.get('event_id')
        print(f"[DEBUG] 查询 event_id: {event_id}, params: {plan.params}")
        
        if event_id:
            for event in events:
                if isinstance(event, dict) and event.get('event_id') == event_id:
                    return ExecutionResult(
                        success=True, operation_type="query",
                        data_type="daily_event", target_path=plan.target_path,
                        message=f"查询到事件：{event_id}",
                        data_after=event, affected_count=1
                    )
            return ExecutionResult(
                success=False, operation_type="query",
                data_type="daily_event", target_path=plan.target_path,
                message=f"未找到 event_id 为 {event_id} 的事件"
            )
        
        results = [e for e in events if self._match_condition(e, plan.params)]
        return ExecutionResult(
            success=True, operation_type="query",
            data_type="daily_event", target_path=plan.target_path,
            message=f"查询到 {len(results)} 条事件",
            data_after=results, affected_count=len(results)
        )
    
    def _whole_day_rewrite_daily_event(self, plan: OperationPlan) -> ExecutionResult:
        """按日期重写当日所有 daily_event 数据（基于 LLM 生成）"""
        import time
        from utils.llm_call import llm_call_j
        
        start_time = time.time()
        
        # 1. 获取目标日期
        target_date = plan.params.get('date') or plan.index_value
        if not target_date:
            return ExecutionResult(
                success=False, operation_type="whole_day_rewrite",
                data_type="daily_event", target_path=plan.target_path,
                message="重写 daily_event 必须提供日期",
                execution_time_ms=(time.time() - start_time) * 1000
            )
        
        # 2. 加载当日数据作为参考
        events = self._load_daily_events()
        reference_events = [e for e in events if isinstance(e, dict) and target_date in self._extract_dates_from_event(e)]
        
        # 3. 加载当日的 daily_draft 作为额外参考
        drafts = self._load_daily_drafts()
        reference_draft = drafts.get(target_date, {})
        
        # 4. 构建 LLM 输入
        rewrite_guidance = plan.params.get('guidance', plan.modification.get('guidance', ''))
        
        prompt = f"""
你是一个生活时间线编辑专家。请根据以下指导要求，重新生成 {target_date} 全天的日常事件数据。

## 原始指导要求
{rewrite_guidance}

## 当日原有事件参考（共 {len(reference_events)} 条）
{json.dumps(reference_events, ensure_ascii=False, indent=2) if reference_events else '无'}

## 当日草稿参考
{json.dumps(reference_draft, ensure_ascii=False, indent=2) if reference_draft else '无'}

## 输出要求
1. 生成 {target_date} 全天的完整事件列表
2. 确保事件之间的时间不冲突
3. 符合生活常识和逻辑
4. 每个事件必须包含以下字段：
   - event_id: 唯一标识符（格式：evt_日期_序号，如 evt_20250310_001）
   - date: 日期（YYYY-MM-DD）
   - name: 事件名称
   - description: 事件描述
   - location: 地点（可选）
   - participants: 参与人（可选，数组）
   - atomic_id: 若有没变动的事件，填写对应的原事件的atomic_id

5.格式和当日原有事件参考的格式一致。

## 输出格式
仅输出 JSON 数组，不要任何解释文字：

[
  {{
    "event_id": "evt_20250310_001",
    "date": "{target_date}",
    "name": "事件名称",
    "description": "事件描述",
    "start_time": "09:00",
    "end_time": "10:00",
    "location": "地点",
    "participants": ["人物 A", "人物 B"]
  }},
  ...
]
"""
        
        # 5. 调用 LLM 生成新的事件数据
        try:
            llm_output = llm_call_j(prompt)
            new_events = json.loads(llm_output)
            
            if not isinstance(new_events, list):
                return ExecutionResult(
                    success=False, operation_type="whole_day_rewrite",
                    data_type="daily_event", target_path=plan.target_path,
                    message="LLM 返回的数据不是数组格式",
                    execution_time_ms=(time.time() - start_time) * 1000
                )
            
            # 6. 删除原有当日事件并添加新生成的事件
            events_to_keep = [e for e in events if not (isinstance(e, dict) and target_date in self._extract_dates_from_event(e))]
            
            # 7. 为新生成的事件分配整数 event_id
            max_event_id = 0
            for e in events_to_keep:
                if isinstance(e, dict):
                    eid = e.get('event_id')
                    if isinstance(eid, int):
                        max_event_id = max(max_event_id, eid)
                    elif isinstance(eid, str):
                        try:
                            max_event_id = max(max_event_id, int(eid))
                        except ValueError:
                            pass
            
            # 为每个新事件分配递增的整数 ID
            for i, new_event in enumerate(new_events):
                if isinstance(new_event, dict):
                    new_event['event_id'] = max_event_id + i + 1
            
            events_to_keep.extend(new_events)
            
            # 8. 更新缓存中的数据
            self._cache['daily_event'] = events_to_keep
            
            print(f"[ExecutionAgent] ✓ 已重写 {target_date} 的事件：删除 {len(reference_events)} 条，新增 {len(new_events)} 条")
            
            return ExecutionResult(
                success=True, operation_type="whole_day_rewrite",
                data_type="daily_event", target_path=plan.target_path,
                message=f"已重写 {target_date} 全天事件：删除 {len(reference_events)} 条，新增 {len(new_events)} 条",
                data_before=reference_events,
                data_after=new_events,
                affected_count=len(new_events),
                execution_time_ms=(time.time() - start_time) * 1000
            )
            
        except json.JSONDecodeError as e:
            return ExecutionResult(
                success=False, operation_type="whole_day_rewrite",
                data_type="daily_event", target_path=plan.target_path,
                message=f"LLM 返回的 JSON 解析失败：{str(e)}",
                execution_time_ms=(time.time() - start_time) * 1000
            )
        except Exception as e:
            return ExecutionResult(
                success=False, operation_type="whole_day_rewrite",
                data_type="daily_event", target_path=plan.target_path,
                message=f"重写异常：{str(e)}",
                execution_time_ms=(time.time() - start_time) * 1000
            )
    
    # ========== phone_data 操作方法 ==========
    
    def _add_phone_data_direct(self, plan: OperationPlan) -> ExecutionResult:
        """添加手机数据（直接添加，无需 LLM）"""
        phone_data = self._load_phone_data()
        
        sub_type = plan.target_path.replace('phone_data/', '') if plan.target_path and plan.target_path.startswith('phone_data/') else None
        if not sub_type:
            sub_type = plan.params.get('sub_type', 'call')
        
        if sub_type not in phone_data:
            phone_data[sub_type] = []
        
        new_record = plan.params.get('record', {})
        if not new_record:
            return ExecutionResult(
                success=False, operation_type="add",
                data_type="phone_data", target_path=plan.target_path,
                message="未提供要添加的记录数据"
            )
        
        file_config = self._get_file_config(DataType.PHONE_DATA)
        id_field = file_config['id_field']
        
        if id_field not in new_record:
            new_record[id_field] = self._generate_id(len(phone_data[sub_type]))
        
        phone_data[sub_type].append(new_record)
        
        return ExecutionResult(
            success=True, operation_type="add",
            data_type="phone_data", target_path=plan.target_path,
            message=f"已添加记录到 {sub_type}: {new_record.get(id_field)}",
            data_after=new_record,
            affected_count=1
        )
    
    def _delete_phone_data_by_id(self, plan: OperationPlan) -> ExecutionResult:
        """删除手机数据（按 phone_id 定位）"""
        phone_data = self._load_phone_data()
        
        sub_type = plan.target_path.replace('phone_data/', '') if plan.target_path and plan.target_path.startswith('phone_data/') else None
        if not sub_type:
            sub_type = plan.params.get('sub_type', 'call')
        
        if sub_type not in phone_data:
            return ExecutionResult(
                success=False, operation_type="delete",
                data_type="phone_data", target_path=plan.target_path,
                message=f"子类型 {sub_type} 不存在"
            )
        
        data_before = copy.deepcopy(phone_data)
        records = phone_data[sub_type]
        phone_id = plan.params.get('phone_id')
        
        # 显式检查 None，允许 0 值
        if phone_id is None:
            return ExecutionResult(
                success=False, operation_type="delete",
                data_type="phone_data", target_path=plan.target_path,
                message="删除 phone_data 必须提供 phone_id"
            )
        
        found_idx = -1
        
        for idx, record in enumerate(records):
            if isinstance(record, dict) and record.get('phone_id') == phone_id:
                found_idx = idx
                break
        
        if found_idx == -1:
            return ExecutionResult(
                success=False, operation_type="delete",
                data_type="phone_data", target_path=plan.target_path,
                message=f"未找到 phone_id 为 {phone_id} 的记录"
            )
        
        records.pop(found_idx)
        
        return ExecutionResult(
            success=True, operation_type="delete",
            data_type="phone_data", target_path=plan.target_path,
            message=f"已删除记录：{phone_id}",
            data_before=data_before,
            data_after=copy.deepcopy(phone_data),
            affected_count=1
        )
    
    def _update_phone_data_by_id(self, plan: OperationPlan) -> ExecutionResult:
        """更新手机数据（按 phone_id 定位）"""
        phone_data = self._load_phone_data()
        
        sub_type = plan.target_path.replace('phone_data/', '') if plan.target_path and plan.target_path.startswith('phone_data/') else None
        if not sub_type:
            sub_type = plan.params.get('sub_type', 'call')
        
        if sub_type not in phone_data:
            return ExecutionResult(
                success=False, operation_type="update",
                data_type="phone_data", target_path=plan.target_path,
                message=f"子类型 {sub_type} 不存在"
            )
        
        records = phone_data[sub_type]
        # 只使用 phone_id，支持 0 值
        phone_id = plan.params.get('phone_id')
        
        print(f"[DEBUG] _update_phone_data: phone_id={phone_id}, type={type(phone_id)}")
        print(f"[DEBUG] _update_phone_data: plan.params={plan.params}")
        
        # 显式检查 None，允许 0 值
        if phone_id is None:
            return ExecutionResult(
                success=False, operation_type="update",
                data_type="phone_data", target_path=plan.target_path,
                message="更新 phone_data 必须提供 phone_id"
            )
        
        found_idx = -1
        
        for idx, record in enumerate(records):
            if isinstance(record, dict) and record.get('phone_id') == phone_id:
                found_idx = idx
                break
        
        if found_idx == -1:
            return ExecutionResult(
                success=False, operation_type="update",
                data_type="phone_data", target_path=plan.target_path,
                message=f"未找到 phone_id 为 {phone_id} 的记录"
            )
        
        # 直接更新指定字段
        updates = plan.params.get('updates', {})
        for key, value in updates.items():
            records[found_idx][key] = value
        
        return ExecutionResult(
            success=True, operation_type="update",
            data_type="phone_data", target_path=plan.target_path,
            message=f"已更新记录：{phone_id}",
            affected_count=1
        )
    
    def _query_phone_data_by_id(self, plan: OperationPlan) -> ExecutionResult:
        """查询手机数据（按 phone_id 定位）"""
        phone_data = self._load_phone_data()
        
        sub_type = plan.target_path.replace('phone_data/', '') if plan.target_path and plan.target_path.startswith('phone_data/') else None
        if not sub_type:
            sub_type = plan.params.get('sub_type', 'call')
        
        if sub_type not in phone_data:
            return ExecutionResult(
                success=False, operation_type="query",
                data_type="phone_data", target_path=plan.target_path,
                message=f"子类型 {sub_type} 不存在"
            )
        
        records = phone_data[sub_type]
        phone_id = plan.params.get('phone_id')
        
        if phone_id is None:
            return ExecutionResult(
                success=True, operation_type="query",
                data_type="phone_data", target_path=plan.target_path,
                message=f"查询到 {len(records)} 条 {sub_type} 记录",
                data_after=records, affected_count=len(records)
            )
        
        for record in records:
            if isinstance(record, dict) and record.get('phone_id') == phone_id:
                return ExecutionResult(
                    success=True, operation_type="query",
                    data_type="phone_data", target_path=plan.target_path,
                    message=f"查询到记录：{phone_id}",
                    data_after=record, affected_count=1
                )
        
        return ExecutionResult(
            success=False, operation_type="query",
            data_type="phone_data", target_path=plan.target_path,
            message=f"未找到 phone_id 为 {phone_id} 的记录"
        )
    
    # ========== 工具方法 ==========
    
    def _generate_id(self, existing_count: int) -> int:
        """生成唯一 ID（纯整数）"""
        return existing_count + 1
    
    def _update_daily_draft(self, plan: OperationPlan) -> ExecutionResult:
        """daily_draft 专用更新方法：处理月份嵌套结构"""
        drafts = self._load_daily_drafts()
        target_date = plan.params.get('date') or plan.params.get('draft_id')
        
        if not target_date:
            return ExecutionResult(
                success=False, operation_type="update",
                data_type="daily_draft", target_path=plan.target_path,
                message="未提供更新的日期"
            )
        
        found_month, found_idx, old_record = None, -1, None
        for month_key, month_data in drafts.items():
            if isinstance(month_data, list):
                for idx, record in enumerate(month_data):
                    if isinstance(record, dict) and record.get('date') == target_date:
                        found_month, found_idx, old_record = month_key, idx, record
                        break
                if found_month:
                    break
        
        if not found_month or not old_record:
            return ExecutionResult(
                success=False, operation_type="update",
                data_type="daily_draft", target_path=plan.target_path,
                message=f"未找到日期 {target_date} 的草稿"
            )
        
        updates = plan.params.get('updates', plan.params.get('modification', {}))
        for key, value in updates.items():
            old_record[key] = value
        drafts[found_month][found_idx] = old_record
        
        return ExecutionResult(
            success=True, operation_type="update",
            data_type="daily_draft", target_path=plan.target_path,
            message=f"已更新 {found_month} 中 {target_date} 的草稿",
            affected_count=1
        )
    
    def _query_daily_draft(self, plan: OperationPlan) -> ExecutionResult:
        """daily_draft 专用查询：支持月份 + 日期嵌套结构"""
        drafts = self._load_daily_drafts()
        draft_id = plan.params.get('draft_id')
        target_date = plan.params.get('date') or draft_id
        condition = plan.params.get('condition', plan.params)
        
        if not condition and not target_date:
            return ExecutionResult(
                success=True, operation_type="query",
                data_type="daily_draft", target_path=plan.target_path,
                message=f"查询到 {len(drafts)} 个月份的草稿",
                data_after=drafts, affected_count=len(drafts)
            )
        
        results = []
        if target_date:
            for month_data in drafts.values():
                if isinstance(month_data, list):
                    for record in month_data:
                        if isinstance(record, dict) and record.get('date') == target_date:
                            results.append(record)
                            break
            msg = f"查询到日期 {target_date} 的草稿" if results else f"未找到日期 {target_date} 的草稿"
            return ExecutionResult(
                success=bool(results), operation_type="query",
                data_type="daily_draft", target_path=plan.target_path,
                message=msg, data_after=results, affected_count=len(results)
            )
        
        for month_data in drafts.values():
            if isinstance(month_data, list):
                for record in month_data:
                    if self._match_condition(record, condition):
                        results.append(record)
        
        return ExecutionResult(
            success=True, operation_type="query",
            data_type="daily_draft", target_path=plan.target_path,
            message=f"查询到 {len(results)} 条匹配草稿",
            data_after=results, affected_count=len(results)
        )


    
    # ========== 工具方法 ==========
    
    def _extract_dates_from_event(self, event: Dict) -> List[str]:
        """从事件中提取所有日期（含 datetime 格式和带时间的范围）"""
        import re
        dates = []
        
        # 检查 date 字段（可能是字符串或列表）
        date_field = event.get("date", [])
        if isinstance(date_field, str):
            date_field = [date_field]
        
        if isinstance(date_field, list):
            for d in date_field:
                if not isinstance(d, str):
                    continue
                if "至" in d:
                    # 带时间的范围："2025-01-02 06:30:00 至 2025-01-02 09:00:00"
                    # 先提取两端的日期部分再展开
                    parts = d.split("至")
                    clean = [re.search(r'(\d{4}-\d{2}-\d{2})', p) for p in parts]
                    clean_dates = [m.group(1) for m in clean if m]
                    if len(clean_dates) == 2:
                        dates.extend(self._expand_date_range(
                            f"{clean_dates[0]}至{clean_dates[1]}"
                        ))
                    else:
                        dates.extend(clean_dates)
                else:
                    # 可能是 "2025-01-02" 或 "2025-01-02 08:00:00"
                    m = re.search(r'(\d{4}-\d{2}-\d{2})', d)
                    if m:
                        dates.append(m.group(1))
        
        return dates
    
    def _expand_date_range(self, date_range: str) -> List[str]:
        """展开日期范围"""
        from datetime import datetime, timedelta
        if "至" not in date_range:
            return [date_range]
        
        try:
            start_str, end_str = date_range.split("至")
            start = datetime.strptime(start_str.strip(), "%Y-%m-%d")
            end = datetime.strptime(end_str.strip(), "%Y-%m-%d")
            
            dates = []
            current = start
            while current <= end:
                dates.append(current.strftime("%Y-%m-%d"))
                current += timedelta(days=1)
            return dates
        except ValueError:
            return [date_range]
    
    def _match_condition(self, data: Dict, condition: Dict) -> bool:
        """检查数据是否匹配条件"""
        for key, value in condition.items():
            if key not in data or data[key] != value:
                return False
        return True