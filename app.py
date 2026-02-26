"""
UAV Swarm Mission Control — Interactive Dashboard
Real-time visualization of privacy, energy, and cryptographic operations.
Run:  streamlit run app.py
"""

import streamlit as st
import networkx as nx
from pyvis.network import Network
import streamlit.components.v1 as components
import time
import random
import tempfile
import traceback

from simulation_engine import SimulationEngine, MissionPhase
from config import MISSION_CONFIG

# ───────────── page config ─────────────
st.set_page_config(
    layout="wide",
    page_title="UAV Swarm Mission Control",
    page_icon="🛸",
    initial_sidebar_state="expanded",
)

# ───────────── CSS ─────────────
CSS = """
<style>
.stApp { background-color: #0a0e17; }
[data-testid="stSidebar"] { background: #111827; border-right: 1px solid #1f2937; }
[data-testid="stMetricValue"] {
    font-family: 'Courier New', monospace; font-weight: bold;
}
div.stButton > button {
    border: 1px solid #10b981; color: #10b981; background: transparent;
    border-radius: 6px; font-family: 'Courier New', monospace;
    transition: all 0.3s; width: 100%;
}
div.stButton > button:hover { background: #10b981; color: #000; box-shadow: 0 0 12px #10b981; }
h1,h2,h3,h4 { color: #60a5fa !important; }
.hex-view {
    font-family: 'Courier New', monospace; font-size: 11px;
    color: #10b981; background: #0d1117; padding: 6px;
    border-radius: 6px; border: 1px solid #1f2937;
    word-break: break-all; line-height: 1.5;
}
.crypto-label {
    color: #9ca3af; font-size: 11px; text-transform: uppercase;
    letter-spacing: 1px; margin-bottom: 2px;
}
.key-badge {
    display: inline-block; padding: 2px 6px; border-radius: 4px;
    font-size: 11px; font-family: 'Courier New', monospace;
    background: #1e293b; border: 1px solid #334155; color: #94a3b8;
}
.stat-card {
    background: #111827; border: 1px solid #1f2937; border-radius: 8px;
    padding: 10px 14px; text-align: center;
}
.stat-label { color: #6b7280; font-size: 10px; text-transform: uppercase; letter-spacing: 1px; }
.stat-value { color: #e5e7eb; font-size: 22px; font-weight: bold; font-family: 'Courier New', monospace; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ───────────── session state ─────────────
if "engine" not in st.session_state:
    st.session_state.engine = SimulationEngine()
if "auto_play" not in st.session_state:
    st.session_state.auto_play = False
if "speed" not in st.session_state:
    st.session_state.speed = 0.5

engine: SimulationEngine = st.session_state.engine
state = engine.state

# ───────────── sidebar ─────────────
with st.sidebar:
    st.markdown("# 🛸 MISSION CONTROL")
    st.markdown("---")

    # ── controls ──
    st.markdown("### ⚙️ Simulation")
    c1, c2 = st.columns(2)
    if c1.button("▶ START"):
        st.session_state.auto_play = True
    if c2.button("⏸ PAUSE"):
        st.session_state.auto_play = False
    if st.button("⏭ STEP (1 Round)"):
        engine.step()
    if st.button("🔄 RESET"):
        st.session_state.engine = SimulationEngine()
        st.session_state.auto_play = False
        st.rerun()

    st.session_state.speed = st.slider("Speed", 0.1, 2.0, 0.5, 0.1)

    st.markdown("---")
    st.markdown("### 🛡️ Countermeasures")
    if st.button("🎯 Deploy Decoys"):
        engine.deploy_decoy()
    if st.button("⚡ EMP Blast"):
        engine.trigger_emp()
    if st.button("🔴 Escalate → THREAT"):
        engine.escalate_threat()

    st.markdown("---")
    view_mode = st.radio(
        "PERSPECTIVE", ["God Mode 👁️", "Adversary Mode 🕵️"],
        index=0, horizontal=False,
    )
    st.caption(
        "**God Mode**: Full swarm visibility.\n\n"
        "**Adversary Mode**: Only intercepted traffic."
    )

# ── auto-play loop ──
if st.session_state.auto_play:
    engine.step()
    time.sleep(st.session_state.speed)
    st.rerun()

# ═══════════════════════════════════════════════════════════
# GAME OVER BANNER
# ═══════════════════════════════════════════════════════════
if state.game_over:
    st.error("💀 MISSION FAILED — Swarm integrity below 30%")

# ═══════════════════════════════════════════════════════════
# HUD — TOP METRICS BAR
# ═══════════════════════════════════════════════════════════
m1, m2, m3, m4, m5, m6 = st.columns(6)
m1.metric("ROUND", state.round_num)
m2.metric("SCORE", f"{state.score:,}")

phase_emoji = {"PATROL": "🟢", "SURVEILLANCE": "🟡", "THREAT": "🔴"}.get(
    state.phase, ""
)
m3.metric("PHASE", f"{phase_emoji} {state.phase}")
m4.metric("DRONES", f"{state.active_drones}/{state.total_drones}")
m5.metric("AVG BATTERY", f"{state.avg_battery:.1f}%")

# Trace rate — the key privacy metric
trace_pct = state.adversary_trace_rate * 100
m6.metric(
    "TRACE SUCCESS",
    f"{trace_pct:.1f}%",
    delta=f"{state.round_trace_rate*100:.0f}% this round" if state.round_num > 0 else None,
    delta_color="inverse",  # lower is better for defender
)

# ── Phase privacy config banner ──
ph_cfg = MISSION_CONFIG.get(state.phase, {})
crypto_cfg = state.crypto_phase_config
banner_parts = [
    f"Hops: <b>{ph_cfg.get('routing_depth', '?')}</b>",
    f"Dummy: <b>{ph_cfg.get('dummy_rate', 0)*100:.0f}%</b>",
    f"Jitter: <b>{ph_cfg.get('timing_jitter_ms', 0)}ms</b>",
]
if crypto_cfg:
    banner_parts.append(f"Cipher: <b>{crypto_cfg.get('cipher', '?')}</b>")
    if crypto_cfg.get("hmac"):
        banner_parts.append("HMAC: <b>✓</b>")
    if crypto_cfg.get("sign"):
        banner_parts.append("Ed25519: <b>✓</b>")

st.markdown(
    '<div style="background:#111827;border:1px solid #1f2937;border-radius:8px;'
    'padding:6px 14px;margin:4px 0;font-size:12px;color:#9ca3af">'
    + " &nbsp;·&nbsp; ".join(banner_parts)
    + "</div>",
    unsafe_allow_html=True,
)

# ═══════════════════════════════════════════════════════════
# MAIN: MAP + CRYPTO INSPECTOR
# ═══════════════════════════════════════════════════════════
map_col, inspector_col = st.columns([3, 2])

# ── TACTICAL MAP ──
with map_col:
    st.markdown("### 🗺️ TACTICAL MAP")
    try:
        net = Network(
            height="460px", width="100%", bgcolor="#0a0e17",
            font_color="#e5e7eb", directed=False,
        )
        net.set_options("""{
            "physics": {
                "forceAtlas2Based": {"gravitationalConstant": -70,
                    "centralGravity": 0.01, "springLength": 110,
                    "springConstant": 0.04},
                "solver": "forceAtlas2Based",
                "stabilization": {"iterations": 50}
            },
            "interaction": {"hover": true, "tooltipDelay": 100}
        }""")

        god = "God" in view_mode

        for nid, drone in engine.swarm.drones.items():
            bat = drone.battery_level
            if god:
                if bat > 70:
                    color = "#10b981"
                elif bat > 40:
                    color = "#f59e0b"
                elif bat > 15:
                    color = "#ef4444"
                else:
                    color = "#6b7280"
                label = f"D{nid}"
                fp = (
                    engine.crypto.ecdh_keys[nid].fingerprint()
                    if nid in engine.crypto.ecdh_keys
                    else "?"
                )
                title = (
                    f"<b>Drone {nid}</b><br>"
                    f"Battery: {bat:.1f}%<br>"
                    f"Phase: {drone.mission_state}<br>"
                    f"Sent: {drone.messages_sent} | Relayed: {drone.messages_relayed}<br>"
                    f"<span style='color:#10b981'>Key: {fp}</span>"
                )
                size = 10 + (bat / 100) * 14
            else:
                # Adversary view: hide everything
                color = "#374151"
                label = "?"
                title = "Unknown node"
                size = 12
                # The adversary can partially identify high-traffic nodes
                if drone.messages_relayed > 3 and random.random() < 0.2:
                    color = "#ef444488"
                    label = f"T{nid}"
                    title = "<b>SUSPECTED</b>"

            net.add_node(nid, label=label, title=title, color=color, size=size)

        # Command server
        net.add_node(
            "CMD", label="⬟ BASE", color="#3b82f6", shape="diamond",
            size=30, title="<b>Command Server</b>",
        )

        graph = engine.swarm.network
        if graph is not None:
            for u, v in graph.edges():
                if god:
                    net.add_edge(u, v, color="#1f293788", width=1)
                else:
                    if random.random() < 0.06:
                        net.add_edge(u, v, color="#ef444444", width=2)

        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".html", mode="w"
        ) as tmp:
            net.save_graph(tmp.name)
            with open(tmp.name, "r", encoding="utf-8") as f:
                html = f.read()
            components.html(html, height=480, scrolling=False)

    except Exception as e:
        st.error(f"Graph error: {e}")
        st.code(traceback.format_exc())

# ── CRYPTO INSPECTOR ──
with inspector_col:
    st.markdown("### 🔐 CRYPTO INSPECTOR")

    bundle = state.last_crypto_bundle
    if bundle:
        st.markdown(
            f'<div class="crypto-label">CIPHER: {bundle["cipher"]} | '
            f'PHASE: {bundle.get("phase", "?")}</div>',
            unsafe_allow_html=True,
        )

        c1, c2 = st.columns(2)
        with c1:
            st.markdown('<div class="crypto-label">PLAINTEXT</div>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="hex-view" style="color:#60a5fa">'
                f'{bundle.get("plaintext_preview", "")}</div>',
                unsafe_allow_html=True,
            )
        with c2:
            st.markdown('<div class="crypto-label">CIPHERTEXT (HEX)</div>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="hex-view">{bundle["encrypted"]["ciphertext"][:48]}...</div>',
                unsafe_allow_html=True,
            )

        n1, n2 = st.columns(2)
        with n1:
            st.markdown('<div class="crypto-label">NONCE</div>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="hex-view">{bundle["encrypted"]["nonce"]}</div>',
                unsafe_allow_html=True,
            )
        with n2:
            st.markdown('<div class="crypto-label">AUTH TAG</div>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="hex-view">{bundle["encrypted"]["tag"]}</div>',
                unsafe_allow_html=True,
            )

        st.markdown('<div class="crypto-label">SHA3-256 HASH</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="hex-view" style="color:#f59e0b">{bundle.get("hash", "")}</div>',
            unsafe_allow_html=True,
        )

        if bundle.get("hmac"):
            st.markdown('<div class="crypto-label">HMAC-SHA256</div>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="hex-view" style="color:#ec4899">{bundle["hmac"][:48]}...</div>',
                unsafe_allow_html=True,
            )

        if bundle.get("signature"):
            st.markdown('<div class="crypto-label">Ed25519 SIGNATURE</div>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="hex-view" style="color:#a78bfa">{bundle["signature"][:48]}...</div>',
                unsafe_allow_html=True,
            )

        # ── Key Exchange ──
        st.markdown("#### 🔑 ECDH Sessions")
        if engine.crypto.session_keys:
            sessions = list(engine.crypto.session_keys.items())[-6:]
            sess_html = ""
            for pair, key_bytes in sessions:
                parts = pair.split("-")
                src = f"D{parts[0]}"
                dst = "CMD" if len(parts) > 1 and parts[1] == "-1" else f"D{parts[1]}" if len(parts) > 1 else "?"
                sess_html += (
                    f'<div style="font-size:11px;color:#d1d5db;padding:2px 0;'
                    f'border-bottom:1px solid #1f2937">'
                    f'<span style="color:#3b82f6">{src}</span> ⇌ '
                    f'<span style="color:#10b981">{dst}</span> '
                    f'<span class="key-badge">{key_bytes.hex()[:20]}...</span>'
                    f'</div>'
                )
            st.markdown(
                f'<div style="background:#0d1117;border-radius:6px;padding:6px;'
                f'border:1px solid #1f2937;max-height:150px;overflow-y:auto">{sess_html}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.caption("No ECDH sessions yet.")
    else:
        st.info("Press **STEP** or **START** to begin — crypto data will appear here.")

# ═══════════════════════════════════════════════════════════
# BOTTOM: EVENT LOG + CHARTS
# ═══════════════════════════════════════════════════════════
log_col, chart_col = st.columns([1, 2])

# ── EVENT LOG ──
with log_col:
    st.markdown("### 📟 EVENT LOG")
    log_html = ""
    for ev in list(state.events)[:40]:
        if any(w in ev for w in ["TRACE", "CRITICAL", "FAILED"]):
            c = "#ef4444"
        elif any(w in ev for w in ["PHASE", "MANUAL"]):
            c = "#f59e0b"
        elif any(w in ev for w in ["DECOY", "EMP"]):
            c = "#3b82f6"
        elif any(w in ev for w in ["Crypto", "🔐"]):
            c = "#a78bfa"
        else:
            c = "#10b981"
        log_html += (
            f'<div style="color:{c};font-family:monospace;font-size:11px;'
            f'padding:2px 0;border-bottom:1px solid #1f293744">{ev}</div>'
        )
    st.markdown(
        f'<div style="max-height:320px;overflow-y:auto;padding:8px;'
        f'background:#111827;border-radius:8px">{log_html}</div>',
        unsafe_allow_html=True,
    )

# ── TELEMETRY CHARTS ──
with chart_col:
    st.markdown("### 📊 TELEMETRY")
    hist = engine.history

    if len(hist["rounds"]) > 1:
        t1, t2, t3, t4 = st.tabs([
            "Trace Rate %", "Battery", "Messages", "Score",
        ])
        with t1:
            st.line_chart(
                data={"Adversary Trace Rate %": hist["trace_rate"]},
                color=["#ef4444"],
            )
            st.caption("Lower = better privacy. THREAT phase should approach 0%.")
        with t2:
            st.line_chart(
                data={
                    "Average": hist["battery_avg"],
                    "Minimum": hist["battery_min"],
                },
                color=["#3b82f6", "#ef4444"],
            )
        with t3:
            st.line_chart(
                data={
                    "Real": hist["messages"],
                    "Dummy": hist["dummy"],
                },
                color=["#10b981", "#6b7280"],
            )
            st.caption("More dummy traffic = better privacy cover.")
        with t4:
            st.line_chart(
                data={"Score": hist["score"]},
                color=["#a78bfa"],
            )
            st.caption("Score = messages delivered safely + dummy cover + phase bonus.")
    else:
        st.info("Run the simulation to see telemetry data.")

# ── Summary stats ──
if state.round_num > 0:
    st.markdown("---")
    s1, s2, s3, s4, s5 = st.columns(5)
    s1.markdown(
        f'<div class="stat-card"><div class="stat-label">Total Messages</div>'
        f'<div class="stat-value">{state.total_messages_sent}</div></div>',
        unsafe_allow_html=True,
    )
    s2.markdown(
        f'<div class="stat-card"><div class="stat-label">Dummy Traffic</div>'
        f'<div class="stat-value">{state.total_dummy_messages}</div></div>',
        unsafe_allow_html=True,
    )
    ratio = (
        state.total_dummy_messages / max(1, state.total_messages_sent) * 100
    )
    s3.markdown(
        f'<div class="stat-card"><div class="stat-label">Dummy Ratio</div>'
        f'<div class="stat-value">{ratio:.0f}%</div></div>',
        unsafe_allow_html=True,
    )
    s4.markdown(
        f'<div class="stat-card"><div class="stat-label">Observations</div>'
        f'<div class="stat-value">{state.adversary_observations}</div></div>',
        unsafe_allow_html=True,
    )
    # Crypto timing
    crypto_stats = engine.crypto.log.stats()
    enc_alg = crypto_cfg.get("cipher", "AES-256-GCM") if crypto_cfg else "AES-256-GCM"
    enc_us = crypto_stats.get(enc_alg, {}).get("avg_us", 0) if crypto_stats else 0
    s5.markdown(
        f'<div class="stat-card"><div class="stat-label">Encrypt Time</div>'
        f'<div class="stat-value">{enc_us}μs</div></div>',
        unsafe_allow_html=True,
    )
