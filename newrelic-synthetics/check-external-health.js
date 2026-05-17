// check-external-health.js
// New Relic Synthetics - API Test
// Monitorea disponibilidad de Pasarela de Pagos (Stripe) y Motor de Busqueda
// Variables de entorno (configurar en el monitor de Synthetics):
//   PAYMENT_GATEWAY_HEALTH — URL del health check de Stripe (default: api.stripe.com)
//   SEARCH_ENGINE_HEALTH  — URL del health check del Search Service
//   MAX_RESPONSE_TIME_MS  — Umbral maximo de respuesta (default: 2000ms)

const assert = require('assert');

const PAYMENT_GATEWAY_HEALTH = $env.PAYMENT_GATEWAY_HEALTH || 'https://api.stripe.com/v1/health';
const SEARCH_ENGINE_HEALTH = $env.SEARCH_ENGINE_HEALTH || 'http://search:8006/healthz/liveness';
const MAX_RESPONSE_TIME_MS = parseInt($env.MAX_RESPONSE_TIME_MS || '2000', 10);

$util.insights.set('max_response_time_ms', MAX_RESPONSE_TIME_MS);
$util.insights.set('payment_gateway_url', PAYMENT_GATEWAY_HEALTH);
$util.insights.set('search_engine_url', SEARCH_ENGINE_HEALTH);

// Check 1: Pasarela de Pagos (Stripe)
try {
    var paymentResponse = await $http.get(PAYMENT_GATEWAY_HEALTH, {
        headers: { 'Accept': 'application/json' },
        timeout: 10000
    });

    assert.ok(
        paymentResponse.status === 200,
        `Payment Gateway expected 200, got ${paymentResponse.status}`
    );
    assert.ok(
        paymentResponse.timing < MAX_RESPONSE_TIME_MS,
        `Payment Gateway response time ${paymentResponse.timing}ms exceeds ${MAX_RESPONSE_TIME_MS}ms`
    );

    $util.insights.set('payment_gateway_status', paymentResponse.status);
    $util.insights.set('payment_gateway_latency_ms', paymentResponse.timing);
    console.log(`PASS: Payment Gateway - status=${paymentResponse.status} latency=${paymentResponse.timing}ms`);
} catch (err) {
    $util.insights.set('payment_gateway_status', 0);
    $util.insights.set('payment_gateway_error', err.message);
    console.error(`FAIL: Payment Gateway - ${err.message}`);
    throw err;
}

// Check 2: Motor de Busqueda (TravelHub Search Service)
try {
    var searchResponse = await $http.get(SEARCH_ENGINE_HEALTH, {
        headers: { 'Accept': 'application/json' },
        timeout: 5000
    });

    assert.ok(
        searchResponse.status === 200,
        `Search Engine expected 200, got ${searchResponse.status}`
    );
    assert.ok(
        searchResponse.timing < MAX_RESPONSE_TIME_MS,
        `Search Engine response time ${searchResponse.timing}ms exceeds ${MAX_RESPONSE_TIME_MS}ms`
    );

    var searchBody = JSON.parse(searchResponse.body);
    assert.ok(
        searchBody.status === 'alive',
        `Search Engine unexpected status: ${searchBody.status}`
    );

    $util.insights.set('search_engine_status', searchResponse.status);
    $util.insights.set('search_engine_latency_ms', searchResponse.timing);
    console.log(`PASS: Search Engine - status=${searchResponse.status} latency=${searchResponse.timing}ms body=${JSON.stringify(searchBody)}`);
} catch (err) {
    $util.insights.set('search_engine_status', 0);
    $util.insights.set('search_engine_error', err.message);
    console.error(`FAIL: Search Engine - ${err.message}`);
    throw err;
}

console.log('PASS: All external health checks completed successfully');
