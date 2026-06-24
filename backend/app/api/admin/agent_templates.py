"""Agent 模板市场 API — 预置多 Agent 协作方案，一键部署。"""
from __future__ import annotations
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ...db.session import get_db
from ...db.models import User, AgentTemplate, Agent, AgentSkill, Skill
from ...deps import require_admin_or_operator

router = APIRouter(prefix="/api/admin/agent-templates", tags=["admin"])


@router.get("")
async def list_templates(
    category: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin_or_operator),
):
    q = select(AgentTemplate).order_by(AgentTemplate.id)
    if category:
        q = q.where(AgentTemplate.category == category)
    return (await db.execute(q)).scalars().all()


@router.get("/categories")
async def get_categories(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin_or_operator),
):
    rows = (await db.execute(
        select(AgentTemplate.category).distinct()
    )).scalars().all()
    return rows


@router.get("/{template_id}")
async def get_template(
    template_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin_or_operator),
):
    tpl = (await db.execute(select(AgentTemplate).where(AgentTemplate.id == template_id))).scalar_one_or_none()
    if not tpl:
        raise HTTPException(404)
    return tpl


# ---------------------------------------------------------------------------
# 完整模板配置 — 包含 system_prompt + 模型参数 + 预置技能 + 建议工作流
# ---------------------------------------------------------------------------

TEMPLATE_CONFIGS: dict[str, dict] = {
    "hr-recruitment": {
        "code": "hr-recruitment",
        "name": "招聘流程",
        "description": "简历筛选 → 面试邀约 → 面试 → 录用审批，多 Agent 协同完成招聘全流程",
        "category": "hr",
        "icon": "👥",
        "agents": [
            {
                "code": "recruiter",
                "name": "招聘专员",
                "description": "负责简历筛选、候选人沟通和面试安排",
                "system_prompt": "你是一位专业的招聘专员，负责筛选简历、联系候选人、安排面试。需要高效沟通，及时跟进。",
                "effort": "medium",
                "skills": [],
                "mcp_servers": [],
            },
            {
                "code": "interviewer",
                "name": "面试官",
                "description": "负责技术面试和综合评估",
                "system_prompt": "你是一位资深面试官，负责对候选人进行技术面试和综合能力评估。需要客观公正，给出详细反馈。",
                "effort": "high",
                "skills": [],
                "mcp_servers": [],
            },
            {
                "code": "offer-manager",
                "name": "录用经理",
                "description": "负责薪资谈判和录用审批",
                "system_prompt": "你是一位录用经理，负责薪资方案制定、录用审批和入职安排。需要平衡公司利益和候选人期望。",
                "effort": "high",
                "skills": [],
                "mcp_servers": [],
            },
        ],
        "suggested_workflows": ["onboarding-pipeline"],
    },
    "customer-service": {
        "code": "customer-service",
        "name": "客户服务中心",
        "description": "一线客服 → 技术支持 → 升级处理，分级响应客户问题",
        "category": "support",
        "icon": "🎧",
        "agents": [
            {
                "code": "tier1-support",
                "name": "一线客服",
                "description": "处理常见问题咨询和工单创建",
                "system_prompt": "你是一线客服代表，快速响应客户咨询，解决常见问题。无法解决的问题转交技术支持。",
                "effort": "low",
                "skills": [],
                "mcp_servers": [],
            },
            {
                "code": "tier2-tech",
                "name": "技术支持",
                "description": "处理技术问题和故障排查",
                "system_prompt": "你是技术支持工程师，负责处理一线升级的技术问题，进行故障排查和方案制定。",
                "effort": "high",
                "skills": [],
                "mcp_servers": [],
            },
            {
                "code": "escalation-manager",
                "name": "升级经理",
                "description": "处理紧急问题和客户投诉",
                "system_prompt": "你是升级经理，负责处理紧急事件和客户投诉，协调资源确保问题快速解决。",
                "effort": "high",
                "skills": [],
                "mcp_servers": [],
            },
        ],
        "suggested_workflows": [],
    },
    "marketing-campaign": {
        "code": "marketing-campaign",
        "name": "营销活动执行",
        "description": "策略制定 → 内容创作 → 设计 → 审核，矩阵式营销协作",
        "category": "marketing",
        "icon": "📢",
        "agents": [
            {
                "code": "strategist",
                "name": "营销策略师",
                "description": "制定营销策略和活动方案",
                "system_prompt": "你是一位营销策略师，负责分析市场趋势、制定营销策略、规划活动方案。",
                "effort": "high",
                "skills": [],
                "mcp_servers": [],
            },
            {
                "code": "copywriter",
                "name": "文案创作",
                "description": "撰写营销文案和宣传材料",
                "system_prompt": "你是一位文案专家，负责撰写各种营销文案、广告语、宣传材料。",
                "effort": "medium",
                "skills": [],
                "mcp_servers": [],
            },
            {
                "code": "content-designer",
                "name": "内容设计",
                "description": "设计视觉素材和排版",
                "system_prompt": "你是一位内容设计师，负责设计营销素材的视觉风格、排版和配图方案。",
                "effort": "medium",
                "skills": [],
                "mcp_servers": [],
            },
            {
                "code": "reviewer",
                "name": "内容审核",
                "description": "审核营销内容合规性和品牌一致性",
                "system_prompt": "你是内容审核员，确保所有营销内容符合品牌规范和法律合规要求。",
                "effort": "high",
                "skills": [],
                "mcp_servers": [],
            },
        ],
        "suggested_workflows": [],
    },
    "employee-onboarding": {
        "code": "employee-onboarding",
        "name": "员工入职流程",
        "description": "HR通知 → IT设备准备 → 导师分配 → 欢迎引导，新员工一站式入职",
        "category": "admin",
        "icon": "🎉",
        "agents": [
            {
                "code": "hr-onboarding",
                "name": "入职HR",
                "description": "负责入职通知和入职资料收集",
                "system_prompt": "你负责新员工入职流程的HR环节，发送入职通知、收集入职资料、安排入职培训。",
                "effort": "medium",
                "skills": [],
                "mcp_servers": [],
            },
            {
                "code": "it-setup",
                "name": "IT配置员",
                "description": "负责工位和设备准备",
                "system_prompt": "你负责为新员工准备电脑、账号、权限等IT资源，确保入职当天一切就绪。",
                "effort": "medium",
                "skills": [],
                "mcp_servers": [],
            },
            {
                "code": "mentor",
                "name": "导师",
                "description": "负责新员工指导和融入",
                "system_prompt": "你是一位导师，负责指导新员工熟悉团队、业务和文化，帮助快速融入。",
                "effort": "medium",
                "skills": [],
                "mcp_servers": [],
            },
            {
                "code": "welcome-buddy",
                "name": "欢迎伙伴",
                "description": "负责新员工关怀和答疑",
                "system_prompt": "你是一位热情的小伙伴，负责新员工的日常关怀、答疑和组织欢迎活动。",
                "effort": "low",
                "skills": [],
                "mcp_servers": [],
            },
        ],
        "suggested_workflows": ["onboarding-pipeline"],
    },
    "software-dev-team": {
        "code": "software-dev-team",
        "name": "软件开发团队",
        "description": "产品经理 → 开发者 → QA → DevOps，全流程软件交付协作",
        "category": "it",
        "icon": "💻",
        "agents": [
            {
                "code": "pm",
                "name": "产品经理",
                "description": "负责需求分析和产品规划",
                "system_prompt": "你是一位产品经理，负责需求调研、产品规划、PRD编写和进度跟踪。",
                "effort": "high",
                "skills": [],
                "mcp_servers": [],
            },
            {
                "code": "developer",
                "name": "开发者",
                "description": "负责代码实现和技术方案",
                "system_prompt": "你是一位全栈开发者，负责技术方案设计、编码实现和代码审查。",
                "effort": "high",
                "skills": [],
                "mcp_servers": [],
            },
            {
                "code": "qa",
                "name": "测试工程师",
                "description": "负责测试用例和质量管理",
                "system_prompt": "你是一位QA工程师，负责编写测试用例、执行测试、跟踪缺陷。",
                "effort": "medium",
                "skills": [],
                "mcp_servers": [],
            },
            {
                "code": "devops",
                "name": "DevOps工程师",
                "description": "负责CI/CD和运维部署",
                "system_prompt": "你负责CI/CD流水线、环境部署、监控告警和运维支持。",
                "effort": "medium",
                "skills": [],
                "mcp_servers": [],
            },
        ],
        "suggested_workflows": [],
    },
}


@router.post("/{template_id}/deploy")
async def deploy_template(
    template_id: int,
    payload: dict | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin_or_operator),
):
    """一键部署模板 — 创建完整 Agent 配置，返回下一步操作指引。"""
    tpl = (await db.execute(select(AgentTemplate).where(AgentTemplate.id == template_id))).scalar_one_or_none()
    if not tpl:
        raise HTTPException(404, "模板不存在")

    # 优先使用结构化 TEMPLATE_CONFIGS，fallback 到 yaml_text
    config = TEMPLATE_CONFIGS.get(tpl.code)
    if not config:
        import yaml
        raw = yaml.safe_load(tpl.yaml_text)
        if not raw or "agents" not in raw:
            raise HTTPException(400, "模板配置无效")
        config = {
            "code": tpl.code,
            "name": tpl.name,
            "description": tpl.description or "",
            "category": tpl.category,
            "agents": raw["agents"],
            "suggested_workflows": [],
        }

    created = []
    next_steps: list[str] = []

    for agent_cfg in config["agents"]:
        code = agent_cfg["code"]
        # 避免 code 冲突
        if (await db.execute(select(Agent).where(Agent.code == code))).scalar_one_or_none():
            code = f"{code}-{user.id}-{tpl.id}"

        agent = Agent(
            code=code,
            name=agent_cfg["name"],
            description=agent_cfg.get("description", ""),
            system_prompt=agent_cfg.get("system_prompt", ""),
            effort=agent_cfg.get("effort", "medium"),
            enabled=True,
        )
        db.add(agent)
        await db.flush()

        created.append({"id": agent.id, "name": agent.name, "code": agent.code})

        # 生成下一步操作指引
        agent_steps = []
        if agent_cfg.get("skills"):
            agent_steps.append(f"为 {agent.name} 配置技能: {', '.join(agent_cfg['skills'])}")
        else:
            agent_steps.append(f"为 {agent.name} 配置技能（如有需要）")
        if agent_cfg.get("mcp_servers"):
            agent_steps.append(f"为 {agent.name} 配置 MCP 服务器: {', '.join(agent_cfg['mcp_servers'])}")
        else:
            agent_steps.append(f"为 {agent.name} 配置 MCP 服务器（如有需要）")
        agent_steps.append(f"为 {agent.name} 关联知识库（如有需要）")
        next_steps.extend(agent_steps)

    if config.get("suggested_workflows"):
        next_steps.append(f"建议创建工作流: {', '.join(config['suggested_workflows'])}")

    tpl.usage_count = (tpl.usage_count or 0) + 1
    await db.commit()

    return {
        "template": tpl.name,
        "agents": created,
        "count": len(created),
        "next_steps": next_steps,
    }


BUILTIN_TEMPLATES = [
    {
        "code": "hr-recruitment",
        "name": "招聘流程",
        "description": "简历筛选 → 面试邀约 → 面试 → 录用审批，多 Agent 协同完成招聘全流程",
        "category": "hr",
        "icon": "👥",
        "agent_count": 3,
        "yaml_text": """
agents:
  - code: recruiter
    name: 招聘专员
    description: 负责简历筛选、候选人沟通和面试安排
    system_prompt: 你是一位专业的招聘专员，负责筛选简历、联系候选人、安排面试。需要高效沟通，及时跟进。
    effort: medium
  - code: interviewer
    name: 面试官
    description: 负责技术面试和综合评估
    system_prompt: 你是一位资深面试官，负责对候选人进行技术面试和综合能力评估。需要客观公正，给出详细反馈。
    effort: high
  - code: offer-manager
    name: 录用经理
    description: 负责薪资谈判和录用审批
    system_prompt: 你是一位录用经理，负责薪资方案制定、录用审批和入职安排。需要平衡公司利益和候选人期望。
    effort: high
""",
    },
    {
        "code": "customer-service",
        "name": "客户服务中心",
        "description": "一线客服 → 技术支持 → 升级处理，分级响应客户问题",
        "category": "support",
        "icon": "🎧",
        "agent_count": 3,
        "yaml_text": """
agents:
  - code: tier1-support
    name: 一线客服
    description: 处理常见问题咨询和工单创建
    system_prompt: 你是一线客服代表，快速响应客户咨询，解决常见问题。无法解决的问题转交技术支持。
    effort: low
  - code: tier2-tech
    name: 技术支持
    description: 处理技术问题和故障排查
    system_prompt: 你是技术支持工程师，负责处理一线升级的技术问题，进行故障排查和方案制定。
    effort: high
  - code: escalation-manager
    name: 升级经理
    description: 处理紧急问题和客户投诉
    system_prompt: 你是升级经理，负责处理紧急事件和客户投诉，协调资源确保问题快速解决。
    effort: high
""",
    },
    {
        "code": "marketing-campaign",
        "name": "营销活动执行",
        "description": "策略制定 → 内容创作 → 设计 → 审核，矩阵式营销协作",
        "category": "marketing",
        "icon": "📢",
        "agent_count": 4,
        "yaml_text": """
agents:
  - code: strategist
    name: 营销策略师
    description: 制定营销策略和活动方案
    system_prompt: 你是一位营销策略师，负责分析市场趋势、制定营销策略、规划活动方案。
    effort: high
  - code: copywriter
    name: 文案创作
    description: 撰写营销文案和宣传材料
    system_prompt: 你是一位文案专家，负责撰写各种营销文案、广告语、宣传材料。
    effort: medium
  - code: content-designer
    name: 内容设计
    description: 设计视觉素材和排版
    system_prompt: 你是一位内容设计师，负责设计营销素材的视觉风格、排版和配图方案。
    effort: medium
  - code: reviewer
    name: 内容审核
    description: 审核营销内容合规性和品牌一致性
    system_prompt: 你是内容审核员，确保所有营销内容符合品牌规范和法律合规要求。
    effort: high
""",
    },
    {
        "code": "employee-onboarding",
        "name": "员工入职流程",
        "description": "HR通知 → IT设备准备 → 导师分配 → 欢迎引导，新员工一站式入职",
        "category": "admin",
        "icon": "🎉",
        "agent_count": 4,
        "yaml_text": """
agents:
  - code: hr-onboarding
    name: 入职HR
    description: 负责入职通知和入职资料收集
    system_prompt: 你负责新员工入职流程的HR环节，发送入职通知、收集入职资料、安排入职培训。
    effort: medium
  - code: it-setup
    name: IT配置员
    description: 负责工位和设备准备
    system_prompt: 你负责为新员工准备电脑、账号、权限等IT资源，确保入职当天一切就绪。
    effort: medium
  - code: mentor
    name: 导师
    description: 负责新员工指导和融入
    system_prompt: 你是一位导师，负责指导新员工熟悉团队、业务和文化，帮助快速融入。
    effort: medium
  - code: welcome-buddy
    name: 欢迎伙伴
    description: 负责新员工关怀和答疑
    system_prompt: 你是一位热情的小伙伴，负责新员工的日常关怀、答疑和组织欢迎活动。
    effort: low
""",
    },
    {
        "code": "software-dev-team",
        "name": "软件开发团队",
        "description": "产品经理 → 开发者 → QA → DevOps，全流程软件交付协作",
        "category": "it",
        "icon": "💻",
        "agent_count": 4,
        "yaml_text": """
agents:
  - code: pm
    name: 产品经理
    description: 负责需求分析和产品规划
    system_prompt: 你是一位产品经理，负责需求调研、产品规划、PRD编写和进度跟踪。
    effort: high
  - code: developer
    name: 开发者
    description: 负责代码实现和技术方案
    system_prompt: 你是一位全栈开发者，负责技术方案设计、编码实现和代码审查。
    effort: high
  - code: qa
    name: 测试工程师
    description: 负责测试用例和质量管理
    system_prompt: 你是一位QA工程师，负责编写测试用例、执行测试、跟踪缺陷。
    effort: medium
  - code: devops
    name: DevOps工程师
    description: 负责CI/CD和运维部署
    system_prompt: 你负责CI/CD流水线、环境部署、监控告警和运维支持。
    effort: medium
""",
    },
]


async def seed_templates(db: AsyncSession):
    """播种内置模板。"""
    for tpl in BUILTIN_TEMPLATES:
        existing = (await db.execute(
            select(AgentTemplate).where(AgentTemplate.code == tpl["code"])
        )).scalar_one_or_none()
        if existing:
            continue
        db.add(AgentTemplate(**tpl))
    await db.commit()
