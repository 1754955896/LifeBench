/* Offline LifeBench viewer. No network requests or external dependencies. */
"use strict";
const TYPE_NAMES = {sms:"短信",call:"通话",calendar:"日程",note:"笔记",photo:"照片",push:"通知",agent_chat:"AI 对话",fitness_health:"运动健康",contact:"通讯录"};
// Inline SVG keeps type icons consistent and available offline.
const ICON_PATHS = {
  message:'<path d="M21 11.5a8.5 8.5 0 0 1-8.5 8.5H4l-2 2V11.5a9.5 9.5 0 0 1 19 0Z"/><path d="M7 9h9M7 13h6"/>',
  phone:'<path d="m7 3 3 5-3 3a16 16 0 0 0 6 6l3-3 5 3-1 4C10 22 2 14 3 4Z"/>',
  calendar:'<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4m10-4v4M3 11h18M7 15h3m4 0h3"/>',
  note:'<path d="M14 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-9M8 16l1-4L18 3l3 3-9 9-4 1Z"/>',
  camera:'<path d="m8 5 2-2h4l2 2h4a2 2 0 0 1 2 2v12H2V7a2 2 0 0 1 2-2Z"/><circle cx="12" cy="12" r="4"/>',
  bell:'<path d="M18 8a6 6 0 0 0-12 0c0 7-3 8-3 8h18s-3-1-3-8M9 20h6"/>',
  bot:'<rect x="4" y="6" width="16" height="14" rx="4"/><path d="M12 2v4M1 11v5m22-5v5M8 11v2m8-2v2m-7 4h6"/>',
  heart:'<path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0l-1 1-1-1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z"/>',
  contact:'<rect x="4" y="3" width="17" height="18" rx="2"/><circle cx="12" cy="9" r="2"/><path d="M8 17a4 4 0 0 1 8 0M2 7h3m-3 5h3m-3 5h3"/>',
  home:'<path d="m3 10 9-7 9 7v11h-6v-7H9v7H3V10Z"/>',
  briefcase:'<rect x="3" y="7" width="18" height="14" rx="2"/><path d="M8 7V3h8v4M3 12a23 23 0 0 0 18 0m-9 0v4"/>',
  book:'<path d="M12 5C9 3 5 3 2 4v16c3-1 7-1 10 1 3-2 7-2 10-1V4c-3-1-7-1-10 1Zm0 0v16"/>',
  people:'<circle cx="9" cy="7" r="3"/><path d="M2 21v-3a7 7 0 0 1 14 0v3M17 4a3 3 0 0 1 0 6m2 4a5 5 0 0 1 3 4v3"/>',
  wallet:'<path d="M20 7V3H5a3 3 0 0 0 0 6h16v12H5a3 3 0 0 1-3-3V6m19 7h-6v4h6"/>',
  leaf:'<path d="M20 3C9 2 2 7 4 14s16 7 16-11ZM4 21 16 9"/>',
  bolt:'<path d="m13 2-9 12h7l-1 8L21 9h-8l1-7Z"/>',
  grid:'<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>'
};
const PHONE_STYLES = {sms:["green","message"],call:["blue","phone"],calendar:["indigo","calendar"],note:["amber","note"],photo:["purple","camera"],push:["orange","bell"],agent_chat:["teal","bot"],fitness_health:["rose","heart"],contact:["slate","contact"]};
const EVENT_STYLES = {personallife:["green","leaf"],familylivingsituation:["amber","home"],family:["amber","home"],homelivingsituation:["amber","home"],career:["blue","briefcase"],health:["rose","heart"],relationships:["purple","people"],education:["indigo","book"],finance:["teal","wallet"],unexpectedevents:["orange","bolt"],other:["slate","grid"]};
function typeStyle(type, kind = "phone") { return (kind === "event" ? EVENT_STYLES[String(type).toLowerCase().replace(/[^a-z]/g,"")] : PHONE_STYLES[type]) || ["slate","grid"]; }
function typeBadge(type, kind = "phone") {
  const [color, icon] = typeStyle(type, kind);
  return `<span class="tag type-badge tone-${color}"><svg class="type-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICON_PATHS[icon]}</svg>${esc(kind === "phone" ? TYPE_NAMES[type] || type : type || "生活事件")}</span>`;
}
const LABELS = {title:"标题",description:"描述",content:"内容",message_content:"短信内容",contactName:"联系人",phoneNumber:"电话号码",datetime:"记录时间",datetime_end:"结束时间",start_time:"开始时间",end_time:"结束时间",date:"日期",caption:"照片描述",location:"地点",conversation:"对话",user:"用户",assistant:"助手",action:"动作",source:"来源",message_type:"收发类型",direction:"通话方向（原始值）",call_result:"通话结果",summarized_info:"摘要",event_id:"原子事件 ID",daily_event_id:"关联日常事件 ID",phone_id:"手机记录 ID",faceRecognition:"人脸识别",imageTag:"图片标签",ocrText:"文字识别",shoot_mode:"拍摄模式",image_size:"图片尺寸",push_status:"通知状态",jump_path:"跳转路径",name:"姓名",relation:"关系"};
const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const textValue = value => typeof value === "object" && value !== null ? JSON.stringify(value) : String(value ?? "");
const asArray = value => Array.isArray(value) ? value : value == null ? [] : [value];
function dateKey(value) { const m = String(value ?? "").match(/(\d{4})[-/](\d{2})[-/](\d{2})/); return m ? `${m[1]}-${m[2]}-${m[3]}` : ""; }
function eventDates(event) {
  const days = new Set();
  for (const range of asArray(event.date)) {
    const matches = [...String(range).matchAll(/\d{4}[-/]\d{2}[-/]\d{2}/g)].map(m => dateKey(m[0]));
    if (!matches.length) continue;
    days.add(matches[0]);
    if (matches.length > 1 && matches[1] > matches[0]) {
      const end = Date.parse(matches[1] + "T00:00:00Z");
      for (let t = Date.parse(matches[0] + "T00:00:00Z") + 86400000; t <= end; t += 86400000) days.add(new Date(t).toISOString().slice(0,10));
    }
  }
  return [...days];
}
function recordDate(record) { return dateKey(record.datetime || record.date || record["日期"] || record.start_time); }
function buildModel(events, sources) {
  if (!Array.isArray(events)) throw new Error("daily_event.json 顶层必须是数组。");
  if (events.some(e => !e || typeof e !== "object" || Array.isArray(e) || e.event_id == null || !eventDates(e).length)) throw new Error("daily_event.json 中存在缺少 event_id 或有效 date 的事件。");
  const byDay = new Map(), byId = new Map(), linked = new Map(), extras = new Map(), records = [], warnings = [];
  for (const e of events) {
    const id = String(e.event_id);
    if (byId.has(id)) throw new Error(`发现重复 event_id：${id}，无法可靠关联手机记录。`);
    byId.set(id, e);
    for (const day of eventDates(e)) { if (!byDay.has(day)) byDay.set(day, []); byDay.get(day).push(e); }
  }
  let undated = 0, orphaned = 0;
  for (const {type, data, file} of sources) {
    if (!Array.isArray(data)) { warnings.push(`${file}：顶层不是数组，已跳过。`); continue; }
    for (const raw of data) {
      if (!raw || typeof raw !== "object" || Array.isArray(raw)) { warnings.push(`${file}：跳过非对象记录。`); continue; }
      const record = {raw, type, file}; records.push(record);
      const ids = [...new Set(asArray(raw.daily_event_id).filter(x => x != null && String(x).trim() !== "").map(String))];
      const valid = ids.filter(id => byId.has(id));
      if (ids.some(id => !byId.has(id))) orphaned++;
      if (valid.length) for (const id of valid) { if (!linked.has(id)) linked.set(id, []); linked.get(id).push(record); }
      else { const day = recordDate(raw); if (day) { if (!extras.has(day)) extras.set(day, []); extras.get(day).push(record); } else undated++; }
    }
  }
  for (const values of byDay.values()) values.sort((a,b) => String(asArray(a.date)[0]).localeCompare(String(asArray(b.date)[0])));
  if (orphaned) warnings.push(`${orphaned} 条手机记录引用了不存在的 daily_event_id；无有效关联的记录按自身日期展示。`);
  if (undated) warnings.push(`${undated} 条记录既无有效事件关联，也无日期（例如通讯录），不归入某一天。`);
  return {events, byDay, byId, linked, extras, records, warnings, dates:[...new Set([...byDay.keys(), ...extras.keys()])].sort()};
}
function formatFields(value, depth = 0) {
  if (value === null || value === undefined || value === "") return '<span class="muted">—</span>';
  if (typeof value !== "object") return esc(value);
  if (depth > 5) return esc(JSON.stringify(value, null, 2));
  if (Array.isArray(value) && value.every(v => v === null || typeof v !== "object")) return value.map(esc).join(" · ") || "—";
  return `<dl class="fields${depth ? " nested" : ""}">${Object.entries(value).map(([key,val]) => `<div class="field"><dt>${esc(LABELS[key] || key)}</dt><dd>${formatFields(val, depth + 1)}</dd></div>`).join("")}</dl>`;
}
function rawDetails(raw) { return `<details class="raw"><summary>查看原始 JSON</summary><pre>${esc(JSON.stringify(raw, null, 2))}</pre></details>`; }
function recordHTML(record) {
  const {raw, type, file} = record;
  const fields = Object.fromEntries(Object.entries(raw).filter(([key]) => !["type","phone_id","daily_event_id"].includes(key)));
  return `<article class="phone-record tone-${typeStyle(type)[0]}"><div class="record-head">${typeBadge(type)}<span>${esc(raw.datetime || raw.date || raw["日期"] || raw.start_time || "无时间")}</span><span class="record-id">${esc(file)} · #${esc(raw.phone_id ?? "—")}</span></div>${formatFields(fields)}${rawDetails(raw)}</article>`;
}
if (typeof module !== "undefined" && module.exports) module.exports = {buildModel, eventDates, recordDate, esc, recordHTML};
if (typeof document !== "undefined") {
  const $ = id => document.getElementById(id);
  let model = null, selectedDate = "", month = "", expanded = false;
  const displayStatus = (message, error = false) => { $("status").hidden = !message; $("status").textContent = message; $("status").className = error ? "error" : ""; };
  const chooseFolder = () => $("folderInput").click();
  $("folderButton").onclick = chooseFolder; $("welcomeButton").onclick = chooseFolder;
  $("folderInput").onchange = async event => {
    const files = [...event.target.files]; if (!files.length) return;
    $("folderButton").disabled = true; displayStatus("正在读取人物数据并建立事件关联…");
    try {
      const pathOf = f => (f.webkitRelativePath || f.name).replace(/\\/g,"/");
      const dailyFiles = files.filter(f => f.name.toLowerCase() === "daily_event.json");
      if (dailyFiles.length !== 1) throw new Error(dailyFiles.length ? "发现多个人物，请选择单个人物的文件夹。" : "未找到 daily_event.json，请选择人物数据文件夹。");
      const dailyFile = dailyFiles[0], base = pathOf(dailyFile).slice(0,-dailyFile.name.length);
      const readJSON = async f => JSON.parse((await f.text()).replace(/^\uFEFF/,""));
      const sources = [], warnings = [];
      const events = await readJSON(dailyFile);
      const phoneFiles = files.filter(f => pathOf(f).startsWith(base + "phone_data/") && /\.json$/i.test(f.name));
      for (const file of phoneFiles) {
        try { sources.push({type:file.name.replace(/\.json$/i,""), file:file.name, data:await readJSON(file)}); }
        catch (error) { warnings.push(`${file.name} 读取失败：${error.message}`); }
      }
      let persona = {};
      const personaFile = files.find(f => pathOf(f) === base + "persona.json");
      if (personaFile) { try { persona = await readJSON(personaFile) || {}; } catch { warnings.push("persona.json 读取失败，使用文件夹名称。"); } }
      const next = buildModel(events, sources); next.warnings.push(...warnings);
      if (!phoneFiles.length) next.warnings.push("没有找到 phone_data/*.json，仅展示生活事件。");
      model = next; const folder = base.split("/").filter(Boolean).pop() || "人物数据";
      const name = persona.name || folder;
      $("profile").innerHTML = `<div class="avatar">${esc(String(name).slice(0,1))}</div><div><strong>${esc(name)}</strong><small>${esc(persona.job || persona.occupation || folder)}</small></div>`;
      $("datasetStats").textContent = `${folder} · ${model.dates.length} 天 / ${model.events.length.toLocaleString()} 个事件 / ${model.records.length.toLocaleString()} 条手机记录`;
      $("typeFilter").innerHTML = '<option value="">全部手机类型</option>' + [...new Set(model.records.map(r => r.type))].map(t => `<option value="${esc(t)}">${esc(TYPE_NAMES[t] || t)}</option>`).join("");
      $("search").value = ""; expanded = false;
      for (const id of ["search","typeFilter","dateInput","expandAll"]) $(id).disabled = false;
      $("diagnostics").hidden = !model.warnings.length;
      $("diagnosticsBody").innerHTML = model.warnings.map(w => `<p>${esc(w)}</p>`).join("");
      selectDate(model.dates[0] || new Date().toISOString().slice(0,10));
      displayStatus(model.warnings.length ? `已载入 ${name} 的数据；有 ${model.warnings.length} 项载入说明，可在页面底部查看。` : "");
    } catch (error) { displayStatus(`载入失败：${error.message}${model ? " 原有数据仍保留。" : ""}`, true); }
    finally { $("folderButton").disabled = false; $("folderInput").value = ""; }
  };
  function selectDate(date) { selectedDate = date; month = date.slice(0,7); $("dateInput").value = date; renderCalendar(); renderDay(); }
  function renderCalendar() {
    if (!month) return;
    const [year,m] = month.split("-").map(Number), first = new Date(year,m-1,1), count = new Date(year,m,0).getDate();
    $("monthTitle").textContent = `${year} 年 ${m} 月`;
    let html = "<span></span>".repeat((first.getDay()+6)%7);
    for (let day=1;day<=count;day++) { const date = `${month}-${String(day).padStart(2,"0")}`; html += `<button data-date="${date}" aria-label="${date}${model?.byDay.has(date) ? ' 有生活事件' : ''}" aria-pressed="${date === selectedDate}" class="${model?.byDay.has(date) ? "has-data " : ""}${date === selectedDate ? "selected" : ""}">${day}</button>`; }
    $("calendar").innerHTML = html;
  }
  $("calendar").onclick = e => { const date = e.target.closest("button")?.dataset.date; if (date && model) selectDate(date); };
  for (const [id,delta] of [["prevMonth",-1],["nextMonth",1]]) $(id).onclick = () => { if (!month) return; const [y,m] = month.split("-").map(Number); const date = new Date(y,m-1+delta,1); month = `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,"0")}`; renderCalendar(); };
  $("dateInput").onchange = e => { if (e.target.value) selectDate(e.target.value); };
  $("prevDay").onclick = () => { const day = model.dates.filter(d => d < selectedDate).at(-1); if(day) selectDate(day); };
  $("nextDay").onclick = () => { const day = model.dates.find(d => d > selectedDate); if(day) selectDate(day); };
  $("search").oninput = renderDay; $("typeFilter").onchange = renderDay;
  $("expandAll").onclick = () => { expanded = !expanded; document.querySelectorAll("details.phone-group").forEach(d => d.open = expanded); $("expandAll").textContent = expanded ? "收起全部手机记录" : "展开全部手机记录"; };
  function renderDay() {
    if (!model) return;
    const events = model.byDay.get(selectedDate) || [], extras = model.extras.get(selectedDate) || [];
    const phonesForDay = e => (model.linked.get(String(e.event_id)) || []).filter(r => recordDate(r.raw) === selectedDate);
    const records = [...new Set(events.flatMap(phonesForDay))];
    const day = new Date(selectedDate + "T12:00:00");
    $("dayTitle").textContent = `${day.getFullYear()} 年 ${day.getMonth()+1} 月 ${day.getDate()} 日`;
    $("daySubtitle").textContent = `${new Intl.DateTimeFormat("zh-CN",{weekday:"long"}).format(day)} · 记录生活的细节，读懂一天的轨迹`;
    for (const [id,value] of [["eventCount",events.length],["phoneCount",records.length],["typeCount",new Set(records.map(r => r.type)).size],["extraCount",extras.length]]) $(id).textContent = value;
    $("prevDay").disabled = !model.dates.some(d => d < selectedDate); $("nextDay").disabled = !model.dates.some(d => d > selectedDate);
    const query = $("search").value.trim().toLowerCase(), type = $("typeFilter").value;
    const matches = r => (!type || r.type === type) && (!query || JSON.stringify(r.raw).toLowerCase().includes(query));
    const shown = events.filter(e => { const phones = phonesForDay(e); return (!type || phones.some(r => r.type === type)) && (!query || JSON.stringify(e).toLowerCase().includes(query) || phones.some(matches)); });
    $("visibleCount").textContent = `${shown.length} / ${events.length} 个事件`;
    $("expandAll").textContent = expanded ? "收起全部手机记录" : "展开全部手机记录";
    $("timeline").innerHTML = shown.map(e => {
      const all = phonesForDay(e), phones = all.filter(r => !type || r.type === type);
      const time = String(asArray(e.date)[0]).match(/\d{2}:\d{2}/)?.[0] || "全天";
      const types = [...new Set(phones.map(r => r.type))];
      return `<article class="event tone-${typeStyle(e.type, "event")[0]}"><div class="time">${esc(time)}</div><div class="event-card"><div class="event-content"><div class="event-top"><span class="tag">${esc(e.type || "生活事件")}</span><span class="event-id">EVENT #${esc(e.event_id)}</span></div><h3>${esc(e.name || "未命名事件")}</h3><p class="description">${esc(e.description)}</p><div class="meta"><span>◷ ${asArray(e.date).map(esc).join(" / ")}</span><span>⌖ ${esc(textValue(e.location))}</span><span>♧ ${esc(asArray(e.participant).map(p => typeof p === "object" && p !== null ? `${p.name || ""}${p.relation ? `（${p.relation}）` : ""}` : String(p)).join("、"))}</span></div>${rawDetails(e)}</div>${phones.length ? `<details class="phone-group"${expanded ? " open" : ""}><summary>手机数据 <b>${phones.length}</b><span class="source-badges">${types.map(t => typeBadge(t)).join("")}</span></summary><div class="phone-list">${phones.map(recordHTML).join("")}</div></details>` : '<div class="no-phone">暂无通过 daily_event_id 关联的手机记录</div>'}</div></article>`;
    }).join("") || `<div class="empty">${events.length ? "没有符合筛选条件的事件，试试其他关键词或类型。" : "这一天没有 daily event 数据，可切换其他日期。"}</div>`;
    const shownExtras = extras.filter(matches);
    $("extras").hidden = !extras.length;
    $("extras").innerHTML = `<h2>当日未关联记录 <span class="tag">${shownExtras.length} / ${extras.length}</span></h2><p>按手机记录自身日期展示；缺少或无效的 daily_event_id 不会自动匹配到生活事件。</p>${shownExtras.map(r => `<details class="phone-group"><summary>${esc(TYPE_NAMES[r.type] || r.type)} · ${esc(r.raw.title || r.raw.datetime || r.raw.date || r.raw["日期"] || "记录")} <span class="source-badges">${esc(r.raw.daily_event_id == null ? "缺少关联 ID" : "未找到对应事件")}</span></summary>${recordHTML(r)}</details>`).join("") || '<p class="empty">没有符合筛选条件的未关联记录。</p>'}`;
  }
}
