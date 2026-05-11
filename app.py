import streamlit as st
from openai import OpenAI
from supabase import create_client
import base64
from datetime import datetime

# ── 配置 ─────────────────────────────────────────
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
DEEPSEEK_KEY = st.secrets["DEEPSEEK_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="我的知识库", page_icon="📚", layout="wide")

# ── 工具函数 ──────────────────────────────────────
TYPE_LABELS = {"text": "📝 文字", "image": "🖼️ 图片",
               "link": "🔗 链接", "audio": "🎵 音频", "video": "🎬 视频"}

def fmt_date(ts):
    return datetime.fromisoformat(ts[:19]).strftime("%m-%d %H:%M")

def load_notes():
    res = supabase.table("notes").select("*").order("created_at", desc=True).execute()
    return res.data or []

def save_note(note):
    supabase.table("notes").insert(note).execute()

def update_note(note_id, title, content, url):
    supabase.table("notes").update({
        "title": title or None,
        "content": content or None,
        "url": url or None,
    }).eq("id", note_id).execute()

def delete_notes(ids):
    for nid in ids:
        supabase.table("notes").delete().eq("id", nid).execute()

def notes_context(notes):
    if not notes:
        return "（暂无笔记）"
    lines = []
    for i, n in enumerate(notes):
        body = n.get("content") or n.get("url") or f"[{n['type']}文件: {n.get('filename','')}]"
        lines.append(
            f"[{i+1}] 类型:{n['type']} 标题:{n.get('title','无')} "
            f"标签:{','.join(n.get('tags') or []) or '无'} 时间:{n.get('created_at','')[:16]}\n内容:{body}"
        )
    return "\n\n".join(lines)

# ── Session State 初始化 ──────────────────────────
if "messages"      not in st.session_state: st.session_state.messages      = []
if "selected"      not in st.session_state: st.session_state.selected      = None
if "notes"         not in st.session_state: st.session_state.notes         = load_notes()
if "checked"       not in st.session_state: st.session_state.checked       = set()
if "editing_id"    not in st.session_state: st.session_state.editing_id    = None

# ── 布局 ─────────────────────────────────────────
left, mid, right = st.columns([1.2, 2, 1.4])

# ════════════════════════════════
#  左栏：笔记列表（含勾选）
# ════════════════════════════════
with left:
    st.markdown("### 📚 知识库")

    if st.button("🔄 刷新", use_container_width=True):
        st.session_state.notes  = load_notes()
        st.session_state.checked = set()
        st.rerun()

    search = st.text_input("搜索", placeholder="关键词…", label_visibility="collapsed")

    filtered = [
        n for n in st.session_state.notes
        if not search or search.lower() in (
            (n.get("title") or "") + (n.get("content") or "") + (n.get("url") or "")
        ).lower()
    ]

    if not filtered:
        st.caption("还没有笔记，在中间添加吧～")

    # 笔记列表（勾选框 + 标题按钮）
    for n in filtered:
        col_check, col_title = st.columns([0.08, 0.92])
        with col_check:
            checked = st.checkbox(
                "", value=(n["id"] in st.session_state.checked),
                key=f"chk_{n['id']}", label_visibility="collapsed"
            )
            if checked:
                st.session_state.checked.add(n["id"])
            else:
                st.session_state.checked.discard(n["id"])
        with col_title:
            label = f"{TYPE_LABELS.get(n['type'],'?')} {n.get('title') or (n.get('content') or '')[:20] or '（无标题）'}"
            if st.button(label, key=f"sel_{n['id']}", use_container_width=True):
                st.session_state.selected  = n["id"]
                st.session_state.editing_id = None

    # 多选操作栏
    st.divider()
    n_checked = len(st.session_state.checked)
    if n_checked > 0:
        st.caption(f"已选 {n_checked} 条")
        col_e, col_d, col_c = st.columns(3)
        with col_e:
            if n_checked == 1 and st.button("✏️ 编辑", use_container_width=True):
                st.session_state.editing_id = next(iter(st.session_state.checked))
                st.session_state.selected   = st.session_state.editing_id
                st.rerun()
        with col_d:
            if st.button("🗑️ 删除", use_container_width=True):
                delete_notes(list(st.session_state.checked))
                st.session_state.notes   = load_notes()
                st.session_state.checked = set()
                st.session_state.selected = None
                st.rerun()
        with col_c:
            if st.button("✕ 取消", use_container_width=True):
                st.session_state.checked    = set()
                st.session_state.editing_id = None
                st.rerun()

# ════════════════════════════════
#  中间：详情 / 编辑 / 添加
# ════════════════════════════════
with mid:
    selected_note = next(
        (n for n in st.session_state.notes if n["id"] == st.session_state.selected), None
    )

    # 编辑模式
    if st.session_state.editing_id and selected_note:
        st.markdown("#### ✏️ 编辑笔记")
        new_title   = st.text_input("标题", value=selected_note.get("title") or "")
        new_content = st.text_area("内容", value=selected_note.get("content") or "", height=160)
        new_url     = st.text_input("链接", value=selected_note.get("url") or "")
        col_s, col_x = st.columns(2)
        with col_s:
            if st.button("💾 保存修改", type="primary", use_container_width=True):
                update_note(selected_note["id"], new_title, new_content, new_url)
                st.session_state.notes      = load_notes()
                st.session_state.editing_id = None
                st.session_state.checked    = set()
                st.success("已保存！")
                st.rerun()
        with col_x:
            if st.button("取消", use_container_width=True):
                st.session_state.editing_id = None
                st.rerun()
        st.divider()

    # 详情模式
    elif selected_note:
        st.markdown(f"#### {selected_note.get('title') or '（无标题）'}")
        st.caption(f"{TYPE_LABELS.get(selected_note['type'])} · {fmt_date(selected_note['created_at'])}")
        if selected_note.get("tags"):
            st.markdown(" ".join(f"`{t}`" for t in selected_note["tags"]))
        t = selected_note["type"]
        if t == "text":
            st.markdown(selected_note.get("content", ""))
        elif t == "link":
            url = selected_note.get("url", "")
            st.markdown(f"[{url}]({url})")
        elif t == "image" and selected_note.get("data"):
            st.image(base64.b64decode(selected_note["data"]))
        elif t == "audio" and selected_note.get("data"):
            st.audio(base64.b64decode(selected_note["data"]))
        elif t == "video" and selected_note.get("data"):
            st.video(base64.b64decode(selected_note["data"]))
        st.divider()

    # 添加笔记
    with st.expander("➕ 添加笔记", expanded=not selected_note):
        note_type = st.selectbox("类型", list(TYPE_LABELS.keys()),
                                 format_func=lambda x: TYPE_LABELS[x])
        title = st.text_input("标题（可选）")
        tags  = st.text_input("标签（逗号分隔）")

        content = url = file_data = filename = None

        if note_type == "text":
            content = st.text_area("内容", height=160)
        elif note_type == "link":
            url = st.text_input("链接地址")
        else:
            uploaded = st.file_uploader("选择文件", key=f"up_{note_type}")
            if uploaded:
                file_data = base64.b64encode(uploaded.read()).decode()
                filename  = uploaded.name

        if st.button("保存笔记", type="primary"):
            new_note = {
                "id":         str(datetime.now().timestamp()),
                "type":       note_type,
                "title":      title or None,
                "tags":       [t.strip() for t in tags.split(",") if t.strip()],
                "content":    content or None,
                "url":        url or None,
                "data":       file_data or None,
                "filename":   filename or None,
                "created_at": datetime.now().isoformat(),
            }
            save_note(new_note)
            st.session_state.notes    = load_notes()
            st.session_state.selected = new_note["id"]
            st.success("已保存！")
            st.rerun()

# ════════════════════════════════
#  右栏：DeepSeek AI 对话
# ════════════════════════════════
with right:
    st.markdown("### ✦ AI 助手")

    chat_box = st.container(height=420)
    with chat_box:
        for m in st.session_state.messages:
            with st.chat_message(m["role"]):
                st.markdown(m["content"])

    user_input = st.chat_input("问关于你笔记的问题…")
    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})

        system_prompt = (
            "你是用户的个人知识库助手。用户的笔记数据库如下：\n\n"
            f"{notes_context(st.session_state.notes)}\n\n"
            "请基于笔记内容回答问题。如果笔记中没有相关内容，如实告知。"
            "回答简洁准确，使用中文。"
        )

        client = OpenAI(api_key=DEEPSEEK_KEY, base_url="https://api.deepseek.com")
        with st.spinner("思考中…"):
            resp = client.chat.completions.create(
                model="deepseek-chat",
                max_tokens=1024,
                messages=[
                    {"role": "system", "content": system_prompt},
                    *[{"role": m["role"], "content": m["content"]}
                      for m in st.session_state.messages],
                ],
            )
        reply = resp.choices[0].message.content
        st.session_state.messages.append({"role": "assistant", "content": reply})
        st.rerun()

    if st.button("清空对话", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
