from __future__ import annotations

from typing import Any, Dict, List

import streamlit as st

class ReasoningPanel:
    """
    Premium reasoning and pipeline visibility for the 6-agent system.
    """

    AGENT_ORDER = [
        "archaeologist",
        "analyzer",
        "strategist",
        "governor",
        "syncer",
        "evaluator",
    ]

    def render_agent_outputs(self, agent_outputs: Dict[str, Any]) -> None:
        st.markdown('<div class="premium-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Agent Outputs</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-caption">High-level output snapshots from each intelligence layer.</div>', unsafe_allow_html=True)

        if not agent_outputs:
            st.info("No agent outputs available.")
            st.markdown("</div>", unsafe_allow_html=True)
            return

        for agent_name in self.AGENT_ORDER:
            payload = agent_outputs.get(agent_name)
            if payload is None:
                continue

            with st.expander(agent_name.title(), expanded=False):
                summary = payload.get("summary", {}) if isinstance(payload, dict) else {}
                if summary:
                    st.json(summary)
                else:
                    st.write(payload)

        st.markdown("</div>", unsafe_allow_html=True)

    def render_stage_status(self, stage_status: Dict[str, str], stage_timings: Dict[str, Dict[str, Any]]) -> None:
        st.markdown('<div class="premium-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Stage Status</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-caption">Execution state across the six-stage orchestration lifecycle.</div>', unsafe_allow_html=True)

        if not stage_status:
            st.info("No stage status available.")
            st.markdown("</div>", unsafe_allow_html=True)
            return

        rows = []
        for stage, status in stage_status.items():
            timing = stage_timings.get(stage, {})
            rows.append(
                {
                    "Stage": stage,
                    "Status": status,
                    "Started At": timing.get("started_at", ""),
                    "Completed At": timing.get("completed_at", ""),
                    "Failed At": timing.get("failed_at", ""),
                }
            )

        st.dataframe(rows, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    def render_trace_logs(self, trace_logs: List[Dict[str, Any]]) -> None:
        st.markdown('<div class="premium-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Trace Logs</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-caption">Low-level event visibility for pipeline explainability.</div>', unsafe_allow_html=True)

        if not trace_logs:
            st.info("No trace logs available.")
            st.markdown("</div>", unsafe_allow_html=True)
            return

        rows = []
        for entry in trace_logs:
            rows.append(
                {
                    "Timestamp": entry.get("timestamp", ""),
                    "Stage": entry.get("stage", ""),
                    "Event": entry.get("event", ""),
                    "Payload": entry.get("payload", {}),
                }
            )

        st.dataframe(rows, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    def render_timeline(self, timeline: List[Dict[str, Any]]) -> None:
        st.markdown('<div class="premium-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Run Timeline</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-caption">Chronological view of stage events across the run.</div>', unsafe_allow_html=True)

        if not timeline:
            st.info("No timeline available.")
            st.markdown("</div>", unsafe_allow_html=True)
            return

        rows = []
        for item in timeline:
            rows.append(
                {
                    "Timestamp": item.get("timestamp", ""),
                    "Event": item.get("event", ""),
                    "Stage": item.get("stage", ""),
                    "Reason": item.get("reason", ""),
                }
            )

        st.dataframe(rows, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)