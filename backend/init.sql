-- ============================================================
-- Agent Mill - MySQL 数据库初始化脚本
-- 包含：表结构 + 演示数据
-- ============================================================

-- 创建数据库
CREATE DATABASE IF NOT EXISTS agent_mill CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE agent_mill;

-- ============================================================
-- 1. 表结构
-- ============================================================

-- 角色表
CREATE TABLE IF NOT EXISTS roles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(32) NOT NULL UNIQUE,
    name VARCHAR(64) NOT NULL,
    description VARCHAR(256),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 部门表
CREATE TABLE IF NOT EXISTS departments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(64) NOT NULL UNIQUE,
    name VARCHAR(128) NOT NULL,
    parent_id INT,
    sort INT DEFAULT 0,
    description VARCHAR(256),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_id) REFERENCES departments(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 用户表
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(64) NOT NULL UNIQUE,
    password_hash VARCHAR(256) NOT NULL,
    display_name VARCHAR(128),
    email VARCHAR(256),
    role_id INT NOT NULL,
    department_id INT,
    status VARCHAR(16) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (role_id) REFERENCES roles(id),
    FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE SET NULL,
    INDEX idx_users_username (username),
    INDEX idx_users_department_id (department_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 模型表
CREATE TABLE IF NOT EXISTS models (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(64) NOT NULL UNIQUE,
    provider VARCHAR(32) NOT NULL,
    model_id VARCHAR(128) NOT NULL,
    base_url VARCHAR(256),
    api_key_enc TEXT,
    max_tokens INT DEFAULT 8192,
    enabled BOOLEAN DEFAULT TRUE,
    extra_params_json JSON DEFAULT (JSON_OBJECT()),
    unit_price_per_1k_tokens INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- MCP 连接器表
CREATE TABLE IF NOT EXISTS mcp_connectors (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(64) NOT NULL UNIQUE,
    transport VARCHAR(16) NOT NULL,
    config_json JSON DEFAULT (JSON_OBJECT()),
    enabled BOOLEAN DEFAULT TRUE,
    user_summary TEXT,
    tool_summaries_json JSON,
    user_summary_updated_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 技能表
CREATE TABLE IF NOT EXISTS skills (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(64) NOT NULL UNIQUE,
    name VARCHAR(128) NOT NULL,
    description TEXT NOT NULL,
    type VARCHAR(16) NOT NULL,
    source_json JSON DEFAULT (JSON_OBJECT()),
    enabled BOOLEAN DEFAULT TRUE,
    version INT DEFAULT 1,
    user_summary TEXT,
    user_summary_updated_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 智能体表
CREATE TABLE IF NOT EXISTS agents (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(64) NOT NULL UNIQUE,
    name VARCHAR(128) NOT NULL,
    description TEXT,
    icon VARCHAR(256),
    system_prompt TEXT,
    default_model_id INT,
    fallback_model_id INT,
    upload_policy_json JSON DEFAULT (JSON_OBJECT()),
    max_turns INT DEFAULT 15,
    effort VARCHAR(16) DEFAULT 'medium',
    parsed_content_limit INT,
    enabled BOOLEAN DEFAULT TRUE,
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (default_model_id) REFERENCES models(id),
    FOREIGN KEY (fallback_model_id) REFERENCES models(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 智能体-技能关联表
CREATE TABLE IF NOT EXISTS agent_skills (
    agent_id INT NOT NULL,
    skill_id INT NOT NULL,
    PRIMARY KEY (agent_id, skill_id),
    FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE,
    FOREIGN KEY (skill_id) REFERENCES skills(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 智能体-MCP关联表
CREATE TABLE IF NOT EXISTS agent_mcps (
    agent_id INT NOT NULL,
    mcp_id INT NOT NULL,
    PRIMARY KEY (agent_id, mcp_id),
    FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE,
    FOREIGN KEY (mcp_id) REFERENCES mcp_connectors(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 角色-智能体权限表
CREATE TABLE IF NOT EXISTS role_agent_grants (
    role_id INT NOT NULL,
    agent_id INT NOT NULL,
    PRIMARY KEY (role_id, agent_id),
    FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
    FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 对话表
CREATE TABLE IF NOT EXISTS conversations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    agent_id INT NOT NULL,
    title VARCHAR(256) DEFAULT '新对话',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (agent_id) REFERENCES agents(id),
    INDEX idx_conversations_user_id (user_id),
    INDEX idx_conversations_agent_id (agent_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 消息表
CREATE TABLE IF NOT EXISTS messages (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    conversation_id INT NOT NULL,
    role VARCHAR(16) NOT NULL,
    content_json JSON DEFAULT (JSON_OBJECT()),
    tool_calls_json JSON,
    tokens_in INT DEFAULT 0,
    tokens_out INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
    INDEX idx_messages_conversation_id (conversation_id),
    INDEX idx_messages_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 上传文件表
CREATE TABLE IF NOT EXISTS uploaded_files (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    conversation_id INT,
    name VARCHAR(256) NOT NULL,
    path VARCHAR(512) NOT NULL,
    size BIGINT NOT NULL,
    mime VARCHAR(128) NOT NULL,
    parse_status VARCHAR(16) DEFAULT 'pending',
    parse_engine VARCHAR(32),
    parsed_markdown TEXT,
    parsed_chars INT DEFAULT 0,
    parse_error TEXT,
    parsed_at TIMESTAMP NULL,
    last_used_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE SET NULL,
    INDEX idx_uploaded_files_last_used_at (last_used_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 审计日志表
CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    action VARCHAR(64) NOT NULL,
    target_type VARCHAR(32),
    target_id VARCHAR(64),
    detail_json JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_audit_logs_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 调用日志表
CREATE TABLE IF NOT EXISTS call_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    agent_id INT,
    conversation_id INT,
    model_id INT,
    tokens_in INT DEFAULT 0,
    tokens_out INT DEFAULT 0,
    latency_ms INT DEFAULT 0,
    status VARCHAR(16) DEFAULT 'ok',
    error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE SET NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE SET NULL,
    FOREIGN KEY (model_id) REFERENCES models(id) ON DELETE SET NULL,
    INDEX idx_call_logs_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 用户额度表
CREATE TABLE IF NOT EXISTS user_quotas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL UNIQUE,
    monthly_limit INT DEFAULT 0,
    alert_threshold INT DEFAULT 80,
    last_alert_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_quotas_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 下载令牌表
CREATE TABLE IF NOT EXISTS download_tokens (
    token VARCHAR(64) PRIMARY KEY,
    user_id INT,
    file_path VARCHAR(1024) NOT NULL,
    file_name VARCHAR(256) NOT NULL,
    mime VARCHAR(128) DEFAULT 'application/octet-stream',
    size BIGINT DEFAULT 0,
    expires_at TIMESTAMP NOT NULL,
    download_count INT DEFAULT 0,
    max_downloads INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_download_tokens_user_id (user_id),
    INDEX idx_download_tokens_expires_at (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 解决方案包表
CREATE TABLE IF NOT EXISTS solution_packs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(64) NOT NULL UNIQUE,
    name VARCHAR(128) NOT NULL,
    description TEXT,
    version VARCHAR(32) DEFAULT '1.0.0',
    yaml_text TEXT NOT NULL,
    spec_json JSON DEFAULT (JSON_OBJECT()),
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_solution_packs_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 智能体-解决方案包关联表
CREATE TABLE IF NOT EXISTS agent_packs (
    agent_id INT NOT NULL,
    pack_id INT NOT NULL,
    PRIMARY KEY (agent_id, pack_id),
    FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE,
    FOREIGN KEY (pack_id) REFERENCES solution_packs(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 解决方案包运行记录表
CREATE TABLE IF NOT EXISTS pack_runs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL UNIQUE,
    pack_id INT NOT NULL,
    user_id INT,
    agent_id INT,
    conversation_id INT,
    status VARCHAR(24) DEFAULT 'running',
    inputs JSON DEFAULT (JSON_OBJECT()),
    context_snapshot JSON DEFAULT (JSON_OBJECT()),
    outputs JSON,
    trace JSON,
    error TEXT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP NULL,
    FOREIGN KEY (pack_id) REFERENCES solution_packs(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE SET NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE SET NULL,
    INDEX idx_pack_runs_run_id (run_id),
    INDEX idx_pack_runs_status (status),
    INDEX idx_pack_runs_started_at (started_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 解决方案包审批表
CREATE TABLE IF NOT EXISTS pack_approvals (
    id INT AUTO_INCREMENT PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL,
    pack_id INT NOT NULL,
    node_id VARCHAR(64) NOT NULL,
    status VARCHAR(16) DEFAULT 'pending',
    title VARCHAR(256) NOT NULL,
    message TEXT,
    detail_json JSON,
    assigned_role VARCHAR(32),
    assigned_user_ids JSON,
    decided_by INT,
    decision_reason TEXT,
    expires_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    decided_at TIMESTAMP NULL,
    FOREIGN KEY (pack_id) REFERENCES solution_packs(id) ON DELETE CASCADE,
    FOREIGN KEY (decided_by) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_pack_approvals_run_id (run_id),
    INDEX idx_pack_approvals_status (status),
    INDEX idx_pack_approvals_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 定时任务表
CREATE TABLE IF NOT EXISTS tasks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    owner_user_id INT NOT NULL,
    agent_id INT NOT NULL,
    name VARCHAR(128) NOT NULL,
    description TEXT,
    prompt_text TEXT,
    schedule_type VARCHAR(16) DEFAULT 'manual',
    schedule_value VARCHAR(128),
    timezone VARCHAR(64) DEFAULT 'Asia/Shanghai',
    max_runtime_seconds INT DEFAULT 1800,
    concurrency_policy VARCHAR(16) DEFAULT 'skip',
    notify_channels_json JSON DEFAULT (JSON_ARRAY()),
    notify_email_to VARCHAR(256),
    notify_on VARCHAR(16) DEFAULT 'always',
    enabled BOOLEAN DEFAULT TRUE,
    last_run_id BIGINT,
    last_run_status VARCHAR(16),
    last_run_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (agent_id) REFERENCES agents(id),
    INDEX idx_tasks_owner_user_id (owner_user_id),
    INDEX idx_tasks_agent_id (agent_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 任务运行记录表
CREATE TABLE IF NOT EXISTS task_runs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    task_id INT NOT NULL,
    run_no INT DEFAULT 1,
    triggered_by VARCHAR(16) DEFAULT 'manual',
    triggered_user_id INT,
    status VARCHAR(16) DEFAULT 'pending',
    conversation_id INT,
    started_at TIMESTAMP NULL,
    finished_at TIMESTAMP NULL,
    duration_ms INT DEFAULT 0,
    tokens_in INT DEFAULT 0,
    tokens_out INT DEFAULT 0,
    summary TEXT,
    error_message TEXT,
    notified_at TIMESTAMP NULL,
    notify_status_json JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
    FOREIGN KEY (triggered_user_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE SET NULL,
    INDEX idx_task_runs_task_id (task_id),
    INDEX idx_task_runs_status (status),
    INDEX idx_task_runs_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 通知表
CREATE TABLE IF NOT EXISTS notifications (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    type VARCHAR(32) DEFAULT 'task_run',
    title VARCHAR(256) NOT NULL,
    body TEXT,
    link_url VARCHAR(512),
    detail_json JSON,
    read_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_notifications_user_id (user_id),
    INDEX idx_notifications_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 收藏表
CREATE TABLE IF NOT EXISTS favorites (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    conversation_id INT,
    message_id BIGINT,
    question_text TEXT NOT NULL,
    answer_text TEXT NOT NULL,
    files_json JSON,
    agent_id INT,
    agent_name VARCHAR(128),
    model_code VARCHAR(64),
    note VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE SET NULL,
    FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE SET NULL,
    UNIQUE KEY uq_favorites_user_message (user_id, message_id),
    INDEX idx_favorites_user_id (user_id),
    INDEX idx_favorites_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ============================================================
-- 2. 演示数据
-- ============================================================

-- 角色数据
INSERT INTO roles (code, name, description) VALUES
('admin', '超级管理员', '全部权限'),
('operator', '运营管理员', '可配置 Skill / MCP / 智能体 / 模型 / Solution Pack / 日志'),
('user', '普通用户', '仅使用智能体');

-- 部门数据
INSERT INTO departments (code, name, sort, description) VALUES
('general', '综合管理部', 1, '负责公司日常行政管理'),
('hr', '人力资源部', 2, '负责人才招聘和员工管理'),
('marketing', '市场营销部', 3, '负责市场推广和品牌建设'),
('sales', '销售部', 4, '负责客户开发和销售业绩'),
('finance', '财务部', 5, '负责财务管理和预算控制'),
('admin', '行政部', 6, '负责后勤保障和资产管理');

-- 模型数据
INSERT INTO models (code, provider, model_id, max_tokens, enabled, extra_params_json, unit_price_per_1k_tokens) VALUES
('claude-sonnet', 'anthropic', 'claude-sonnet-4-20250514', 8192, TRUE, '{}', 300),
('claude-haiku', 'anthropic', 'claude-3-5-haiku-20241022', 8192, TRUE, '{}', 80),
('deepseek-chat', 'openai-compatible', 'deepseek-chat', 4096, TRUE, '{}', 20);

-- 技能数据
INSERT INTO skills (code, name, description, type, source_json, enabled) VALUES
-- 通用技能
('web-search', '网络搜索', '搜索最新资讯、行业动态、竞品信息', 'atomic', '{"type":"callable","module":"app.skills.web_search","function":"web_search"}', TRUE),
('document-reader', '文档阅读器', '读取和解析 PDF、Word、Excel 等文档内容', 'atomic', '{"type":"callable","module":"app.skills.document_reader","function":"read_document"}', TRUE),
-- 日常办公技能
('email-writer', '邮件撰写', '生成专业商务邮件，支持通知、催办、感谢、道歉等场景', 'atomic', '{"type":"path","path":"storage/skills/email-writer"}', TRUE),
('document-template', '公文模板', '生成各类公文：通知、通报、报告、请示、函件等', 'atomic', '{"type":"path","path":"storage/skills/document-template"}', TRUE),
('meeting-summary', '会议纪要', '根据会议内容生成结构化纪要，包含议题、决议、待办事项', 'atomic', '{"type":"path","path":"storage/skills/meeting-summary"}', TRUE),
('travel-apply', '出差申请', '生成出差申请单，包含行程安排、费用预算、审批流程', 'atomic', '{"type":"path","path":"storage/skills/travel-apply"}', TRUE),
('expense-report', '费用报销', '生成费用报销单，自动整理发票信息和费用明细', 'atomic', '{"type":"path","path":"storage/skills/expense-report"}', TRUE),
-- 人力资源技能
('jd-generator', 'JD 生成器', '根据岗位需求生成规范的职位描述', 'atomic', '{"type":"path","path":"storage/skills/jd-generator"}', TRUE),
('resume-parser', '简历解析', '解析简历文件，提取教育背景、工作经验、技能标签', 'atomic', '{"type":"callable","module":"app.skills.resume_parser","function":"parse_resume"}', TRUE),
('interview-questions', '面试题库', '根据岗位生成面试问题，包含专业题、行为题、情景题', 'atomic', '{"type":"path","path":"storage/skills/interview-questions"}', TRUE),
('training-plan', '培训计划', '生成员工培训计划，包含课程安排、考核方式、预算', 'atomic', '{"type":"path","path":"storage/skills/training-plan"}', TRUE),
('performance-review', '绩效考核', '生成绩效考核表，支持 KPI、OKR 等多种考核方式', 'atomic', '{"type":"path","path":"storage/skills/performance-review"}', TRUE),
-- 市场营销技能
('copywriting', '文案撰写', '生成营销文案：广告语、宣传稿、产品介绍、软文', 'atomic', '{"type":"path","path":"storage/skills/copywriting"}', TRUE),
('social-media', '社交媒体运营', '生成社交媒体内容：微博、微信、小红书、抖音文案', 'atomic', '{"type":"path","path":"storage/skills/social-media"}', TRUE),
('event-planner', '活动策划', '生成活动策划方案，包含流程、预算、宣传、执行', 'atomic', '{"type":"path","path":"storage/skills/event-planner"}', TRUE),
('competitor-analysis', '竞品分析', '分析竞品信息，生成对比报告和市场洞察', 'atomic', '{"type":"path","path":"storage/skills/competitor-analysis"}', TRUE),
('brand-story', '品牌故事', '生成品牌故事、企业简介、宣传册文案', 'atomic', '{"type":"path","path":"storage/skills/brand-story"}', TRUE),
-- 财务技能
('report-generator', '报告生成', '生成周报、月报、季度报告、年度总结', 'atomic', '{"type":"path","path":"storage/skills/report-generator"}', TRUE),
('budget-planner', '预算编制', '生成部门预算、项目预算、年度预算', 'atomic', '{"type":"path","path":"storage/skills/budget-planner"}', TRUE),
('invoice-helper', '发票助手', '识别和整理发票信息，生成报销清单', 'atomic', '{"type":"callable","module":"app.skills.invoice_helper","function":"parse_invoice"}', TRUE),
-- 销售技能
('sales-pitch', '销售话术', '生成销售话术：开场白、产品介绍、异议处理、促单技巧', 'atomic', '{"type":"path","path":"storage/skills/sales-pitch"}', TRUE),
('proposal-writer', '方案撰写', '生成商务方案、投标文件、项目计划书', 'atomic', '{"type":"path","path":"storage/skills/proposal-writer"}', TRUE),
('contract-review', '合同审查', '审查合同条款，提示风险点和注意事项', 'atomic', '{"type":"path","path":"storage/skills/contract-review"}', TRUE);

-- 智能体数据
INSERT INTO agents (code, name, description, icon, system_prompt, default_model_id, max_turns, effort, enabled, is_default) VALUES
-- 综合办公
('office-assistant', '办公小助手', '日常办公好帮手，处理邮件、会议、公文、出差等事务', '💼', '你是一个专业的办公助手，擅长处理日常办公事务：\n1. 撰写各类商务邮件（通知、催办、感谢、道歉等）\n2. 生成会议纪要和待办事项\n3. 撰写各类公文（通知、报告、请示、函件）\n4. 协助出差申请和费用报销\n5. 整理工作计划和总结\n\n请根据用户需求，提供专业、规范的办公支持。', 2, 15, 'medium', TRUE, TRUE),
('document-expert', '公文专家', '专注各类公文写作，确保格式规范、内容准确', '📝', '你是一个公文写作专家，精通各类公文格式和规范：\n1. 通知、通报、公告\n2. 报告、请示、批复\n3. 函件、纪要、决议\n4. 工作计划、总结、汇报\n5. 规章制度、管理办法\n\n请确保公文格式规范、用语准确、逻辑清晰。', 2, 15, 'medium', TRUE, FALSE),
('meeting-assistant', '会议助手', '协助会议组织、记录和跟进，提高会议效率', '📅', '你是一个会议管理助手，帮助用户高效组织和管理会议：\n1. 生成会议议程和通知\n2. 记录会议内容和决议\n3. 生成会议纪要和待办分配\n4. 跟踪会议任务执行情况\n5. 提供会议效率优化建议\n\n请帮助用户开高效会议、出明确结论、追到位执行。', 2, 15, 'medium', TRUE, FALSE),
-- 人力资源
('hr-manager', 'HR 管理师', '人力资源全流程支持，从招聘到离职的專業顧問', '👥', '你是一个专业的人力资源管理师，提供全方位 HR 支持：\n1. 招聘管理：JD 撰写、简历筛选、面试评估\n2. 培训发展：培训计划、课程设计、效果评估\n3. 绩效管理：KPI 设计、考核方案、反馈辅导\n4. 薪酬福利：薪酬体系、福利方案、激励机制\n5. 员工关系：入职引导、离职面谈、劳动纠纷\n\n请提供专业、合规、人性化的 HR 解决方案。', 2, 20, 'high', TRUE, FALSE),
('recruiter', '招聘专员', '专注人才招聘，从需求分析到录用决策', '🎯', '你是一个专业的招聘专员，擅长人才识别和招聘管理：\n1. 分析岗位需求，撰写 JD\n2. 筛选简历，识别核心能力\n3. 设计面试问题，评估候选人\n4. 提供录用建议和薪酬参考\n5. 优化招聘流程，提高效率\n\n请帮助用户找到最合适的人才。', 2, 15, 'medium', TRUE, FALSE),
('trainer', '培训顾问', '设计和实施员工培训计划，提升团队能力', '📚', '你是一个企业培训顾问，擅长培训体系搭建和课程设计：\n1. 分析培训需求，制定培训计划\n2. 设计课程内容和教学方式\n3. 选择讲师和培训资源\n4. 评估培训效果和 ROI\n5. 建立学习型组织文化\n\n请提供系统化、可落地的培训解决方案。', 2, 15, 'medium', TRUE, FALSE),
-- 市场营销
('marketing-manager', '营销经理', '制定营销策略，策划推广活动，提升品牌影响力', '📈', '你是一个资深营销经理，擅长品牌建设和市场推广：\n1. 制定营销策略和推广计划\n2. 策划线上线下活动\n3. 撰写营销文案和宣传材料\n4. 分析市场数据和竞品动态\n5. 管理社交媒体和内容营销\n\n请提供创新、可执行的营销方案。', 1, 20, 'high', TRUE, FALSE),
('content-creator', '内容创作者', '创作高质量营销内容，包括文案、图文、视频脚本', '✍️', '你是一个专业的内容创作者，擅长各类营销内容创作：\n1. 品牌文案：广告语、宣传稿、品牌故事\n2. 社交媒体：微博、微信、小红书、抖音\n3. 内容营销：软文、种草文、测评文\n4. 活动文案：活动介绍、邀请函、新闻稿\n5. 产品文案：详情页、卖点提炼、用户评价\n\n请创作有吸引力、有传播力的优质内容。', 2, 15, 'medium', TRUE, FALSE),
('event-planner', '活动策划师', '策划和执行各类市场活动、客户活动、品牌活动', '🎉', '你是一个专业的活动策划师，擅长各类活动策划执行：\n1. 线下活动：发布会、沙龙、展会、年会\n2. 线上活动：直播、抽奖、投票、裂变\n3. 客户活动：答谢会、体验日、私享会\n4. 品牌活动：快闪店、联名、跨界合作\n5. 活动复盘：数据分析、效果评估、优化建议\n\n请提供创意十足、执行到位的活动方案。', 1, 20, 'high', TRUE, FALSE),
-- 销售支持
('sales-expert', '销售顾问', '提供销售策略、话术支持和客户管理建议', '🤝', '你是一个资深销售顾问，擅长销售策略和客户管理：\n1. 分析客户需求，制定销售策略\n2. 提供销售话术和沟通技巧\n3. 协助商务谈判和异议处理\n4. 客户关系维护和跟进\n5. 销售数据分析和业绩提升\n\n请帮助用户提高销售转化率和客户满意度。', 2, 15, 'medium', TRUE, FALSE),
('bid-specialist', '投标专员', '协助准备投标文件，提高中标率', '📋', '你是一个专业的投标专员，擅长投标文件编制和管理：\n1. 分析招标文件，提炼关键要求\n2. 编制技术方案和商务方案\n3. 整理资质证明和业绩案例\n4. 优化投标文件，突出竞争优势\n5. 总结投标经验，建立标书库\n\n请帮助用户制作高质量的投标文件。', 1, 20, 'high', TRUE, FALSE),
-- 财务管理
('finance-advisor', '财务顾问', '提供财务分析、预算管理和成本控制建议', '💰', '你是一个专业的财务顾问，擅长财务分析和管理：\n1. 财务报表分析和解读\n2. 预算编制和成本控制\n3. 资金管理和现金流\n4. 税务筹划和合规\n5. 投资分析和风险评估\n\n请提供准确、合规、实用的财务建议。', 2, 15, 'high', TRUE, FALSE),
('expense-assistant', '报销助手', '简化报销流程，快速整理发票和费用明细', '🧾', '你是一个报销管理助手，帮助用户高效处理费用报销：\n1. 识别和整理发票信息\n2. 分类统计各类费用\n3. 生成规范的报销单\n4. 检查票据合规性\n5. 提供报销政策咨询\n\n请帮助用户快速、准确地完成报销。', 2, 10, 'low', TRUE, FALSE),
-- 行政后勤
('admin-assistant', '行政助理', '处理行政事务，包括资产管理、采购、后勤保障', '🏢', '你是一个专业的行政助理，擅长行政事务管理：\n1. 资产管理和采购\n2. 办公环境管理\n3. 后勤保障协调\n4. 供应商管理\n5. 制度流程优化\n\n请提供高效、细致的行政支持。', 2, 15, 'medium', TRUE, FALSE),
('travel-coordinator', '差旅管家', '管理出差行程、费用预算和报销事宜', '✈️', '你是一个差旅管理助手，帮助用户规划和管理出差：\n1. 生成出差申请和行程安排\n2. 预算交通、住宿、餐饮费用\n3. 整理出差票据和报销单\n4. 提供差旅政策咨询\n5. 优化差旅成本\n\n请帮助用户高效、合规地管理差旅。', 2, 10, 'low', TRUE, FALSE);

-- 智能体-技能关联数据
INSERT INTO agent_skills (agent_id, skill_id) VALUES
-- office-assistant (1)
(1, 3), (1, 4), (1, 5),
-- document-expert (2)
(2, 4), (2, 2),
-- meeting-assistant (3)
(3, 5), (3, 3), (3, 4),
-- hr-manager (4)
(4, 8), (4, 9), (4, 10), (4, 11), (4, 12),
-- recruiter (5)
(5, 8), (5, 9), (5, 10),
-- trainer (6)
(6, 11), (6, 4), (6, 18),
-- marketing-manager (7)
(7, 13), (7, 14), (7, 15), (7, 16),
-- content-creator (8)
(8, 13), (8, 14), (8, 17),
-- event-planner (9)
(9, 15), (9, 13), (9, 3),
-- sales-expert (10)
(10, 21), (10, 22), (10, 23),
-- bid-specialist (11)
(11, 22), (11, 2), (11, 18),
-- finance-advisor (12)
(12, 18), (12, 19), (12, 20),
-- expense-assistant (13)
(13, 7), (13, 20),
-- admin-assistant (14)
(14, 4), (14, 3), (14, 18),
-- travel-coordinator (15)
(15, 6), (15, 7);

-- 角色-智能体权限数据
INSERT INTO role_agent_grants (role_id, agent_id) VALUES
-- admin (1) - 所有智能体
(1, 1), (1, 2), (1, 3), (1, 4), (1, 5), (1, 6), (1, 7), (1, 8), (1, 9), (1, 10), (1, 11), (1, 12), (1, 13), (1, 14), (1, 15),
-- operator (2) - 大部分智能体
(2, 1), (2, 2), (2, 3), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (2, 10), (2, 11), (2, 12), (2, 13), (2, 14), (2, 15),
-- user (3) - 基础智能体
(3, 1), (3, 3), (3, 13), (3, 15);

-- 用户数据
-- 注意：密码哈希需要通过 Python 脚本生成，请先运行:
-- cd backend && source .venv/bin/activate && python -m app.db.init_db
-- 这会自动创建正确的密码哈希
INSERT INTO users (username, password_hash, display_name, role_id, department_id, status) VALUES
('admin', 'PLEASE_RUN_PYTHON_SCRIPT', '系统管理员', 1, NULL, 'active'),
('zhangsan', 'PLEASE_RUN_PYTHON_SCRIPT', '张三', 1, 1, 'active'),
('lisi', 'PLEASE_RUN_PYTHON_SCRIPT', '李四', 2, 3, 'active'),
('wangwu', 'PLEASE_RUN_PYTHON_SCRIPT', '王五', 3, 4, 'active'),
('zhaoliu', 'PLEASE_RUN_PYTHON_SCRIPT', '赵六', 2, 2, 'active');


-- ============================================================
-- 完成提示
-- ============================================================
-- 数据库初始化完成！
-- 
-- 演示账号：
--   admin / Admin@2026 (管理员)
--   zhangsan / 123456 (管理员)
--   lisi / 123456 (运营)
--   wangwu / 123456 (普通用户)
--   zhaoliu / 123456 (运营)
--
-- 注意：密码哈希需要通过 Python 脚本重新生成
-- 运行: python -m app.db.init_db
-- ============================================================
