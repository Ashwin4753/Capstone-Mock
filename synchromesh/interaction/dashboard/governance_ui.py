from __future__ import annotations

from typing import Any, Dict, List

import streamlit as st

class GovernanceUI:
    """
    Premium governance and approval rendering for Streamlit.
    """

    def render_summary(self, approval_summary: Dict[str, Any]) -> None:
        c1, c2, c3, c4, c5 = st.columns(5)
        self._mini_metric(c1, "Approval Items", approval_summary.get("total_items", 0), "pill-blue")
        self._mini_metric(c2, "Approval Required", approval_summary.get("approval_required_count", 0), "pill-amber")
        self._mini_metric(c3, "Auto Allowed", approval_summary.get("auto_allowed_count", 0), "pill-green")
        self._mini_metric(c4, "Approved", approval_summary.get("approved_count", 0), "pill-green")
        self._mini_metric(c5, "Rejected", approval_summary.get("rejected_count", 0), "pill-red")

    def render_table(self, approval_items: List[Dict[str, Any]]) -> None:
        st.markdown('<div class="premium-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Governance Review Queue</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-caption">Review the policy posture of modernization recommendations before execution.</div>', unsafe_allow_html=True)

        if not approval_items:
            st.info("No governance items to review.")
        else:
            rows = []
            for item in approval_items:
                rows.append(
                    {
                        "File": item.get("file_path", ""),
                        "Title": item.get("title", ""),
                        "Proposal": item.get("proposal_type", ""),
                        "Risk": item.get("risk_level", ""),
                        "Approval Required": item.get("requires_approval", False),
                        "Auto Allowed": item.get("allowed_to_apply", False),
                        "Approved": item.get("approved", False),
                        "Rejected": item.get("rejected", False),
                        "Policy Tags": ", ".join(item.get("policy_tags", []) or []),
                    }
                )
            st.dataframe(rows, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    def render_review_controls(self, approval_items: List[Dict[str, Any]]) -> Dict[str, bool]:
        decisions: Dict[str, bool] = {}

        st.markdown('<div class="premium-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Interactive Approval Controls</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-caption">Approve, reject, or inspect individual modernization actions.</div>', unsafe_allow_html=True)

        if not approval_items:
            st.info("No governance items available.")
            st.markdown("</div>", unsafe_allow_html=True)
            return decisions

        for item in approval_items:
            risk_class = self._risk_class(str(item.get("risk_level", "MEDIUM")))
            with st.expander(f"{item.get('title', 'Recommendation')} — {item.get('file_path', '')}", expanded=False):
                st.markdown(
                    f"""
                    <span class="pill {risk_class}">{item.get("risk_level", "MEDIUM")}</span>
                    <span class="pill pill-violet">{item.get("proposal_type", "")}</span>
                    """,
                    unsafe_allow_html=True,
                )
                st.markdown(f"**Current State:** `{item.get('current_state', '')}`")
                st.markdown(f"**Proposed State:** `{item.get('proposed_state', '')}`")
                if item.get("target_symbol"):
                    st.markdown(f"**Target Symbol:** `{item.get('target_symbol', '')}`")
                st.markdown(f"**Reasoning:** {item.get('reasoning', '')}")
                st.markdown(f"**Governance Reason:** {item.get('governance_reason', '')}")

                tags = item.get("policy_tags", []) or []
                if tags:
                    st.markdown("**Policy Tags**")
                    st.markdown(
                        "".join(f'<span class="pill pill-slate">{tag}</span>' for tag in tags),
                        unsafe_allow_html=True,
                    )

                if item.get("requires_approval", True):
                    decision = st.radio(
                        "Decision",
                        options=["Pending", "Approve", "Reject"],
                        horizontal=True,
                        key=f"approval_decision_{item['approval_id']}",
                    )
                    if decision == "Approve":
                        decisions[item["approval_id"]] = True
                    elif decision == "Reject":
                        decisions[item["approval_id"]] = False
                else:
                    st.markdown('<span class="status-ok">This item is auto-eligible under current governance policy.</span>', unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)
        return decisions

    def _mini_metric(self, container, label: str, value: Any, pill_class: str) -> None:
        with container:
            st.markdown(
                f"""
                <div class="metric-shell">
                    <div class="metric-label">{label}</div>
                    <div class="metric-value">{value}</div>
                    <div style="margin-top:0.4rem;"><span class="pill {pill_class}">{label}</span></div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    def _risk_class(self, risk: str) -> str:
        upper = risk.upper()
        if upper == "LOW":
            return "pill-green"
        if upper == "HIGH":
            return "pill-red"
        return "pill-amber"