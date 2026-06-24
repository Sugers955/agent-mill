"""Agent 间通信服务 — 支持多 Agent 协作和任务委托。"""
from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timezone
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class AgentCommunicationService:
    """Agent 间通信服务，支持消息传递和任务委托。"""
    
    _instance: "AgentCommunicationService | None" = None
    _polling_task: asyncio.Task | None = None
    _message_events: dict[int, asyncio.Event] = {}
    
    @classmethod
    def get_instance(cls) -> "AgentCommunicationService":
        """获取单例实例（不再持有 db session）。"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        pass  # 不再持有 db session
    
    def wait_for_message(self, message_id: int, timeout: float = 60) -> asyncio.Event:
        """创建一个等待指定消息完成的 Event。"""
        event = asyncio.Event()
        self._message_events[message_id] = event
        return event
    
    def notify_message_complete(self, message_id: int):
        """通知消息已完成。"""
        event = self._message_events.pop(message_id, None)
        if event:
            event.set()
    
    def start_polling(self):
        """启动消息轮询（应用启动时调用）。"""
        if self._polling_task is None or self._polling_task.done():
            self._polling_task = asyncio.create_task(self._poll_loop())
            logger.info("[AgentComm] 消息轮询已启动")
    
    def stop_polling(self):
        """停止消息轮询。"""
        if self._polling_task and not self._polling_task.done():
            self._polling_task.cancel()
            logger.info("[AgentComm] 消息轮询已停止")
    
    async def _poll_loop(self):
        """持续轮询未处理的消息。"""
        while True:
            try:
                await self._process_pending_messages()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("[AgentComm] 消息处理出错: %s", e)
            await asyncio.sleep(5)  # 每 5 秒检查一次
    
    async def _process_pending_messages(self):
        """处理所有未消费的消息。"""
        from ..db.session import SessionLocal
        from ..db.models import AgentMessage, Agent
        from ..runtime.agent_runner import AgentRunner
        
        async with SessionLocal() as db:
            # 获取未消费的消息（status=pending）
            pending = list((await db.execute(
                select(AgentMessage)
                .where(AgentMessage.status == "pending")
                .order_by(AgentMessage.priority.desc(), AgentMessage.created_at.asc())
                .limit(10)
            )).scalars().all())
            
            for msg in pending:
                await self._handle_message(db, msg, Agent, AgentRunner)
    
    async def _handle_message(self, db, msg, Agent, AgentRunner):
        """处理单条消息。"""
        from ..db.models import AgentMessage
        
        try:
            # 标记为处理中
            msg.status = "processing"
            await db.commit()
            
            # 查找目标 Agent
            target_agent = (await db.execute(
                select(Agent).where(Agent.id == msg.to_agent_id)
            )).scalar_one_or_none()
            
            if not target_agent:
                msg.status = "failed"
                msg.result_json = {"error": f"目标 Agent {msg.to_agent_id} 不存在"}
                await db.commit()
                self.notify_message_complete(msg.id)
                return
            
            # 查找源 Agent（用于上下文）
            source_agent = (await db.execute(
                select(Agent).where(Agent.id == msg.from_agent_id)
            )).scalar_one_or_none()
            
            source_name = source_agent.name if source_agent else f"Agent-{msg.from_agent_id}"
            
            # 构建消息上下文
            context = f"来自 {source_name} 的消息：\n{msg.content}"
            if msg.priority == 1:
                context = f"[高优先级] {context}"
            
            # 创建或复用对话
            if msg.conversation_id:
                conversation_id = msg.conversation_id
            else:
                from ..db.models import Conversation
                conv = Conversation(
                    user_id=0,  # 系统发起
                    agent_id=target_agent.id,
                    title=f"Agent 协作: {source_name} → {target_agent.name}",
                )
                db.add(conv)
                await db.commit()
                await db.refresh(conv)
                conversation_id = conv.id
                msg.conversation_id = conversation_id
            
            # 执行 Agent
            runner = AgentRunner(
                agent_code=target_agent.code,
                conversation_id=conversation_id,
                user_id=0,  # 系统用户
            )
            
            result = await runner.run(
                user_message=context,
                db_session=db,
            )
            
            # 保存响应
            msg.result_json = {
                "text": result.get("text", ""),
                "agent": target_agent.code,
                "conversation_id": conversation_id,
            }
            msg.status = "completed"
            await db.commit()
            self.notify_message_complete(msg.id)
            
            logger.info("[AgentComm] 消息 %d 处理完成: %s", msg.id, target_agent.code)
            
        except Exception as e:
            msg.status = "failed"
            msg.result_json = {"error": f"处理失败: {str(e)}"}
            await db.commit()
            self.notify_message_complete(msg.id)
            logger.error("[AgentComm] 消息 %d 处理失败: %s", msg.id, e)
    
    async def send_message(
        self,
        from_agent_id: int,
        to_agent_id: int,
        message_type: str,
        content: str,
        context_json: dict | None = None,
        conversation_id: int | None = None,
        priority: int = 0,
    ) -> int:
        """发送消息给另一个 Agent。
        
        Returns:
            消息 ID
        """
        from ..db.session import SessionLocal
        from ..db.models import AgentMessage
        
        async with SessionLocal() as db:
            msg = AgentMessage(
                from_agent_id=from_agent_id,
                to_agent_id=to_agent_id,
                message_type=message_type,
                content=content,
                context_json=context_json,
                conversation_id=conversation_id,
                status="pending",
                priority=priority,
            )
            db.add(msg)
            await db.commit()
            await db.refresh(msg)
            
            logger.info("Agent message sent: %d → %d, type=%s, id=%d",
                        from_agent_id, to_agent_id, message_type, msg.id)
            return msg.id
    
    async def receive_messages(
        self,
        to_agent_id: int,
        status: str = "pending",
        limit: int = 10,
    ) -> list[dict]:
        """接收待处理的消息。"""
        from ..db.session import SessionLocal
        from ..db.models import AgentMessage
        
        async with SessionLocal() as db:
            msgs = list((await db.execute(
                select(AgentMessage)
                .where(
                    AgentMessage.to_agent_id == to_agent_id,
                    AgentMessage.status == status,
                )
                .order_by(desc(AgentMessage.priority), desc(AgentMessage.created_at))
                .limit(limit)
            )).scalars().all())
            
            return [
                {
                    "id": m.id,
                    "from_agent_id": m.from_agent_id,
                    "message_type": m.message_type,
                    "content": m.content,
                    "context_json": m.context_json,
                    "priority": m.priority,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in msgs
            ]
    
    async def complete_message(
        self,
        message_id: int,
        result: dict,
        status: str = "completed",
    ) -> bool:
        """标记消息为已完成，并返回结果。"""
        from ..db.session import SessionLocal
        from ..db.models import AgentMessage
        
        async with SessionLocal() as db:
            msg = (await db.execute(
                select(AgentMessage).where(AgentMessage.id == message_id)
            )).scalar_one_or_none()
            
            if not msg:
                return False
            
            msg.status = status
            msg.result_json = result
            await db.commit()
            
            logger.info("Agent message %d completed: status=%s", message_id, status)
            return True
    
    async def reply_to_message(
        self,
        original_msg_id: int,
        content: str,
        result: dict | None = None,
    ) -> int:
        """回复一条消息。"""
        from ..db.session import SessionLocal
        from ..db.models import AgentMessage
        
        async with SessionLocal() as db:
            original = (await db.execute(
                select(AgentMessage).where(AgentMessage.id == original_msg_id)
            )).scalar_one_or_none()
            
            if not original:
                raise ValueError(f"消息 {original_msg_id} 不存在")
            
            # 创建回复消息
            reply = AgentMessage(
                from_agent_id=original.to_agent_id,
                to_agent_id=original.from_agent_id,
                message_type="reply",
                content=content,
                context_json=result,
                conversation_id=original.conversation_id,
                status="completed",
                reply_to_id=original_msg_id,
            )
            db.add(reply)
            
            # 标记原消息为已完成
            original.status = "completed"
            original.result_json = result
            
            await db.commit()
            await db.refresh(reply)
            
            return reply.id
    
    async def get_conversation_history(
        self,
        agent_id: int,
        limit: int = 20,
    ) -> list[dict]:
        """获取某个 Agent 的通信历史。"""
        from ..db.session import SessionLocal
        from ..db.models import AgentMessage
        
        async with SessionLocal() as db:
            msgs = list((await db.execute(
                select(AgentMessage)
                .where(
                    (AgentMessage.from_agent_id == agent_id) |
                    (AgentMessage.to_agent_id == agent_id)
                )
                .order_by(desc(AgentMessage.created_at))
                .limit(limit)
            )).scalars().all())
            
            return [
                {
                    "id": m.id,
                    "from_agent_id": m.from_agent_id,
                    "to_agent_id": m.to_agent_id,
                    "message_type": m.message_type,
                    "content": m.content,
                    "status": m.status,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in msgs
            ]
    
    async def delegate_task(
        self,
        from_agent_id: int,
        to_agent_id: int,
        task_description: str,
        context: dict | None = None,
        conversation_id: int | None = None,
    ) -> int:
        """委托任务给另一个 Agent（便捷方法）。"""
        return await self.send_message(
            from_agent_id=from_agent_id,
            to_agent_id=to_agent_id,
            message_type="delegate",
            content=task_description,
            context_json=context,
            conversation_id=conversation_id,
            priority=1,  # 委托任务默认高优先级
        )
    
    async def query_agent(
        self,
        from_agent_id: int,
        to_agent_id: int,
        question: str,
        context: dict | None = None,
    ) -> dict | None:
        """向另一个 Agent 查询信息（同步等待回复）。"""
        import asyncio
        from ..db.session import SessionLocal
        from ..db.models import AgentMessage
        
        msg_id = await self.send_message(
            from_agent_id=from_agent_id,
            to_agent_id=to_agent_id,
            message_type="query",
            content=question,
            context_json=context,
        )
        
        # 等待回复（基于事件驱动）
        event = self.wait_for_message(msg_id, timeout=60)
        try:
            await asyncio.wait_for(event.wait(), timeout=60)
        except asyncio.TimeoutError:
            pass
        
        # 获取结果
        async with SessionLocal() as db:
            msg = (await db.execute(
                select(AgentMessage).where(AgentMessage.id == msg_id)
            )).scalar_one_or_none()
            
            if msg and msg.status == "completed":
                return msg.result_json
        
        return None
