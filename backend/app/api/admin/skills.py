from __future__ import annotations
import os
import shutil
import zipfile
from pathlib import Path
import yaml
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ...core.config import settings
from ...db.session import get_db
from ...db.models import Skill
from ...deps import require_admin_or_operator
from ...schemas import SkillIn, SkillOut
from ...runtime.skill_loader import validate_composite_yaml

router = APIRouter(prefix="/api/admin/skills", tags=["admin-skills"],
                   dependencies=[Depends(require_admin_or_operator)])


def _validate(payload: SkillIn) -> None:
    if payload.type == "composite":
        yaml_text = payload.source_json.get("yaml", "")
        if not yaml_text:
            raise HTTPException(400, "composite skill 需要 source_json.yaml")
        try:
            data = yaml.safe_load(yaml_text)
            validate_composite_yaml(data)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(400, f"YAML 解析失败: {e}")
    elif payload.type == "atomic":
        if "path" not in payload.source_json and "callable" not in payload.source_json:
            raise HTTPException(400, "atomic skill 需要 source_json.path 或 callable")


@router.get("", response_model=list[SkillOut])
async def list_skills(db: AsyncSession = Depends(get_db)):
    return (await db.execute(select(Skill).order_by(Skill.id))).scalars().all()


@router.post("", response_model=SkillOut)
async def create_skill(payload: SkillIn, db: AsyncSession = Depends(get_db)):
    _validate(payload)
    if (await db.execute(select(Skill).where(Skill.code == payload.code))).scalar_one_or_none():
        raise HTTPException(400, "code 已存在")
    s = Skill(**payload.model_dump())
    db.add(s); await db.commit(); await db.refresh(s)
    return s


@router.patch("/{sid}", response_model=SkillOut)
async def update_skill(sid: int, payload: SkillIn, db: AsyncSession = Depends(get_db)):
    _validate(payload)
    s = (await db.execute(select(Skill).where(Skill.id == sid))).scalar_one_or_none()
    if not s:
        raise HTTPException(404, "不存在")
    for k, v in payload.model_dump().items():
        setattr(s, k, v)
    s.version += 1
    await db.commit(); await db.refresh(s)
    return s


@router.delete("/{sid}")
async def delete_skill(sid: int, db: AsyncSession = Depends(get_db)):
    s = (await db.execute(select(Skill).where(Skill.id == sid))).scalar_one_or_none()
    if not s:
        raise HTTPException(404, "不存在")
    # remove uploaded directory if path under SKILLS_DIR
    skills_root = Path(settings.SKILLS_DIR).resolve()
    p = (s.source_json or {}).get("path")
    if p:
        try:
            target = Path(p).resolve()
            if str(target).startswith(str(skills_root)):
                shutil.rmtree(target, ignore_errors=True)
        except Exception:
            pass
    await db.delete(s); await db.commit()
    return {"ok": True}


# ---------- Upload Skill package ----------
def _safe_extract(zf: zipfile.ZipFile, target: Path) -> None:
    """Extract with path traversal protection."""
    target = target.resolve()
    for member in zf.infolist():
        member_path = (target / member.filename).resolve()
        if not str(member_path).startswith(str(target)):
            raise HTTPException(400, f"压缩包包含非法路径: {member.filename}")
    zf.extractall(target)


def _find_skill_root(extracted: Path) -> Path:
    """Find the directory that contains SKILL.md (root or first child)."""
    if (extracted / "SKILL.md").exists():
        return extracted
    children = [p for p in extracted.iterdir() if p.is_dir()]
    if len(children) == 1 and (children[0] / "SKILL.md").exists():
        return children[0]
    raise HTTPException(400, "压缩包根目录或唯一子目录中必须包含 SKILL.md")


@router.post("/upload", response_model=SkillOut)
async def upload_skill(
    code: str = Form(...),
    name: str = Form(...),
    description: str = Form(""),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(400, "请上传 zip 包")
    if (await db.execute(select(Skill).where(Skill.code == code))).scalar_one_or_none():
        raise HTTPException(400, "code 已存在")

    skills_root = Path(settings.SKILLS_DIR)
    skills_root.mkdir(parents=True, exist_ok=True)
    target_dir = skills_root / code
    if target_dir.exists():
        raise HTTPException(400, f"目录已存在: {target_dir}")

    tmp_dir = skills_root / f".__tmp_{code}"
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir()

    try:
        # save zip
        zip_path = tmp_dir / "upload.zip"
        with zip_path.open("wb") as f:
            while chunk := await file.read(1024 * 1024):
                f.write(chunk)
        # extract
        extract_dir = tmp_dir / "extract"
        extract_dir.mkdir()
        with zipfile.ZipFile(zip_path) as zf:
            _safe_extract(zf, extract_dir)
        # locate SKILL.md
        skill_root = _find_skill_root(extract_dir)
        # parse SKILL.md frontmatter for description (best-effort)
        skill_md = (skill_root / "SKILL.md").read_text(encoding="utf-8", errors="ignore")
        if not description:
            description = _extract_description(skill_md) or ""
        # move to final location
        shutil.move(str(skill_root), str(target_dir))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    s = Skill(
        code=code, name=name, description=description, type="atomic",
        source_json={"path": str(target_dir.resolve())},
        enabled=True,
    )
    db.add(s); await db.commit(); await db.refresh(s)
    return s


def _extract_description(md: str) -> str | None:
    """Pull description: from YAML frontmatter, or first non-heading line."""
    lines = md.splitlines()
    if lines and lines[0].strip() == "---":
        try:
            end = lines.index("---", 1)
            fm = yaml.safe_load("\n".join(lines[1:end])) or {}
            if isinstance(fm, dict) and fm.get("description"):
                return str(fm["description"])
        except Exception:
            pass
    for line in lines:
        s = line.strip()
        if s and not s.startswith("#") and s != "---":
            return s[:256]
    return None


# ---------- Detail (file tree + content) ----------
def _resolve_skill_dir(s: Skill) -> Path:
    p = (s.source_json or {}).get("path")
    if not p:
        raise HTTPException(400, "该 Skill 没有可浏览的目录")
    skills_root = Path(settings.SKILLS_DIR).resolve()
    target = Path(p).resolve()
    if not str(target).startswith(str(skills_root)):
        raise HTTPException(400, "Skill 目录不在受管路径下,无法浏览")
    if not target.exists() or not target.is_dir():
        raise HTTPException(404, "Skill 目录不存在")
    return target


def _build_tree(root: Path, base: Path) -> list[dict]:
    nodes: list[dict] = []
    for p in sorted(root.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
        rel = str(p.relative_to(base))
        if p.is_dir():
            nodes.append({"name": p.name, "path": rel, "type": "dir", "children": _build_tree(p, base)})
        else:
            try:
                size = p.stat().st_size
            except OSError:
                size = 0
            nodes.append({"name": p.name, "path": rel, "type": "file", "size": size})
    return nodes


@router.get("/{sid}/files")
async def get_skill_files(sid: int, db: AsyncSession = Depends(get_db)):
    s = (await db.execute(select(Skill).where(Skill.id == sid))).scalar_one_or_none()
    if not s:
        raise HTTPException(404, "不存在")
    root = _resolve_skill_dir(s)
    return {"root": root.name, "tree": _build_tree(root, root)}


TEXT_EXT = {".md", ".txt", ".py", ".js", ".ts", ".json", ".yml", ".yaml", ".html", ".css",
            ".sh", ".toml", ".ini", ".cfg", ".csv", ".xml", ".sql", ".go", ".rs", ".java"}


@router.get("/{sid}/file")
async def get_skill_file(sid: int, path: str, db: AsyncSession = Depends(get_db)):
    s = (await db.execute(select(Skill).where(Skill.id == sid))).scalar_one_or_none()
    if not s:
        raise HTTPException(404, "不存在")
    root = _resolve_skill_dir(s)
    target = (root / path).resolve()
    if not str(target).startswith(str(root)):
        raise HTTPException(400, "非法路径")
    if not target.exists() or not target.is_file():
        raise HTTPException(404, "文件不存在")
    size = target.stat().st_size
    if size > 2 * 1024 * 1024:
        raise HTTPException(400, "文件过大,无法预览 (>2MB)")
    ext = target.suffix.lower()
    is_text = ext in TEXT_EXT or size < 64 * 1024
    try:
        content = target.read_text(encoding="utf-8")
        return {"path": path, "size": size, "ext": ext, "content": content, "binary": False}
    except UnicodeDecodeError:
        return {"path": path, "size": size, "ext": ext, "content": "(二进制文件,无法预览)", "binary": True}
