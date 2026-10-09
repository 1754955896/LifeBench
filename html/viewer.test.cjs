"use strict";
const {test} = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const {buildModel,eventDates,recordHTML} = require("./app.js");
const event = (id,date="2025-01-01 23:30:00至2025-01-02 00:30:00") => ({event_id:id,date:[date],name:"测试事件"});
test("exact ID join accepts zero, deduplicates array IDs, and never joins on atomic event_id", () => {
  const m = buildModel([event(0),event("1")],[{type:"sms",file:"sms.json",data:[
    {daily_event_id:"0",datetime:"2025-02-01",phone_id:0},
    {daily_event_id:[1,"1","0"],phone_id:1},
    {event_id:["0"],datetime:"2025-01-01",phone_id:2},
    {daily_event_id:"missing",datetime:"2025-01-01",phone_id:3},
    {name:"无日期联系人"}
  ]}]);
  assert.equal(m.linked.get("0").length,2);
  assert.equal(m.linked.get("1").length,1);
  assert.equal(m.extras.get("2025-01-01").length,2);
  assert.equal(m.warnings.length,2);
  assert.equal(m.byDay.get("2025-01-02").length,2);
});
test("cross-day, multiple intervals, empty input and invalid event files", () => {
  assert.deepEqual(eventDates({date:["2025-01-31 23:00:00至2025-02-02 01:00:00","2025-02-02 10:00:00至2025-02-02 11:00:00"]}),["2025-01-31","2025-02-01","2025-02-02"]);
  assert.deepEqual(buildModel([],[]).dates,[]);
  assert.throws(()=>buildModel({},[]),/数组/);
  assert.throws(()=>buildModel([event(1),event("1")],[]),/重复/);
  assert.throws(()=>buildModel([{event_id:1}],[]),/有效 date/);
});
test("all rendered data is escaped including nested conversations and raw JSON", () => {
  const html = recordHTML({type:"<img onerror=alert(1)>",file:"x.json",raw:{title:"<script>alert(1)</script>",conversation:{user:{content:'<img src=x onerror="alert(1)">'}}}});
  assert.ok(!html.includes("<script>")); assert.ok(!html.includes("<img"));
  assert.ok(html.includes("&lt;script&gt;")); assert.ok(html.includes("&quot;"));
});
const dataDir = path.resolve(__dirname,"../life_bench_data/version2/data/sunyuwei");
test("full Sun Yuwei dataset agrees with an independent exact-ID lookup", {skip:!fs.existsSync(dataDir)}, () => {
  const events=JSON.parse(fs.readFileSync(path.join(dataDir,"daily_event.json"),"utf8"));
  const sources=fs.readdirSync(path.join(dataDir,"phone_data")).filter(f=>f.endsWith(".json")).map(file=>({file,type:file.slice(0,-5),data:JSON.parse(fs.readFileSync(path.join(dataDir,"phone_data",file),"utf8"))}));
  const model=buildModel(events,sources), all=sources.flatMap(s=>s.data);
  assert.equal(model.events.length,5716); assert.equal(model.records.length,4945); assert.equal(model.dates.length,365);
  for (const e of events) {
    const expected=all.filter(r=>r.daily_event_id != null && String(r.daily_event_id)===String(e.event_id));
    assert.deepEqual((model.linked.get(String(e.event_id)) || []).map(r=>r.raw),expected);
  }
});
test("page load, date changes, content search, type filter and failed reload preserve data", async () => {
  const elements = new Map();
  const get = id => { if(!elements.has(id)) elements.set(id,{value:"",textContent:"",innerHTML:"",disabled:false,hidden:false,click(){}}); return elements.get(id); };
  const document={getElementById:get,querySelectorAll:()=>[]};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,"app.js"),"utf8"),{document,Intl,Date,console});
  const file=(name,value)=>({name:name.split("/").at(-1),webkitRelativePath:`demo/${name}`,text:async()=>JSON.stringify(value)});
  const files=[file("daily_event.json",[{...event(1,"2025-01-01 08:00:00至2025-01-01 09:00:00"),name:"早餐"},{...event(2,"2025-01-02 12:00:00至2025-01-02 13:00:00"),name:"午餐"}]),file("phone_data/sms.json",[{daily_event_id:1,datetime:"2025-01-01 08:30:00",message_content:"搜索独有内容"},{daily_event_id:1,datetime:"2025-01-02 08:30:00",message_content:"跨日隐藏内容"},{daily_event_id:1,message_content:"无日期隐藏内容"}]),file("phone_data/note.json",[{daily_event_id:2,datetime:"2025-01-02 12:30:00",title:"午餐笔记"},{daily_event_id:1,datetime:"2025-01-02 12:00:00",title:"异日笔记"}]),file("persona.json",{name:"测试人物"})];
  await get("folderInput").onchange({target:{files}});
  assert.equal(get("eventCount").textContent,1); assert.equal(get("phoneCount").textContent,1);
  assert.ok(get("timeline").innerHTML.includes("早餐")); assert.ok(get("profile").innerHTML.includes("测试人物"));
  assert.ok(!get("timeline").innerHTML.includes("跨日隐藏内容"));
  assert.ok(!get("timeline").innerHTML.includes("无日期隐藏内容"));
  assert.equal(get("typeCount").textContent,1);
  get("search").value="跨日隐藏内容"; get("search").oninput(); assert.ok(get("timeline").innerHTML.includes("没有符合筛选条件"));
  get("search").value="搜索独有内容"; get("search").oninput(); assert.ok(get("timeline").innerHTML.includes("早餐"));
  get("search").value="不存在关键词"; get("search").oninput(); assert.ok(get("timeline").innerHTML.includes("没有符合筛选条件"));
  get("search").value=""; get("typeFilter").value="note"; get("typeFilter").onchange(); assert.ok(get("timeline").innerHTML.includes("没有符合筛选条件"));
  get("nextDay").onclick(); assert.ok(get("timeline").innerHTML.includes("午餐笔记")); assert.equal(get("dateInput").value,"2025-01-02");
  await get("folderInput").onchange({target:{files:[file("daily_event.json",{})]}});
  assert.ok(get("status").textContent.includes("载入失败")); assert.ok(get("timeline").innerHTML.includes("午餐笔记"));
  get("dateInput").onchange({target:{value:"2025-06-01"}}); assert.equal(get("eventCount").textContent,0);
  assert.ok(get("timeline").innerHTML.includes("没有 daily event"));
});
