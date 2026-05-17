#!/usr/bin/env bash
# Diagnostico de API key de New Relic
set -euo pipefail

echo "=========================================="
echo " Diagnostico de API Key New Relic"
echo "=========================================="
echo ""

# 1. Verificar que las vars existen
if [ -z "${NEW_RELIC_API_KEY:-}" ]; then
    echo "[ERROR] NEW_RELIC_API_KEY no esta definida."
    echo "  Ejecuta: export NEW_RELIC_API_KEY='NRAK-...'"
    echo "  Las USER keys empiezan con NRAK-"
    exit 1
fi

if [ -z "${NEW_RELIC_ACCOUNT_ID:-}" ]; then
    echo "[WARN] NEW_RELIC_ACCOUNT_ID no esta definida."
    echo "  Se usara la query para obtenerla."
fi

# 2. Mostrar key (parcialmente oculta)
PREFIX="${NEW_RELIC_API_KEY:0:5}"
SUFFIX="${NEW_RELIC_API_KEY: -4}"
LEN=${#NEW_RELIC_API_KEY}
echo "API Key configurada:"
echo "  Longitud: $LEN caracteres"
echo "  Prefijo:  $PREFIX..."
echo "  Sufijo:   ...$SUFFIX"

if [[ "$NEW_RELIC_API_KEY" == NRAK-* ]]; then
    echo "  Formato: NRAK-... (USER key) [OK]"
else
    echo "  Formato: NO empieza con NRAK- [ADVERTENCIA]"
    echo "  Las USER keys de New Relic suelen empezar con NRAK-."
    echo "  Si esto es una LICENSE key (hex 40 chars), NO sirve para NerdGraph."
fi

echo ""

# 3. Probar endpoint US
echo "--- Probando endpoint US ---"
US_RESP=$(curl -s -w "\n%{http_code}" -X POST "https://api.newrelic.com/graphql" \
    -H "Content-Type: application/json" \
    -H "API-Key: $NEW_RELIC_API_KEY" \
    -d '{"query":"{ requestContext { userId accountId } }"}')
US_HTTP=$(echo "$US_RESP" | tail -1)
US_BODY=$(echo "$US_RESP" | sed '$d')
echo "  HTTP: $US_HTTP"

if [ "$US_HTTP" = "200" ]; then
    echo "  [OK] Autenticacion exitosa en endpoint US"
    echo "  Respuesta: $US_BODY"
    ACCOUNT_ID_FROM_API=$(echo "$US_BODY" | jq -r '.data.requestContext.accountId' 2>/dev/null)
    echo "  Account ID desde API: $ACCOUNT_ID_FROM_API"
else
    echo "  [FAIL] $US_BODY"
fi

echo ""

# 4. Probar endpoint EU
echo "--- Probando endpoint EU ---"
EU_RESP=$(curl -s -w "\n%{http_code}" -X POST "https://api.eu.newrelic.com/graphql" \
    -H "Content-Type: application/json" \
    -H "API-Key: $NEW_RELIC_API_KEY" \
    -d '{"query":"{ requestContext { userId accountId } }"}')
EU_HTTP=$(echo "$EU_RESP" | tail -1)
EU_BODY=$(echo "$EU_RESP" | sed '$d')
echo "  HTTP: $EU_HTTP"

if [ "$EU_HTTP" = "200" ]; then
    echo "  [OK] Autenticacion exitosa en endpoint EU"
    echo "  Respuesta: $EU_BODY"
    ACCOUNT_ID_FROM_API=$(echo "$EU_BODY" | jq -r '.data.requestContext.accountId' 2>/dev/null)
    echo "  Account ID desde API: $ACCOUNT_ID_FROM_API"
else
    echo "  [FAIL] $EU_BODY"
fi

echo ""

# 5. Resumen
echo "=========================================="
echo " Resumen"
echo "=========================================="

if [ "$US_HTTP" = "200" ] || [ "$EU_HTTP" = "200" ]; then
    ENDPOINT="US"
    [ "$US_HTTP" != "200" ] && ENDPOINT="EU"
    echo "  Key valida en endpoint: $ENDPOINT"
    echo "  Para desplegar dashboard usa:"
    echo "    export NEW_RELIC_API_KEY='$NEW_RELIC_API_KEY'"
    echo "    export NEW_RELIC_ACCOUNT_ID='$ACCOUNT_ID_FROM_API'"
    echo "    make dashboard-deploy"
else
    echo "  La key NO es valida en ningun endpoint."
    echo ""
    echo "  Causas posibles:"
    echo "  1. La key fue creada como INGEST-LICENSE (no sirve para NerdGraph)"
    echo "  2. La key expiro o fue revocada"
    echo "  3. La key pertenece a otra cuenta"
    echo ""
    echo "  Solucion:"
    echo "  1. Ir a https://one.newrelic.com/admin-portal/api-keys"
    echo "  2. Crear API key tipo: USER"
    echo "  3. Copiar el valor (empieza con NRAK-)"
    echo "  4. export NEW_RELIC_API_KEY='NRAK-...'"
    echo "  5. Re-ejecutar este diagnostico"
fi
