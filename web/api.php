<?php
// Proxy mínimo: a página (mesmo domínio) chama este arquivo, que repassa ao
// servidor do agente. Só dois caminhos passam: /saude e /mensagens.
// Os endpoints da coordenação NÃO são expostos por aqui.
require __DIR__ . '/config.php';
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');
@set_time_limit(180);

if (BACKEND_URL === '') {
    http_response_code(503);
    echo json_encode(['detail' => 'servidor do agente ainda não configurado']);
    exit;
}

$rota = $_GET['r'] ?? '';
if ($rota === 'saude' && $_SERVER['REQUEST_METHOD'] === 'GET') {
    $url = BACKEND_URL . '/saude';
    $corpo = null;
} elseif ($rota === 'mensagens' && $_SERVER['REQUEST_METHOD'] === 'POST') {
    $corpo = file_get_contents('php://input');
    if (strlen($corpo) > 4000) {
        http_response_code(413);
        echo json_encode(['detail' => 'mensagem grande demais']);
        exit;
    }
    $url = BACKEND_URL . '/mensagens';
} else {
    http_response_code(404);
    echo json_encode(['detail' => 'rota não encontrada']);
    exit;
}

$ch = curl_init($url);
curl_setopt_array($ch, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_CONNECTTIMEOUT => 90,   // o plano gratuito "dorme" e leva ~1 min para acordar
    CURLOPT_TIMEOUT => 170,
    CURLOPT_HTTPHEADER => ['Content-Type: application/json', 'Accept: application/json'],
]);
if ($corpo !== null) {
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_POSTFIELDS, $corpo);
}
$resposta = curl_exec($ch);
if ($resposta === false) {
    http_response_code(502);
    echo json_encode(['detail' => 'servidor do agente não respondeu: ' . curl_error($ch)]);
    exit;
}
http_response_code(curl_getinfo($ch, CURLINFO_HTTP_CODE));
echo $resposta;
