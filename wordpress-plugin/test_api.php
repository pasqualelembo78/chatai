<?php
/**
 * Test API Backend ARIA
 * Esegui: php test_api.php
 */

$backend_url = 'http://82.165.218.56:5000';

function api_request($endpoint, $method = 'GET', $data = null) {
    global $backend_url;
    $url = $backend_url . $endpoint;
    
    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $url);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_TIMEOUT, 30);
    
    if ($method === 'POST') {
        curl_setopt($ch, CURLOPT_POST, true);
        curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($data));
        curl_setopt($ch, CURLOPT_HTTPHEADER, [
            'Content-Type: application/json',
            'Accept: application/json'
        ]);
    }
    
    $response = curl_exec($ch);
    $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    
    return [
        'success' => $http_code >= 200 && $http_code < 300,
        'code' => $http_code,
        'data' => json_decode($response, true) ?: $response
    ];
}

echo "=== Test API Backend ARIA ===\n\n";
echo "URL: $backend_url\n\n";

// 1. Health check
echo "1. Health Check...\n";
$result = api_request('/');
echo "   Status: " . ($result['success'] ? 'OK' : 'FAIL') . " (HTTP {$result['code']})\n\n";

// 2. Categorie
echo "2. Categorie personaggi...\n";
$result = api_request('/categories');
if ($result['success'] && is_array($result['data'])) {
    echo "   Categorie trovate: " . count($result['data']) . "\n";
    foreach (array_slice($result['data'], 0, 3) as $cat) {
        echo "   - {$cat['name']} ({$cat['character_count']} personaggi)\n";
    }
} else {
    echo "   FAIL: " . ($result['data'] ?? 'Unknown error') . "\n";
}
echo "\n";

// 3. Personaggi
echo "3. Personaggi (prime 5)...\n";
$result = api_request('/characters?limit=5');
if ($result['success'] && is_array($result['data'])) {
    echo "   Personaggi trovati: " . count($result['data']) . "\n";
    foreach ($result['data'] as $char) {
        echo "   - {$char['name']} ({$char['role']})\n";
    }
} else {
    echo "   FAIL\n";
}
echo "\n";

// 4. Provider
echo "4. Provider AI disponibili...\n";
$result = api_request('/providers');
if ($result['success'] && is_array($result['data'])) {
    foreach ($result['data'] as $pid => $provider) {
        $models = is_array($provider['models']) ? count($provider['models']) : 0;
        $status = $provider['has_key'] ? '✓' : '✗';
        echo "   - {$provider['name']} ($status) - $models modelli\n";
    }
} else {
    echo "   FAIL\n";
}
echo "\n";

// 5. Modelli disponibili
echo "5. Modelli disponibili (chain)...\n";
$result = api_request('/available-models');
if ($result['success'] && is_array($result['data'])) {
    $total = 0;
    foreach ($result['data'] as $pid => $models) {
        if (is_array($models)) {
            $total += count($models);
            echo "   - $pid: " . count($models) . " modelli\n";
        }
    }
    echo "   Totale: $total modelli\n";
} else {
    echo "   FAIL\n";
}
echo "\n";

// 6. Login test
echo "6. Login test (crea utente se non esiste)...\n";
$test_user = 'test_wp_' . time();
$result = api_request('/auth/register', 'POST', [
    'username' => $test_user,
    'email' => $test_user . '@test.it',
    'password' => 'test123456',
    'birth_date' => '1990-01-01'
]);
if ($result['success']) {
    echo "   Utente creato: {$test_user}\n";
} else {
    echo "   Utente esiste o errore: " . ($result['data']['detail'] ?? 'OK') . "\n";
}

// Login
$result = api_request('/auth/login', 'POST', [
    'username' => $test_user,
    'password' => 'test123456'
]);
if ($result['success'] && isset($result['data']['access_token'])) {
    $access_token = $result['data']['access_token'];
    echo "   Login OK, token ottenuto\n\n";
    
    // 7. Chat test (autenticato)
    echo "7. Test chat (autenticato)...\n";
    $ch = curl_init($backend_url . '/chat');
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode([
        'character' => 'marco_amicizia',
        'text' => 'Ciao, come stai?',
        'username' => $test_user
    ]));
    curl_setopt($ch, CURLOPT_HTTPHEADER, [
        'Content-Type: application/json',
        'Authorization: Bearer ' . $access_token
    ]);
    $response = curl_exec($ch);
    $chat_data = json_decode($response, true);
    curl_close($ch);
    
    if (is_array($chat_data) && isset($chat_data['ai_text'])) {
        echo "   Risposta AI: " . substr($chat_data['ai_text'], 0, 100) . "...\n";
        echo "   Provider: " . ($chat_data['ai_provider'] ?? 'N/A') . "\n";
        echo "   Emozione: " . ($chat_data['emotion'] ?? 'N/A') . "\n";
    } else {
        echo "   FAIL: " . ($chat_data['detail'] ?? 'Risposta non valida') . "\n";
    }
} else {
    echo "   Login FAIL\n";
}
echo "\n";

echo "=== Test completati ===\n";
