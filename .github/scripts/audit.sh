# shellcheck shell=sh
# ===================================================
# Structured audit logging — RGPD Art. 32 / HDS traceability
# ===================================================
# Sourced by every security job:  . .github/scripts/audit.sh
# Emits structured audit events (run id, commit SHA, workflow config
# hash, scan result) so security scans stay traceable for compliance.
#
# POSIX sh on purpose: the OWASP job runs inside a container whose
# default shell may be `sh`, so no bashisms (no ${var//}, no ${var:0:n}).
#
# Usage:  audit_log "<event>" "<status>" "<details>"

# Tamper-evidence: short hash of the workflow that produced this run.
CI_CONFIG_HASH="n/a"
if [ -f ".github/workflows/ci.yml" ]; then
  CI_CONFIG_HASH=$(sha256sum .github/workflows/ci.yml | cut -c1-16)
fi

audit_log() {
  _event=$(printf '%s' "${1:-}" | tr -cd 'a-zA-Z0-9_. -')
  _status=$(printf '%s' "${2:-}" | tr -cd 'a-zA-Z0-9_. -')
  _details=$(printf '%s' "${3:-}" | tr -cd 'a-zA-Z0-9_. /:=-')
  _sha=$(printf '%s' "${GITHUB_SHA:-}" | cut -c1-8)
  echo "[AUDIT] ts=$(date -u +%Y-%m-%dT%H:%M:%SZ) | run=${GITHUB_RUN_ID:-} | project=${GITHUB_REPOSITORY:-} | branch=${GITHUB_REF_NAME:-} | sha=${_sha} | config_hash=${CI_CONFIG_HASH} | job=${GITHUB_JOB:-} | event=${_event} | status=${_status} | details=${_details}"
}
