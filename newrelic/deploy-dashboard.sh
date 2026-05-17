#!/usr/bin/env bash
# deploy-dashboard.sh — Crea/actualiza el dashboard en New Relic via NerdGraph API
# Uso:  export NEW_RELIC_API_KEY="NRAK-..."
#       export NEW_RELIC_ACCOUNT_ID="1234567"
#       ./deploy-dashboard.sh
set -euo pipefail

DASHBOARD_DIR="$(dirname "$0")"
DASHBOARD_JSON="$DASHBOARD_DIR/dashboard.json"
DASHBOARD_GUID_FILE="$DASHBOARD_DIR/.dashboard-guid"
GRAPHQL_URL="https://api.newrelic.com/graphql"

# ─── Validaciones ───────────────────────────────────────────────────

if [ ! -f "$DASHBOARD_JSON" ]; then
    echo "ERROR: No se encuentra $DASHBOARD_JSON" >&2
    exit 1
fi

if [ -z "${NEW_RELIC_API_KEY:-}" ]; then
    echo "ERROR: NEW_RELIC_API_KEY no esta configurada." >&2
    echo "  Obten una USER key en New Relic > Settings > API Keys > Create key (tipo USER)" >&2
    echo "  Luego: export NEW_RELIC_API_KEY='NRAK-...'" >&2
    exit 1
fi

if [ -z "${NEW_RELIC_ACCOUNT_ID:-}" ]; then
    echo "ERROR: NEW_RELIC_ACCOUNT_ID no esta configurada." >&2
    echo "  En New Relic: Profile > Account settings > Account ID" >&2
    echo "  Luego: export NEW_RELIC_ACCOUNT_ID='1234567'" >&2
    exit 1
fi

API_KEY="$NEW_RELIC_API_KEY"
ACCOUNT_ID="$NEW_RELIC_ACCOUNT_ID"

if [[ "$API_KEY" != NRAK-* ]]; then
    echo "ADVERTENCIA: La API key no empieza con 'NRAK-'." >&2
    echo "  Las USER keys de New Relic suelen empezar con NRAK-." >&2
fi

# ─── Validacion de API key ───────────────────────────────────────────

echo "Validando API key contra NerdGraph..."
VALIDACION=$(curl -s -w "\n%{http_code}" -X POST "$GRAPHQL_URL" \
    -H "Content-Type: application/json" \
    -H "Api-Key: $API_KEY" \
    -d '{"query": "{ requestContext { userId accountId } }"}' 2>&1)

HTTP_CODE=$(echo "$VALIDACION" | tail -1)

if [ "$HTTP_CODE" != "200" ]; then
    echo "ERROR: NerdGraph rechazo la API key (HTTP $HTTP_CODE)" >&2
    echo "  Solucion: Crear USER key en https://one.newrelic.com/admin-portal/api-keys" >&2
    exit 1
fi

echo "API key valida. Continuando..."
echo ""

# ─── Pipeline de transformacion del JSON ─────────────────────────────
# 1. Reemplazar accountId placeholder (0 → ID real) via sed
# 2. Agregar permissions obligatorio
# 3. Extraer el dashboard def para la mutacion
# Nota: la configuracion de widgets se envia como objeto tipado
#       (discriminated union: billboard/line/area), NO como rawConfiguration string.

ACCOUNT_ID_PLACEHOLDER="\"accountId\": 0"
ACCOUNT_ID_REAL="\"accountId\": $ACCOUNT_ID"

TMP_JSON=$(mktemp)
sed "s/$ACCOUNT_ID_PLACEHOLDER/$ACCOUNT_ID_REAL/g" "$DASHBOARD_JSON" \
    | jq '.permissions = "PRIVATE"' > "$TMP_JSON"

DASHBOARD_NAME=$(jq -r '.name' "$TMP_JSON")
DASHBOARD_DEF=$(jq -c '{ name, description, permissions, pages }' "$TMP_JSON")

# ─── Despliegue del Dashboard ───────────────────────────────────────
# Schema NerdGraph (v2):
#   dashboardCreate(accountId: Int!, dashboard: DashboardInput!): DashboardCreateResult
#   DashboardCreateResult.entityResult → { guid }
#   DashboardInput { name!, description, permissions!, pages! }
#   DashboardWidgetInput { title!, layout!, visualization!, configuration! }
#   configuration: discriminated union — { billboard: { nrqlQueries, thresholds } },
#                                           { line: { nrqlQueries } },
#                                           { area: { nrqlQueries } }

if [ -f "$DASHBOARD_GUID_FILE" ]; then
    # ── Actualizar dashboard existente ──
    GUID=$(cat "$DASHBOARD_GUID_FILE")
    echo "Actualizando dashboard existente: $GUID ($DASHBOARD_NAME)"

    MUTATION=$(jq -n --arg guid "$GUID" --argjson def "$DASHBOARD_DEF" '{
        query: "
            mutation($guid: String!, $dashboard: DashboardInput!) {
                dashboardUpdate(guid: $guid, dashboard: $dashboard) {
                    entityResult { guid }
                    errors { description }
                }
            }
        ",
        variables: {
            guid: $guid,
            dashboard: $def
        }
    }')

    RESP=$(curl -s -w "\n%{http_code}" -X POST "$GRAPHQL_URL" \
        -H "Content-Type: application/json" \
        -H "Api-Key: $API_KEY" \
        -d "$MUTATION")

    HTTP_CODE=$(echo "$RESP" | tail -1)
    BODY=$(echo "$RESP" | sed '$d')

    if [ "$HTTP_CODE" != "200" ]; then
        echo "ERROR: HTTP $HTTP_CODE" >&2
        echo "$BODY" >&2
        rm -f "$TMP_JSON"
        exit 1
    fi

    DASHBOARD_GUID=$(echo "$BODY" | jq -r '.data.dashboardUpdate.entityResult.guid // empty')

    if [ -z "$DASHBOARD_GUID" ]; then
        echo "ERROR: No se pudo extraer el GUID." >&2
        echo "Respuesta:" >&2
        echo "$BODY" | jq . >&2
        rm -f "$TMP_JSON"
        exit 1
    fi

    echo "$DASHBOARD_GUID" > "$DASHBOARD_GUID_FILE"
    echo "Actualizado: https://onenr.io/$DASHBOARD_GUID"
else
    # ── Crear nuevo dashboard ──
    echo "Creando nuevo dashboard: $DASHBOARD_NAME"

    MUTATION=$(jq -n --arg accountId "$ACCOUNT_ID" --argjson def "$DASHBOARD_DEF" '{
        query: "
            mutation($accountId: Int!, $dashboard: DashboardInput!) {
                dashboardCreate(accountId: $accountId, dashboard: $dashboard) {
                    entityResult { guid }
                    errors { description }
                }
            }
        ",
        variables: {
            accountId: ($accountId | tonumber),
            dashboard: $def
        }
    }')

    RESP=$(curl -s -w "\n%{http_code}" -X POST "$GRAPHQL_URL" \
        -H "Content-Type: application/json" \
        -H "Api-Key: $API_KEY" \
        -d "$MUTATION")

    HTTP_CODE=$(echo "$RESP" | tail -1)
    BODY=$(echo "$RESP" | sed '$d')

    if [ "$HTTP_CODE" != "200" ]; then
        echo "ERROR: HTTP $HTTP_CODE" >&2
        echo "$BODY" >&2
        rm -f "$TMP_JSON"
        exit 1
    fi

    DASHBOARD_GUID=$(echo "$BODY" | jq -r '.data.dashboardCreate.entityResult.guid // empty')

    if [ -z "$DASHBOARD_GUID" ]; then
        echo "ERROR: No se pudo extraer el GUID." >&2
        echo "Respuesta completa:" >&2
        echo "$BODY" | jq . >&2
        rm -f "$TMP_JSON"
        exit 1
    fi

    echo "$DASHBOARD_GUID" > "$DASHBOARD_GUID_FILE"
    echo "Creado: https://onenr.io/$DASHBOARD_GUID"
fi

rm -f "$TMP_JSON"
echo "Done."
