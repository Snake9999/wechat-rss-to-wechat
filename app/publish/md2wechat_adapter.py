from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path


def upload_markdown(
    run_sh: str,
    markdown_path: Path,
    cover_path: Path | None = None,
    dry_run: bool = False,
) -> subprocess.CompletedProcess[str]:
    if not run_sh:
        raise RuntimeError("MD2WECHAT_RUN_SCRIPT is empty")

    env = os.environ.copy()
    # Avoid stale global credentials overriding ~/.config/md2wechat/config.yaml.
    env.pop("WECHAT_APPID", None)
    env.pop("WECHAT_SECRET", None)
    if dry_run:
        command = build_md2wechat_command(run_sh, "convert", str(markdown_path), "--draft")
        if cover_path is not None:
            command.extend(["--cover", str(cover_path)])
        return subprocess.CompletedProcess(command, 0, stdout="dry run", stderr="")

    with tempfile.TemporaryDirectory(prefix="werss2md-md2wechat-") as tmp_dir:
        draft_path = Path(tmp_dir) / "draft.json"
        convert_command = build_md2wechat_command(run_sh, "convert", str(markdown_path), "--save-draft", str(draft_path))
        convert_result = subprocess.run(convert_command, capture_output=True, text=True, check=False, env=env)
        if convert_result.returncode != 0:
            return convert_result

        draft_payload = json.loads(draft_path.read_text(encoding="utf-8"))
        articles = draft_payload.get("articles", [])
        if not articles:
            return subprocess.CompletedProcess(
                convert_command,
                1,
                stdout=convert_result.stdout,
                stderr=convert_result.stderr + "\nno articles found in saved draft payload",
            )

        title = extract_markdown_title(markdown_path)
        if title:
            articles[0]["title"] = title

        combined_stdout = [convert_result.stdout]
        combined_stderr = [convert_result.stderr]
        command_chain: list[list[str]] = [convert_command]

        if cover_path is not None:
            upload_command = build_md2wechat_command(run_sh, "upload_image", str(cover_path))
            upload_result = subprocess.run(upload_command, capture_output=True, text=True, check=False, env=env)
            command_chain.append(upload_command)
            combined_stdout.append(upload_result.stdout)
            combined_stderr.append(upload_result.stderr)
            if upload_result.returncode != 0:
                return subprocess.CompletedProcess(
                    upload_command,
                    upload_result.returncode,
                    stdout="".join(combined_stdout),
                    stderr="".join(combined_stderr),
                )
            media_id = extract_media_id(upload_result.stdout)
            if not media_id:
                return subprocess.CompletedProcess(
                    upload_command,
                    1,
                    stdout="".join(combined_stdout),
                    stderr="".join(combined_stderr) + "\nfailed to parse media_id from upload_image output",
                )
            articles[0]["thumb_media_id"] = media_id

        draft_path.write_text(json.dumps(draft_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        create_draft_command = build_md2wechat_command(run_sh, "create_draft", str(draft_path))
        create_result = subprocess.run(create_draft_command, capture_output=True, text=True, check=False, env=env)
        command_chain.append(create_draft_command)
        combined_stdout.append(create_result.stdout)
        combined_stderr.append(create_result.stderr)

        return subprocess.CompletedProcess(
            [" && ".join(" ".join(command) for command in command_chain)],
            create_result.returncode,
            stdout="".join(combined_stdout),
            stderr="".join(combined_stderr),
        )


def extract_markdown_title(markdown_path: Path) -> str:
    try:
        markdown = markdown_path.read_text(encoding="utf-8")
    except OSError:
        return ""
    for line in markdown.splitlines():
        text = line.strip()
        if text.startswith("# "):
            return text[2:].strip()
    return ""


def build_md2wechat_command(run_script: str, *args: str) -> list[str]:
    script_path = Path(run_script)
    suffix = script_path.suffix.lower()
    if suffix == ".ps1":
        return [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script_path),
            *args,
        ]
    if suffix in {".cmd", ".bat"}:
        return ["cmd", "/c", str(script_path), *args]
    if suffix == ".sh":
        return ["bash", str(script_path), *args]
    return [str(script_path), *args]


def extract_media_id(stdout: str) -> str:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        lines = [line.strip() for line in stdout.splitlines() if line.strip().startswith("{")]
        for line in reversed(lines):
            try:
                payload = json.loads(line)
                break
            except json.JSONDecodeError:
                continue
        else:
            return ""
    data = payload.get("data", {})
    media_id = data.get("media_id") if isinstance(data, dict) else ""
    return str(media_id).strip()
