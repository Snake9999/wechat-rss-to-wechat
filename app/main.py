from __future__ import annotations

import argparse
import json
from datetime import datetime
from datetime import timezone
from pathlib import Path
import yaml

from app.extract.wechat_article import extract_article
from app.fetch.wewe_rss import fetch_available_sources, fetch_latest_articles, parse_published_timestamp
from app.image.generate_cover_image import (
    download_cover_from_url,
)
from app.image.wechat_cover import generate_wechat_cover_assets
from app.publish.upload_draft import upload_draft
from app.settings import load_settings, load_yaml
from app.state.dedupe import ProcessedArticleStore
from app.state.run_log import append_run_log
from app.transform.html_cleaner import clean_html
from app.transform.content_policy import apply_content_policy
from app.transform.html_to_markdown import convert_html_to_markdown, fallback_text_markdown
from app.transform.rewrite_article import maybe_rewrite_markdown
from app.utils.http import get
from app.utils.file_io import write_json, write_text
from app.utils.logger import get_logger
from app.utils.slug import slugify

logger = get_logger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="werss2md CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="Check environment and config")
    doctor.set_defaults(handler=handle_doctor)

    prepare = subparsers.add_parser("prepare", help="Check prerequisites and suggest next steps")
    prepare.set_defaults(handler=handle_prepare)

    fetch = subparsers.add_parser("fetch-latest", help="Fetch latest article metadata")
    fetch.add_argument("--source", help="wewe-rss source id; omit to auto-select across enabled sources")
    fetch.set_defaults(handler=handle_fetch_latest)

    sync_sources = subparsers.add_parser("sync-sources", help="Sync source list from wewe-rss /feeds into config/sources.yaml")
    sync_sources.set_defaults(handler=handle_sync_sources)

    candidates = subparsers.add_parser("daily-candidates", help="Collect today's topic candidates across sources")
    candidates.add_argument("--source", help="Only inspect one wewe-rss source id")
    candidates.add_argument("--limit-per-source", type=int, default=0, help="Override pipeline.fetch_limit")
    candidates.add_argument("--include-processed", action="store_true", help="Include already processed items in the candidate list")
    candidates.add_argument("--no-summary", action="store_true", help="Skip body preview extraction for faster candidate generation")
    candidates.set_defaults(handler=handle_daily_candidates)

    extract = subparsers.add_parser("extract-url", help="Extract WeChat article")
    extract.add_argument("url", help="WeChat article URL")
    extract.set_defaults(handler=handle_extract_url)

    run_once = subparsers.add_parser("run-once", help="Run the minimal pipeline once")
    run_once.add_argument("--source", help="wewe-rss source id; omit to auto-select across enabled sources")
    run_once.add_argument("--item-id", default="", help="Exact wewe-rss item id selected from daily-candidates")
    run_once.add_argument("--dry-run", action="store_true", help="Skip real md2wechat upload")
    run_once.add_argument("--force", action="store_true", help="Reprocess even if article was already marked processed")
    run_once.add_argument("--cover", default="", help="Optional local cover image path for draft upload")
    run_once.add_argument("--auto-cover", action="store_true", help="Generate cover image automatically when --cover is not provided")
    run_once.add_argument("--rewrite", action="store_true", help="Enable LLM rewrite before publishing")
    run_once.set_defaults(handler=handle_run_once)

    generate_cover = subparsers.add_parser("generate-cover", help="Generate a WeChat cover image")
    generate_cover.add_argument("--source", help="wewe-rss source id; fetch latest article and generate cover")
    generate_cover.add_argument("--markdown", help="Generate cover from an existing markdown file")
    generate_cover.add_argument("--title", default="", help="Optional title override")
    generate_cover.add_argument("--subtitle", default="", help="Optional subtitle override")
    generate_cover.add_argument("--style", default="", help="Optional style override")
    generate_cover.add_argument("--accent", default="", help="Optional accent override")
    generate_cover.add_argument("--variant", default="", help="Optional variant override")
    generate_cover.add_argument("--profile", default="", help="Optional cover profile override")
    generate_cover.add_argument("--output", default="", help="Optional output image path")
    generate_cover.set_defaults(handler=handle_generate_cover)

    snapshot = subparsers.add_parser("snapshot", help="Write an iteration snapshot markdown")
    snapshot.add_argument("--title", required=True, help="Snapshot title")
    snapshot.add_argument("--summary", default="", help="Short summary")
    snapshot.set_defaults(handler=handle_snapshot)

    return parser


def handle_doctor(_: argparse.Namespace) -> int:
    settings = load_settings()
    pipeline_config = load_yaml(settings.pipeline_config_path)
    results = []
    md2wechat_ok = bool(settings.md2wechat_run_sh) and Path(settings.md2wechat_run_sh).exists()
    sources_exists = settings.sources_config_path.exists()
    pipeline_exists = settings.pipeline_config_path.exists()
    wewe_rss_ok, wewe_rss_detail = diagnose_wewe_rss_connectivity(
        settings.wewe_rss_base_url,
        pipeline_config,
    )

    results.append(("WEWE_RSS_BASE_URL", wewe_rss_ok, wewe_rss_detail))
    results.append(("MD2WECHAT_RUN_SH", md2wechat_ok, settings.md2wechat_run_sh or "(empty)"))
    results.append((".env", (settings.root_dir / ".env").exists(), str(settings.root_dir / ".env")))
    results.append(("config/sources.yaml", sources_exists, str(settings.sources_config_path)))
    results.append(("config/pipeline.yaml", pipeline_exists, str(settings.pipeline_config_path)))

    for label, ok, detail in results:
        prefix = "[OK]" if ok else "[WARN]"
        print(f"{prefix} {label}: {detail}")

    if sources_exists:
        try:
            get_pipeline_source_ids()
            print("[OK] sources config parsed")
        except Exception as exc:
            print(f"[WARN] sources config parse failed: {exc}")
    else:
        print("[WARN] sources config not initialized")

    return 0


def handle_prepare(_: argparse.Namespace) -> int:
    settings = load_settings()
    pipeline_config = load_yaml(settings.pipeline_config_path)
    report = build_prepare_report(settings, pipeline_config)

    for label, ok, detail in report["checks"]:
        prefix = "[OK]" if ok else "[WARN]"
        print(f"{prefix} {label}: {detail}")

    print("")
    if report["ready"]:
        print("[READY] prerequisites look good")
        print("[NEXT] ./skill/scripts/run_pipeline.sh sync")
        print("[NEXT] ./skill/scripts/run_pipeline.sh candidates")
        print("[NEXT] ./skill/scripts/run_pipeline.sh run --source <SOURCE_ID> --item-id <ITEM_ID> --rewrite --auto-cover --dry-run")
        return 0

    print("[BLOCKED] fix the items above before running the production chain")
    for step in report["next_steps"]:
        print(f"[NEXT] {step}")
    return 1


def handle_fetch_latest(args: argparse.Namespace) -> int:
    settings = load_settings()
    pipeline_config = load_yaml(settings.pipeline_config_path)
    templates = get_feed_url_templates(pipeline_config)
    if args.source:
        article = fetch_latest_articles(
            settings.wewe_rss_base_url,
            args.source,
            limit=1,
            feed_url_templates=templates,
        )[0]
    else:
        article = select_article(
            settings=settings,
            pipeline_config=pipeline_config,
            source_id=args.source,
            item_id="",
            feed_templates=templates,
            skip_processed=False,
        )
    print(json.dumps(article.to_dict(), ensure_ascii=False, indent=2))
    return 0


def handle_sync_sources(_: argparse.Namespace) -> int:
    settings = load_settings()
    discovered_sources = fetch_available_sources(settings.wewe_rss_base_url)
    existing_config = load_yaml(settings.sources_config_path)
    existing_sources = existing_config.get("sources", [])
    merged_sources = merge_source_configs(existing_sources, discovered_sources)

    payload = {"sources": merged_sources}
    settings.sources_config_path.parent.mkdir(parents=True, exist_ok=True)
    settings.sources_config_path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    discovered_ids = {source["id"] for source in discovered_sources}
    existing_ids = {source.get("id") for source in existing_sources if isinstance(source, dict) and source.get("id")}
    created_ids = sorted(discovered_ids - existing_ids)
    updated_ids = sorted(discovered_ids & existing_ids)
    preserved_ids = sorted(existing_ids - discovered_ids)

    print(
        json.dumps(
            {
                "ok": True,
                "wewe_rss_base_url": settings.wewe_rss_base_url,
                "sources_config_path": str(settings.sources_config_path),
                "summary": {
                    "discovered_count": len(discovered_sources),
                    "merged_count": len(merged_sources),
                    "created_count": len(created_ids),
                    "updated_count": len(updated_ids),
                    "preserved_manual_count": len(preserved_ids),
                },
                "created_ids": created_ids,
                "updated_ids": updated_ids,
                "preserved_manual_ids": preserved_ids,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def handle_daily_candidates(args: argparse.Namespace) -> int:
    settings = load_settings()
    pipeline_config = load_yaml(settings.pipeline_config_path)
    templates = get_feed_url_templates(pipeline_config)
    report = build_daily_candidates_report(
        settings=settings,
        pipeline_config=pipeline_config,
        source_id=args.source,
        feed_templates=templates,
        skip_processed=not args.include_processed,
        limit_per_source=args.limit_per_source,
        include_summary=not args.no_summary,
    )
    report_path = settings.output_dir / "candidates" / "latest.json"
    markdown_report_path = settings.output_dir / "candidates" / "latest.md"
    write_json(report_path, report)
    write_text(markdown_report_path, build_daily_candidates_markdown(report))
    payload = dict(report)
    payload["saved_report_path"] = str(report_path)
    payload["saved_markdown_report_path"] = str(markdown_report_path)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def handle_extract_url(args: argparse.Namespace) -> int:
    article = extract_article(args.url)
    print(json.dumps(article.to_dict(), ensure_ascii=False, indent=2))
    return 0


def handle_run_once(args: argparse.Namespace) -> int:
    settings = load_settings()
    pipeline_config = load_yaml(settings.pipeline_config_path)
    skip_if_processed = pipeline_config.get("pipeline", {}).get("skip_if_processed", True)
    upload_enabled = pipeline_config.get("publish", {}).get("upload_draft", True)
    templates = get_feed_url_templates(pipeline_config)
    cover_path = Path(args.cover).expanduser() if args.cover else None
    require_cover = pipeline_config.get("publish", {}).get("require_cover_for_draft", True)
    image_config = pipeline_config.get("image", {})
    keep_original_images = pipeline_config.get("content", {}).get("keep_original_images", False)
    processed_store = ProcessedArticleStore(settings.state_dir / "processed_articles.json")
    latest = select_article(
        settings=settings,
        pipeline_config=pipeline_config,
        source_id=args.source,
        item_id=args.item_id,
        feed_templates=templates,
        skip_processed=skip_if_processed and not args.force,
    )
    logger.info("selected article: %s / %s", latest.source_id, latest.item_id)

    if skip_if_processed and not args.force and processed_store.has_processed(latest.source_id, latest.item_id):
        logger.info("article already processed, skipping: %s", latest.item_id)
        return 0

    logger.info("extracting article body from source url")
    extracted = extract_article(latest.url)
    cleaned_html = clean_html(extracted.content_html, keep_images=keep_original_images)
    logger.info("converting article html to markdown")
    try:
        markdown = convert_html_to_markdown(cleaned_html)
    except Exception:
        markdown = fallback_text_markdown(cleaned_html)

    slug = f"{latest.source_id}-{latest.item_id}-{slugify(latest.title)}"
    raw_html_path = settings.output_dir / "raw" / f"{slug}.html"
    markdown_path = settings.output_dir / "markdown" / f"{slug}.md"
    rewritten_markdown_path = settings.output_dir / "rewritten" / f"{slug}.md"
    write_text(raw_html_path, cleaned_html)
    original_markdown = f"# {extracted.title}\n\n{markdown}"
    content_config = pipeline_config.get("content", {})
    source_config = get_source_config_by_id(settings, latest.source_id)
    preprocessed_markdown, preprocess_content_meta = apply_content_policy(
        original_markdown,
        content_config=content_config,
    )
    write_text(markdown_path, preprocessed_markdown)

    rewrite_enabled = args.rewrite or pipeline_config.get("rewrite", {}).get("enabled", False)
    model_config = pipeline_config.get("model", {})
    quality_config = pipeline_config.get("quality", {})
    rewrite_config = dict(pipeline_config.get("rewrite", {}))
    rewrite_config["quality"] = quality_config
    if rewrite_enabled:
        logger.info("running rewrite with quality guardrails")
    else:
        logger.info("rewrite disabled, continuing with extracted markdown")
    final_markdown, rewrite_meta, rewrite_quality = maybe_rewrite_markdown(
        preprocessed_markdown,
        title=latest.title,
        source_name=latest.source_name,
        source_url=latest.url,
        root_dir=settings.root_dir,
        enabled=rewrite_enabled,
        rewrite_config=rewrite_config,
        model_config=model_config,
    )
    publish_markdown_path = markdown_path
    if rewrite_meta.get("rewritten"):
        write_text(rewritten_markdown_path, final_markdown)
        publish_markdown_path = rewritten_markdown_path
    elif rewrite_enabled and rewrite_config.get("required", True):
        logger.warning("rewrite required but failed: %s", rewrite_meta.get("reason", "unknown"))
        append_run_log(
            settings.state_dir / "run_history.jsonl",
            {
                "source_id": latest.source_id,
                "item_id": latest.item_id,
                "status": "failed_rewrite_required",
                "markdown_path": str(markdown_path),
                "rewrite": rewrite_meta,
                "rewrite_quality": rewrite_quality,
                "content_policy": preprocess_content_meta,
                "cover": build_cover_log_entry({"path": "", "enabled": False, "generated": False}),
            },
        )
        raise RuntimeError(
            "rewrite required but failed: "
            f"{rewrite_meta.get('reason', 'unknown')} "
            f"(attempts={rewrite_meta.get('attempts', 0)})"
        )

    content_meta = dict(preprocess_content_meta)
    if rewrite_meta.get("rewritten"):
        processed_markdown, content_meta = apply_content_policy(
            final_markdown,
            content_config=content_config,
        )
        if processed_markdown != final_markdown:
            write_text(rewritten_markdown_path, processed_markdown)
            final_markdown = processed_markdown
            publish_markdown_path = rewritten_markdown_path

    auto_cover_meta = {"enabled": False, "generated": False}
    auto_cover_enabled = (args.auto_cover or image_config.get("enabled", False)) and cover_path is None
    if auto_cover_enabled:
        logger.info("generating cover image")
        auto_cover_meta["enabled"] = True
        generated = generate_wechat_cover_assets(
            root_dir=settings.root_dir,
            output_dir=settings.output_dir,
            slug=slug,
            title=latest.title,
            markdown=final_markdown,
            source_name=latest.source_name,
            cover_config=image_config.get("wechat_cover", {}),
            model_config=model_config,
            image_config=image_config,
            cover_profile=str(source_config.get("cover_profile", "")).strip(),
        )
        auto_cover_meta.update(generated)
        if generated.get("ok"):
            auto_cover_meta["generated"] = True
            cover_path = Path(generated["path"])
        elif image_config.get("fallback_to_source_cover", True):
            logger.warning("ai cover generation failed, trying source cover fallback")
            fallback_path = settings.output_dir / "covers" / f"{slug}-source-cover.jpg"
            fallback = download_cover_from_url(extracted.cover_image_url, fallback_path)
            auto_cover_meta["fallback"] = fallback
            if fallback.get("ok"):
                auto_cover_meta["generated"] = True
                auto_cover_meta["fallback_used"] = "source_cover_url"
                cover_path = Path(fallback["path"])

    if upload_enabled:
        if cover_path is not None and not cover_path.exists():
            raise RuntimeError(f"cover file not found: {cover_path}")

        logger.info("uploading markdown to md2wechat (%s)", "dry-run" if args.dry_run else "draft")
        publish_result = upload_draft(
            settings.md2wechat_run_sh,
            markdown_path=publish_markdown_path,
            cover_path=cover_path,
            dry_run=args.dry_run,
        )
        if (
            not args.dry_run
            and not publish_result["ok"]
            and require_cover
            and "创建草稿需要封面图片" in publish_result.get("stdout", "")
            and cover_path is None
        ):
            publish_result = {
                "ok": True,
                "returncode": 0,
                "stdout": (
                    "converted markdown but skipped draft upload because cover is required. "
                    "rerun with --cover /path/to/cover.jpg"
                ),
                "stderr": "",
                "command": [],
                "skipped_upload_reason": "cover_required",
            }
    else:
        publish_result = {
            "ok": True,
            "returncode": 0,
            "stdout": "publish.upload_draft=false, skipped upload",
            "stderr": "",
            "command": [],
        }

    if is_invalid_ip_whitelist_error(publish_result):
        status = "failed_invalid_ip_whitelist"
        publish_result["hint"] = (
            "WeChat API rejected current egress IP (errcode=40164). "
            "Add this machine public IP to WeChat IP whitelist, then rerun."
        )
    elif args.dry_run and publish_result["ok"]:
        status = "draft_dry_run"
    elif publish_result.get("skipped_upload_reason") == "cover_required":
        status = "draft_skipped_cover_required"
    elif publish_result["ok"]:
        status = "draft_uploaded"
    else:
        status = "failed"
    processed_store.mark(latest.source_id, latest.item_id, latest.title, latest.url, status)
    append_run_log(
        settings.state_dir / "run_history.jsonl",
        {
            "source_id": latest.source_id,
            "item_id": latest.item_id,
            "status": status,
            "markdown_path": str(markdown_path),
            "rewrite": rewrite_meta,
            "rewrite_quality": rewrite_quality,
            "content_policy": content_meta,
            "cover": build_cover_log_entry({"path": str(cover_path) if cover_path else "", **auto_cover_meta}),
        },
    )

    print(
        json.dumps(
            {
                "article": latest.to_dict(),
                "markdown_path": str(markdown_path),
                "publish_markdown_path": str(publish_markdown_path),
                "rewrite": rewrite_meta,
                "rewrite_quality": rewrite_quality,
                "content_policy": content_meta,
                "cover": {"path": str(cover_path) if cover_path else "", **auto_cover_meta},
                "publish": publish_result,
                "status": status,
                "status_reply": build_status_reply(
                    status=status,
                    rewrite_meta=rewrite_meta,
                    rewrite_quality=rewrite_quality,
                    content_meta=content_meta,
                    cover_meta={"path": str(cover_path) if cover_path else "", **auto_cover_meta},
                    publish_result=publish_result,
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if publish_result["ok"] else 1


def handle_generate_cover(args: argparse.Namespace) -> int:
    settings = load_settings()
    pipeline_config = load_yaml(settings.pipeline_config_path)
    image_config = pipeline_config.get("image", {})
    model_config = pipeline_config.get("model", {})

    if args.source:
        latest = fetch_latest_articles(
            settings.wewe_rss_base_url,
            args.source,
            limit=1,
            feed_url_templates=get_feed_url_templates(pipeline_config),
        )[0]
        extracted = extract_article(latest.url)
        cleaned_html = clean_html(
            extracted.content_html,
            keep_images=bool(pipeline_config.get("content", {}).get("keep_original_images", False)),
        )
        try:
            markdown_body = convert_html_to_markdown(cleaned_html)
        except Exception:
            markdown_body = fallback_text_markdown(cleaned_html)
        markdown = f"# {extracted.title}\n\n{markdown_body}"
        markdown, _ = apply_content_policy(markdown, pipeline_config.get("content", {}))
        title = args.title or extracted.title
        source_name = latest.source_name
        slug = f"{latest.source_id}-{latest.item_id}-{slugify(title)}"
        cover_profile = args.profile or str(get_source_config_by_id(settings, latest.source_id).get("cover_profile", "")).strip()
    elif args.markdown:
        markdown_path = Path(args.markdown).expanduser()
        markdown = markdown_path.read_text(encoding="utf-8")
        title = args.title or extract_title_from_markdown(markdown, markdown_path.stem)
        source_name = "manual"
        slug = slugify(title) or markdown_path.stem
        cover_profile = args.profile
    else:
        raise RuntimeError("generate-cover requires either --source or --markdown")

    generated = generate_wechat_cover_assets(
        root_dir=settings.root_dir,
        output_dir=settings.output_dir,
        slug=slug,
        title=title,
        markdown=markdown,
        source_name=source_name,
        cover_config=image_config.get("wechat_cover", {}),
        model_config=model_config,
        image_config=image_config,
        cover_profile=cover_profile,
        subtitle=args.subtitle,
        style=args.style,
        accent=args.accent,
        variant=args.variant,
    )

    if args.output and generated.get("ok"):
        output_path = Path(args.output).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(Path(generated["path"]).read_bytes())
        generated["copied_output_path"] = str(output_path)

    print(json.dumps(generated, ensure_ascii=False, indent=2))
    return 0 if generated.get("ok") else 1


def get_pipeline_source_ids() -> list[str]:
    settings = load_settings()
    return [source["id"] for source in load_source_configs(settings) if source.get("enabled", True)]


def get_source_config_by_id(settings, source_id: str) -> dict:
    for source in load_source_configs(settings):
        if source.get("id") == source_id:
            return source
    return {}


def build_status_reply(
    status: str,
    rewrite_meta: dict,
    rewrite_quality: dict,
    content_meta: dict,
    cover_meta: dict,
    publish_result: dict,
) -> dict:
    rewrite_summary = {
        "enabled": bool(rewrite_meta.get("rewritten") or rewrite_meta.get("reason") != "rewrite disabled"),
        "ok": bool(rewrite_meta.get("rewritten")),
        "style": rewrite_meta.get("style", ""),
        "attempts": rewrite_meta.get("attempts", 0),
        "reason": rewrite_meta.get("reason", ""),
        "quality_passed": bool(rewrite_quality.get("passed", True)),
        "missing_numbers": rewrite_quality.get("missing_numbers", []),
        "new_numbers": rewrite_quality.get("new_numbers", []),
        "frequency_mismatches": rewrite_quality.get("frequency_mismatches", []),
    }
    content_summary = {
        "footer_stripped": bool(content_meta.get("footer_cut_index") is not None),
        "unified_footer_applied": bool(content_meta.get("unified_footer_applied", False)),
    }
    cover_summary = {
        "used": bool(cover_meta.get("path")),
        "generated": bool(cover_meta.get("generated", False)),
        "fallback_used": cover_meta.get("fallback_used", ""),
        "ok": bool(cover_meta.get("ok", False)) if cover_meta.get("enabled") else bool(cover_meta.get("path")),
    }
    publish_summary = {
        "ok": bool(publish_result.get("ok", False)),
        "mode": "dry_run" if status == "draft_dry_run" else "draft_upload",
        "reason": publish_result.get("skipped_upload_reason", "") or publish_result.get("hint", ""),
    }
    return {
        "status": status,
        "rewrite": rewrite_summary,
        "content": content_summary,
        "cover": cover_summary,
        "publish": publish_summary,
    }


def build_cover_log_entry(cover_meta: dict) -> dict:
    path = str(cover_meta.get("path", "")).strip()
    enabled = bool(cover_meta.get("enabled", False))
    fallback_used = str(cover_meta.get("fallback_used", "")).strip()
    entry = {
        "used": bool(path),
        "path": path,
        "generated": bool(cover_meta.get("generated", False)),
        "ok": bool(cover_meta.get("ok", False)) if enabled else bool(path),
        "source": "manual",
        "fallback_used": fallback_used,
        "model": str(cover_meta.get("model", "")).strip(),
        "base_url": str(cover_meta.get("base_url", "")).strip(),
        "size": str(cover_meta.get("size", "")).strip(),
        "render_size": str(cover_meta.get("render_size", "")).strip(),
        "output_size": str(cover_meta.get("output_size", "")).strip(),
        "tried_models": cover_meta.get("tried_models", []),
    }
    if enabled:
        entry["source"] = "source_cover_url" if fallback_used else "ai_generated"
    if not path:
        entry["source"] = "none"
    return entry


def extract_title_from_markdown(markdown: str, fallback: str) -> str:
    for line in markdown.splitlines():
        text = line.strip()
        if text.startswith("# "):
            return text[2:].strip() or fallback
    return fallback


def load_source_configs(settings) -> list[dict]:
    config = load_yaml(settings.sources_config_path)
    sources = config.get("sources", [])
    if sources:
        return [source for source in sources if isinstance(source, dict) and source.get("id")]

    try:
        discovered_sources = fetch_available_sources(settings.wewe_rss_base_url)
    except Exception:
        return []
    return merge_source_configs([], discovered_sources)


def build_prepare_report(settings, pipeline_config: dict) -> dict:
    env_exists = (settings.root_dir / ".env").exists()
    pipeline_exists = settings.pipeline_config_path.exists()
    sources_exists = settings.sources_config_path.exists()
    md2wechat_ok = bool(settings.md2wechat_run_sh) and Path(settings.md2wechat_run_sh).exists()
    wewe_rss_ok, wewe_rss_detail = diagnose_wewe_rss_connectivity(
        settings.wewe_rss_base_url,
        pipeline_config,
    )

    checks: list[tuple[str, bool, str]] = [
        (".env", env_exists, str(settings.root_dir / ".env")),
        ("config/pipeline.yaml", pipeline_exists, str(settings.pipeline_config_path)),
        (
            "WEWE_RSS_BASE_URL",
            wewe_rss_ok,
            wewe_rss_detail,
        ),
        (
            "MD2WECHAT_RUN_SH",
            md2wechat_ok,
            settings.md2wechat_run_sh or "(empty)",
        ),
    ]

    source_catalog_ok = False
    source_catalog_count = 0
    source_catalog_detail = "skipped because wewe-rss is not reachable"
    if wewe_rss_ok:
        try:
            discovered_sources = fetch_available_sources(settings.wewe_rss_base_url)
            source_catalog_count = len(discovered_sources)
            source_catalog_ok = source_catalog_count > 0
            if source_catalog_ok:
                sample_names = [source.get("name") or source["id"] for source in discovered_sources[:3]]
                source_catalog_detail = (
                    f"found {source_catalog_count} subscribed source(s)"
                    f"{': ' + ' / '.join(sample_names) if sample_names else ''}"
                )
            else:
                source_catalog_detail = "wewe-rss is reachable, but no subscribed source was found yet"
        except Exception as exc:
            source_catalog_detail = f"failed to read /feeds: {exc}"

    checks.append(("wewe-rss subscribed sources", source_catalog_ok, source_catalog_detail))
    checks.append(
        (
            "config/sources.yaml",
            sources_exists,
            str(settings.sources_config_path) if sources_exists else "missing; sync will create it after sources are ready",
        )
    )

    next_steps: list[str] = []
    if not env_exists or not pipeline_exists:
        next_steps.append("run ./skill/scripts/run_pipeline.sh bootstrap to create local config files and install Python dependencies")
    if not wewe_rss_ok:
        next_steps.append("check whether wewe-rss is running, then confirm WEWE_RSS_BASE_URL should use localhost or a LAN URL")
    if wewe_rss_ok and not source_catalog_ok:
        next_steps.append("open your wewe-rss admin and subscribe at least one WeChat source, then rerun sync")
    if not md2wechat_ok:
        next_steps.append("install md2wechat or point MD2WECHAT_RUN_SH to its scripts/run.sh")
    if md2wechat_ok:
        next_steps.append("make sure md2wechat has finished its own publisher config init before real draft upload")
    if wewe_rss_ok and source_catalog_ok and not sources_exists:
        next_steps.append("run ./skill/scripts/run_pipeline.sh sync to generate config/sources.yaml from your subscriptions")
    if wewe_rss_ok and source_catalog_ok and md2wechat_ok and env_exists and pipeline_exists:
        next_steps.append("run ./skill/scripts/run_pipeline.sh sync")
        next_steps.append("run ./skill/scripts/run_pipeline.sh candidates")
        next_steps.append("after you pick an item, run ./skill/scripts/run_pipeline.sh run --source <SOURCE_ID> --item-id <ITEM_ID> --rewrite --auto-cover --dry-run")

    ready = all([env_exists, pipeline_exists, wewe_rss_ok, source_catalog_ok, md2wechat_ok])
    return {
        "ready": ready,
        "checks": checks,
        "next_steps": next_steps,
        "source_catalog_count": source_catalog_count,
    }


def merge_source_configs(existing_sources: list[dict], discovered_sources: list[dict]) -> list[dict]:
    existing_by_id = {
        str(source.get("id")).strip(): source
        for source in existing_sources
        if isinstance(source, dict) and str(source.get("id") or "").strip()
    }
    merged: list[dict] = []
    discovered_ids: set[str] = set()

    for discovered in discovered_sources:
        source_id = str(discovered.get("id") or "").strip()
        if not source_id:
            continue
        discovered_ids.add(source_id)
        existing = existing_by_id.get(source_id, {})
        merged.append(
            {
                "id": source_id,
                "name": discovered.get("name") or existing.get("name") or source_id,
                "enabled": bool(existing.get("enabled", True)),
                "rewrite_profile": existing.get("rewrite_profile", "default"),
                "cover_profile": existing.get("cover_profile", "news-tech"),
                "intro": discovered.get("intro") or existing.get("intro", ""),
                "cover": discovered.get("cover") or existing.get("cover", ""),
            }
        )

    for source in existing_sources:
        if not isinstance(source, dict):
            continue
        source_id = str(source.get("id") or "").strip()
        if not source_id or source_id in discovered_ids:
            continue
        merged.append(source)

    return merged


def get_fetch_limit(pipeline_config: dict, override: int = 0) -> int:
    if override and override > 0:
        return override
    value = pipeline_config.get("pipeline", {}).get("fetch_limit", 5)
    try:
        return max(1, int(value))
    except Exception:
        return 5


def get_pick_mode(pipeline_config: dict) -> str:
    return str(pipeline_config.get("freshness", {}).get("pick_mode", "latest")).strip() or "latest"


def get_max_age_hours(pipeline_config: dict) -> int:
    value = pipeline_config.get("freshness", {}).get("max_age_hours", 48)
    try:
        return max(1, int(value))
    except Exception:
        return 48


def sort_candidate_records(records: list[dict], source_ids: list[str], pick_mode: str) -> list[dict]:
    if pick_mode == "source_order":
        ordered_ids = {sid: idx for idx, sid in enumerate(source_ids)}
        return sorted(
            records,
            key=lambda item: (
                ordered_ids.get(item["article"].source_id, 9999),
                -item["published_ts"],
                item["source_rank"],
            ),
        )

    return sorted(
        records,
        key=lambda item: (item["published_ts"], -item["source_rank"]),
        reverse=True,
    )


def collect_candidate_records(
    settings,
    pipeline_config: dict,
    source_id: str | None,
    feed_templates: list[str],
    skip_processed: bool,
    limit_per_source: int = 0,
    item_id: str = "",
) -> tuple[list[dict], list[dict], list[dict], list[str]]:
    source_ids = [source_id] if source_id else get_pipeline_source_ids()
    if not source_ids:
        raise RuntimeError("no enabled sources found in config/sources.yaml")

    fetch_limit = get_fetch_limit(pipeline_config, limit_per_source)
    max_age_hours = get_max_age_hours(pipeline_config)
    now_ts = datetime.now(timezone.utc).timestamp()
    processed_store = ProcessedArticleStore(settings.state_dir / "processed_articles.json")

    candidates: list[dict] = []
    skipped: list[dict] = []
    errors: list[dict] = []

    for sid in source_ids:
        try:
            articles = fetch_latest_articles(
                settings.wewe_rss_base_url,
                sid,
                limit=fetch_limit,
                feed_url_templates=feed_templates,
            )
        except Exception as exc:
            errors.append({"source_id": sid, "error": str(exc)})
            continue

        for source_rank, article in enumerate(articles, start=1):
            if item_id and article.item_id != item_id:
                continue

            ts = parse_published_timestamp(article.published_at)
            age_hours = round((now_ts - ts) / 3600, 2) if ts > 0 else None
            is_fresh = bool(item_id) or (age_hours is not None and age_hours <= max_age_hours)
            already_processed = processed_store.has_processed(article.source_id, article.item_id)
            record = {
                "article": article,
                "published_ts": ts,
                "age_hours": age_hours,
                "is_fresh": is_fresh,
                "processed": already_processed,
                "source_rank": source_rank,
            }

            if item_id:
                candidates.append(record)
                break

            if not is_fresh:
                skipped.append({**record, "skip_reason": "stale"})
                continue
            if skip_processed and already_processed:
                skipped.append({**record, "skip_reason": "processed"})
                continue
            candidates.append(record)

    return candidates, skipped, errors, source_ids


def candidate_record_to_dict(record: dict, rank: int | None = None) -> dict:
    article = record["article"]
    payload = {
        "source_id": article.source_id,
        "source_name": article.source_name,
        "item_id": article.item_id,
        "title": article.title,
        "url": article.url,
        "published_at": article.published_at,
        "age_hours": record.get("age_hours"),
        "processed": bool(record.get("processed", False)),
        "is_fresh": bool(record.get("is_fresh", False)),
        "source_rank": int(record.get("source_rank", 0)),
        "summary": record.get("summary", ""),
    }
    if rank is not None:
        payload["rank"] = rank
    if record.get("skip_reason"):
        payload["skip_reason"] = record["skip_reason"]
    if record.get("summary_error"):
        payload["summary_error"] = record["summary_error"]
    return payload


def build_daily_candidates_report(
    settings,
    pipeline_config: dict,
    source_id: str | None,
    feed_templates: list[str],
    skip_processed: bool,
    limit_per_source: int = 0,
    include_summary: bool = True,
) -> dict:
    candidates, skipped, errors, source_ids = collect_candidate_records(
        settings=settings,
        pipeline_config=pipeline_config,
        source_id=source_id,
        feed_templates=feed_templates,
        skip_processed=skip_processed,
        limit_per_source=limit_per_source,
    )
    pick_mode = get_pick_mode(pipeline_config)
    ordered = sort_candidate_records(candidates, source_ids, pick_mode)
    if include_summary:
        enrich_candidate_records_with_summaries(
            ordered,
            content_config=pipeline_config.get("content", {}),
            keep_original_images=bool(pipeline_config.get("content", {}).get("keep_original_images", False)),
        )
    return {
        "generated_at": datetime.now().isoformat(),
        "config": {
            "source_scope": source_id or "all_enabled_sources",
            "source_count": len(source_ids),
            "fetch_limit": get_fetch_limit(pipeline_config, limit_per_source),
            "max_age_hours": get_max_age_hours(pipeline_config),
            "pick_mode": pick_mode,
            "skip_processed": skip_processed,
            "include_summary": include_summary,
        },
        "summary": {
            "candidate_count": len(ordered),
            "skipped_count": len(skipped),
            "error_count": len(errors),
        },
        "candidates": [candidate_record_to_dict(record, rank=index) for index, record in enumerate(ordered, start=1)],
        "skipped": [candidate_record_to_dict(record) for record in skipped],
        "errors": errors,
    }


def build_daily_candidates_markdown(report: dict) -> str:
    config = report.get("config", {})
    summary = report.get("summary", {})
    candidates = report.get("candidates", [])
    generated_at = str(report.get("generated_at", "")).strip()
    lines = [
        "# 今日选题",
        "",
        f"- 生成时间：{generated_at or '未知'}",
        f"- 时间窗口：近 {int(config.get('max_age_hours', 0) // 24) if config.get('max_age_hours') else '?'} 天",
        f"- 候选数：{summary.get('candidate_count', 0)}",
        f"- 已处理/跳过：{summary.get('skipped_count', 0)}",
        "",
    ]

    if not candidates:
        lines.extend(
            [
                "今天没有可直接进入生产链的候选。",
                "",
                "建议先看：",
                "- `output/candidates/latest.json` 里的 `skipped`",
                "- 是否需要放宽 `freshness.max_age_hours`",
                "- 是否需要先 `python -m app.main sync-sources`",
            ]
        )
        return "\n".join(lines).rstrip() + "\n"

    for item in candidates:
        lines.extend(
            [
                f"{item.get('rank', '?')}. {item.get('title', '')}",
                f"来源：{item.get('source_name', '')}",
                f"时间：约 {item.get('age_hours', '?')} 小时前",
                f"摘要：{item.get('summary', '') or '暂无摘要'}",
                f"标识：`{item.get('source_id', '')} / {item.get('item_id', '')}`",
                "",
            ]
        )

    skipped_processed = [item for item in report.get("skipped", []) if item.get("skip_reason") == "processed"]
    if skipped_processed:
        lines.append("已处理过：")
        for item in skipped_processed:
            lines.append(f"- {item.get('title', '')}")
        lines.append("")

    lines.extend(
        [
            "你可以直接回复：",
            "- `选 8`",
            "- `选 4 和 12`",
            "- `先给我缩成 Top 5`",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def enrich_candidate_records_with_summaries(
    records: list[dict],
    content_config: dict,
    keep_original_images: bool,
) -> None:
    for record in records:
        article = record["article"]
        try:
            extracted = extract_article(article.url)
            cleaned_html = clean_html(extracted.content_html, keep_images=keep_original_images)
            try:
                markdown = convert_html_to_markdown(cleaned_html)
            except Exception:
                markdown = fallback_text_markdown(cleaned_html)
            markdown, _ = apply_content_policy(markdown, content_config=content_config)
            record["summary"] = build_markdown_summary(markdown, article.title)
        except Exception as exc:
            record["summary"] = ""
            record["summary_error"] = str(exc)


def build_markdown_summary(markdown: str, title: str, max_chars: int = 120) -> str:
    normalized_title = normalize_summary_text(title)
    pieces: list[str] = []
    current_len = 0

    for raw_line in markdown.splitlines():
        text = normalize_summary_text(raw_line)
        if not text:
            continue
        if normalized_title and text == normalized_title:
            continue
        if should_skip_summary_line(text):
            continue
        if current_len and current_len + 1 + len(text) > max_chars:
            remaining = max_chars - current_len - 1
            if remaining > 12:
                pieces.append(text[:remaining].rstrip(" ,，。；;:：") + "...")
            break
        pieces.append(text)
        current_len = len(" ".join(pieces))
        if current_len >= max_chars:
            break

    return " ".join(pieces).strip()


def normalize_summary_text(text: str) -> str:
    value = str(text).strip()
    if not value:
        return ""
    replacements = [
        ("#", ""),
        ("*", ""),
        ("`", ""),
        (">", ""),
        ("[", ""),
        ("]", ""),
        ("(", ""),
        (")", ""),
    ]
    for old, new in replacements:
        value = value.replace(old, new)
    value = " ".join(value.split())
    return value.strip()


def should_skip_summary_line(text: str) -> bool:
    skip_markers = [
        "发现“在看”",
        "发现\"在看\"",
        "戳我试试吧",
        "点赞",
        "在看",
        "分享",
    ]
    if len(text) <= 6 and any(marker in text for marker in skip_markers):
        return True
    return any(marker in text for marker in ("发现“在看”", "发现\"在看\"", "戳我试试吧"))


def select_article(
    settings,
    pipeline_config: dict,
    source_id: str | None,
    item_id: str,
    feed_templates: list[str],
    skip_processed: bool,
):
    if source_id and not item_id and not skip_processed:
        return fetch_latest_articles(
            settings.wewe_rss_base_url,
            source_id,
            limit=1,
            feed_url_templates=feed_templates,
        )[0]

    candidates, _, errors, source_ids = collect_candidate_records(
        settings=settings,
        pipeline_config=pipeline_config,
        source_id=source_id,
        feed_templates=feed_templates,
        skip_processed=skip_processed,
        item_id=item_id,
    )

    if item_id:
        if not candidates:
            detail = f"source={source_id}, item_id={item_id}"
            raise RuntimeError(f"selected candidate not found in recent feed window: {detail}")
        return candidates[0]["article"]

    if not candidates:
        if source_id:
            raise RuntimeError(f"no eligible article found for source={source_id}")
        if errors and len(errors) == len(source_ids):
            raise RuntimeError("all enabled sources failed to fetch; run doctor and inspect wewe-rss reachability")
        raise RuntimeError("no fresh unprocessed article found across enabled sources")

    ordered = sort_candidate_records(candidates, source_ids, get_pick_mode(pipeline_config))
    return ordered[0]["article"]


def get_feed_url_templates(pipeline_config: dict) -> list[str]:
    templates = pipeline_config.get("pipeline", {}).get("feed_url_templates", [])
    return [template for template in templates if isinstance(template, str) and template.strip()]


def diagnose_wewe_rss_connectivity(base_url: str, pipeline_config: dict) -> tuple[bool, str]:
    templates = get_feed_url_templates(pipeline_config)
    probe_urls = [base_url]
    if templates:
        probe_urls.append(
            templates[0]
            .replace("{base_url}", base_url.rstrip("/"))
            .replace("{source_id}", "health-probe")
            .replace("{source_id_escaped}", "health-probe")
            .replace("{limit}", "1")
            .replace("{query}", "limit=1")
        )

    errors: list[str] = []
    for url in probe_urls:
        try:
            get(url, timeout=3)
            return True, f"{base_url} (reachable)"
        except Exception as exc:
            errors.append(f"{url}: {exc.__class__.__name__}")
            continue

    hint = "check that wewe-rss is running and that WEWE_RSS_BASE_URL points to a reachable address"
    if any(loopback in base_url for loopback in ("localhost", "127.0.0.1", "::1")):
        hint += "; if another execution environment needs access, try a LAN URL like http://<LAN_IP>:4000"

    attempted = ", ".join(errors) if errors else "no probe URL attempted"
    return False, f"{base_url} (unreachable; {hint}. probes: {attempted})"


def is_invalid_ip_whitelist_error(publish_result: dict) -> bool:
    combined = f"{publish_result.get('stdout', '')}\n{publish_result.get('stderr', '')}"
    lowered = combined.lower()
    return "errcode=40164" in lowered or "invalid ip" in lowered


def handle_snapshot(args: argparse.Namespace) -> int:
    settings = load_settings()
    snapshot_dir = settings.root_dir / "docs" / "internal" / "snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d-%H%M%S")
    filename = f"{timestamp}-{slugify(args.title)}.md"
    path = snapshot_dir / filename
    content = (
        f"# {args.title}\n\n"
        f"- Date: {now.isoformat()}\n"
        f"- Summary: {args.summary or 'N/A'}\n\n"
        "## Changes\n\n"
        "- Pending details\n\n"
        "## Verification\n\n"
        "- Pending details\n\n"
        "## Next\n\n"
        "- Pending details\n"
    )
    write_text(path, content)
    print(str(path))
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
