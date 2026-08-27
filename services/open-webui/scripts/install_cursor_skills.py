#!/usr/bin/env python3
"""Install Cursor skills from ~/.cursor/skills-cursor into Open WebUI Skills workspace.

Run inside the open-webui container:
  PYTHONPATH=/app/backend python3 /tmp/install_cursor_skills.py
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import tempfile
import zipfile
from pathlib import Path

import yaml
from sqlalchemy import text

SKILLS_ROOT = Path(os.environ.get("CURSOR_SKILLS_DIR", "/skills-cursor"))
OWNER_EMAIL = os.environ.get("IRON_LAB_OWNER_EMAIL", "iron@hub.local")
MODEL_ID = os.environ.get("IRON_LAB_MODEL_ID", "qwen-local")
MAX_CONTENT_BYTES = int(os.environ.get("IRON_SKILL_MAX_BYTES", str(900_000)))
SKIP_DIR_NAMES = {
    "saas-zero-trust-security-workspace",  # evals only
    ".git",
    "__pycache__",
}


def slugify(value: str) -> str:
    value = value.strip().lower().replace(" ", "-")
    value = re.sub(r"[^a-z0-9._-]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value or "skill"


def parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    raw = text[3:end].strip()
    body = text[end + 4 :].lstrip("\n")
    try:
        meta = yaml.safe_load(raw) or {}
        if not isinstance(meta, dict):
            meta = {}
    except Exception:
        meta = {}
    return meta, body


def collect_reference_mds(root: Path) -> list[Path]:
    refs: list[Path] = []
    for pattern in ("references/**/*.md", "reference-*.md", "**/references/**/*.md"):
        refs.extend(root.glob(pattern))
    # de-dupe, stable order, skip SKILL.md
    seen = set()
    out = []
    for p in sorted(refs, key=lambda x: str(x)):
        if p.name.upper() == "SKILL.MD":
            continue
        rp = p.resolve()
        if rp in seen:
            continue
        seen.add(rp)
        out.append(p)
    return out


def build_content_from_dir(skill_dir: Path) -> tuple[str, dict]:
    skill_md = skill_dir / "SKILL.md"
    text = skill_md.read_text(encoding="utf-8", errors="replace")
    meta, _ = parse_frontmatter(text)
    parts = [text.rstrip(), ""]
    for ref in collect_reference_mds(skill_dir):
        rel = ref.relative_to(skill_dir)
        parts.append(f"\n\n---\n\n## Reference: `{rel.as_posix()}`\n\n")
        parts.append(ref.read_text(encoding="utf-8", errors="replace").rstrip())
        parts.append("")
    content = "\n".join(parts).strip() + "\n"
    return content, meta


def build_content_from_skill_zip(skill_zip: Path) -> tuple[str, dict, str]:
    with zipfile.ZipFile(skill_zip) as zf:
        names = zf.namelist()
        skill_names = [n for n in names if n.endswith("SKILL.md") or n.endswith("skill.md")]
        if not skill_names:
            raise FileNotFoundError(f"no SKILL.md in {skill_zip}")
        # Prefer top-level */SKILL.md
        skill_names.sort(key=lambda n: (n.count("/"), len(n)))
        main = skill_names[0]
        base_prefix = str(Path(main).parent)
        if base_prefix == ".":
            base_prefix = ""
        text = zf.read(main).decode("utf-8", errors="replace")
        meta, _ = parse_frontmatter(text)
        parts = [text.rstrip(), ""]
        ref_names = [
            n
            for n in names
            if n.endswith(".md")
            and n != main
            and ("/references/" in n or n.startswith("references/") or "/reference-" in n or Path(n).name.startswith("reference-"))
        ]
        for n in sorted(ref_names):
            parts.append(f"\n\n---\n\n## Reference: `{n}`\n\n")
            parts.append(zf.read(n).decode("utf-8", errors="replace").rstrip())
            parts.append("")
        content = "\n".join(parts).strip() + "\n"
        sid = slugify(meta.get("name") or skill_zip.stem)
        return content, meta, sid


def discover_skills(root: Path) -> list[dict]:
    items: list[dict] = []
    # Directory skills
    for skill_md in sorted(root.glob("*/SKILL.md")):
        if skill_md.parent.name in SKIP_DIR_NAMES:
            continue
        content, meta = build_content_from_dir(skill_md.parent)
        name = str(meta.get("name") or skill_md.parent.name)
        items.append(
            {
                "id": slugify(name),
                "name": name,
                "description": str(meta.get("description") or "").strip() or f"Cursor skill: {name}",
                "content": content,
                "tags": ["cursor", "skills-cursor", skill_md.parent.name],
                "source": str(skill_md.parent),
            }
        )
    # Packaged .skill zips
    for skill_zip in sorted(root.glob("*.skill")):
        content, meta, sid = build_content_from_skill_zip(skill_zip)
        name = str(meta.get("name") or skill_zip.stem)
        items.append(
            {
                "id": slugify(name) if meta.get("name") else sid,
                "name": name,
                "description": str(meta.get("description") or "").strip() or f"Cursor skill: {name}",
                "content": content,
                "tags": ["cursor", "skills-cursor", "packaged", skill_zip.stem],
                "source": str(skill_zip),
            }
        )
    # de-dupe by id (prefer longer/richer content)
    by_id: dict[str, dict] = {}
    for item in items:
        prev = by_id.get(item["id"])
        if prev is None or len(item["content"]) > len(prev["content"]):
            by_id[item["id"]] = item
    return list(by_id.values())


def truncate_content(content: str) -> tuple[str, bool]:
    data = content.encode("utf-8")
    if len(data) <= MAX_CONTENT_BYTES:
        return content, False
    # keep head
    cut = data[:MAX_CONTENT_BYTES].decode("utf-8", errors="ignore")
    cut += "\n\n<!-- truncated for Open WebUI skill size limit -->\n"
    return cut, True


async def main() -> int:
    from open_webui.internal.db import get_async_db_context
    from open_webui.models.skills import SkillForm, SkillMeta, Skills

    if not SKILLS_ROOT.is_dir():
        print(f"ERROR: skills root not found: {SKILLS_ROOT}", file=sys.stderr)
        return 1

    skills = discover_skills(SKILLS_ROOT)
    print(f"discovered {len(skills)} skills under {SKILLS_ROOT}")

    async with get_async_db_context() as db:
        row = (
            await db.execute(text("select id, email, role from user where email = :e"), {"e": OWNER_EMAIL})
        ).fetchone()
        if not row:
            row = (await db.execute(text("select id, email, role from user where role = 'admin' limit 1"))).fetchone()
        if not row:
            print("ERROR: no admin user", file=sys.stderr)
            return 1
        user_id = row[0]
        print(f"owner: {row[1]} ({user_id})")

    installed_ids: list[str] = []
    created = updated = 0

    for item in sorted(skills, key=lambda x: x["id"]):
        content, truncated = truncate_content(item["content"])
        form = SkillForm(
            id=item["id"],
            name=item["name"],
            description=item["description"][:2000],
            content=content,
            meta=SkillMeta(tags=item["tags"]),
            is_active=True,
            access_grants=[],
        )
        existing = await Skills.get_skill_by_id(form.id)
        # name unique — if another skill owns the name, suffix id into name
        by_name = await Skills.get_skill_by_name(form.name)
        if by_name and by_name.id != form.id:
            form.name = f"{form.name} ({form.id})"

        if existing:
            ok = await Skills.update_skill_by_id(
                form.id,
                {
                    "name": form.name,
                    "description": form.description,
                    "content": form.content,
                    "meta": form.meta.model_dump(),
                    "is_active": True,
                },
            )
            updated += 1 if ok else 0
            status = "updated" if ok else "update-failed"
        else:
            ok = await Skills.insert_new_skill(user_id, form)
            created += 1 if ok else 0
            status = "created" if ok else "create-failed"

        installed_ids.append(form.id)
        flag = " [truncated]" if truncated else ""
        print(f"  {status:14} {form.id:40} {len(content):7} bytes{flag}  ← {item['source']}")

    # Do NOT auto-attach all skills to the workspace model.
    # Attaching ~30 skills injects hundreds of KB into every prompt and makes
    # Qwen-27B on dual V520 unusable (45k+ token prefills). Skills remain
    # installed for on-demand use ($skill / UI attach).
    async with get_async_db_context() as db:
        row = (await db.execute(text("select meta, params from model where id = :id"), {"id": MODEL_ID})).fetchone()
        if not row:
            print(f"WARNING: model {MODEL_ID} not found — enable skills manually", file=sys.stderr)
        else:
            meta = json.loads(row[0]) if isinstance(row[0], str) else (row[0] or {})
            params = json.loads(row[1]) if isinstance(row[1], str) else (row[1] or {})
            caps = dict(meta.get("capabilities") or {})
            caps["skills"] = True
            meta["capabilities"] = caps
            # Keep whatever the operator set; never bulk-merge installed_ids.
            await db.execute(
                text("update model set meta = :m, params = :p, updated_at = strftime('%s','now') where id = :id"),
                {"m": json.dumps(meta), "p": json.dumps(params), "id": MODEL_ID},
            )
            await db.commit()
            print(f"model {MODEL_ID}: skillIds={len(meta.get('skillIds') or [])} (not auto-attached; installed={len(installed_ids)})")

    print(f"done: created={created} updated={updated} total={len(installed_ids)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
