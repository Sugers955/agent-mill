"""Agent 编排调度器 — 支持多 Agent 协作任务。"""
from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timezone
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from .agent_communication import AgentCommunicationService

logger = logging.getLogger(__name__)


class Orchestrator:
    """Agent 编排调度器，支持多种工作流模式。"""
    
    async def run_multi_agent_task(
        self,
        task_config: dict,
        db: AsyncSession,
    ) -> dict:
        """运行多 Agent 协作任务。
        
        task_config format:
        {
            "agents": ["agent1", "agent2"],
            "task": "Analyze user feedback and generate report",
            "workflow": "sequential",  # sequential / parallel / map_reduce
            "timeout": 300,
        }
        """
        from ..db.models import Agent, AgentMessage
        
        workflow = task_config.get("workflow", "sequential")
        agent_codes = task_config.get("agents", [])
        task = task_config.get("task", "")
        timeout = task_config.get("timeout", 300)
        
        if not agent_codes:
            return {"error": "未指定 Agent"}
        
        # Lookup all agents
        agents = []
        for code in agent_codes:
            agent = (await db.execute(
                select(Agent).where(Agent.code == code, Agent.enabled == True)
            )).scalar_one_or_none()
            if not agent:
                return {"error": f"Agent '{code}' 不存在或已禁用"}
            agents.append(agent)
        
        if workflow == "sequential":
            return await self._run_sequential(db, agents, task, timeout)
        elif workflow == "parallel":
            return await self._run_parallel(db, agents, task, timeout)
        elif workflow == "map_reduce":
            return await self._run_map_reduce(db, agents, task, timeout)
        else:
            return {"error": f"未知工作流类型: {workflow}"}
    
    async def _run_sequential(
        self,
        db: AsyncSession,
        agents: list,
        task: str,
        timeout: int,
    ) -> dict:
        """顺序执行：Agent1 → Agent2 → ... → AgentN"""
        from ..db.models import AgentMessage
        
        results = []
        current_input = task
        start_time = asyncio.get_event_loop().time()
        
        for agent in agents:
            # 检查超时
            if asyncio.get_event_loop().time() - start_time >= timeout:
                results.append({
                    "agent": agent.code,
                    "status": "timeout",
                    "error": "任务超时",
                })
                break
            
            # 创建消息
            msg = AgentMessage(
                from_agent_id=0,  # 系统发起
                to_agent_id=agent.id,
                message_type="delegate",
                content=current_input,
                priority=1,
                status="pending",
            )
            db.add(msg)
            await db.commit()
            await db.refresh(msg)
            
            # 等待处理完成（事件驱动）
            remaining_timeout = timeout - (asyncio.get_event_loop().time() - start_time)
            comm = AgentCommunicationService.get_instance()
            event = comm.wait_for_message(msg.id, timeout=remaining_timeout)
            try:
                await asyncio.wait_for(event.wait(), timeout=remaining_timeout)
            except asyncio.TimeoutError:
                pass
            
            # 刷新以获取最新状态
            await db.refresh(msg)
            
            if msg.status == "completed":
                output = msg.result_json.get("text", "") if msg.result_json else ""
                results.append({
                    "agent": agent.code,
                    "status": "success",
                    "output": output,
                })
                current_input = output  # 下一个 Agent 的输入
            else:
                error = msg.result_json.get("error", "处理失败") if msg.result_json else "超时"
                results.append({
                    "agent": agent.code,
                    "status": "failed",
                    "error": error,
                })
                break
        
        return {
            "workflow": "sequential",
            "results": results,
            "success": all(r["status"] == "success" for r in results),
        }
    
    async def _run_parallel(
        self,
        db: AsyncSession,
        agents: list,
        task: str,
        timeout: int,
    ) -> dict:
        """并行执行：所有 Agent 同时处理。"""
        from ..db.models import AgentMessage
        
        messages = []
        for agent in agents:
            msg = AgentMessage(
                from_agent_id=0,  # 系统发起
                to_agent_id=agent.id,
                message_type="delegate",
                content=task,
                priority=1,
                status="pending",
            )
            db.add(msg)
            await db.commit()
            await db.refresh(msg)
            messages.append((agent.code, msg))
        
        # 等待所有处理完成（事件驱动）
        start_time = asyncio.get_event_loop().time()
        comm = AgentCommunicationService.get_instance()
        events = []
        for _, msg in messages:
            remaining_timeout = timeout - (asyncio.get_event_loop().time() - start_time)
            event = comm.wait_for_message(msg.id, timeout=remaining_timeout)
            events.append(event)
        
        # 等待所有事件
        remaining_timeout = timeout - (asyncio.get_event_loop().time() - start_time)
        try:
            await asyncio.wait_for(
                asyncio.gather(*(e.wait() for e in events)),
                timeout=remaining_timeout
            )
        except asyncio.TimeoutError:
            pass
        
        # 刷新所有消息状态
        for _, msg in messages:
            await db.refresh(msg)
        
        results = []
        for agent_code, msg in messages:
            await db.refresh(msg)
            if msg.status == "completed":
                output = msg.result_json.get("text", "") if msg.result_json else ""
                results.append({
                    "agent": agent_code,
                    "status": "success",
                    "output": output,
                })
            else:
                error = msg.result_json.get("error", "处理失败") if msg.result_json else "超时"
                results.append({
                    "agent": agent_code,
                    "status": "failed",
                    "error": error,
                })
        
        return {
            "workflow": "parallel",
            "results": results,
            "success": all(r["status"] == "success" for r in results),
        }
    
    async def _run_map_reduce(
        self,
        db: AsyncSession,
        agents: list,
        task: str,
        timeout: int,
    ) -> dict:
        """Map-Reduce：各 Agent 独立处理，最后汇总。"""
        from ..db.models import AgentMessage
        
        # Map 阶段
        map_results = await self._run_parallel(db, agents, task, timeout // 2)
        
        if not map_results["success"]:
            return map_results
        
        # Reduce 阶段：使用第一个 Agent 汇总结果
        summary_input = "请汇总以下各 Agent 的分析结果：\n\n"
        for r in map_results["results"]:
            summary_input += f"## {r['agent']} Result\n{r['output']}\n\n"
        
        msg = AgentMessage(
            from_agent_id=0,  # System-initiated
            to_agent_id=agents[0].id,  # 使用第一个 Agent 汇总
            message_type="delegate",
            content=summary_input,
            priority=1,
            status="pending",
        )
        db.add(msg)
        await db.commit()
        await db.refresh(msg)
        
        # 等待汇总完成（事件驱动）
        start_time = asyncio.get_event_loop().time()
        reduce_timeout = timeout // 2
        comm = AgentCommunicationService.get_instance()
        event = comm.wait_for_message(msg.id, timeout=reduce_timeout)
        try:
            await asyncio.wait_for(event.wait(), timeout=reduce_timeout)
        except asyncio.TimeoutError:
            pass
        
        # Refresh to get latest status
        await db.refresh(msg)
        
        if msg.status == "completed":
            reduce_output = msg.result_json.get("text", "") if msg.result_json else ""
        else:
            reduce_output = None
        
        return {
            "workflow": "map_reduce",
            "map_results": map_results["results"],
            "reduce_result": reduce_output,
            "success": msg.status == "completed",
        }
