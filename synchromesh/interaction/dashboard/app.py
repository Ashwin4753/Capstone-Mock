from __future__ import annotations

import asyncio
from typing import Any, Dict

import streamlit as st

from core import SynchroMeshOrchestrator
from integration import FigmaMCPClient, GitHubMCPClient, LocalRepoClient, RepoAdapter
from interaction import ApprovalGate
from interaction.dashboard import GovernanceUI, ReasoningPanel, Visualizer

def _inject_global_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --bg: #0b1020;
            --panel: #121a2b;
            --panel-2: #18233a;
            --panel-3: #1c2742;
            --text: #eef3ff;
            --muted: #9fb0d1;
            --border: rgba(255,255,255,0.08);
            --accent: #4da3ff;
            --accent-2: #7c5cff;
            --success: #1fd286;
            --warning: #f7b84b;
            --danger: #ff5f7a;
            --shadow: 0 10px 30px rgba(0,0,0,0.28);
        }

        .stApp {
            background:
                radial-gradient(circle at top left, rgba(124,92,255,0.16), transparent 28%),
                radial-gradient(circle at top right, rgba(77,163,255,0.16), transparent 24%),
                linear-gradient(180deg, #0b1020 0%, #0e1426 100%);
            color: var(--text);
        }

        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #111829 0%, #0e1524 100%);
            border-right: 1px solid var(--border);
        }

        [data-testid="stSidebar"] * {
            color: var(--text) !important;
        }

        .block-container {
            padding-top: 1.2rem;
            padding-bottom: 2rem;
            max-width: 1450px;
        }

        .synchro-title {
            font-size: 2rem;
            font-weight: 800;
            letter-spacing: -0.02em;
            color: var(--text);
            margin-bottom: 0.2rem;
        }

        .synchro-subtitle {
            color: var(--muted);
            font-size: 0.98rem;
            margin-bottom: 1.2rem;
        }

        .premium-card {
            background: linear-gradient(180deg, rgba(24,35,58,0.96), rgba(18,26,43,0.96));
            border: 1px solid var(--border);
            border-radius: 18px;
            padding: 1rem 1rem 0.9rem 1rem;
            box-shadow: var(--shadow);
            margin-bottom: 1rem;
        }

        .premium-card h3,
        .premium-card h4 {
            color: var(--text);
            margin-top: 0;
        }

        .section-title {
            font-size: 1.05rem;
            font-weight: 700;
            color: var(--text);
            margin-bottom: 0.75rem;
        }

        .section-caption {
            color: var(--muted);
            font-size: 0.9rem;
            margin-bottom: 0.8rem;
        }

        .hero-banner {
            background:
                linear-gradient(135deg, rgba(77,163,255,0.24), rgba(124,92,255,0.22)),
                linear-gradient(180deg, rgba(24,35,58,0.98), rgba(18,26,43,0.98));
            border: 1px solid rgba(255,255,255,0.10);
            border-radius: 22px;
            padding: 1.25rem 1.25rem;
            box-shadow: var(--shadow);
            margin-bottom: 1rem;
        }

        .hero-title {
            font-size: 1.4rem;
            font-weight: 800;
            color: white;
            margin-bottom: 0.35rem;
        }

        .hero-text {
            color: #d9e5ff;
            font-size: 0.95rem;
        }

        .metric-shell {
            background: linear-gradient(180deg, rgba(28,39,66,0.98), rgba(18,26,43,0.98));
            border: 1px solid var(--border);
            border-radius: 18px;
            padding: 0.95rem 1rem;
            box-shadow: var(--shadow);
        }

        .metric-label {
            color: var(--muted);
            font-size: 0.82rem;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            margin-bottom: 0.3rem;
        }

        .metric-value {
            color: white;
            font-size: 1.7rem;
            font-weight: 800;
            line-height: 1.1;
        }

        .metric-note {
            color: #c7d6f5;
            font-size: 0.85rem;
            margin-top: 0.25rem;
        }

        .pill {
            display: inline-block;
            padding: 0.26rem 0.62rem;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0.01em;
            margin-right: 0.35rem;
            margin-bottom: 0.35rem;
        }

        .pill-blue { background: rgba(77,163,255,0.18); color: #9fceff; border: 1px solid rgba(77,163,255,0.28);}
        .pill-violet { background: rgba(124,92,255,0.18); color: #cab8ff; border: 1px solid rgba(124,92,255,0.28);}
        .pill-green { background: rgba(31,210,134,0.18); color: #96f1c9; border: 1px solid rgba(31,210,134,0.28);}
        .pill-amber { background: rgba(247,184,75,0.18); color: #ffd798; border: 1px solid rgba(247,184,75,0.28);}
        .pill-red { background: rgba(255,95,122,0.18); color: #ffb0be; border: 1px solid rgba(255,95,122,0.28);}
        .pill-slate { background: rgba(255,255,255,0.08); color: #d8e2f6; border: 1px solid rgba(255,255,255,0.10);}

        .status-ok {
            color: var(--success);
            font-weight: 700;
        }

        .status-warn {
            color: var(--warning);
            font-weight: 700;
        }

        .status-bad {
            color: var(--danger);
            font-weight: 700;
        }

        .divider-soft {
            border-top: 1px solid var(--border);
            margin: 0.6rem 0 0.8rem 0;
        }

        div[data-testid="stDataFrame"] {
            border: 1px solid var(--border);
            border-radius: 16px;
            overflow: hidden;
            background: rgba(18,26,43,0.92);
        }

        div[data-testid="stTabs"] button {
            border-radius: 12px !important;
        }

        .stButton > button {
            border-radius: 12px;
            border: 1px solid var(--border);
            background: linear-gradient(180deg, #223152, #1b2742);
            color: white;
            font-weight: 700;
        }

        .stButton > button:hover {
            border-color: rgba(77,163,255,0.45);
            color: white;
        }

        .stDownloadButton > button {
            border-radius: 12px;
        }

        .stTextInput input,
        .stTextArea textarea,
        .stSelectbox div[data-baseweb="select"] > div,
        .stMultiSelect div[data-baseweb="select"] > div {
            background: rgba(13,18,31,0.78) !important;
            color: white !important;
            border-radius: 12px !important;
            border: 1px solid rgba(255,255,255,0.08) !important;
        }

        .stRadio label, .stCheckbox label {
            color: var(--text) !important;
        }

        .stAlert {
            border-radius: 14px;
        }

        .small-note {
            color: var(--muted);
            font-size: 0.84rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_header() -> None:
    st.markdown('<div class="synchro-title">SynchroMesh Modernization Console</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="synchro-subtitle">A premium governance and modernization control center for full-stack engineering systems.</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="hero-banner">
            <div class="hero-title">Engineering modernization with governed execution</div>
            <div class="hero-text">
                Analyze frontend, backend, config, and architecture concerns through a six-agent pipeline with
                policy-aware approvals, patch planning, and audit-friendly reporting.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _build_repo_client(
    *,
    repo_root: str,
    use_local: bool,
    use_github_mcp: bool,
    github_owner: str,
    github_repo: str,
) -> RepoAdapter:
    local_client = LocalRepoClient(repo_root=repo_root) if use_local and repo_root else None

    github_client = None
    if use_github_mcp:
        github_client = GitHubMCPClient()

    return RepoAdapter(
        local_client=local_client,
        github_client=github_client,
        prefer_local_for_files=True,
        prefer_mcp_for_analysis=True,
    )


async def _set_github_repo_if_needed(repo_client: RepoAdapter, owner: str, repo: str) -> None:
    github = getattr(repo_client, "github", None)
    if github and owner and repo and hasattr(github, "set_repo"):
        await github.set_repo(owner, repo)


async def _run_pipeline(
    *,
    repo_root: str,
    use_local: bool,
    use_github_mcp: bool,
    github_owner: str,
    github_repo: str,
    use_figma: bool,
    figma_file_key: str,
    export_dir: str,
    require_approved: bool,
) -> Dict[str, Any]:
    repo_client = _build_repo_client(
        repo_root=repo_root,
        use_local=use_local,
        use_github_mcp=use_github_mcp,
        github_owner=github_owner,
        github_repo=github_repo,
    )

    await _set_github_repo_if_needed(repo_client, github_owner, github_repo)

    figma_tokens: Dict[str, Any] = {}
    if use_figma:
        figma_client = FigmaMCPClient()
        try:
            figma_tokens = await figma_client.fetch_tokens(file_key=figma_file_key)
        except Exception:
            figma_tokens = {}

    orchestrator = SynchroMeshOrchestrator(repo_client=repo_client)

    return await orchestrator.run(
        repo_root="",
        figma_tokens=figma_tokens,
        export_output_dir=export_dir or None,
        require_approved=require_approved,
    )


def main() -> None:
    st.set_page_config(
        page_title="SynchroMesh Modernization Console",
        page_icon="🛠️",
        layout="wide",
    )
    _inject_global_styles()
    _render_header()

    with st.sidebar:
        st.markdown("### Run Configuration")
        st.markdown('<div class="small-note">Configure data sources and execution behavior.</div>', unsafe_allow_html=True)

        repo_root = st.text_input("Local Repository Root", value="")
        use_local = st.checkbox("Use Local Repository", value=True)

        st.markdown("---")
        use_github_mcp = st.checkbox("Use GitHub MCP Enrichment", value=False)
        github_owner = st.text_input("GitHub Owner", value="")
        github_repo = st.text_input("GitHub Repo", value="")

        st.markdown("---")
        use_figma = st.checkbox("Use Figma Tokens", value=False)
        figma_file_key = st.text_input("Figma File Key", value="")

        st.markdown("---")
        export_dir = st.text_input("Export Output Directory", value="artifacts/run_outputs")
        require_approved = st.checkbox("Require Approval Before Apply", value=False)

        st.markdown("---")
        run_clicked = st.button("Run Modernization Pipeline", type="primary", use_container_width=True)

    if not run_clicked:
        st.info("Configure the pipeline on the left and launch a run.")
        return

    if not repo_root and not use_github_mcp:
        st.error("Provide a local repository root or enable GitHub MCP enrichment.")
        return

    with st.spinner("Running modernization pipeline..."):
        try:
            result = asyncio.run(
                _run_pipeline(
                    repo_root=repo_root,
                    use_local=use_local,
                    use_github_mcp=use_github_mcp,
                    github_owner=github_owner,
                    github_repo=github_repo,
                    use_figma=use_figma,
                    figma_file_key=figma_file_key,
                    export_dir=export_dir,
                    require_approved=require_approved,
                )
            )
        except Exception as exc:
            st.exception(exc)
            return

    metrics = result.get("metrics", {})
    findings = result.get("analysis_findings", []) or []
    recommendations = result.get("modernization_recommendations", []) or []
    governed_actions = result.get("governed_actions", []) or []
    patch_plans = result.get("patch_plans", []) or []
    warnings = result.get("warnings", []) or []
    errors = result.get("errors", []) or []
    fallback_events = result.get("fallback_events", []) or []

    visualizer = Visualizer()
    governance_ui = GovernanceUI()
    reasoning_panel = ReasoningPanel()
    approval_gate = ApprovalGate()

    approval_items = approval_gate.build_approval_items(recommendations, governed_actions)
    approval_items = approval_gate.apply_interactive_policy(approval_items)
    approval_summary = approval_gate.summarize(approval_items)

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        [
            "Overview",
            "Findings",
            "Governance",
            "Execution",
            "Reasoning",
        ]
    )

    with tab1:
        visualizer.render_headline_metrics(metrics)
        visualizer.render_operating_context(result)
        col1, col2 = st.columns([1.1, 1])
        with col1:
            visualizer.render_category_breakdown(metrics)
            visualizer.render_top_impacted_files(metrics)
        with col2:
            visualizer.render_recommendation_breakdown(metrics)
            visualizer.render_risk_breakdown(metrics)

        if warnings or errors or fallback_events:
            st.markdown('<div class="premium-card">', unsafe_allow_html=True)
            st.markdown('<div class="section-title">Operational Signals</div>', unsafe_allow_html=True)
            if warnings:
                st.warning(f"{len(warnings)} warning(s) detected during the run.")
                st.json(warnings)
            if errors:
                st.error(f"{len(errors)} error(s) detected during the run.")
                st.json(errors)
            if fallback_events:
                st.info(f"{len(fallback_events)} fallback event(s) recorded.")
                st.json(fallback_events)
            st.markdown("</div>", unsafe_allow_html=True)

    with tab2:
        visualizer.render_findings_table(findings)
        visualizer.render_recommendations_table(recommendations)

    with tab3:
        governance_ui.render_summary(approval_summary)
        governance_ui.render_table(approval_items)
        decisions = governance_ui.render_review_controls(approval_items)

        if decisions:
            updated_items = approval_gate.apply_user_decisions(approval_items, decisions)
            st.markdown('<div class="premium-card">', unsafe_allow_html=True)
            st.markdown('<div class="section-title">Decision Preview</div>', unsafe_allow_html=True)
            st.dataframe(updated_items, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

    with tab4:
        visualizer.render_execution_summary(patch_plans)
        visualizer.render_diff_panels(result.get("diffs", []) or [])

        exported = result.get("exported_paths", {})
        if exported:
            st.markdown('<div class="premium-card">', unsafe_allow_html=True)
            st.markdown('<div class="section-title">Exported Artifacts</div>', unsafe_allow_html=True)
            st.json(exported)
            st.markdown("</div>", unsafe_allow_html=True)

    with tab5:
        reasoning_panel.render_stage_status(
            result.get("stage_status", {}),
            result.get("stage_timings", {}),
        )
        reasoning_panel.render_agent_outputs(result.get("agent_outputs", {}))
        reasoning_panel.render_trace_logs(result.get("trace_logs", []))
        reasoning_panel.render_timeline(result.get("timeline", []))


if __name__ == "__main__":
    main()