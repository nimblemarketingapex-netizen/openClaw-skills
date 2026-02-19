#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./report.sh CAMPAIGN_ID DATE_FROM DATE_TO REPORT_TYPE
# Example:
#   ./report.sh 707144106 2026-02-10 2026-02-19 CAMPAIGN
# REPORT_TYPE: CAMPAIGN | AD | QUERY

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Try to read creds from global OpenClaw config first
GLOBAL_CONFIG="$HOME/.openclaw/openclaw.json"
YANDEX_TOKEN=""
CLIENT_LOGIN=""

if [[ -f "$GLOBAL_CONFIG" ]]; then
  YANDEX_TOKEN=$(jq -r '.skills.entries["direct-analysis"].env.YANDEX_TOKEN' "$GLOBAL_CONFIG" 2>/dev/null || echo "")
  CLIENT_LOGIN=$(jq -r '.skills.entries["direct-analysis"].env.CLIENT_LOGIN' "$GLOBAL_CONFIG" 2>/dev/null || echo "")
fi

# Fallback: local config.json next to this script
if [[ -z "$YANDEX_TOKEN" || "$YANDEX_TOKEN" == "null" || -z "$CLIENT_LOGIN" || "$CLIENT_LOGIN" == "null" ]]; then
  CONFIG_FILE="$SCRIPT_DIR/config.json"
  if [[ -f "$CONFIG_FILE" ]]; then
    YANDEX_TOKEN=$(jq -r '.YANDEX_TOKEN' "$CONFIG_FILE" 2>/dev/null || echo "")
    CLIENT_LOGIN=$(jq -r '.CLIENT_LOGIN' "$CONFIG_FILE" 2>/dev/null || echo "")
  fi
fi

if [[ -z "$YANDEX_TOKEN" || "$YANDEX_TOKEN" == "null" ]]; then
  echo "[ERROR] YANDEX_TOKEN is missing in openclaw.json and config.json" >&2
  exit 1
fi

if [[ -z "$CLIENT_LOGIN" || "$CLIENT_LOGIN" == "null" ]]; then
  echo "[ERROR] CLIENT_LOGIN is missing in openclaw.json and config.json" >&2
  exit 1
fi

if [[ $# -lt 4 ]]; then
  echo "Usage: $0 CAMPAIGN_ID DATE_FROM DATE_TO REPORT_TYPE(CAMPAIGN|AD|QUERY)" >&2
  exit 1
fi

CAMPAIGN_ID="$1"
DATE_FROM="$2"
DATE_TO="$3"
REPORT_KIND="$4"  # CAMPAIGN | AD | QUERY

# Map to Yandex report types and field sets
REPORT_TYPE=""
FIELDS_JSON=""

case "$REPORT_KIND" in
  CAMPAIGN)
    REPORT_TYPE="CAMPAIGN_PERFORMANCE_REPORT"
    FIELDS_JSON='["Date","CampaignId","Impressions","Clicks","Cost","AvgCpc","Conversions","GoalsRoi"]';;
  AD)
    REPORT_TYPE="AD_PERFORMANCE_REPORT"
    FIELDS_JSON='["Date","CampaignId","AdGroupId","AdId","Impressions","Clicks","Cost","AvgCpc","Conversions"]';;
  QUERY)
    REPORT_TYPE="SEARCH_QUERY_PERFORMANCE_REPORT"
    FIELDS_JSON='["Date","CampaignId","AdGroupId","Query","Impressions","Clicks","Cost","AvgCpc","Conversions"]';;
  *)
    echo "[ERROR] Unknown REPORT_TYPE: $REPORT_KIND (use CAMPAIGN|AD|QUERY)" >&2
    exit 1;;
 esac

OUT_DIR="$SCRIPT_DIR/out"
mkdir -p "$OUT_DIR"
TS="$(date +%Y%m%d_%H%M%S)"
OUT_FILE="$OUT_DIR/${CAMPAIGN_ID}_${REPORT_KIND}_${TS}.tsv"

# Build body JSON
BODY=$(cat <<EOF
{
  "params": {
    "SelectionCriteria": {
      "DateFrom": "$DATE_FROM",
      "DateTo": "$DATE_TO",
      "Filter": [
        {
          "Field": "CampaignId",
          "Operator": "EQUALS",
          "Values": ["$CAMPAIGN_ID"]
        }
      ]
    },
    "FieldNames": $FIELDS_JSON,
    "ReportName": "direct_analysis_${CAMPAIGN_ID}_${REPORT_KIND}",
    "ReportType": "$REPORT_TYPE",
    "DateRangeType": "CUSTOM_DATE",
    "Format": "TSV",
    "IncludeVAT": "YES",
    "IncludeDiscount": "NO"
  }
}
EOF
)

# Call Yandex Direct Reports API
curl -sS \
  -H "Authorization: Bearer $YANDEX_TOKEN" \
  -H "Client-Login: $CLIENT_LOGIN" \
  -H "Accept-Language: ru" \
  -H "processingMode: auto" \
  -H "returnMoneyInMicros: false" \
  -H "skipReportHeader: true" \
  -H "skipColumnHeader: false" \
  -H "skipReportSummary: true" \
  -X POST "https://api.direct.yandex.com/json/v5/reports" \
  -d "$BODY" > "$OUT_FILE"

if [[ $? -ne 0 ]]; then
  echo "[ERROR] Failed to get report from Yandex Direct" >&2
  exit 1
fi

echo "[OK] Report saved to $OUT_FILE"