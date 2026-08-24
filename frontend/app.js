/* 多智能体小说生成引擎 - Web 工作台 */

const state = {
  novels: [],
  novel: null,      // 当前小说详情
  tab: "blueprint",
  busy: false,
  expandedChapter: null,  // 片段重写后保持章节展开
  pending: [],      // 待确认提案（仅定稿后产生；确认后入正式库）
  activeJobId: null,  // 正在轮询的后台任务（写章/定稿）
  cocreateStream: null,  // null=未知；true=思考+流式；false=整包共创（无思考 UI）
};

const segmentPick = { chapterNo: null, text: "" };

/* ================= API 基础 ================= */

async function api(method, path, body) {
  const resp = await fetch(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.detail || `请求失败 (${resp.status})`);
  }
  return resp.json();
}

/* SSE over POST：解析 event/data 流并回调 */
async function sse(path, body, handlers) {
  const resp = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : "{}",
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.detail || `请求失败 (${resp.status})`);
  }
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx;
    while ((idx = buffer.indexOf("\n\n")) >= 0) {
      const chunk = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      let event = "message", data = {};
      for (const line of chunk.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) {
          try { data = JSON.parse(line.slice(5).trim()); } catch { /* ignore */ }
        }
      }
      if (handlers[event]) handlers[event](data);
    }
  }
}

/* ================= 进度面板 ================= */

const progress = {
  _timer: null,
  _startedAt: 0,
  _currentStep: null,

  show(title) {
    document.getElementById("progress-panel").classList.remove("hidden");
    document.getElementById("progress-steps").innerHTML = "";
    const log = document.getElementById("progress-log");
    log.innerHTML = "";
    this._startedAt = Date.now();
    this._currentStep = null;
    this._ensureLiveCard(title);
    this._startTimer();
    this.log(`▶ ${title}`);
  },
  _ensureLiveCard(title) {
    let card = document.getElementById("live-pipeline");
    if (!card) {
      const host = document.getElementById("tab-content");
      if (!host) return;
      card = document.createElement("div");
      card.id = "live-pipeline";
      card.className = "card live-pipeline";
      host.prepend(card);
    }
    card.classList.remove("hidden");
    card.innerHTML = `
      <h3>⚙️ ${title || "生成进度"}</h3>
      <p class="muted" id="live-pipeline-status">已启动，等待步骤清单…</p>
      <p class="muted" id="live-pipeline-elapsed">已用时 0 秒</p>
      <ul id="live-pipeline-steps"></ul>`;
  },
  _startTimer() {
    if (this._timer) clearInterval(this._timer);
    this._timer = setInterval(() => {
      const sec = Math.floor((Date.now() - this._startedAt) / 1000);
      const el = document.getElementById("live-pipeline-elapsed");
      if (el) el.textContent = `已用时 ${sec} 秒` + (this._currentStep ? ` · 当前：${this._currentStep}` : "");
      const running = document.querySelectorAll("#progress-steps li.running, #live-pipeline-steps li.running");
      running.forEach(li => {
        const base = li.dataset.label || li.textContent.replace(/^\S+\s/, "").replace(/\s·.*$/, "");
        li.dataset.label = li.dataset.label || base;
        const tip = li.querySelector(".step-elapsed") || document.createElement("span");
        tip.className = "step-elapsed muted";
        tip.textContent = ` · ${sec}s`;
        if (!tip.parentNode) li.appendChild(tip);
      });
    }, 1000);
  },
  _stopTimer() {
    if (this._timer) { clearInterval(this._timer); this._timer = null; }
  },
  setSteps(steps) {
    const html = steps.map(s =>
      `<li id="step-${s.id}" data-label="${s.label}">${s.label}</li>`).join("");
    const ul = document.getElementById("progress-steps");
    ul.innerHTML = html;
    const live = document.getElementById("live-pipeline-steps");
    if (live) {
      live.innerHTML = steps.map(s =>
        `<li id="live-step-${s.id}" data-label="${s.label}">${s.label}</li>`).join("");
    }
    const status = document.getElementById("live-pipeline-status");
    if (status) status.textContent = `共 ${steps.length} 步，等待开始…`;
  },
  stepStart(id, label, index, total) {
    this._currentStep = label || id;
    const mark = (li) => {
      if (!li) return;
      document.querySelectorAll(`#${li.parentElement.id} li.running`).forEach(x => x.classList.remove("running"));
      li.classList.remove("done");
      li.classList.add("running");
      li.dataset.label = label || li.dataset.label || id;
      li.innerHTML = `… ${label || li.dataset.label}`;
    };
    mark(document.getElementById(`step-${id}`));
    mark(document.getElementById(`live-step-${id}`));
    const status = document.getElementById("live-pipeline-status");
    if (status) {
      status.textContent = index && total
        ? `正在进行 ${index}/${total}：${label || id}`
        : `正在进行：${label || id}`;
    }
    this.log(`… ${index && total ? `[${index}/${total}] ` : ""}${label || id}`);
  },
  stepDone(id, label) {
    const finish = (li) => {
      if (!li) return;
      li.classList.remove("running");
      li.classList.add("done");
      li.innerHTML = `✓ ${label || li.dataset.label || id}`;
    };
    finish(document.getElementById(`step-${id}`));
    finish(document.getElementById(`live-step-${id}`));
    this.log(`✓ ${label || id}`);
  },
  log(msg, isErr = false) {
    const log = document.getElementById("progress-log");
    const div = document.createElement("div");
    div.textContent = `${new Date().toLocaleTimeString()} ${msg}`;
    if (isErr) div.className = "err";
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
    const status = document.getElementById("live-pipeline-status");
    if (status && !isErr && msg && !msg.startsWith("▶")) status.textContent = msg;
  },
  actionLine(html) {
    const log = document.getElementById("progress-log");
    const div = document.createElement("div");
    div.innerHTML = html;
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
  },
  setCancelVisible(show) {
    const btn = document.getElementById("job-cancel");
    if (btn) btn.classList.toggle("hidden", !show);
  },
  finish(ok) {
    this._stopTimer();
    this._currentStep = null;
    const status = document.getElementById("live-pipeline-status");
    if (status) status.textContent = ok ? "✅ 全部完成" : "已结束（见右侧日志）";
  },
};

/* 通用：跑一个 SSE 任务并在完成后刷新当前小说 */
async function runTask(title, path, body) {
  if (state.busy) { alert("已有任务进行中，请等待完成"); return false; }
  state.busy = true;
  progress.show(title);
  progress.log("已发送请求，等待服务端推送步骤…");
  let ok = false;
  try {
    await sse(path, body, {
      steps: d => progress.setSteps(d.steps || []),
      step_start: d => progress.stepStart(d.id, d.label, d.index, d.total),
      step_done: d => {
        progress.stepDone(d.id, d.label);
        if (d.payload?.impacted?.length) logImpact(d.payload.impacted);
      },
      log: d => progress.log(d.message || ""),
      done: () => { ok = true; progress.log("✅ 完成"); },
      error: d => progress.log(`❌ ${d.message}`, true),
    });
  } catch (e) {
    progress.log(`❌ ${e.message}`, true);
  } finally {
    progress.finish(ok);
    state.busy = false;
  }
  if (state.novel) await ui.openNovel(state.novel.id, true);
  return ok;
}

/* ================= 后台任务（jobs 队列） ================= */

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function renderJobEvent(entry) {
  const d = entry.data || {};
  switch (entry.event) {
    case "steps": progress.setSteps(d.steps || []); break;
    case "step_start": progress.stepStart(d.id, d.label, d.index, d.total); break;
    case "step_done":
      progress.stepDone(d.id, d.label);
      if (d.payload?.impacted?.length) logImpact(d.payload.impacted);
      break;
    case "log": progress.log(d.message || ""); break;
    case "done": progress.log("✅ 完成"); progress.finish(true); break;
    case "error": progress.log(`❌ ${d.message || "未知错误"}`, true); progress.finish(false); break;
  }
}

/* 入队后台任务并轮询到结束；关闭/刷新页面不会中断任务本身 */
async function runJob(title, enqueuePath, body) {
  if (state.busy) { alert("已有任务进行中，请等待完成"); return false; }
  let jobId;
  try {
    const resp = await api("POST", enqueuePath, body);
    jobId = resp.job_id;
  } catch (e) {
    alert(e.message);
    return false;
  }
  progress.show(`${title}（后台任务 #${jobId}，刷新页面不会中断）`);
  return pollJob(jobId);
}

/* 轮询任务进度；页面刷新后可对同一任务续接 */
async function pollJob(jobId) {
  state.busy = true;
  state.activeJobId = jobId;
  progress.setCancelVisible(true);
  let ok = false;
  let rendered = 0;
  try {
    for (;;) {
      let job;
      try {
        job = await api("GET", `/api/jobs/${jobId}`);
      } catch {
        await sleep(3000);  // 网络抖动/服务重启：继续轮询
        continue;
      }
      const events = job.progress || [];
      for (; rendered < events.length; rendered++) renderJobEvent(events[rendered]);
      if (job.status === "succeeded") { ok = true; break; }
      if (job.status === "failed" || job.status === "cancelled") {
        if (job.status === "failed") {
          progress.log(`❌ 任务失败：${job.error || "未知错误"}`, true);
        } else {
          progress.log("⏹ 任务已取消", true);
        }
        progress.actionLine(
          `<button class="btn sm" onclick="actions.retryJob(${jobId})">↻ 从断点重试（已完成步骤不重跑）</button>`);
        break;
      }
      await sleep(1500);
    }
  } finally {
    state.busy = false;
    state.activeJobId = null;
    progress.setCancelVisible(false);
  }
  if (state.novel) await ui.openNovel(state.novel.id, true);
  return ok;
}

/* ================= UI ================= */

const ui = {
  /* ---- 列表与导航 ---- */
  async refreshList() {
    state.novels = await api("GET", "/api/novels");
    const ul = document.getElementById("novel-list");
    ul.innerHTML = state.novels.map(n => `
      <li onclick="ui.openNovel(${n.id})" class="${state.novel?.id === n.id ? "active" : ""}">
        <div class="nl-title">${esc(n.title)}</div>
        <div class="nl-sub">${esc(n.genre || "未分类")} · 已写${n.chapters_done}章${n.num_chapters > 0 ? ` · 约${n.num_chapters}` : " · 规模开放"}
          ${n.has_blueprint ? "· 已有蓝图" : ""}</div>
      </li>`).join("");
  },

  showCreateForm() {
    document.getElementById("welcome").classList.remove("hidden");
    document.getElementById("workbench").classList.add("hidden");
    document.getElementById("create-form").classList.remove("hidden");
    state.novel = null;
    this.refreshList();
  },
  hideCreateForm() {
    document.getElementById("create-form").classList.add("hidden");
  },

  async createNovel() {
    const premise = document.getElementById("f-premise").value.trim();
    if (premise.length < 2) { alert("请填写故事方向"); return; }
    const payload = {
      title: document.getElementById("f-title").value.trim() || "未命名小说",
      premise,
      num_chapters: 0,
      words_per_chapter: parseInt(document.getElementById("f-words").value) || 3000,
      is_fanfic: !!document.getElementById("f-fanfic")?.checked,
    };
    const { id } = await api("POST", "/api/novels", payload);
    await this.refreshList();
    await this.openNovel(id);
  },

  async openNovel(id, keepTab = false) {
    state.novel = await api("GET", `/api/novels/${id}`);
    if (!keepTab) state.tab = "blueprint";
    document.getElementById("welcome").classList.add("hidden");
    document.getElementById("workbench").classList.remove("hidden");
    document.getElementById("wb-title").textContent = state.novel.title;
    const pendingHint = state.novel.pending_count
      ? ` · 待确认 ${state.novel.pending_count}` : "";
    const scaleMeta = (state.novel.num_chapters > 0)
      ? `软估计约${state.novel.num_chapters}章`
      : "规模未锁定";
    document.getElementById("wb-meta").textContent =
      `${state.novel.genre || "未分类"} · ${scaleMeta} · 每章约${state.novel.words_per_chapter}字${pendingHint}`;
    document.querySelectorAll(".tab").forEach(t =>
      t.classList.toggle("active", t.dataset.tab === state.tab));
    try {
      const data = await api("GET", `/api/novels/${id}/pending`);
      state.pending = data.items || [];
    } catch {
      state.pending = [];
    }
    this.ensureCocreateCap().finally(() => this.renderTab());
    if (state.expandedChapter) {
      const body = document.getElementById(`chapter-body-${state.expandedChapter}`);
      if (body) body.classList.remove("hidden");
    }
    this.refreshList();
    this.resumeActiveJobIfAny();  // 刷新页面后续接进行中的后台任务
  },

  async resumeActiveJobIfAny() {
    if (state.busy || !state.novel) return;
    try {
      const { job } = await api("GET", `/api/novels/${state.novel.id}/jobs/active`);
      if (!job || !["queued", "running", "cancelling"].includes(job.status)) return;
      const kindLabel = job.kind === "write_chapter" ? "写章" : "定稿";
      progress.show(`续接后台任务 #${job.id}（${kindLabel}第${job.params?.chapter_no ?? "?"}章）`);
      await pollJob(job.id);
    } catch { /* 无任务或接口不可用时静默 */ }
  },

  async deleteNovel() {
    if (!state.novel) return;
    if (!confirm(`确定删除《${state.novel.title}》？此操作不可恢复`)) return;
    await api("DELETE", `/api/novels/${state.novel.id}`);
    state.novel = null;
    this.showCreateForm();
  },

  hideProgress() {
    document.getElementById("progress-panel").classList.add("hidden");
  },

  /* ---- Tab 渲染 ---- */
  renderTab() {
    const el = document.getElementById("tab-content");
    const n = state.novel;
    if (!n) { el.innerHTML = ""; return; }
    const renderers = {
      blueprint: this.renderBlueprint,
      characters: this.renderCharacters,
      outlines: this.renderOutlines,
      chapters: this.renderChapters,
      lore: this.renderLore,
      state: this.renderState,
    };
    el.innerHTML = renderers[state.tab].call(this, n);
  },

  renderBlueprint(n) {
    const styleCard = renderStyleGuideCard(n);
    if (!n.core_seed) {
      return renderCocreatePanel(n) + renderGuidesCard(n) + renderScaleCard(n) + `<div class="empty-hint">
        <p>共创确认后（或跳过共创），生成蓝图：</p>
        <p class="muted" style="margin:8px 0">核心种子 → 角色（锁共创） → 世界观 → 第1弧架构 → 弱指南针 → 状态表 → 首批细纲</p>
        <button class="btn primary" onclick="actions.generateBlueprint()">🚀 生成蓝图</button>
      </div>` + styleCard;
    }
    return [
      renderGuidesCard(n),
      renderScaleCard(n),
      editableBlock("full_story", "故事倾向摘要（弱指南针；可改，非全书散文）", n.full_story),
      editableBlock("core_seed", "核心种子", n.core_seed),
      editableBlock("world_building", "世界观", n.world_building),
      editableBlock("plot_architecture", "第1弧架构（近处节拍，非全书三幕）", n.plot_architecture),
      editableBlock("character_dynamics", "角色动力学", n.character_dynamics),
      renderMetaCard(n),
      renderCompassCard(n),
      renderStyleRulesCard(n),
      renderStyleGuideCard(n),
      `<div class="card"><h3>重新生成</h3>
        <p class="muted">将覆盖以上全部蓝图内容（角色卡与细纲一并重建）</p>
        <div class="actions"><button class="btn primary" onclick="actions.generateBlueprint()">重新生成蓝图</button></div>
      </div>`,
    ].join("");
  },

  renderCharacters(n) {
    const factionsSec = renderFactions(n);
    const planBtn = `<div class="actions" style="margin-bottom:12px">
      <button class="btn primary" onclick="actions.deepenPlannedCharacter()">📋 为下章规划新角色</button>
    </div>`;
    if (!n.characters.length) {
      return planBtn + `<div class="empty-hint">尚无角色卡。角色卡会在<strong>章节定稿</strong>时按章增量建档，并<strong>自动深化</strong>新登场重要角色。也可先用上方按钮为 upcoming 章节预建人设。</div>` + renderCastLedger(n) + factionsSec;
    }
    const active = n.characters.filter(c => c.status === "active");
    const inactive = n.characters.filter(c => c.status !== "active");
    const renderCard = c => `
      <div class="card char-card ${c.status !== "active" ? "inactive-card" : ""}">
        <div class="char-name">${esc(c.name)}
          <span class="badge ${c.status === "active" ? "draft" : ""}">${c.status === "active" ? "活跃" : "离场"}</span>
          ${c._deepened ? `<span class="badge finalized">已深化</span>` : `<span class="badge">初稿</span>`}
          ${c.first_chapter ? `<span class="muted">第${c.first_chapter}-${c.last_chapter || c.first_chapter}章</span>` : ""}</div>
        <button class="btn sm" style="margin-bottom:6px" onclick="ui.toggleCharacterStatus(${c.id}, '${c.status === "active" ? "inactive" : "active"}')">${c.status === "active" ? "标为离场" : "标为活跃"}</button>
        ${!c._deepened ? `<button class="btn sm" style="margin-bottom:6px" onclick="actions.deepenCharacter('${esc(c.name).replace(/'/g, "\\'")}')">🎭 深化人设</button>` : ""}
        <div class="char-identity">${esc(c.identity || "")}</div>
        <div class="traits">${(c.traits || []).map(t => `<span class="trait">${esc(t)}</span>`).join("")}</div>
        ${c.motivation ? `<div class="char-sec"><b>驱动力：</b>表面-${esc(c.motivation.surface || "")}；
          渴望-${esc(c.motivation.desire || "")}；灵魂-${esc(c.motivation.soul || "")}</div>` : ""}
        ${c.secret ? `<div class="char-sec"><b>秘密：</b>${esc(c.secret)}</div>` : ""}
        ${c.arc ? `<div class="char-sec"><b>弧线：</b>${esc(c.arc)}</div>` : ""}
        ${c.story_function ? `<div class="char-sec"><b>叙事功能：</b>${esc(c.story_function)}</div>` : ""}
        ${c.debut_plan ? `<div class="char-sec"><b>出场规划：</b>${esc(c.debut_plan)}</div>` : ""}
        ${(c.voice_rules || []).length ? `<div class="char-sec"><b>对话规则：</b>${c.voice_rules.map(r => esc(r)).join("；")}</div>` : ""}
        ${(c.relationships || []).length ? `<div class="char-sec"><b>关系：</b>
          ${c.relationships.map(r => `<div class="rel"><span class="rel-type">[${esc(r.type || "")}]</span>
            → ${esc(r.target || "")}：${esc(r.detail || "")}</div>`).join("")}</div>` : ""}
      </div>`;
    return planBtn + factionsSec + renderCastLedger(n) + `<p class="muted">共 ${n.characters.length} 人（活跃 ${active.length} / 离场 ${inactive.length}）</p>`
      + `<div class="char-grid">` + n.characters.map(renderCard).join("") + `</div>`;
  },

  renderOutlines(n) {
    const blocks = n.chapter_outlines.map(o => `
      <div class="card chapter-item ${o.status}">
        <div class="ch-head">
          <span class="ch-title">第${o.chapter_no}章 ${esc(o.title)}
            <span class="badge ${o.status}">${statusLabel(o.status)}</span></span>
          <div class="actions" style="margin:0">
            <button class="btn sm" onclick="ui.editOutline(${o.chapter_no})">编辑</button>
            <button class="btn sm" onclick="ui.openRevise('chapter_outline', ${o.chapter_no})">AI 修订</button>
          </div>
        </div>
        <pre class="outline-text" id="outline-view-${o.chapter_no}">${esc(o.content)}</pre>
        <div class="hidden" id="outline-edit-${o.chapter_no}">
          <textarea rows="8">${esc(o.content)}</textarea>
          <div class="actions">
            <button class="btn primary sm" onclick="ui.saveOutline(${o.chapter_no})">保存</button>
            <button class="btn sm" onclick="ui.cancelEditOutline(${o.chapter_no})">取消</button>
          </div>
        </div>
      </div>`).join("");
    const nextBtn = n.core_seed
      ? `<div class="card"><h3>滚动细纲</h3>
          <p class="muted">每次生成接下来几章的细纲（结合最新前文摘要与角色状态）</p>
          <div class="actions"><button class="btn primary" onclick="actions.nextOutlines()">➕ 生成后续章节细纲</button></div>
         </div>`
      : `<div class="empty-hint">请先生成蓝图</div>`;
    return renderVolumes(n) + blocks + nextBtn;
  },

  renderChapters(n) {
    const outlineNos = new Set(n.chapter_outlines.map(o => o.chapter_no));
    const chapterMap = new Map(n.chapters.map(c => [c.chapter_no, c]));
    const items = [...outlineNos].sort((a, b) => a - b).map(no => {
      const ch = chapterMap.get(no);
      const outline = n.chapter_outlines.find(o => o.chapter_no === no);
      if (!ch || !ch.content) {
        return `<div class="card chapter-item">
          <div class="ch-head">
            <span class="ch-title">第${no}章 ${esc(outline?.title || "")}
              <span class="badge">未写作</span></span>
            <button class="btn primary sm" onclick="actions.writeChapter(${no})">✍ 生成正文</button>
          </div></div>`;
      }
      const review = parseReview(ch.review);
      return `<div class="card chapter-item ${ch.status}">
        <div class="ch-head">
          <span class="ch-title">第${no}章 ${esc(ch.title)}
            <span class="badge ${ch.status}">${statusLabel(ch.status)}</span>
            <span class="muted">${ch.content.length}字</span></span>
          <div class="actions" style="margin:0">
            <button class="btn sm" onclick="ui.toggleChapter(${no})">展开/收起</button>
            <button class="btn sm" onclick="ui.openRevise('chapter', ${no})">AI 修订</button>
            <button class="btn sm" onclick="actions.polishChapter(${no})">✨ 润色</button>
            <button class="btn sm" onclick="actions.humanizeChapter(${no})">🧹 去AI味</button>
            <button class="btn sm" onclick="actions.critiqueChapter(${no})">🔍 评审</button>
            <button class="btn sm" onclick="actions.healthCheckChapter(${no})">🩺 健康检查</button>
            <button class="btn sm" onclick="actions.writeChapter(${no})">重新生成</button>
            ${ch.status !== "finalized"
              ? `<button class="btn success sm" onclick="actions.finalizeChapter(${no})">定稿</button>` : ""}
          </div>
        </div>
        ${renderReview(review)}
        ${renderHealthReport(ch.health_report)}
        ${renderReadinessReport(ch.readiness_report)}
        ${renderQualityDecision(ch.quality_decision)}
        ${renderToxinReport(ch.toxin_report)}
        ${renderCritique(ch.critique, no)}
        <div class="hidden" id="chapter-body-${no}">
          <div class="chapter-read" id="chapter-read-${no}" data-chapter-no="${no}">${esc(ch.content)}</div>
          <p class="muted segment-hint">在正文中拖选一段（AIGC 标红段落），浮层可：重写 / 润色 / 去AI味（只改选中部分，自动拼回）</p>
          <details class="chapter-edit">
            <summary>全文手动编辑</summary>
            <textarea rows="14" id="chapter-text-${no}">${esc(ch.content)}</textarea>
            <div class="actions">
              <button class="btn primary sm" onclick="ui.saveChapter(${no})">保存修改</button>
            </div>
          </details>
        </div>
      </div>`;
    }).join("");
    return items || `<div class="empty-hint">先在「细纲」页生成章节细纲，再回到这里逐章写作。
      <p class="muted" style="margin-top:8px">已有正文后可点 <strong>🩺 健康检查</strong>（规则检测，零 token）；定稿后自动跑毒点/爽点扫描。</p></div>`;
  },

  renderLore(n) {
    if (!n.core_seed) return `<div class="empty-hint">请先生成蓝图</div>`;
    const entries = n.lore_entries || [];
    const header = `<div class="card"><h3>世界书 / 设定库（${entries.length}条）</h3>
      <p class="muted">写章节时按「条目名/关键词」与本章细纲自动匹配，仅注入相关条目（不耗 token）；
        定稿时 WorldKeeper 自动沉淀本章新确立的硬设定。</p>
      <div class="actions">
        <button class="btn ${entries.length ? "" : "primary"}" onclick="actions.generateLore()">
          ${entries.length ? "重新从蓝图整理（覆盖现有条目）" : "📚 从蓝图整理世界书"}</button>
        <button class="btn sm" onclick="ui.showAddLore()">＋ 手动添加条目</button>
      </div>
      <div class="hidden" id="lore-add" style="margin-top:10px">
        <div class="row">
          <label>条目名<input id="lore-new-name" placeholder="如：青冥剑"></label>
          <label>分类<input id="lore-new-category" placeholder="地点/物品/组织/规则/历史/种族/能力/其他" value="其他"></label>
        </div>
        <label>触发关键词（逗号分隔）<input id="lore-new-keywords" placeholder="别名1，相关词2"></label>
        <label>内容（写作必须遵守的硬事实）<textarea id="lore-new-content" rows="3"></textarea></label>
        <div class="actions">
          <button class="btn primary sm" onclick="ui.addLore()">添加</button>
          <button class="btn sm" onclick="ui.hideAddLore()">取消</button>
        </div>
      </div>
    </div>`;
    if (!entries.length) return header;
    const groups = {};
    for (const e of entries) (groups[e.category] ||= []).push(e);
    const body = Object.entries(groups).map(([cat, items]) => `
      <div class="card"><h3>${esc(cat)}（${items.length}）</h3>
        ${items.map(e => `
        <div class="card chapter-item ${e.enabled ? "draft" : ""}" style="margin-bottom:10px;${e.enabled ? "" : "opacity:.55"}">
          <div class="ch-head">
            <span class="ch-title">${esc(e.name)}
              ${e.source_chapter ? `<span class="muted">第${e.source_chapter}章沉淀</span>` : ""}
              ${e.enabled ? "" : `<span class="badge">已停用</span>`}</span>
            <div class="actions" style="margin:0">
              <button class="btn sm" onclick="ui.editLore(${e.id})">编辑</button>
              <button class="btn sm" onclick="ui.toggleLore(${e.id}, ${e.enabled ? "false" : "true"})">${e.enabled ? "停用" : "启用"}</button>
              <button class="btn danger sm" onclick="ui.deleteLore(${e.id})">删除</button>
            </div>
          </div>
          <div id="lore-view-${e.id}">
            <div style="font-size:13px">${esc(e.content)}</div>
            ${(e.keywords || []).length ? `<div class="traits" style="margin-top:4px">
              ${e.keywords.map(k => `<span class="trait">${esc(k)}</span>`).join("")}</div>` : ""}
          </div>
          <div class="hidden" id="lore-edit-${e.id}">
            <input class="l-name" value="${esc(e.name)}" placeholder="条目名" style="width:100%;margin-bottom:6px">
            <input class="l-category" value="${esc(e.category)}" placeholder="分类" style="width:100%;margin-bottom:6px">
            <input class="l-keywords" value="${esc((e.keywords || []).join("，"))}" placeholder="关键词，逗号分隔" style="width:100%;margin-bottom:6px">
            <textarea class="l-content" rows="3">${esc(e.content)}</textarea>
            <div class="actions">
              <button class="btn primary sm" onclick="ui.saveLore(${e.id})">保存</button>
              <button class="btn sm" onclick="ui.cancelEditLore(${e.id})">取消</button>
            </div>
          </div>
        </div>`).join("")}
      </div>`).join("");
    return header + body;
  },

  renderState(n) {
    const hint = `<div class="card feature-card" style="margin-bottom:12px">
      <h3>增强能力（novel-engine-next）</h3>
      <ul class="muted" style="font-size:13px;line-height:1.8;margin:0;padding-left:18px">
        <li><strong>写法特征池</strong>：蓝图页 → 写法引擎 → 学习并绑定</li>
        <li><strong>质量门</strong>：写章后 health + 发布结构审稿；critical 阻断定稿</li>
        <li><strong>待确认提案</strong>：仅定稿后产生；下方确认后才入正式库（不自动入账）</li>
      </ul>
    </div>`;
    return [
      hint,
      renderPendingPanel(n),
      renderPayoffs(n.payoffs || []),
      renderForeshadowings(n.foreshadowings || []),
      editableBlock("global_summary", "前文摘要（定稿后自动更新）", n.global_summary || "（尚无，定稿第一章后生成）"),
      editableBlock("character_state", "角色状态表（定稿后自动更新）", n.character_state || "（尚无，生成蓝图后建立）"),
    ].join("");
  },

  /* ---- 行内编辑 ---- */
  async saveField(field) {
    const ta = document.getElementById(`field-${field}`);
    await api("PUT", `/api/novels/${state.novel.id}/field`, { field, content: ta.value });
    await this.openNovel(state.novel.id, true);
  },

  async saveScaleFields() {
    const genre = document.getElementById("field-genre")?.value ?? "";
    const num = document.getElementById("field-num_chapters")?.value ?? "0";
    const words = document.getElementById("field-words_per_chapter")?.value ?? "3000";
    await api("PUT", `/api/novels/${state.novel.id}/field`, { field: "genre", content: genre });
    await api("PUT", `/api/novels/${state.novel.id}/field`, { field: "num_chapters", content: String(num) });
    await api("PUT", `/api/novels/${state.novel.id}/field`, { field: "words_per_chapter", content: String(words) });
    await this.openNovel(state.novel.id, true);
  },

  editOutline(no) {
    document.getElementById(`outline-view-${no}`).classList.add("hidden");
    document.getElementById(`outline-edit-${no}`).classList.remove("hidden");
  },
  cancelEditOutline(no) {
    document.getElementById(`outline-view-${no}`).classList.remove("hidden");
    document.getElementById(`outline-edit-${no}`).classList.add("hidden");
  },
  async saveOutline(no) {
    const ta = document.querySelector(`#outline-edit-${no} textarea`);
    await api("PUT", `/api/novels/${state.novel.id}/outlines/${no}`, { content: ta.value });
    await this.openNovel(state.novel.id, true);
  },

  editVolume(no) {
    document.getElementById(`volume-view-${no}`).classList.add("hidden");
    document.getElementById(`volume-edit-${no}`).classList.remove("hidden");
  },
  cancelEditVolume(no) {
    document.getElementById(`volume-view-${no}`).classList.remove("hidden");
    document.getElementById(`volume-edit-${no}`).classList.add("hidden");
  },
  async saveVolume(no) {
    const box = document.getElementById(`volume-edit-${no}`);
    await api("PUT", `/api/novels/${state.novel.id}/volumes/${no}`, {
      title: box.querySelector(".v-title").value.trim(),
      theme: box.querySelector(".v-theme").value.trim(),
      summary: box.querySelector(".v-summary").value.trim(),
    });
    await this.openNovel(state.novel.id, true);
  },

  async saveCompass() {
    const threads = document.getElementById("compass-threads")?.value
      .split("\n").map(s => s.trim()).filter(Boolean) || [];
    await api("PUT", `/api/novels/${state.novel.id}/compass`, {
      ending_direction: document.getElementById("compass-ending")?.value.trim() || "",
      open_threads: threads,
      estimated_scale: document.getElementById("compass-scale")?.value.trim() || "",
    });
    await this.openNovel(state.novel.id, true);
  },

  showAddLore() { document.getElementById("lore-add").classList.remove("hidden"); },
  hideAddLore() { document.getElementById("lore-add").classList.add("hidden"); },
  async addLore() {
    const name = document.getElementById("lore-new-name").value.trim();
    if (!name) { alert("请填写条目名"); return; }
    await api("POST", `/api/novels/${state.novel.id}/lore`, {
      name,
      category: document.getElementById("lore-new-category").value.trim() || "其他",
      keywords: splitKeywords(document.getElementById("lore-new-keywords").value),
      content: document.getElementById("lore-new-content").value.trim(),
    });
    await this.openNovel(state.novel.id, true);
  },
  editLore(id) {
    document.getElementById(`lore-view-${id}`).classList.add("hidden");
    document.getElementById(`lore-edit-${id}`).classList.remove("hidden");
  },
  cancelEditLore(id) {
    document.getElementById(`lore-view-${id}`).classList.remove("hidden");
    document.getElementById(`lore-edit-${id}`).classList.add("hidden");
  },
  async saveLore(id) {
    const box = document.getElementById(`lore-edit-${id}`);
    await api("PUT", `/api/novels/${state.novel.id}/lore/${id}`, {
      name: box.querySelector(".l-name").value.trim(),
      category: box.querySelector(".l-category").value.trim() || "其他",
      keywords: splitKeywords(box.querySelector(".l-keywords").value),
      content: box.querySelector(".l-content").value.trim(),
    });
    await this.openNovel(state.novel.id, true);
  },
  async toggleLore(id, enabled) {
    await api("PUT", `/api/novels/${state.novel.id}/lore/${id}`, { enabled });
    await this.openNovel(state.novel.id, true);
  },
  async deleteLore(id) {
    if (!confirm("删除该设定条目？")) return;
    await api("DELETE", `/api/novels/${state.novel.id}/lore/${id}`);
    await this.openNovel(state.novel.id, true);
  },

  async toggleCharacterStatus(id, status) {
    await api("PUT", `/api/novels/${state.novel.id}/characters/${id}/status?status=${status}`);
    await this.openNovel(state.novel.id, true);
  },
  async toggleFactionStatus(id, status) {
    await api("PUT", `/api/novels/${state.novel.id}/factions/${id}/status?status=${status}`);
    await this.openNovel(state.novel.id, true);
  },

  toggleChapter(no) {
    const body = document.getElementById(`chapter-body-${no}`);
    body.classList.toggle("hidden");
    state.expandedChapter = body.classList.contains("hidden") ? null : no;
    hideSegmentToolbar();
  },
  async saveChapter(no) {
    const ta = document.getElementById(`chapter-text-${no}`);
    await api("PUT", `/api/novels/${state.novel.id}/chapters/${no}`, { content: ta.value });
    await this.openNovel(state.novel.id, true);
  },

  /* ---- AI 修订弹窗 ---- */
  openRevise(targetType, chapterNo = null, fieldLabel = "") {
    const labels = {
      full_story: "故事倾向摘要", core_seed: "核心种子", world_building: "世界观",
      plot_architecture: "第1弧架构", character_dynamics: "角色动力学",
      chapter_outline: `第${chapterNo}章细纲`, chapter: `第${chapterNo}章正文`,
    };
    document.getElementById("modal-title").textContent = `AI 修订：${fieldLabel || labels[targetType] || targetType}`;
    document.getElementById("modal-desc").textContent =
      "Revision 会在保持设定一致的前提下按指令修改，原内容自动存入修订历史。";
    document.getElementById("modal-instruction").value = "";
    document.getElementById("modal-mask").classList.remove("hidden");
    document.getElementById("modal-confirm").onclick = async () => {
      const instruction = document.getElementById("modal-instruction").value.trim();
      if (instruction.length < 2) { alert("请填写修改指令"); return; }
      this.closeModal();
      await runTask(`AI 修订`, `/api/novels/${state.novel.id}/revise`,
        { target_type: targetType, chapter_no: chapterNo, instruction });
    };
  },
  closeModal(e) {
    if (e && e.target !== document.getElementById("modal-mask")) return;
    document.getElementById("modal-mask").classList.add("hidden");
  },

  openSegmentRevise() {
    if (!segmentPick.text || !segmentPick.chapterNo) return;
    hideSegmentToolbar();
    window.getSelection()?.removeAllRanges();
    document.getElementById("segment-preview").value = segmentPick.text;
    document.getElementById("segment-instruction").value = "";
    document.getElementById("segment-modal-mask").classList.remove("hidden");
    document.getElementById("segment-confirm").onclick = async () => {
      const instruction = document.getElementById("segment-instruction").value.trim();
      if (instruction.length < 2) { alert("请填写修改要求"); return; }
      const no = segmentPick.chapterNo;
      const selected = segmentPick.text;
      this.closeSegmentModal();
      await this._runSegmentTask(no, selected, "revise_segment",
        `片段重写第${no}章`, `/api/novels/${state.novel.id}/chapters/${no}/revise_segment`,
        { selected_text: selected, instruction });
    };
  },
  async runSegmentPolish() {
    if (!segmentPick.text || !segmentPick.chapterNo) return;
    const no = segmentPick.chapterNo;
    const selected = segmentPick.text;
    hideSegmentToolbar();
    window.getSelection()?.removeAllRanges();
    const extra = prompt("片段润色额外要求（可留空）：", "");
    if (extra === null) return;
    await this._runSegmentTask(no, selected, "polish_segment",
      `片段润色第${no}章`, `/api/novels/${state.novel.id}/chapters/${no}/polish_segment`,
      { selected_text: selected, instruction: extra });
  },
  async runSegmentHumanize() {
    if (!segmentPick.text || !segmentPick.chapterNo) return;
    const no = segmentPick.chapterNo;
    const selected = segmentPick.text;
    hideSegmentToolbar();
    window.getSelection()?.removeAllRanges();
    const extra = prompt("片段去 AI 味额外要求（可留空；默认按判据库改写）：", "");
    if (extra === null) return;
    await this._runSegmentTask(no, selected, "humanize_segment",
      `片段去AI味第${no}章`, `/api/novels/${state.novel.id}/chapters/${no}/humanize_segment`,
      { selected_text: selected, instruction: extra });
  },
  async _runSegmentTask(chapterNo, selected, keepExpanded, title, path, body) {
    state.expandedChapter = chapterNo;
    state.tab = "chapters";
    document.querySelectorAll(".tab").forEach(t =>
      t.classList.toggle("active", t.dataset.tab === "chapters"));
    await runTask(title, path, body);
  },
  closeSegmentModal(e) {
    if (e && e.target !== document.getElementById("segment-modal-mask")) return;
    document.getElementById("segment-modal-mask").classList.add("hidden");
  },
};

/* ================= 生成动作 ================= */

const actions = {
  async cancelActiveJob() {
    if (!state.activeJobId) return;
    if (!confirm("取消当前后台任务？已完成的步骤会保留为断点，可稍后重试续跑")) return;
    try {
      await api("POST", `/api/jobs/${state.activeJobId}/cancel`);
      progress.log("… 已请求取消，等待当前步骤结束");
    } catch (e) {
      progress.log(`❌ ${e.message}`, true);
    }
  },
  async retryJob(jobId) {
    if (state.busy) { alert("已有任务进行中，请等待完成"); return; }
    try {
      await api("POST", `/api/jobs/${jobId}/retry`);
    } catch (e) {
      alert(e.message);
      return;
    }
    progress.show(`重试后台任务 #${jobId}（从断点继续）`);
    await pollJob(jobId);
  },
  async ensureCocreateCap() {
    if (!state.novel || state.cocreateStream != null) return;
    try {
      const d = await api("GET", `/api/novels/${state.novel.id}/cocreate/capabilities`);
      state.cocreateStream = !!d.stream;
    } catch {
      state.cocreateStream = false;
    }
  },
  async cocreateSend() {
    if (!state.novel) return;
    const input = document.getElementById("cocreate-input");
    const msg = (input?.value || "").trim();
    if (!msg) return;
    if (state.busy) { alert("已有任务进行中"); return; }
    state.busy = true;
    try {
      const looksFanfic = /同人|原作|战锤|哈利|火影|漫威|DC|原神|穿越进/.test(
        msg + (state.novel.premise || "") + (state.novel.genre || ""));
      if (looksFanfic && !state.novel.is_fanfic) {
        if (confirm("这段描述像同人作品。是否切换为同人模式（更强原作约束）？")) {
          await api("POST", `/api/novels/${state.novel.id}/cocreate/enable_fanfic`, {});
          state.novel.is_fanfic = true;
        }
      }
      await this.ensureCocreateCap();
      if (state.cocreateStream) {
        await this.cocreateSendStream(msg, input);
      } else {
        const data = await api("POST", `/api/novels/${state.novel.id}/cocreate/chat`, { message: msg });
        state.novel.cocreate_messages = data.messages || [];
        state.novel.cocreate_draft = data.draft || "";
        state.novel.cocreate_ready = !!data.ready;
        if (input) input.value = "";
        ui.renderTab();
      }
    } catch (e) {
      alert(e.message);
      ui.renderTab();
    } finally {
      state.busy = false;
    }
  },
  async cocreateSendStream(msg, input) {
    if (input) input.value = "";
    beginCocreateLive(msg);
    let thinking = "";
    let reply = "";
    await sse(`/api/novels/${state.novel.id}/cocreate/chat_stream`, { message: msg }, {
      thinking_start() { setCocreateThinkSummary("思考中…"); },
      thinking(d) {
        thinking += d.delta || "";
        setCocreateThinkBody(thinking);
      },
      reply_start() { setCocreateThinkSummary("本轮思考"); },
      reply(d) {
        reply += d.delta || "";
        setCocreateReply(reply);
      },
      done(data) {
        state.novel.cocreate_messages = data.messages || [];
        state.novel.cocreate_draft = data.draft || "";
        state.novel.cocreate_ready = !!data.ready;
        ui.renderTab();
      },
      error(d) { throw new Error(d.message || "共创流式失败"); },
    });
  },
  async cocreateSuggest(text) {
    const input = document.getElementById("cocreate-input");
    if (input) input.value = text;
  },
  async cocreateFinalize() {
    if (!state.novel) return;
    if (state.busy) { alert("已有任务进行中"); return; }
    if (!confirm("确认当前共创草稿？将写入创作约束，随后可生成蓝图。")) return;
    state.busy = true;
    try {
      const data = await api("POST", `/api/novels/${state.novel.id}/cocreate/finalize`, { confirm: true });
      if (data.novel) state.novel = data.novel;
      else {
        state.novel.cocreate_ready = true;
        state.novel.cocreate_draft = data.cocreate_draft || state.novel.cocreate_draft;
        state.novel.cocreate_locks = data.cocreate_locks || {};
      }
      ui.renderTab();
      alert("共创已确认。可以点击「生成蓝图」。");
    } catch (e) {
      alert(e.message);
    } finally {
      state.busy = false;
    }
  },
  async generateBlueprint() {
    if (state.novel?.cocreate_draft && !state.novel.cocreate_ready) {
      if (!confirm("共创草稿尚未点「确认」。仍直接生成蓝图？（将尽量注入当前草稿）")) return;
    }
    await runTask("生成小说蓝图", `/api/novels/${state.novel.id}/blueprint`);
  },
  async nextOutlines() {
    await runTask("生成后续细纲", `/api/novels/${state.novel.id}/outlines/next`);
  },
  async writeChapter(no) {
    const extra = prompt("本章额外指导（可留空）：", "") || "";
    await runJob(`写作第${no}章`,
      `/api/novels/${state.novel.id}/chapters/${no}/write_job`, { user_guidance: extra });
    state.tab = "chapters";
    document.querySelectorAll(".tab").forEach(t =>
      t.classList.toggle("active", t.dataset.tab === "chapters"));
    ui.renderTab();
  },
  async finalizeChapter(no) {
    if (!confirm(
      `定稿第${no}章？\n\n` +
      `将更新摘要、角色状态、伏笔/爽点等台账。\n` +
      `新角色/配角/阵营/设定会进入「待确认提案」，需你在「⑥ 全局状态」确认后才会写入正式库。`,
    )) return;
    const ok = await runJob(`定稿第${no}章`,
      `/api/novels/${state.novel.id}/chapters/${no}/finalize_job`);
    if (!ok) return;
    await actions.loadPending();
    if ((state.pending || []).length) {
      state.tab = "state";
      document.querySelectorAll(".tab").forEach(t =>
        t.classList.toggle("active", t.dataset.tab === "state"));
      ui.renderTab();
      progress.log(`📋 有 ${state.pending.length} 条待确认提案，请确认后入账`);
    }
  },
  async deepenPlannedCharacter() {
    const name = prompt("新角色姓名：");
    if (!name?.trim()) return;
    const role = prompt("在下章的叙事功能（如：对手、证人、旧识）：", "") || "";
    const nextNo = (state.novel.chapters?.length || 0) + 1;
    const ch = prompt("预计登场章节号：", String(nextNo));
    if (!ch) return;
    const target = parseInt(ch, 10);
    if (!Number.isFinite(target) || target < 1) {
      alert("请输入有效章节号");
      return;
    }
    await runTask(`规划新角色：${name.trim()}`,
      `/api/novels/${state.novel.id}/characters/deepen`, {
        planned: [{ name: name.trim(), role_hint: role }],
        target_chapter_no: target,
      });
    state.tab = "characters";
    document.querySelectorAll(".tab").forEach(t =>
      t.classList.toggle("active", t.dataset.tab === "characters"));
    ui.renderTab();
  },
  async deepenCharacter(name) {
    await runTask(`深化 ${name}`,
      `/api/novels/${state.novel.id}/characters/deepen`, { names: [name] });
    state.tab = "characters";
    document.querySelectorAll(".tab").forEach(t =>
      t.classList.toggle("active", t.dataset.tab === "characters"));
    ui.renderTab();
  },
  async generateMeta() {
    await runTask("生成书籍包装", `/api/novels/${state.novel.id}/meta/generate`);
  },
  async generateVolumes() {
    if (state.novel.volumes?.length &&
        !confirm("重新规划首卷将删除全部卷/弧结构（已定稿正文保留），确定继续？")) return;
    await runTask("首卷规划", `/api/novels/${state.novel.id}/volumes/generate`);
  },
  async proposeNextVolume() {
    const hint = prompt("对下一卷的补充意图（可留空）：", "");
    if (hint === null) return;
    if (state.busy) { alert("已有任务进行中"); return; }
    progress.show("生成下一卷方向");
    try {
      const result = await api("POST",
        `/api/novels/${state.novel.id}/volumes/propose-next`, { user_hint: hint || "" });
      progress.log(`✅ 已生成 ${(result.options || []).length} 个方向`);
      await ui.openNovel(state.novel.id, true);
    } catch (e) {
      progress.log(`❌ ${e.message}`, true);
    }
  },
  async appendVolume(optionId) {
    const hint = prompt("追加说明（可留空，会用于校准指南针）：", "");
    if (hint === null) return;
    await runTask(`追加卷（方向 ${optionId}）`,
      `/api/novels/${state.novel.id}/volumes/append`,
      { option_id: optionId, user_hint: hint || "" });
    state.tab = "outlines";
    document.querySelectorAll(".tab").forEach(t =>
      t.classList.toggle("active", t.dataset.tab === "outlines"));
    ui.renderTab();
  },
  async replanSkeleton(volumeNo) {
    const hint = prompt("调整意图（例：加强感情线、缩短本卷）：", "");
    if (hint === null) return;
    await runTask(`重规划第${volumeNo}卷 skeleton 弧`,
      `/api/novels/${state.novel.id}/volumes/${volumeNo}/replan-skeleton`,
      { user_hint: hint || "" });
  },
  async refreshCompass() {
    const hint = prompt("说明你的新方向或要调整的点：", "");
    if (hint === null) return;
    await runTask("刷新终局指南针",
      `/api/novels/${state.novel.id}/compass/refresh`, { user_hint: hint || "" });
  },
  async completeBook() {
    if (!confirm("确认标记全书完结？之后将无法追加新卷或继续写作。")) return;
    const hint = prompt("完结说明（可留空）：", "");
    if (hint === null) return;
    await runTask("标记全书完结",
      `/api/novels/${state.novel.id}/book/complete`, { user_hint: hint || "" });
  },
  async expandArc(volumeNo, arcNo) {
    if (!confirm(`展开第${volumeNo}卷第${arcNo}弧？将分配章范围并生成该弧全部细纲`)) return;
    await runTask(`展开第${volumeNo}卷第${arcNo}弧`,
      `/api/novels/${state.novel.id}/arcs/expand`,
      { volume_no: volumeNo, arc_no: arcNo });
    state.tab = "outlines";
    document.querySelectorAll(".tab").forEach(t =>
      t.classList.toggle("active", t.dataset.tab === "outlines"));
    ui.renderTab();
  },
  async generateFactions() {
    await runTask("识别开篇阵营", `/api/novels/${state.novel.id}/factions/generate`);
  },
  async polishChapter(no) {
    const extra = prompt("润色额外要求（可留空，例：对话更口语化）：", "");
    if (extra === null) return;
    await runTask(`润色第${no}章`,
      `/api/novels/${state.novel.id}/chapters/${no}/polish`, { instruction: extra });
  },
  async humanizeChapter(no) {
    const extra = prompt("去 AI 味额外要求（可留空；默认按 ainovel-cli 判据库改写）：", "");
    if (extra === null) return;
    await runTask(`去 AI 味第${no}章`,
      `/api/novels/${state.novel.id}/chapters/${no}/humanize`, { instruction: extra });
  },
  async critiqueChapter(no) {
    await runTask(`评审第${no}章`,
      `/api/novels/${state.novel.id}/chapters/${no}/critique`);
  },
  async healthCheckChapter(no) {
    try {
      const report = await api("POST",
        `/api/novels/${state.novel.id}/chapters/${no}/health_check`);
      progress.show(`健康检查第${no}章`);
      progress.log(report.summary || report.status);
      for (const it of report.items || []) {
        progress.log(`${it.level === "critical" ? "❌" : "⚠"} ${it.message}`);
      }
      await ui.openNovel(state.novel.id, true);
    } catch (e) {
      alert(e.message);
    }
  },
  async learnStyle() {
    const ref = document.getElementById("style-ref-text")?.value?.trim();
    if (!ref || ref.length < 200) {
      alert("请粘贴至少 200 字的参考书节选");
      return;
    }
    await runTask("写法特征池学习",
      `/api/novels/${state.novel.id}/style-profile/learn`,
      { reference_text: ref, bind_to_novel: true });
  },
  async loadPending() {
    if (!state.novel) return;
    const data = await api("GET", `/api/novels/${state.novel.id}/pending`);
    state.pending = data.items || [];
    if (state.novel) state.novel.pending_count = state.pending.length;
    if (state.tab === "state") ui.renderTab();
  },
  async confirmPending(ids) {
    const list = Array.isArray(ids) ? ids : [ids];
    if (!list.length) return;
    if (!confirm(`确认将 ${list.length} 条提案写入正式库？\n（仅已定稿章节产生的提案可确认入账）`)) return;
    try {
      const r = await api("POST", `/api/novels/${state.novel.id}/pending/confirm`, {
        proposal_ids: list,
      });
      progress.show("确认提案入账");
      progress.log(`已确认 ${r.confirmed || 0}，跳过 ${r.skipped || 0}` +
        (r.rejected ? `，应用失败 ${r.rejected}` : ""));
      await ui.openNovel(state.novel.id, true);
    } catch (e) {
      alert(e.message);
    }
  },
  async rejectPending(ids) {
    const list = Array.isArray(ids) ? ids : [ids];
    if (!list.length) return;
    if (!confirm(`拒绝 ${list.length} 条提案？拒绝后不会写入正式库。`)) return;
    try {
      const r = await api("POST", `/api/novels/${state.novel.id}/pending/reject`, {
        proposal_ids: list,
      });
      progress.show("拒绝提案");
      progress.log(`已拒绝 ${r.rejected || list.length} 条`);
      await ui.openNovel(state.novel.id, true);
    } catch (e) {
      alert(e.message);
    }
  },
  async confirmPendingAll(chapterNo) {
    if (!confirm(
      `确认第 ${chapterNo} 章全部待确认提案入账？\n` +
      `这些提案来自该章定稿提取；确认后写入角色/配角/阵营/设定库。`,
    )) return;
    try {
      const r = await api(
        "POST",
        `/api/novels/${state.novel.id}/pending/confirm-all/${chapterNo}`,
        {},
      );
      progress.show(`确认第${chapterNo}章提案`);
      progress.log(`已确认 ${r.confirmed || 0}，跳过 ${r.skipped || 0}`);
      await ui.openNovel(state.novel.id, true);
    } catch (e) {
      alert(e.message);
    }
  },
  async reviseByCritique(no) {
    if (!confirm(`按评审意见修订第${no}章？原文将存入修订历史`)) return;
    await runTask(`按评审意见修订第${no}章`,
      `/api/novels/${state.novel.id}/chapters/${no}/revise_by_critique`);
  },
  async generateLore() {
    if (state.novel.lore_entries?.length &&
        !confirm("重新整理将覆盖现有全部设定条目（含手动添加与定稿沉淀），确定继续？")) return;
    await runTask("整理世界书", `/api/novels/${state.novel.id}/lore/generate`);
  },
};

/* ================= 工具函数 ================= */

function esc(s) {
  return String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function splitKeywords(s) {
  return String(s || "").split(/[,，、;；]/).map(x => x.trim()).filter(Boolean);
}

function findChapterRead(node) {
  let el = node?.nodeType === 3 ? node.parentElement : node;
  while (el) {
    if (el.classList?.contains("chapter-read")) return el;
    el = el.parentElement;
  }
  return null;
}

function hideSegmentToolbar() {
  document.getElementById("segment-toolbar")?.classList.add("hidden");
  segmentPick.chapterNo = null;
  segmentPick.text = "";
}

function showSegmentToolbar(rect) {
  const bar = document.getElementById("segment-toolbar");
  if (!bar) return;
  bar.style.left = `${rect.left + rect.width / 2}px`;
  bar.style.top = `${Math.max(8, rect.top - 8)}px`;
  bar.classList.remove("hidden");
}

function initSegmentSelection() {
  document.addEventListener("mouseup", () => {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed || sel.rangeCount === 0) {
      hideSegmentToolbar();
      return;
    }
    const text = sel.toString().trim();
    if (text.length < 8) {
      hideSegmentToolbar();
      return;
    }
    const readEl = findChapterRead(sel.anchorNode) || findChapterRead(sel.focusNode);
    if (!readEl) {
      hideSegmentToolbar();
      return;
    }
    segmentPick.chapterNo = parseInt(readEl.dataset.chapterNo, 10);
    segmentPick.text = text;
    showSegmentToolbar(sel.getRangeAt(0).getBoundingClientRect());
  });
  document.addEventListener("mousedown", e => {
    if (e.target.closest("#segment-toolbar") || e.target.closest("#segment-modal-mask")) return;
    if (!e.target.closest(".chapter-read")) hideSegmentToolbar();
  });
  document.addEventListener("scroll", hideSegmentToolbar, true);
}

function statusLabel(s) {
  return { draft: "草稿", edited: "已编辑", finalized: "已定稿", approved: "已确认" }[s] || s;
}

function editableBlock(field, title, content) {
  const revisable = ["full_story", "core_seed", "world_building", "plot_architecture", "character_dynamics"].includes(field);
  return `<div class="card editable-block">
    <h3>${title}</h3>
    <textarea id="field-${field}" rows="${Math.min(16, Math.max(5, (content || "").split("\n").length + 1))}">${esc(content)}</textarea>
    <div class="block-actions">
      <button class="btn primary sm" onclick="ui.saveField('${field}')">保存</button>
      ${revisable ? `<button class="btn sm" onclick="ui.openRevise('${field}')">AI 修订</button>` : ""}
    </div>
  </div>`;
}

function renderCocreatePanel(n) {
  const msgs = n.cocreate_messages || [];
  const lastAssistant = [...msgs].reverse().find(m => m.role === "assistant");
  const suggestions = lastAssistant?.suggestions || [];
  const fanficBadge = n.is_fanfic
    ? `<span class="muted">· 同人模式</span>`
    : `<span class="muted">· 一般模式（像同人时可勾选创建，或在对话中确认切换）</span>`;
  const chatHtml = msgs.length
    ? msgs.map(m => {
        const who = m.role === "user" ? "你" : "共创";
        const think = (state.cocreateStream && m.role === "assistant" && m.thinking)
          ? `<details class="cocreate-think"><summary>本轮思考</summary><div class="cocreate-think-body">${escapeHtml(m.thinking)}</div></details>`
          : "";
        return `<div class="cocreate-msg">${think}<strong>${who}</strong>：${escapeHtml(m.content || "")}</div>`;
      }).join("")
    : `<p class="muted">还没有对话。先说清你想写什么、不能碰什么；同人请尽早点明原作。</p>`;
  const sugHtml = suggestions.length
    ? `<div class="cocreate-suggestions">${suggestions.map((s, i) =>
        `<button class="btn sm" onclick='actions.cocreateSuggest(${JSON.stringify(s)})'>${i + 1}. ${escapeHtml(s)}</button>`
      ).join(" ")}</div>`
    : "";
  const draft = n.cocreate_draft
    ? `<pre class="cocreate-draft">${escapeHtml(n.cocreate_draft)}</pre>`
    : `<p class="muted">草稿会随对话累积更新</p>`;
  const readyHint = n.cocreate_ready
    ? `<p class="muted">✅ 助手认为可以开书了——请点「确认共创」再生成蓝图。</p>`
    : "";
  return `<div class="card cocreate-panel">
    <h3>🧭 开书共创 ${fanficBadge}</h3>
    <p class="muted">多轮澄清后整理创作指令；可谈类型、篇幅感、全局写作指导（文风/视角/禁忌，每块可跳过）。世界观与蓝图会跟这份草稿走。也可跳过，直接下方生成蓝图。</p>
    <div class="cocreate-layout">
      <div class="cocreate-chat">
        <div class="cocreate-log">${chatHtml}</div>
        ${sugHtml}
        <textarea id="cocreate-input" rows="3" placeholder="例如：主角是旁观者穿越，不能公开与帝国翻脸……"></textarea>
        <div class="actions">
          <button class="btn primary sm" onclick="actions.cocreateSend()">发送</button>
          <button class="btn sm" onclick="actions.cocreateFinalize()" ${n.cocreate_draft ? "" : "disabled"}>确认共创</button>
        </div>
        ${readyHint}
      </div>
      <div class="cocreate-side">
        <h4>创作指令草稿</h4>
        ${draft}
      </div>
    </div>
  </div>`;
}

function beginCocreateLive(userMsg) {
  const log = document.getElementById("cocreate-log");
  if (!log) return;
  const empty = log.querySelector("p.muted");
  if (empty) empty.remove();
  log.insertAdjacentHTML("beforeend",
    `<div class="cocreate-msg"><strong>你</strong>：${escapeHtml(userMsg)}</div>
     <div class="cocreate-msg" id="cocreate-live">
       <details class="cocreate-think">
         <summary id="cocreate-live-think-sum">思考中…</summary>
         <div class="cocreate-think-body" id="cocreate-live-think-body"></div>
       </details>
       <strong>共创</strong>：<span id="cocreate-live-reply"></span>
     </div>`);
  log.scrollTop = log.scrollHeight;
}

function setCocreateThinkSummary(text) {
  const el = document.getElementById("cocreate-live-think-sum");
  if (el) el.textContent = text;
}

function setCocreateThinkBody(text) {
  const el = document.getElementById("cocreate-live-think-body");
  if (el) el.textContent = text;
  const log = document.getElementById("cocreate-log");
  if (log) log.scrollTop = log.scrollHeight;
}

function setCocreateReply(text) {
  const el = document.getElementById("cocreate-live-reply");
  if (el) el.textContent = text;
  const log = document.getElementById("cocreate-log");
  if (log) log.scrollTop = log.scrollHeight;
}

function escapeHtml(s) {
  return String(s || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function renderStyleGuideCard(n) {
  const guide = n.style_guide || "";
  const profileHint = n.style_profile_id
    ? `<span class="badge finalized">特征池 #${n.style_profile_id}</span>`
    : `<span class="badge draft">未绑定特征池</span>`;
  return `<div class="card feature-card"><h3>📖 写法引擎 ${profileHint}</h3>
    <p class="muted">StyleLearner 提炼可开关写法特征；与弧末 style_rules 编译后注入 Writer/Editor。</p>
    <label>参考书节选<textarea id="style-ref-text" rows="5" placeholder="粘贴 200-12000 字参考段落……">${esc("")}</textarea></label>
    <div class="actions">
      <button class="btn primary sm" onclick="actions.learnStyle()">📖 学习并绑定特征池</button>
    </div>
    ${guide ? `<div style="margin-top:12px">
      <div class="muted" style="font-size:12px;margin-bottom:4px">当前风格指南（可手动编辑）</div>
      <textarea id="field-style_guide" rows="8">${esc(guide)}</textarea>
      <button class="btn sm" onclick="ui.saveField('style_guide')">保存指南</button>
    </div>` : `<p class="muted" style="margin-top:8px">尚未生成风格指南。</p>`}
  </div>`;
}

function renderPayoffs(items) {
  const stars = n => "★".repeat(Math.min(5, Math.max(1, n || 3)));
  const rows = items.length
    ? items.map(p => `<div class="card chapter-item draft" style="margin-bottom:10px">
        <div class="ch-head"><span class="ch-title">${esc(p.name || p.payoff_type)}
          <span class="badge draft">${esc(p.payoff_type)}</span>
          <span class="muted">第${p.chapter_no}章 ${stars(p.intensity)}</span></span></div>
        <div class="muted" style="font-size:13px">${esc(p.description)}</div>
      </div>`).join("")
    : `<p class="muted">暂无爽点记录。定稿时 NarrativeLedger 自动抽取；细纲生成时会检查节奏缺口。</p>`;
  const last = items.length ? items[items.length - 1].chapter_no : 0;
  const gapNote = last ? `<p class="muted" style="font-size:12px;margin-top:6px">最近爽点：第${last}章</p>` : "";
  return `<div class="card"><h3>爽点台账 <span class="badge draft">NarrativeLedger</span>（${items.length}条）</h3>${rows}${gapNote}</div>`;
}

function renderReadinessReport(reportStr) {
  let r;
  try { r = JSON.parse(reportStr || "{}"); } catch { return ""; }
  if (!r || !r.status) return "";
  const cls = r.status === "ok" ? "review-ok" : (r.status === "critical" ? "health-critical" : "health-warn");
  const icon = r.status === "ok" ? "✓" : (r.status === "critical" ? "❌" : "⚠");
  const blockers = (r.blockers || []).map(b => `<div class="issue critical">${esc(b)}</div>`).join("");
  const m = r.metrics || {};
  return `<div class="review-box health-box">
    <span class="${cls}">${icon} 发布结构：${esc(r.summary)}</span>
    <div class="muted" style="font-size:12px">场戏${m.scene_count ?? 0} · 裸对话${m.naked_dialogue ?? 0} · 账本${m.bookkeeping ?? 0}</div>
    ${blockers}
  </div>`;
}

function renderQualityDecision(reportStr) {
  let r;
  try { r = JSON.parse(reportStr || "{}"); } catch { return ""; }
  if (!r || !r.decision) return "";
  return `<div class="muted" style="font-size:12px;margin-top:4px">质量决策：${esc(r.decision)} — ${esc(r.reason || "")}</div>`;
}

const PENDING_KIND_LABEL = {
  character: "新角色",
  cast: "配角",
  lore: "设定",
  faction: "阵营",
  faction_relation: "阵营关系",
};

function pendingPayloadSummary(p) {
  const pl = p.payload || {};
  if (p.kind === "faction_relation") {
    return `${pl.source || "?"} → ${pl.target || "?"}（${pl.relation_type || "关系"}）`;
  }
  if (pl.name) return String(pl.name);
  if (pl.brief_role) return String(pl.brief_role);
  try {
    return JSON.stringify(pl).slice(0, 60);
  } catch {
    return "（无摘要）";
  }
}

function pendingPayloadDetail(p) {
  const pl = p.payload || {};
  const bits = [];
  if (pl.brief_role) bits.push(pl.brief_role);
  if (pl.category) bits.push(`分类：${pl.category}`);
  if (pl.content) bits.push(String(pl.content).slice(0, 120));
  if (pl.data && typeof pl.data === "object") {
    const d = pl.data;
    if (d.role) bits.push(d.role);
    if (d.brief) bits.push(String(d.brief).slice(0, 80));
  }
  if (pl.public_stance) bits.push(pl.public_stance);
  return bits.filter(Boolean).join(" · ");
}

function renderPendingPanel(n) {
  const items = state.pending || [];
  const count = items.length || n.pending_count || 0;
  if (!count && !items.length) {
    return `<div class="card" style="margin-top:12px">
      <h3>待确认提案 <span class="badge">0</span></h3>
      <p class="muted" style="font-size:13px;line-height:1.7;margin:0">
        流程：<strong>章节定稿</strong> → AI 提取新角色/配角/阵营/设定为提案 →
        <strong>你在此确认</strong> → 写入正式库并参与后续写作。<br>
        未定稿不会产生提案；未确认不会进入角色卡/设定库。
      </p>
    </div>`;
  }

  const byChapter = {};
  for (const p of items) {
    const ch = p.chapter_no || 0;
    (byChapter[ch] || (byChapter[ch] = [])).push(p);
  }
  const chapters = Object.keys(byChapter).map(Number).sort((a, b) => a - b);

  const groups = chapters.map(ch => {
    const rows = byChapter[ch];
    const ids = rows.map(p => p.id);
    const list = rows.map(p => {
      const kind = PENDING_KIND_LABEL[p.kind] || p.kind;
      const detail = pendingPayloadDetail(p);
      const pl = p.payload || {};
      const score = Number(pl.importance || 0);
      const relevance = {
        high: "高复用", medium: "中复用", low: "低复用",
      }[pl.future_relevance] || "待判断";
      return `<div class="pending-item" style="display:flex;gap:8px;align-items:flex-start;margin-top:8px;padding:8px 0;border-top:1px solid var(--border,#333)">
        <div style="flex:1;min-width:0">
          <div>
            <span class="badge draft">${esc(kind)}</span>
            <strong>${esc(pendingPayloadSummary(p))}</strong>
            <span class="muted" style="font-size:12px">重要性 ${score.toFixed(2)} · ${relevance}</span>
          </div>
          ${detail ? `<div class="muted" style="font-size:12px;margin-top:4px">${esc(detail)}</div>` : ""}
          ${pl.reason ? `<div style="font-size:12px;margin-top:5px">入账理由：${esc(pl.reason)}</div>` : ""}
          ${pl.evidence ? `<div class="muted" style="font-size:12px;margin-top:4px">正文证据：“${esc(pl.evidence)}”</div>` : ""}
        </div>
        <div class="actions" style="flex-shrink:0">
          <button class="btn success sm" onclick="actions.confirmPending([${p.id}])">确认</button>
          <button class="btn danger sm" onclick="actions.rejectPending([${p.id}])">拒绝</button>
        </div>
      </div>`;
    }).join("");
    return `<div class="pending-chapter" style="margin-top:12px">
      <div class="ch-head" style="display:flex;align-items:center;justify-content:space-between;gap:8px">
        <span><strong>第 ${ch} 章定稿</strong>
          <span class="badge draft">${rows.length} 条</span></span>
        <div class="actions">
          <button class="btn danger sm" onclick="actions.rejectPending([${ids.join(",")}])">拒绝本章全部</button>
        </div>
      </div>
      ${list}
    </div>`;
  }).join("");

  return `<div class="card" style="margin-top:12px;border-color:#c90">
    <h3>待确认提案 <span class="badge draft">${count}</span></h3>
    <p class="muted" style="font-size:13px;line-height:1.7">
      仅在<strong>该章定稿成功后</strong>才会出现提案。确认后写入正式库；拒绝则丢弃。
      系统已先做正文证据校验、重要性阈值、去重和每章配额；写作上下文只用已确认条目（L0），未确认仅作提醒（L4）。
    </p>
    <div class="actions">
      <button class="btn sm" onclick="actions.loadPending()">刷新列表</button>
    </div>
    ${items.length ? groups : `<p class="muted">计数 ${count}，点击刷新加载详情。</p>`}
  </div>`;
}

function renderHealthReport(reportStr) {
  let r;
  try { r = JSON.parse(reportStr || "{}"); } catch { return ""; }
  if (!r || !r.status) return "";
  const cls = r.status === "ok" ? "review-ok" : (r.status === "critical" ? "health-critical" : "health-warn");
  const icon = r.status === "ok" ? "✓" : (r.status === "critical" ? "❌" : "⚠");
  const items = (r.items || []).map(it =>
    `<div class="issue ${esc(it.level)}">[${esc(it.level)}] ${esc(it.message)}</div>`).join("");
  return `<div class="review-box health-box">
    <span class="${cls}">${icon} 健康检查：${esc(r.summary)}（${r.char_count || 0}字）</span>
    ${items}
  </div>`;
}

function renderToxinReport(reportStr) {
  let r;
  try { r = JSON.parse(reportStr || "{}"); } catch { return ""; }
  if (!r || !r.issues) return "";
  if (!r.issues.length) {
    return `<div class="review-box"><span class="review-ok">✓ 毒点扫描：未发现明显毒点</span></div>`;
  }
  const items = r.issues.map(it =>
    `<div class="issue ${esc(it.severity)}">[${esc(it.severity)}/${esc(it.type)}] ${esc(it.evidence)}
      ${it.suggestion ? `<div class="muted">建议：${esc(it.suggestion)}</div>` : ""}</div>`).join("");
  return `<div class="review-box">⚠ 毒点扫描（${r.issues.length}项）${r.summary ? `：${esc(r.summary)}` : ""}
    ${items}
  </div>`;
}

function renderForeshadowings(items) {
  const statusMap = {
    planted: ["已埋设", "draft"],
    reinforced: ["已强化", "draft"],
    resolved: ["已回收", "finalized"],
  };
  const rows = items.length
    ? items.map(f => {
        const [label, cls] = statusMap[f.status] || [f.status, ""];
        const due = f.resolve_by_chapter ? `，建议第${f.resolve_by_chapter}章前回收` : "";
        return `<div class="card chapter-item ${cls === "finalized" ? "finalized" : "draft"}" style="margin-bottom:10px">
          <div class="ch-head"><span class="ch-title">${esc(f.name)}
            <span class="badge ${cls}">${label}</span>
            <span class="muted">第${f.planted_chapter}章埋设${due}</span></span></div>
          <div class="muted" style="font-size:13px">${esc(f.description)}</div>
          ${f.notes ? `<pre class="outline-text muted" style="margin-top:6px">${esc(f.notes)}</pre>` : ""}
        </div>`;
      }).join("")
    : `<p class="muted">暂无伏笔记录。定稿时 NarrativeLedger 自动抽取维护。</p>`;
  return `<div class="card"><h3>伏笔台账（${items.length}条）</h3>${rows}</div>`;
}

function renderGuidesCard(n) {
  return `<div class="card">
    <h3>全局写作指导</h3>
    <p class="muted" style="font-size:12px;margin-bottom:8px">与书籍包装的「创作风格/叙事视角」分离；写章时本卡优先。每块可留空（等同跳过）。改后立即作用于后续生成，不必重跑蓝图。</p>
    <div style="margin-bottom:8px">
      <div class="muted" style="font-size:12px;margin-bottom:2px">文风语气</div>
      <textarea id="field-guide_style" rows="3" placeholder="例如：冷峻克制，少抒情……">${esc(n.guide_style || "")}</textarea>
      <button class="btn sm" onclick="ui.saveField('guide_style')">保存</button>
    </div>
    <div style="margin-bottom:8px">
      <div class="muted" style="font-size:12px;margin-bottom:2px">视角人称</div>
      <textarea id="field-guide_pov" rows="2" placeholder="例如：第三人称有限，跟主角……">${esc(n.guide_pov || "")}</textarea>
      <button class="btn sm" onclick="ui.saveField('guide_pov')">保存</button>
    </div>
    <div style="margin-bottom:8px">
      <div class="muted" style="font-size:12px;margin-bottom:2px">禁忌与硬要求</div>
      <textarea id="field-guide_taboos" rows="3" placeholder="例如：禁止开后宫；不写幼女……">${esc(n.guide_taboos || "")}</textarea>
      <button class="btn sm" onclick="ui.saveField('guide_taboos')">保存</button>
    </div>
  </div>`;
}

function renderScaleCard(n) {
  const open = !(n.num_chapters > 0);
  return `<div class="card">
    <h3>规模与类型</h3>
    <p class="muted" style="font-size:12px;margin-bottom:8px">总章数默认开放；仅当作者给出软估计时填写正整数。清除为 0 即回到未锁定。</p>
    <div class="row" style="gap:12px;align-items:flex-end;flex-wrap:wrap">
      <label>类型
        <input id="field-genre" value="${esc(n.genre || "")}" placeholder="都市奇幻 / 未定" style="width:160px" />
      </label>
      <label>软估计总章数（0=未锁定）
        <input id="field-num_chapters" type="number" min="0" max="2000" value="${n.num_chapters || 0}" style="width:120px" />
      </label>
      <label>每章字数
        <input id="field-words_per_chapter" type="number" min="300" value="${n.words_per_chapter || 3000}" style="width:120px" />
      </label>
      <button class="btn primary sm" onclick="ui.saveScaleFields()">保存</button>
    </div>
    <p class="muted" style="font-size:12px;margin-top:6px">${open ? "当前：规模未锁定" : `当前：软估计约 ${n.num_chapters} 章`}</p>
  </div>`;
}

function renderMetaCard(n) {
  const hasMeta = n.writing_style || n.subtitle || n.introduction;
  if (!hasMeta) {
    return `<div class="card"><h3>书籍包装</h3>
      <p class="muted">由 Planner（书籍包装）生成标题/副标题/引言/简介/创作风格/叙事视角/时代背景/标签。
        其中「创作风格」与「叙事视角」会约束后续所有章节的写作。</p>
      <div class="actions"><button class="btn primary" onclick="actions.generateMeta()">📦 生成书籍包装</button></div>
    </div>`;
  }
  const tags = (n.tags || []).map(t => `<span class="trait">${esc(t)}</span>`).join("");
  return `<div class="card"><h3>书籍包装 ${tags ? `<span class="traits" style="margin-left:8px">${tags}</span>` : ""}</h3>` +
    [
      ["subtitle", "副标题", n.subtitle],
      ["writing_style", "创作风格（书籍包装/弱补充；作者契约见上方「全局写作指导」）", n.writing_style],
      ["narrative_pov", "叙事视角（书籍包装；作者契约见上方「全局写作指导」）", n.narrative_pov],
      ["era_background", "时代背景", n.era_background],
      ["introduction", "引言", n.introduction],
      ["book_summary", "简介", n.book_summary],
    ].map(([f, label, v]) => `
      <div style="margin-bottom:8px">
        <div class="muted" style="font-size:12px;margin-bottom:2px">${label}</div>
        <textarea id="field-${f}" rows="${v && v.length > 60 ? 4 : 1}">${esc(v || "")}</textarea>
        <button class="btn sm" onclick="ui.saveField('${f}')">保存</button>
      </div>`).join("") +
    `<div class="actions"><button class="btn sm" onclick="actions.generateMeta()">重新生成包装</button></div>
  </div>`;
}

function renderCompassCard(n) {
  const c = n.story_compass || {};
  const complete = c.book_complete;
  const threads = (c.open_threads || []).join("\n");
  if (!c.ending_direction && !threads && !c.estimated_scale && !complete) return "";
  return `<div class="card"><h3>终局指南针 ${complete ? '<span class="badge finalized">全书已完结</span>' : '<span class="badge draft">滚动规划</span>'}</h3>
    <p class="muted" style="font-size:12px;margin-bottom:8px">软锚：可手改或 AI 刷新；具体卷/弧在写作中 append 或重规划，不写死全书。</p>
    <div style="margin-bottom:8px">
      <div class="muted" style="font-size:12px">终局方向</div>
      <textarea id="compass-ending" rows="3">${esc(c.ending_direction || "")}</textarea>
    </div>
    <div style="margin-bottom:8px">
      <div class="muted" style="font-size:12px">活跃长线（每行一条）</div>
      <textarea id="compass-threads" rows="4">${esc(threads)}</textarea>
    </div>
    <div style="margin-bottom:8px">
      <div class="muted" style="font-size:12px">规模预期</div>
      <input id="compass-scale" value="${esc(c.estimated_scale || "")}" style="width:100%">
    </div>
    <div class="actions">
      <button class="btn primary sm" onclick="ui.saveCompass()">保存指南针</button>
      <button class="btn sm" onclick="actions.refreshCompass()">AI 刷新</button>
      ${!complete ? `<button class="btn sm" onclick="actions.completeBook()">标记全书完结</button>` : ""}
    </div>
  </div>`;
}

function renderVolumeProposals(n) {
  const c = n.story_compass || {};
  if (c.book_complete) return "";
  const opts = c.pending_volume_options || [];
  if (!opts.length) return "";
  const canComplete = c.can_complete_book;
  const hint = c.complete_book_hint || "";
  const cards = opts.map(o => `
    <div class="card chapter-item draft" style="margin-bottom:8px">
      <div class="ch-head">
        <span class="ch-title">${esc(o.id)} · 《${esc(o.title)}》
          <span class="badge draft">${esc(o.narrative_function || "下一卷")}</span>
          <span class="muted">约${o.estimated_chapters || "?"}章</span></span>
      </div>
      <div style="font-size:13px"><b>主题：</b>${esc(o.theme || "")}</div>
      <div class="muted" style="font-size:12px;margin-top:4px">${esc(o.summary || "")}</div>
      ${o.pros ? `<div class="muted" style="font-size:11px;margin-top:4px">✓ ${esc(o.pros)}</div>` : ""}
      ${o.risks ? `<div class="muted" style="font-size:11px">⚠ ${esc(o.risks)}</div>` : ""}
      <button class="btn primary sm" style="margin-top:8px" onclick="actions.appendVolume('${esc(o.id)}')">选定并追加此卷</button>
    </div>`).join("");
  return `<div class="card"><h3>下一卷方向（${opts.length} 选 1）</h3>
    ${canComplete ? `<p class="muted" style="font-size:12px">也可选择完结：${esc(hint)}</p>` : ""}
    ${cards}
    <div class="actions">
      <button class="btn sm" onclick="actions.proposeNextVolume()">重新生成方向</button>
    </div>
  </div>`;
}

function renderStyleRulesCard(n) {
  const r = n.writing_style_rules || {};
  const prose = r.prose || [];
  const dialogue = r.dialogue || [];
  const taboos = r.taboos || [];
  if (!prose.length && !dialogue.length && !taboos.length) return "";
  const dialogueHtml = dialogue.length
    ? `<div style="font-size:13px;margin-top:6px"><b>对话：</b><ul style="margin:4px 0;padding-left:18px">${
      dialogue.map(d => `<li><b>${esc(d.name || "")}</b>：${(d.rules || []).map(esc).join("；")}</li>`).join("")
    }</ul></div>` : "";
  return `<div class="card"><h3>写作风格规则（弧末沉淀）</h3>
    ${prose.length ? `<div style="font-size:13px"><b>叙述：</b><ul style="margin:4px 0;padding-left:18px">${prose.map(p => `<li>${esc(p)}</li>`).join("")}</ul></div>` : ""}
    ${dialogueHtml}
    ${taboos.length ? `<div class="muted" style="font-size:13px;margin-top:6px"><b>禁忌：</b><ul style="margin:4px 0;padding-left:18px">${taboos.map(t => `<li>${esc(t)}</li>`).join("")}</ul></div>` : ""}
  </div>`;
}

function renderCastLedger(n) {
  const rows = n.cast_entries || [];
  if (!rows.length) return "";
  return `<div class="card" style="margin-bottom:12px"><h3>配角名册（${rows.length}）</h3>
    <p class="muted" style="font-size:12px">定稿时自动维护；写作时会注入近期活跃条目以保持口吻一致。</p>
    <div class="char-grid">${rows.slice(0, 24).map(c => `
      <div class="card char-card" style="padding:8px">
        <div class="char-name">${esc(c.name)} <span class="muted">×${c.appearance_count}</span></div>
        <div class="muted" style="font-size:12px">${esc(c.brief_role || "（无定位）")}</div>
        <div class="muted" style="font-size:11px">第${c.first_seen_chapter}-${c.last_seen_chapter}章</div>
      </div>`).join("")}
    </div>
  </div>`;
}

function renderVolumes(n) {
  if (!n.core_seed) return "";
  const proposals = renderVolumeProposals(n);
  if (!(n.volumes || []).length) {
    return `<div class="card"><h3>滚动分卷</h3>
      <p class="muted">开局只规划<strong>第 1 卷</strong>与弧结构；终局由指南针锚定。卷末生成多个下一卷方向供选择，再 append 追加。弧仍用 skeleton → 展开 → 弧末沉淀。</p>
      <div class="actions"><button class="btn" onclick="actions.generateVolumes()">📚 生成首卷规划</button></div>
    </div>`;
  }
  const items = n.volumes.map(v => `
    <div class="card chapter-item draft" style="margin-bottom:10px">
      <div class="ch-head">
        <span class="ch-title">第${v.volume_no}卷《${esc(v.title)}》
          <span class="muted">第${v.start_chapter}-${v.end_chapter}章</span></span>
        <button class="btn sm" onclick="ui.editVolume(${v.volume_no})">编辑</button>
      </div>
      <div id="volume-view-${v.volume_no}">
        <div style="font-size:13px"><b>主题：</b>${esc(v.theme)}</div>
        <div class="muted" style="font-size:13px;margin-top:4px"><b>卷摘要：</b>${esc(v.summary)}</div>
        ${(v.key_events || []).length ? `<div class="muted" style="font-size:12px;margin-top:4px"><b>关键事件：</b>${v.key_events.map(esc).join("；")}</div>` : ""}
        ${(v.arcs || []).some(a => a.status === "skeleton") ? `
        <div class="actions" style="margin-top:6px">
          <button class="btn sm" onclick="actions.replanSkeleton(${v.volume_no})">重规划 skeleton 弧</button>
        </div>` : ""}
        ${(v.arcs || []).length ? `<div style="margin-top:8px;font-size:12px">
          <b>弧结构（${v.arcs.length}）：</b>
          ${v.arcs.map(a => {
            const range = a.status === "skeleton" || !a.start_chapter
              ? `骨架·预估${a.estimated_chapters || "?"}章`
              : `第${a.start_chapter}-${a.end_chapter}章`;
            const badge = a.status === "finished" ? "已完结"
              : a.status === "skeleton" ? "待展开" : "进行中";
            const expandBtn = a.status === "skeleton"
              ? `<button class="btn sm" style="margin-top:4px" onclick="actions.expandArc(${v.volume_no}, ${a.arc_no})">展开此弧</button>`
              : "";
            return `<div class="muted" style="margin-top:4px;padding-left:8px;border-left:2px solid var(--border)">
            第${a.arc_no}弧《${esc(a.title)}》${range}
            <span class="badge ${a.status === 'finished' ? 'finalized' : ''}">${badge}</span><br>
            目标：${esc(a.goal)}${a.summary ? `<br>摘要：${esc(a.summary)}` : ""}
            ${(a.key_events || []).length ? `<br>关键事件：${a.key_events.map(esc).join("；")}` : ""}
            ${a.arc_review ? `<br><span class="muted">弧级评审已落盘</span>` : ""}
            ${expandBtn}
          </div>`;
          }).join("")}
        </div>` : ""}
      </div>
      <div class="hidden" id="volume-edit-${v.volume_no}">
        <input class="v-title" value="${esc(v.title)}" placeholder="卷名" style="width:100%;margin-bottom:6px">
        <textarea class="v-theme" rows="2" placeholder="主题">${esc(v.theme)}</textarea>
        <textarea class="v-summary" rows="3" placeholder="走向">${esc(v.summary)}</textarea>
        <div class="actions">
          <button class="btn primary sm" onclick="ui.saveVolume(${v.volume_no})">保存</button>
          <button class="btn sm" onclick="ui.cancelEditVolume(${v.volume_no})">取消</button>
        </div>
      </div>
    </div>`).join("");
  const lastVol = n.volumes[n.volumes.length - 1];
  const atEnd = (n.chapters || []).some(ch =>
    ch.status === "finalized" && ch.chapter_no === lastVol.end_chapter);
  const hasPending = (n.story_compass?.pending_volume_options || []).length > 0;
  const proposeBtn = !n.story_compass?.book_complete && atEnd && !hasPending
    ? `<button class="btn sm" onclick="actions.proposeNextVolume()">生成下一卷方向</button>` : "";
  return `${proposals}<div class="card"><h3>滚动分卷（${n.volumes.length} 卷已 append）</h3>${items}
    <div class="actions">${proposeBtn}
      <button class="btn sm" onclick="actions.generateVolumes()">重新规划首卷</button>
    </div>
  </div>`;
}

const REL_LABELS = {
  hostile: "敌对", allied: "同盟", cold_war: "冷战", dependent: "依附",
  subordinate: "从属", trade_partner: "贸易伙伴",
  secret_cooperation: "秘密合作", historical_enemy: "历史宿敌",
};

function renderFactions(n) {
  if (!n.core_seed) return "";
  if (!(n.factions || []).length) {
    return `<div class="card"><h3>阵营库</h3>
      <p class="muted">阵营随<strong>章节定稿</strong>增量建档；也可手动从蓝图识别 0-2 个开篇核心阵营。细纲生成时仅注入<strong>活跃</strong>阵营。</p>
      <div class="actions"><button class="btn" onclick="actions.generateFactions()">⚔ 识别开篇阵营（可选）</button></div>
    </div>`;
  }
  const cards = n.factions.map(f => `
    <div class="card char-card ${f.status !== "active" ? "inactive-card" : ""}">
      <div class="char-name">${esc(f.name)}
        <span class="badge">${esc(f.faction_type || "")}</span>
        <span class="badge ${f.status === "active" ? "draft" : ""}">${f.status === "active" ? "活跃" : "离场"}</span>
        ${f.first_chapter ? `<span class="muted">第${f.first_chapter}-${f.last_chapter || f.first_chapter}章</span>` : ""}</div>
      <button class="btn sm" style="margin-bottom:6px" onclick="ui.toggleFactionStatus(${f.id}, '${f.status === "active" ? "inactive" : "active"}')">${f.status === "active" ? "标为离场" : "标为活跃"}</button>
      <div class="char-identity">${esc(f.positioning || "")}</div>
      <div class="traits">${(f.tags || []).map(t => `<span class="trait">${esc(t)}</span>`).join("")}</div>
      <div class="char-sec"><b>公开立场：</b>${esc(f.public_stance || "")}</div>
      <div class="char-sec"><b>真实目标：</b>${esc(f.core_goal || "")}</div>
      ${f.hidden_goal ? `<div class="char-sec"><b>隐藏目标：</b>${esc(f.hidden_goal)}</div>` : ""}
      <div class="char-sec"><b>与主线：</b>${esc(f.conflict_with_mainline || "")}</div>
      ${(f.resources_and_advantages || []).length
        ? `<div class="char-sec"><b>资源优势：</b>${f.resources_and_advantages.map(esc).join("、")}</div>` : ""}
    </div>`).join("");
  const rels = (n.faction_relations || []).map(r => `
    <div class="rel"><span class="rel-type">[${REL_LABELS[r.relation_type] || esc(r.relation_type)}${r.intensity ? `·强度${r.intensity}` : ""}]</span>
      ${esc(r.source)} ↔ ${esc(r.target)}：${esc(r.core_conflict || r.current_state || "")}
      ${r.possible_change ? `<div class="muted" style="margin-left:12px">可能变化：${esc(r.possible_change)}</div>` : ""}</div>`).join("");
  const activeN = n.factions.filter(f => f.status === "active").length;
  return `<div class="card"><h3>阵营库（${n.factions.length}个，活跃 ${activeN}）</h3>
    <div class="char-grid">${cards}</div>
    ${rels ? `<div style="margin-top:10px"><b>阵营关系</b>${rels}</div>` : ""}
    <div class="actions"><button class="btn sm" onclick="actions.generateFactions()">从蓝图补充开篇阵营</button></div>
  </div>`;
}

const SEVERITY_ICONS = { high: "🔴", medium: "🟡", low: "🟢" };
const IMPACT_TYPE_LABELS = {
  chapter_outline: "细纲", chapter: "章节正文",
  character_state: "角色状态表", global_summary: "前文摘要",
};

function logImpact(impacted) {
  progress.log("⚠ 修订影响分析报告：");
  for (const it of impacted) {
    const icon = SEVERITY_ICONS[it.severity] || "•";
    const type = IMPACT_TYPE_LABELS[it.type] || it.type;
    progress.log(`${icon} [${type} ${it.ref}] ${it.reason}`);
    if (it.suggestion) progress.log(`   建议：${it.suggestion}`);
  }
  progress.log("（受影响的细纲/章节可用「AI 修订」或「重新生成」处理）");
}

const CRITIQUE_DIMS = {
  plot: "剧情", character: "性格", dialogue: "对话",
  setting_fit: "设定", requirement_fit: "要求", prose: "文字",
};

function renderCritique(critiqueStr, no) {
  let c;
  try { c = JSON.parse(critiqueStr || "{}"); } catch { return ""; }
  if (!c || c.overall === undefined) return "";
  const pass = c.verdict === "pass";
  const scoreSpans = Object.entries(c.scores || {}).map(([k, v]) =>
    `<span class="trait" title="${CRITIQUE_DIMS[k] || k}">${CRITIQUE_DIMS[k] || k} ${esc(v)}</span>`).join("");
  const strengths = (c.strengths || []).length
    ? `<div class="muted" style="font-size:13px;margin-top:4px">亮点：${c.strengths.map(esc).join("；")}</div>` : "";
  const issues = (c.issues || []).map(i => `<div class="issue ${esc(i.severity)}">
      [${esc(i.severity)}/${CRITIQUE_DIMS[i.type] || esc(i.type)}] ${esc(i.description)}
      ${i.suggestion ? `<div class="muted">建议：${esc(i.suggestion)}</div>` : ""}</div>`).join("");
  const reviseBtn = (!pass && (c.issues || []).length && !c.applied)
    ? `<div class="actions"><button class="btn primary sm" onclick="actions.reviseByCritique(${no})">按评审意见修订</button></div>`
    : (c.applied ? `<div class="muted" style="font-size:12px;margin-top:4px">↻ 评审问题已修订，建议再次评审确认</div>` : "");
  return `<div class="review-box">
    <span class="${pass ? "review-ok" : ""}">${pass ? "✓" : "⚠"} Reviewer 评审：${esc(c.overall)}分
      （${pass ? "达到出稿标准" : "需要修改"}）</span>
    <span class="traits" style="margin-left:8px">${scoreSpans}</span>
    ${c.comment ? `<div class="muted" style="font-size:13px;margin-top:4px">${esc(c.comment)}</div>` : ""}
    ${strengths}${issues}${reviseBtn}
  </div>`;
}

function parseReview(reviewStr) {
  try { return JSON.parse(reviewStr || "{}"); } catch { return {}; }
}

function renderReview(review) {
  if (!review || review.ok === undefined) return "";
  if (review.ok && !(review.issues || []).length) {
    return `<div class="review-box"><span class="review-ok">✓ 一致性审校通过</span></div>`;
  }
  return `<div class="review-box">⚠ 一致性审校发现 ${review.issues.length} 个问题：
    ${review.issues.map(i => `<div class="issue ${i.severity}">
      [${esc(i.severity)}/${esc(i.type)}] ${esc(i.description)}
      ${i.suggestion ? `<div class="muted">建议：${esc(i.suggestion)}</div>` : ""}</div>`).join("")}
  </div>`;
}

/* ================= 初始化 ================= */

document.querySelectorAll(".tab").forEach(t => {
  t.addEventListener("click", () => {
    state.tab = t.dataset.tab;
    document.querySelectorAll(".tab").forEach(x => x.classList.toggle("active", x === t));
    hideSegmentToolbar();
    ui.renderTab();
  });
});

initSegmentSelection();
ui.refreshList();
