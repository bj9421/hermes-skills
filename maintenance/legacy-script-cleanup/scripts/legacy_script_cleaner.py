#!/usr/bin/env python3
"""
Legacy script cleaner for /opt/data/scripts/ and /opt/data/ root.

Checks which files are referenced by cron jobs and classifies
all .py/.sh files into: KEEP / ARCHIVE / DELETE candidates.

Usage:
    python3 legacy_script_cleaner.py [--target /opt/data/scripts/]
    python3 legacy_script_cleaner.py --dry-run
    python3 legacy_script_cleaner.py --delete test_twse_*.py
"""

import argparse
import glob
import json
import os
import sys
from datetime import datetime


def load_cron_refs(profiles_dir="/opt/data/profiles"):
    """Load all cron job prompts from all profiles."""
    all_prompts = []
    
    # Global cron
    for path in ["/opt/data/cron/jobs.json"]:
        if os.path.exists(path):
            with open(path) as f:
                data = json.load(f)
                for j in data.get("jobs", []):
                    prompt = j.get("prompt", "") or ""
                    all_prompts.append((j.get("name", ""), prompt))
    
    # Profile crons
    if os.path.isdir(profiles_dir):
        for profile in os.listdir(profiles_dir):
            cron_path = os.path.join(profiles_dir, profile, "cron", "jobs.json")
            if os.path.exists(cron_path):
                with open(cron_path) as f:
                    data = json.load(f)
                    for j in data.get("jobs", []):
                        prompt = j.get("prompt", "") or ""
                        all_prompts.append((f"{profile}/{j.get('name','')}", prompt))
    
    return all_prompts


def classify_file(filepath, all_prompts):
    """Classify a file as KEEP, REVIEW, or DELETE candidate."""
    fname = os.path.basename(filepath)
    
    # Check if referenced by any cron job
    is_referenced = False
    referring_jobs = []
    for name, prompt in all_prompts:
        if fname in prompt:
            is_referenced = True
            referring_jobs.append(name)
    
    if is_referenced:
        return "KEEP", referring_jobs
    
    # Heuristic classifications
    # Same-night test files (test_<source>_<feature>.py pattern)
    if fname.startswith("test_") and ("twse" in fname or "tpex" in fname or 
                                      "finmind" in fname or "tdcc" in fname or
                                      "open" in fname or "sources" in fname):
        return "DELETE_API_TEST", []
    
    # Comparison scripts
    if fname.startswith("compare_") or fname.startswith("final_"):
        return "DELETE_COMPARISON", []
    
    # Rate limit tests
    if fname == "rate_limit_test.py":
        return "DELETE_COMPARISON", []
    
    # Old iteration versions
    if fname.startswith("fix_incomplete_"):
        if fname not in ("fix_incomplete_v3.py",):
            return "DELETE_OLD_ITERATION", []
    
    # Old incremental update scripts
    if "incremental_update" in fname and fname != "run_daily_incremental_update.sh":
        return "DELETE_OLD_ITERATION", []
    
    # One-time manual scripts
    if fname.startswith("manual_update_"):
        return "DELETE_ONE_TIME", []
    
    # Wrapper scripts
    if fname.endswith(".sh") and ("daily" in fname or "update" in fname or
                                  "incremental" in fname):
        return "REVIEW_WRAPPER", []
    
    return "REVIEW", []


def scan_directory(target_dir, all_prompts):
    """Scan a directory and classify all .py/.sh files."""
    results = {"KEEP": [], "DELETE_API_TEST": [], "DELETE_COMPARISON": [],
               "DELETE_OLD_ITERATION": [], "DELETE_ONE_TIME": [],
               "REVIEW": [], "REVIEW_WRAPPER": []}
    
    if not os.path.isdir(target_dir):
        print(f"❌ Directory not found: {target_dir}")
        sys.exit(1)
    
    for fname in sorted(os.listdir(target_dir)):
        if not (fname.endswith(".py") or fname.endswith(".sh")):
            continue
        
        filepath = os.path.join(target_dir, fname)
        if not os.path.isfile(filepath):
            continue
        
        size = os.path.getsize(filepath)
        mtime = os.path.getmtime(filepath)
        date_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
        
        category, refs = classify_file(filepath, all_prompts)
        results[category].append({
            "file": fname,
            "size": size,
            "date": date_str,
            "refs": refs
        })
    
    return results


def print_report(results, target_dir):
    """Print a formatted classification report."""
    print(f"\n{'='*70}")
    print(f"  Legacy Script Cleaner — {target_dir}")
    print(f"{'='*70}\n")
    
    total_files = sum(len(v) for v in results.values())
    total_size = sum(r["size"] for v in results.values() for r in v)
    
    print(f"Total: {total_files} files, {total_size/1024:.1f} KB\n")
    
    if results["KEEP"]:
        print(f"✅ KEEP ({len(results['KEEP'])} files)")
        for r in results["KEEP"]:
            refs = ", ".join(r["refs"]) if r["refs"] else "direct cron ref"
            print(f"   📌 {r['file']:40s} {r['size']:>6d}B  {r['date']}  ← {refs}")
        print()
    
    delete_cats = ["DELETE_API_TEST", "DELETE_COMPARISON", "DELETE_OLD_ITERATION", "DELETE_ONE_TIME"]
    delete_total = sum(len(results[c]) for c in delete_cats)
    if delete_total:
        print(f"❌ DELETE CANDIDATES ({delete_total} files)")
        for cat in delete_cats:
            if results[cat]:
                print(f"\n   [{cat}]")
                for r in results[cat]:
                    print(f"      {r['file']:40s} {r['size']:>6d}B  {r['date']}")
        print()
    
    review_cats = ["REVIEW", "REVIEW_WRAPPER"]
    review_total = sum(len(results[c]) for c in review_cats)
    if review_total:
        print(f"⚠️  REVIEW NEEDED ({review_total} files)")
        for cat in review_cats:
            if results[cat]:
                for r in results[cat]:
                    print(f"      {r['file']:40s} {r['size']:>6d}B  {r['date']}")
        print()


def main():
    parser = argparse.ArgumentParser(description="Clean up legacy scripts")
    parser.add_argument("--target", default="/opt/data/scripts/",
                        help="Target directory to scan")
    parser.add_argument("--profiles-dir", default="/opt/data/profiles",
                        help="Profiles directory for cron lookup")
    parser.add_argument("--delete", nargs="*", default=[],
                        help="Files to delete (comma-separated or positional)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show report without deleting")
    args = parser.parse_args()
    
    all_prompts = load_cron_refs(args.profiles_dir)
    
    if args.delete:
        target = args.target.rstrip("/")
        for fname in args.delete:
            fpath = os.path.join(target, fname)
            if os.path.exists(fpath):
                os.remove(fpath)
                print(f"Deleted: {fpath}")
            else:
                print(f"Not found: {fpath}")
        return
    
    results = scan_directory(args.target, all_prompts)
    print_report(results, args.target)
    
    delete_cats = ["DELETE_API_TEST", "DELETE_COMPARISON", "DELETE_OLD_ITERATION", "DELETE_ONE_TIME"]
    all_delete = []
    for cat in delete_cats:
        all_delete.extend([r["file"] for r in results[cat]])
    
    if all_delete:
        print(f"\n{'='*70}")
        print(f"  Suggested deletion command:")
        print(f"  rm {' '.join(all_delete)}")
        print(f"{'='*70}")


if __name__ == "__main__":
    main()
