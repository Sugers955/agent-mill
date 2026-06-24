"""企业级演示数据种子脚本

包含：日常办公、企业OA、市场营销、人力资源、财务管理等场景
"""
from __future__ import annotations
import asyncio
import os
from pathlib import Path
from sqlalchemy import select
from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal, engine, Base
from app.db.models import (
    Role, User, Department, Model, Skill, Agent,
    AgentSkill, RoleAgentGrant, MCPConnector
)


# 技能目录的绝对路径
SKILLS_DIR = str(Path(settings.SKILLS_DIR).resolve())


# ============================================================
# 部门数据
# ============================================================
DEPARTMENTS = [
    {"code": "general", "name": "综合管理部", "sort": 1, "description": "负责公司日常行政管理"},
    {"code": "hr", "name": "人力资源部", "sort": 2, "description": "负责人才招聘和员工管理"},
    {"code": "marketing", "name": "市场营销部", "sort": 3, "description": "负责市场推广和品牌建设"},
    {"code": "sales", "name": "销售部", "sort": 4, "description": "负责客户开发和销售业绩"},
    {"code": "finance", "name": "财务部", "sort": 5, "description": "负责财务管理和预算控制"},
    {"code": "admin", "name": "行政部", "sort": 6, "description": "负责后勤保障和资产管理"},
]


# ============================================================
# 模型数据
# ============================================================
MODELS = [
    {
        "code": "claude-sonnet",
        "provider": "anthropic",
        "model_id": "claude-sonnet-4-20250514",
        "max_tokens": 8192,
        "enabled": True,
        "unit_price_per_1k_tokens": 300,
    },
    {
        "code": "claude-haiku",
        "provider": "anthropic",
        "model_id": "claude-3-5-haiku-20241022",
        "max_tokens": 8192,
        "enabled": True,
        "unit_price_per_1k_tokens": 80,
    },
    {
        "code": "deepseek-chat",
        "provider": "openai-compatible",
        "model_id": "deepseek-chat",
        "base_url": "https://api.deepseek.com/v1",
        "max_tokens": 4096,
        "enabled": True,
        "unit_price_per_1k_tokens": 20,
    },
]


# ============================================================
# 技能数据
# ============================================================
SKILLS = [
    # ── 通用技能 ──
    {
        "code": "web-search",
        "name": "网络搜索",
        "description": "搜索最新资讯、行业动态、竞品信息",
        "type": "atomic",
        "source_json": {"type": "callable", "module": "app.skills.web_search", "function": "web_search"},
        "enabled": True,
    },
    {
        "code": "document-reader",
        "name": "文档阅读器",
        "description": "读取和解析 PDF、Word、Excel 等文档内容",
        "type": "atomic",
        "source_json": {"type": "callable", "module": "app.skills.document_reader", "function": "read_document"},
        "enabled": True,
    },
    
    # ── 日常办公技能 ──
    {
        "code": "email-writer",
        "name": "邮件撰写",
        "description": "生成专业商务邮件，支持通知、催办、感谢、道歉等场景",
        "type": "atomic",
        "source_json": {"type": "path", "path": f"{SKILLS_DIR}/email-writer"},
        "enabled": True,
    },
    {
        "code": "document-template",
        "name": "公文模板",
        "description": "生成各类公文：通知、通报、报告、请示、函件等",
        "type": "atomic",
        "source_json": {"type": "path", "path": f"{SKILLS_DIR}/document-template"},
        "enabled": True,
    },
    {
        "code": "meeting-summary",
        "name": "会议纪要",
        "description": "根据会议内容生成结构化纪要，包含议题、决议、待办事项",
        "type": "atomic",
        "source_json": {"type": "path", "path": f"{SKILLS_DIR}/meeting-summary"},
        "enabled": True,
    },
    {
        "code": "travel-apply",
        "name": "出差申请",
        "description": "生成出差申请单，包含行程安排、费用预算、审批流程",
        "type": "atomic",
        "source_json": {"type": "path", "path": f"{SKILLS_DIR}/travel-apply"},
        "enabled": True,
    },
    {
        "code": "expense-report",
        "name": "费用报销",
        "description": "生成费用报销单，自动整理发票信息和费用明细",
        "type": "atomic",
        "source_json": {"type": "path", "path": f"{SKILLS_DIR}/expense-report"},
        "enabled": True,
    },
    
    # ── 人力资源技能 ──
    {
        "code": "jd-generator",
        "name": "JD 生成器",
        "description": "根据岗位需求生成规范的职位描述",
        "type": "atomic",
        "source_json": {"type": "path", "path": f"{SKILLS_DIR}/jd-generator"},
        "enabled": True,
    },
    {
        "code": "resume-parser",
        "name": "简历解析",
        "description": "解析简历文件，提取教育背景、工作经验、技能标签",
        "type": "atomic",
        "source_json": {"type": "callable", "module": "app.skills.resume_parser", "function": "parse_resume"},
        "enabled": True,
    },
    {
        "code": "interview-questions",
        "name": "面试题库",
        "description": "根据岗位生成面试问题，包含专业题、行为题、情景题",
        "type": "atomic",
        "source_json": {"type": "path", "path": f"{SKILLS_DIR}/interview-questions"},
        "enabled": True,
    },
    {
        "code": "training-plan",
        "name": "培训计划",
        "description": "生成员工培训计划，包含课程安排、考核方式、预算",
        "type": "atomic",
        "source_json": {"type": "path", "path": f"{SKILLS_DIR}/training-plan"},
        "enabled": True,
    },
    {
        "code": "performance-review",
        "name": "绩效考核",
        "description": "生成绩效考核表，支持 KPI、OKR 等多种考核方式",
        "type": "atomic",
        "source_json": {"type": "path", "path": f"{SKILLS_DIR}/performance-review"},
        "enabled": True,
    },
    
    # ── 市场营销技能 ──
    {
        "code": "copywriting",
        "name": "文案撰写",
        "description": "生成营销文案：广告语、宣传稿、产品介绍、软文",
        "type": "atomic",
        "source_json": {"type": "path", "path": f"{SKILLS_DIR}/copywriting"},
        "enabled": True,
    },
    {
        "code": "social-media",
        "name": "社交媒体运营",
        "description": "生成社交媒体内容：微博、微信、小红书、抖音文案",
        "type": "atomic",
        "source_json": {"type": "path", "path": f"{SKILLS_DIR}/social-media"},
        "enabled": True,
    },
    {
        "code": "event-planner",
        "name": "活动策划",
        "description": "生成活动策划方案，包含流程、预算、宣传、执行",
        "type": "atomic",
        "source_json": {"type": "path", "path": f"{SKILLS_DIR}/event-planner"},
        "enabled": True,
    },
    {
        "code": "competitor-analysis",
        "name": "竞品分析",
        "description": "分析竞品信息，生成对比报告和市场洞察",
        "type": "atomic",
        "source_json": {"type": "path", "path": f"{SKILLS_DIR}/competitor-analysis"},
        "enabled": True,
    },
    {
        "code": "brand-story",
        "name": "品牌故事",
        "description": "生成品牌故事、企业简介、宣传册文案",
        "type": "atomic",
        "source_json": {"type": "path", "path": f"{SKILLS_DIR}/brand-story"},
        "enabled": True,
    },
    
    # ── 财务技能 ──
    {
        "code": "report-generator",
        "name": "报告生成",
        "description": "生成周报、月报、季度报告、年度总结",
        "type": "atomic",
        "source_json": {"type": "path", "path": f"{SKILLS_DIR}/report-generator"},
        "enabled": True,
    },
    {
        "code": "budget-planner",
        "name": "预算编制",
        "description": "生成部门预算、项目预算、年度预算",
        "type": "atomic",
        "source_json": {"type": "callable", "module": "app.skills.budget_planner", "function": "plan_budget"},
        "enabled": True,
    },
    {
        "code": "invoice-helper",
        "name": "发票助手",
        "description": "识别和整理发票信息，生成报销清单",
        "type": "atomic",
        "source_json": {"type": "callable", "module": "app.skills.invoice_helper", "function": "parse_invoice"},
        "enabled": True,
    },
    
    # ── 销售技能 ──
    {
        "code": "sales-pitch",
        "name": "销售话术",
        "description": "生成销售话术：开场白、产品介绍、异议处理、促单技巧",
        "type": "atomic",
        "source_json": {"type": "path", "path": f"{SKILLS_DIR}/sales-pitch"},
        "enabled": True,
    },
    {
        "code": "proposal-writer",
        "name": "方案撰写",
        "description": "生成商务方案、投标文件、项目计划书",
        "type": "atomic",
        "source_json": {"type": "path", "path": f"{SKILLS_DIR}/proposal-writer"},
        "enabled": True,
    },
    {
        "code": "contract-review",
        "name": "合同审查",
        "description": "审查合同条款，提示风险点和注意事项",
        "type": "atomic",
        "source_json": {"type": "callable", "module": "app.skills.contract_review", "function": "review_contract"},
        "enabled": True,
    },
]


# ============================================================
# 智能体数据
# ============================================================
AGENTS = [
    # ── 综合办公 ──
    {
        "code": "office-assistant",
        "name": "办公小助手",
        "description": "日常办公好帮手，处理邮件、会议、公文、出差等事务",
        "icon": "💼",
        "system_prompt": """你是一个专业的办公助手，擅长处理日常办公事务：
1. 撰写各类商务邮件（通知、催办、感谢、道歉等）
2. 生成会议纪要和待办事项
3. 撰写各类公文（通知、报告、请示、函件）
4. 协助出差申请和费用报销
5. 整理工作计划和总结

请根据用户需求，提供专业、规范的办公支持。""",
        "max_turns": 15,
        "effort": "medium",
        "enabled": True,
        "is_default": True,
        "skill_codes": ["email-writer", "document-template", "meeting-summary"],
    },
    {
        "code": "document-expert",
        "name": "公文专家",
        "description": "专注各类公文写作，确保格式规范、内容准确",
        "icon": "📝",
        "system_prompt": """你是一个公文写作专家，精通各类公文格式和规范：
1. 通知、通报、公告
2. 报告、请示、批复
3. 函件、纪要、决议
4. 工作计划、总结、汇报
5. 规章制度、管理办法

请确保公文格式规范、用语准确、逻辑清晰。""",
        "max_turns": 15,
        "effort": "medium",
        "enabled": True,
        "skill_codes": ["document-template", "document-reader"],
    },
    {
        "code": "meeting-assistant",
        "name": "会议助手",
        "description": "协助会议组织、记录和跟进，提高会议效率",
        "icon": "📅",
        "system_prompt": """你是一个会议管理助手，帮助用户高效组织和管理会议：
1. 生成会议议程和通知
2. 记录会议内容和决议
3. 生成会议纪要和待办分配
4. 跟踪会议任务执行情况
5. 提供会议效率优化建议

请帮助用户开高效会议、出明确结论、追到位执行。""",
        "max_turns": 15,
        "effort": "medium",
        "enabled": True,
        "skill_codes": ["meeting-summary", "email-writer", "document-template"],
    },
    
    # ── 人力资源 ──
    {
        "code": "hr-manager",
        "name": "HR 管理师",
        "description": "人力资源全流程支持，从招聘到离职的專業顧問",
        "icon": "👥",
        "system_prompt": """你是一个专业的人力资源管理师，提供全方位 HR 支持：
1. 招聘管理：JD 撰写、简历筛选、面试评估
2. 培训发展：培训计划、课程设计、效果评估
3. 绩效管理：KPI 设计、考核方案、反馈辅导
4. 薪酬福利：薪酬体系、福利方案、激励机制
5. 员工关系：入职引导、离职面谈、劳动纠纷

请提供专业、合规、人性化的 HR 解决方案。""",
        "max_turns": 20,
        "effort": "high",
        "enabled": True,
        "skill_codes": ["jd-generator", "resume-parser", "interview-questions", "training-plan", "performance-review"],
    },
    {
        "code": "recruiter",
        "name": "招聘专员",
        "description": "专注人才招聘，从需求分析到录用决策",
        "icon": "🎯",
        "system_prompt": """你是一个专业的招聘专员，擅长人才识别和招聘管理：
1. 分析岗位需求，撰写 JD
2. 筛选简历，识别核心能力
3. 设计面试问题，评估候选人
4. 提供录用建议和薪酬参考
5. 优化招聘流程，提高效率

请帮助用户找到最合适的人才。""",
        "max_turns": 15,
        "effort": "medium",
        "enabled": True,
        "skill_codes": ["jd-generator", "resume-parser", "interview-questions"],
    },
    {
        "code": "trainer",
        "name": "培训顾问",
        "description": "设计和实施员工培训计划，提升团队能力",
        "icon": "📚",
        "system_prompt": """你是一个企业培训顾问，擅长培训体系搭建和课程设计：
1. 分析培训需求，制定培训计划
2. 设计课程内容和教学方式
3. 选择讲师和培训资源
4. 评估培训效果和 ROI
5. 建立学习型组织文化

请提供系统化、可落地的培训解决方案。""",
        "max_turns": 15,
        "effort": "medium",
        "enabled": True,
        "skill_codes": ["training-plan", "document-template", "report-generator"],
    },
    
    # ── 市场营销 ──
    {
        "code": "marketing-manager",
        "name": "营销经理",
        "description": "制定营销策略，策划推广活动，提升品牌影响力",
        "icon": "📈",
        "system_prompt": """你是一个资深营销经理，擅长品牌建设和市场推广：
1. 制定营销策略和推广计划
2. 策划线上线下活动
3. 撰写营销文案和宣传材料
4. 分析市场数据和竞品动态
5. 管理社交媒体和内容营销

请提供创新、可执行的营销方案。""",
        "max_turns": 20,
        "effort": "high",
        "enabled": True,
        "skill_codes": ["copywriting", "social-media", "event-planner", "competitor-analysis"],
    },
    {
        "code": "content-creator",
        "name": "内容创作者",
        "description": "创作高质量营销内容，包括文案、图文、视频脚本",
        "icon": "✍️",
        "system_prompt": """你是一个专业的内容创作者，擅长各类营销内容创作：
1. 品牌文案：广告语、宣传稿、品牌故事
2. 社交媒体：微博、微信、小红书、抖音
3. 内容营销：软文、种草文、测评文
4. 活动文案：活动介绍、邀请函、新闻稿
5. 产品文案：详情页、卖点提炼、用户评价

请创作有吸引力、有传播力的优质内容。""",
        "max_turns": 15,
        "effort": "medium",
        "enabled": True,
        "skill_codes": ["copywriting", "social-media", "brand-story"],
    },
    {
        "code": "event-planner",
        "name": "活动策划师",
        "description": "策划和执行各类市场活动、客户活动、品牌活动",
        "icon": "🎉",
        "system_prompt": """你是一个专业的活动策划师，擅长各类活动策划执行：
1. 线下活动：发布会、沙龙、展会、年会
2. 线上活动：直播、抽奖、投票、裂变
3. 客户活动：答谢会、体验日、私享会
4. 品牌活动：快闪店、联名、跨界合作
5. 活动复盘：数据分析、效果评估、优化建议

请提供创意十足、执行到位的活动方案。""",
        "max_turns": 20,
        "effort": "high",
        "enabled": True,
        "skill_codes": ["event-planner", "copywriting", "email-writer"],
    },
    
    # ── 销售支持 ──
    {
        "code": "sales-expert",
        "name": "销售顾问",
        "description": "提供销售策略、话术支持和客户管理建议",
        "icon": "🤝",
        "system_prompt": """你是一个资深销售顾问，擅长销售策略和客户管理：
1. 分析客户需求，制定销售策略
2. 提供销售话术和沟通技巧
3. 协助商务谈判和异议处理
4. 客户关系维护和跟进
5. 销售数据分析和业绩提升

请帮助用户提高销售转化率和客户满意度。""",
        "max_turns": 15,
        "effort": "medium",
        "enabled": True,
        "skill_codes": ["sales-pitch", "proposal-writer", "contract-review"],
    },
    {
        "code": "bid-specialist",
        "name": "投标专员",
        "description": "协助准备投标文件，提高中标率",
        "icon": "📋",
        "system_prompt": """你是一个专业的投标专员，擅长投标文件编制和管理：
1. 分析招标文件，提炼关键要求
2. 编制技术方案和商务方案
3. 整理资质证明和业绩案例
4. 优化投标文件，突出竞争优势
5. 总结投标经验，建立标书库

请帮助用户制作高质量的投标文件。""",
        "max_turns": 20,
        "effort": "high",
        "enabled": True,
        "skill_codes": ["proposal-writer", "document-reader", "report-generator"],
    },
    
    # ── 财务管理 ──
    {
        "code": "finance-advisor",
        "name": "财务顾问",
        "description": "提供财务分析、预算管理和成本控制建议",
        "icon": "💰",
        "system_prompt": """你是一个专业的财务顾问，擅长财务分析和管理：
1. 财务报表分析和解读
2. 预算编制和成本控制
3. 资金管理和现金流
4. 税务筹划和合规
5. 投资分析和风险评估

请提供准确、合规、实用的财务建议。""",
        "max_turns": 15,
        "effort": "high",
        "enabled": True,
        "skill_codes": ["report-generator", "budget-planner", "invoice-helper"],
    },
    {
        "code": "expense-assistant",
        "name": "报销助手",
        "description": "简化报销流程，快速整理发票和费用明细",
        "icon": "🧾",
        "system_prompt": """你是一个报销管理助手，帮助用户高效处理费用报销：
1. 识别和整理发票信息
2. 分类统计各类费用
3. 生成规范的报销单
4. 检查票据合规性
5. 提供报销政策咨询

请帮助用户快速、准确地完成报销。""",
        "max_turns": 10,
        "effort": "low",
        "enabled": True,
        "skill_codes": ["expense-report", "invoice-helper"],
    },
    
    # ── 行政后勤 ──
    {
        "code": "admin-assistant",
        "name": "行政助理",
        "description": "处理行政事务，包括资产管理、采购、后勤保障",
        "icon": "🏢",
        "system_prompt": """你是一个专业的行政助理，擅长行政事务管理：
1. 资产管理和采购
2. 办公环境管理
3. 后勤保障协调
4. 供应商管理
5. 制度流程优化

请提供高效、细致的行政支持。""",
        "max_turns": 15,
        "effort": "medium",
        "enabled": True,
        "skill_codes": ["document-template", "email-writer", "report-generator"],
    },
    {
        "code": "travel-coordinator",
        "name": "差旅管家",
        "description": "管理出差行程、费用预算和报销事宜",
        "icon": "✈️",
        "system_prompt": """你是一个差旅管理助手，帮助用户规划和管理出差：
1. 生成出差申请和行程安排
2. 预算交通、住宿、餐饮费用
3. 整理出差票据和报销单
4. 提供差旅政策咨询
5. 优化差旅成本

请帮助用户高效、合规地管理差旅。""",
        "max_turns": 10,
        "effort": "low",
        "enabled": True,
        "skill_codes": ["travel-apply", "expense-report"],
    },
]


# ============================================================
# 角色权限配置
# ============================================================
ROLE_PERMISSIONS = {
    "admin": [a["code"] for a in AGENTS],
    "operator": [
        "office-assistant", "document-expert", "meeting-assistant",
        "hr-manager", "recruiter", "trainer",
        "marketing-manager", "content-creator", "event-planner",
        "sales-expert", "bid-specialist",
        "finance-advisor", "expense-assistant",
        "admin-assistant", "travel-coordinator",
    ],
    "user": [
        "office-assistant", "meeting-assistant", "expense-assistant", "travel-coordinator"
    ],
}


async def seed():
    """播种演示数据"""
    default_user_pwd = os.getenv("SEED_USER_PASSWORD", "changeme")
    default_admin_pwd = os.getenv("SEED_ADMIN_PASSWORD", "changeme")
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with SessionLocal() as db:
        # ── 部门 ──
        departments = {}
        for d in DEPARTMENTS:
            existing = (await db.execute(
                select(Department).where(Department.code == d["code"])
            )).scalar_one_or_none()
            if not existing:
                dept = Department(**d)
                db.add(dept)
                await db.flush()
                departments[d["code"]] = dept
            else:
                departments[d["code"]] = existing
        await db.commit()
        
        # ── 模型 ──
        models = {}
        for m in MODELS:
            existing = (await db.execute(
                select(Model).where(Model.code == m["code"])
            )).scalar_one_or_none()
            if not existing:
                model = Model(**m)
                db.add(model)
                await db.flush()
                models[m["code"]] = model
            else:
                models[m["code"]] = existing
        await db.commit()
        
        # ── 技能 ──
        skills = {}
        for s in SKILLS:
            existing = (await db.execute(
                select(Skill).where(Skill.code == s["code"])
            )).scalar_one_or_none()
            if not existing:
                skill = Skill(**s)
                db.add(skill)
                await db.flush()
                skills[s["code"]] = skill
            else:
                skills[s["code"]] = existing
        await db.commit()
        
        # ── 智能体 ──
        agents = {}
        for a in AGENTS:
            skill_codes = a.pop("skill_codes", [])
            existing = (await db.execute(
                select(Agent).where(Agent.code == a["code"])
            )).scalar_one_or_none()
            if not existing:
                a["default_model_id"] = models.get("claude-haiku", {}).get("id") if isinstance(models.get("claude-haiku"), Model) else None
                agent = Agent(**a)
                db.add(agent)
                await db.flush()
                agents[a["code"]] = agent
                for sc in skill_codes:
                    if sc in skills:
                        db.add(AgentSkill(agent_id=agent.id, skill_id=skills[sc].id))
            else:
                agents[a["code"]] = existing
        await db.commit()
        
        # ── 角色权限 ──
        for role_code, agent_codes in ROLE_PERMISSIONS.items():
            role = (await db.execute(
                select(Role).where(Role.code == role_code)
            )).scalar_one_or_none()
            if role:
                for ac in agent_codes:
                    if ac in agents:
                        existing = (await db.execute(
                            select(RoleAgentGrant).where(
                                RoleAgentGrant.role_id == role.id,
                                RoleAgentGrant.agent_id == agents[ac].id
                            )
                        )).scalar_one_or_none()
                        if not existing:
                            db.add(RoleAgentGrant(role_id=role.id, agent_id=agents[ac].id))
        await db.commit()
        
        # ── 演示用户 ──
        demo_users = [
            {"username": "admin", "display_name": "系统管理员", "role": "admin", "dept": None},
            {"username": "zhangsan", "display_name": "张三", "role": "admin", "dept": "general"},
            {"username": "lisi", "display_name": "李四", "role": "operator", "dept": "marketing"},
            {"username": "wangwu", "display_name": "王五", "role": "user", "dept": "sales"},
            {"username": "zhaoliu", "display_name": "赵六", "role": "operator", "dept": "hr"},
        ]
        
        for u in demo_users:
            existing = (await db.execute(
                select(User).where(User.username == u["username"])
            )).scalar_one_or_none()
            if not existing:
                role = (await db.execute(
                    select(Role).where(Role.code == u["role"])
                )).scalar_one()
                dept_id = departments.get(u["dept"], {}).get("id") if u["dept"] and isinstance(departments.get(u["dept"]), Department) else None
                user = User(
                    username=u["username"],
                    password_hash=hash_password(default_user_pwd) if u["username"] != "admin" else hash_password(default_admin_pwd),
                    display_name=u["display_name"],
                    role_id=role.id,
                    department_id=dept_id,
                )
                db.add(user)
        await db.commit()
        
    return {
        "departments": len(DEPARTMENTS),
        "models": len(MODELS),
        "skills": len(SKILLS),
        "agents": len(AGENTS),
        "users": len(demo_users),
    }


if __name__ == "__main__":
    result = asyncio.run(seed())
    print(f"✅ 演示数据播种完成: {result}")
