"""任务模板管理 API。"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from ...db.session import get_db
from ...db.models import TaskTemplate, Task, User
from ...deps import current_user, require_admin

router = APIRouter(prefix="/task-templates", tags=["task-templates"])


class TemplateCreate(BaseModel):
    name: str
    description: str | None = None
    agent_id: int
    prompt_template: str
    variables: list = []
    schedule: dict | None = None
    notify: dict | None = None


class TemplateInstantiate(BaseModel):
    variables: dict = {}
    schedule: dict | None = None


@router.get("")
async def list_templates(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    """获取任务模板列表。"""
    total = (await db.execute(select(func.count(TaskTemplate.id)))).scalar_one()
    stmt = select(TaskTemplate).order_by(desc(TaskTemplate.created_at)).limit(limit).offset(offset)
    result = await db.execute(stmt)
    templates = result.scalars().all()
    return {
        "items": [
            {
                "id": t.id, "name": t.name, "description": t.description,
                "agent_id": t.agent_id, "usage_count": t.usage_count,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in templates
        ],
        "total": total,
    }


@router.post("")
async def create_template(
    body: TemplateCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    """创建任务模板。"""
    template = TaskTemplate(
        name=body.name,
        description=body.description,
        agent_id=body.agent_id,
        prompt_template=body.prompt_template,
        variables_json=body.variables,
        schedule_json=body.schedule,
        notify_config_json=body.notify,
        created_by=user.id,
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return {"id": template.id, "status": "created"}


@router.post("/{template_id}/instantiate")
async def instantiate_template(
    template_id: int,
    body: TemplateInstantiate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    """从模板创建任务。"""
    stmt = select(TaskTemplate).where(TaskTemplate.id == template_id)
    result = await db.execute(stmt)
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(404, "模板不存在")

    # 替换变量
    prompt = template.prompt_template
    for key, value in body.variables.items():
        prompt = prompt.replace("{{" + key + "}}", str(value))

    # 创建任务
    task = Task(
        owner_user_id=user.id,
        agent_id=template.agent_id,
        name=f"来自模板: {template.name}",
        prompt_text=prompt,
        schedule_type="manual",
    )
    db.add(task)

    # 更新使用次数
    template.usage_count = (template.usage_count or 0) + 1
    await db.commit()
    await db.refresh(task)

    return {"task_id": task.id, "status": "created"}


@router.delete("/{template_id}")
async def delete_template(
    template_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    """删除任务模板。"""
    stmt = select(TaskTemplate).where(TaskTemplate.id == template_id)
    result = await db.execute(stmt)
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(404, "模板不存在")
    await db.delete(template)
    await db.commit()
    return {"status": "deleted"}
