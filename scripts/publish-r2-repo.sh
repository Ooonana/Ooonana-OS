#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/lib/common.sh
source "$ROOT/scripts/lib/common.sh"

usage() {
  cat <<'USAGE'
Publish an Ooonana package repo directory to Cloudflare R2.

Usage:
  publish-r2-repo.sh --repo-dir DIR --bucket BUCKET [options]

Options:
  --repo-dir DIR       Generated repo directory with index.tsv and SHA256SUMS
  --bucket NAME        R2 bucket name
  --prefix PATH        Object prefix inside the bucket (default: packages-latest)
  --endpoint-url URL   R2 S3 endpoint (default: https://$CLOUDFLARE_ACCOUNT_ID.r2.cloudflarestorage.com)
  --public-url URL     Public HTTP URL for Ooonana clients
  --source-file PATH   Write an /etc/ooonana/sources.d/*.repo file
  --dry-run            Print upload command only
  -h, --help           Show this help

Environment:
  CLOUDFLARE_ACCOUNT_ID or R2_ACCOUNT_ID
  R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY
  R2_BUCKET, R2_PREFIX, R2_ENDPOINT_URL, R2_PUBLIC_URL

The bucket and public/custom domain must already exist.
USAGE
}

repo_dir=""
bucket="${R2_BUCKET:-}"
prefix="${R2_PREFIX:-packages-latest}"
endpoint_url="${R2_ENDPOINT_URL:-}"
public_url="${R2_PUBLIC_URL:-}"
source_file=""
dry_run=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo-dir)
      repo_dir="${2:-}"
      shift 2
      ;;
    --bucket)
      bucket="${2:-}"
      shift 2
      ;;
    --prefix)
      prefix="${2:-}"
      shift 2
      ;;
    --endpoint-url)
      endpoint_url="${2:-}"
      shift 2
      ;;
    --public-url)
      public_url="${2:-}"
      shift 2
      ;;
    --source-file)
      source_file="${2:-}"
      shift 2
      ;;
    --dry-run)
      dry_run=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      ooonana_die "unknown option: $1"
      ;;
  esac
done

[[ -n "$repo_dir" ]] || ooonana_die "missing --repo-dir"
[[ -n "$bucket" ]] || ooonana_die "missing --bucket"
[[ -d "$repo_dir" ]] || ooonana_die "missing repo directory: $repo_dir"
[[ -f "$repo_dir/index.tsv" ]] || ooonana_die "repo missing index.tsv"
[[ -f "$repo_dir/SHA256SUMS" ]] || ooonana_die "repo missing SHA256SUMS"

if [[ -z "$endpoint_url" ]]; then
  account_id="${CLOUDFLARE_ACCOUNT_ID:-${R2_ACCOUNT_ID:-}}"
  [[ -n "$account_id" ]] || ooonana_die "missing CLOUDFLARE_ACCOUNT_ID, R2_ACCOUNT_ID, or --endpoint-url"
  endpoint_url="https://${account_id}.r2.cloudflarestorage.com"
fi

access_key="${AWS_ACCESS_KEY_ID:-${R2_ACCESS_KEY_ID:-}}"
secret_key="${AWS_SECRET_ACCESS_KEY:-${R2_SECRET_ACCESS_KEY:-}}"
[[ -n "$access_key" ]] || ooonana_die "missing R2_ACCESS_KEY_ID or AWS_ACCESS_KEY_ID"
[[ -n "$secret_key" ]] || ooonana_die "missing R2_SECRET_ACCESS_KEY or AWS_SECRET_ACCESS_KEY"

prefix="${prefix#/}"
prefix="${prefix%/}"
target="s3://${bucket}"
if [[ -n "$prefix" ]]; then
  target="${target}/${prefix}"
fi
target="${target%/}/"

cmd=(aws s3 sync "${repo_dir%/}/" "$target" --endpoint-url "$endpoint_url" --delete --no-progress)

if [[ "$dry_run" -eq 1 ]]; then
  printf 'dry-run: '
  ooonana_print_command "${cmd[@]}"
else
  ooonana_require_command aws
  export AWS_ACCESS_KEY_ID="$access_key"
  export AWS_SECRET_ACCESS_KEY="$secret_key"
  export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-auto}"
  export AWS_EC2_METADATA_DISABLED=true
  "${cmd[@]}"
fi

if [[ -n "$public_url" ]]; then
  public_url="${public_url%/}"
  if [[ -n "$source_file" ]]; then
    mkdir -p "$(dirname "$source_file")"
    {
      printf 'OOONANA_REPO_NAME="r2"\n'
      printf 'OOONANA_REPO_URI="%s"\n' "$public_url"
    } >"$source_file"
  fi
  ooonana_log "client repo: $public_url"
  ooonana_log "install: ooonana repo add r2 $public_url"
else
  ooonana_log "uploaded. set R2_PUBLIC_URL after enabling an R2 public/custom domain"
fi
