# Git Dubious Ownership Fix

## Problem

When running git inside Docker containers, you may encounter:

```
fatal: detected dubious ownership in repository at '/path/to/dir'
To add an exception for this directory, call:
	git config --global --add safe.directory /path/to/dir
```

This happens when the container UID doesn't match the directory owner UID.

## Solutions

### 1. Quick fix (per command)

```bash
git -c safe.directory=/path/to/dir commit -m "..."
```

### 2. Per-repository fix

```bash
git -C /path/to/dir config --add safe.directory /path/to/dir
```

### 3. Global fix (if you have permission)

```bash
git config --global --add safe.directory /path/to/dir
```

### 4. Multiple directories

```bash
git config --global --add safe.directory /opt/data/*
git config --global --add safe.directory /opt/data/scripts
```

## Prevention

When initializing new git repos in Docker:

```bash
# Set up before first commit
git config --global --add safe.directory "$(pwd)"
git init
git add .
git commit -m "init"
```

## Root Cause

Docker containers run as a different UID than the host filesystem owner. Git 2.35+ added this security check to prevent accidental modification of repositories owned by different users.
