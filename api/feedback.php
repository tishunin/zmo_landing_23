<?php
declare(strict_types=1);

const MAX_BODY_BYTES = 8192;
const RATE_WINDOW_SECONDS = 3600;
const RATE_MAX_REQUESTS = 5;
const RATE_MIN_INTERVAL_SECONDS = 20;
const MAIL_TO = 'tishunin.yu@zemlyamo.ru';
const MAIL_FROM = 'tishunin.yu@zemlyamo.ru';

function respond(int $status, array $payload): never
{
    http_response_code($status);
    header('Content-Type: application/json; charset=UTF-8');
    header('Cache-Control: no-store');
    echo json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

function sameOriginRequest(): bool
{
    $fetchSite = $_SERVER['HTTP_SEC_FETCH_SITE'] ?? '';
    if ($fetchSite !== '' && !in_array($fetchSite, ['same-origin', 'none'], true)) {
        return false;
    }

    $origin = $_SERVER['HTTP_ORIGIN'] ?? '';
    $host = strtolower($_SERVER['HTTP_HOST'] ?? '');
    if ($origin === '' || $host === '') {
        return false;
    }

    $parts = parse_url($origin);
    if (!is_array($parts) || !in_array($parts['scheme'] ?? '', ['http', 'https'], true)) {
        return false;
    }

    $originHost = strtolower((string) ($parts['host'] ?? ''));
    if (isset($parts['port'])) {
        $originHost .= ':' . $parts['port'];
    }
    return $originHost !== '' && hash_equals($host, $originHost);
}

function rateLimitExceeded(string $clientIp): bool
{
    $path = sys_get_temp_dir() . '/zmo-registration-' . hash('sha256', $clientIp) . '.json';
    $handle = fopen($path, 'c+');
    if ($handle === false || !flock($handle, LOCK_EX)) {
        return true;
    }

    $raw = stream_get_contents($handle);
    $entries = json_decode($raw !== false ? $raw : '[]', true);
    $entries = is_array($entries) ? $entries : [];
    $now = time();
    $entries = array_values(array_filter(
        $entries,
        static fn ($timestamp): bool => is_int($timestamp) && $timestamp > $now - RATE_WINDOW_SECONDS
    ));

    $last = end($entries);
    $limited = ($last !== false && $now - $last < RATE_MIN_INTERVAL_SECONDS)
        || count($entries) >= RATE_MAX_REQUESTS;

    if (!$limited) {
        $entries[] = $now;
        rewind($handle);
        ftruncate($handle, 0);
        fwrite($handle, json_encode($entries));
        fflush($handle);
        @chmod($path, 0600);
    }

    flock($handle, LOCK_UN);
    fclose($handle);
    return $limited;
}

function cleanText(mixed $value): string
{
    return trim(preg_replace('/\s+/u', ' ', is_string($value) ? $value : '') ?? '');
}

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    header('Allow: POST');
    respond(405, ['ok' => false, 'message' => 'Метод не поддерживается.']);
}

if (!sameOriginRequest()) {
    respond(403, ['ok' => false, 'message' => 'Запрос отклонён.']);
}

$contentType = strtolower(trim(explode(';', $_SERVER['CONTENT_TYPE'] ?? '')[0]));
if ($contentType !== 'application/json') {
    respond(415, ['ok' => false, 'message' => 'Некорректный формат.']);
}

$contentLength = (int) ($_SERVER['CONTENT_LENGTH'] ?? 0);
if ($contentLength <= 0 || $contentLength > MAX_BODY_BYTES) {
    respond(413, ['ok' => false, 'message' => 'Некорректный размер запроса.']);
}

$rawBody = file_get_contents('php://input', false, null, 0, MAX_BODY_BYTES + 1);
if ($rawBody === false || strlen($rawBody) > MAX_BODY_BYTES) {
    respond(413, ['ok' => false, 'message' => 'Некорректный размер запроса.']);
}

try {
    $data = json_decode($rawBody, true, 16, JSON_THROW_ON_ERROR);
} catch (JsonException) {
    respond(422, ['ok' => false, 'message' => 'Некорректные данные.']);
}

if (!is_array($data)) {
    respond(422, ['ok' => false, 'message' => 'Некорректные данные.']);
}

$allowedFields = ['name', 'phone', 'email', 'consent', 'lastname'];
if (array_diff(array_keys($data), $allowedFields) !== []) {
    respond(422, ['ok' => false, 'message' => 'Переданы неизвестные поля.']);
}

$lastname = cleanText($data['lastname'] ?? '');
if ($lastname !== '') {
    respond(200, ['ok' => true]);
}

$name = cleanText($data['name'] ?? '');
$phone = cleanText($data['phone'] ?? '');
$email = strtolower(cleanText($data['email'] ?? ''));
$consent = ($data['consent'] ?? false) === true;

if (strlen($name) < 2 || strlen($name) > 160 || preg_match('/[\x00-\x1F\x7F]/u', $name)) {
    respond(422, ['ok' => false, 'message' => 'Укажите корректное имя.']);
}

$phoneDigits = preg_replace('/\D+/', '', $phone) ?? '';
if (strlen($phoneDigits) < 10 || strlen($phoneDigits) > 15 || strlen($phone) > 30) {
    respond(422, ['ok' => false, 'message' => 'Укажите корректный телефон.']);
}

if (strlen($email) > 254 || filter_var($email, FILTER_VALIDATE_EMAIL) === false) {
    respond(422, ['ok' => false, 'message' => 'Укажите корректную электронную почту.']);
}

if (!$consent) {
    respond(422, ['ok' => false, 'message' => 'Необходимо согласие на обработку данных.']);
}

$clientIp = $_SERVER['REMOTE_ADDR'] ?? 'unknown';
if (rateLimitExceeded($clientIp)) {
    respond(429, ['ok' => false, 'message' => 'Слишком много запросов. Попробуйте позже.']);
}

$fields = [
    'Дата' => '19.09.2026 11:30',
    'Событие' => 'День рождения ЗЕМЛЯ МО 23 года вместе',
    'Форма' => 'Регистрация',
    'Имя' => $name,
    'Телефон' => $phone,
    'E-mail' => $email,
];

$lines = ['Новая заявка с лендинга «23 года вместе»', ''];
foreach ($fields as $label => $value) {
    $lines[] = $label . ': ' . $value;
}

$message = implode("\r\n", $lines) . "\r\n";
$subject = '=?UTF-8?B?' . base64_encode('Новая заявка с лендинга Земля МО') . '?=';
$fromName = '=?UTF-8?B?' . base64_encode('Земля МО — регистрация') . '?=';
$headers = implode("\r\n", [
    'MIME-Version: 1.0',
    'Content-Type: text/plain; charset=UTF-8',
    "From: {$fromName} <" . MAIL_FROM . '>',
    'Reply-To: ' . MAIL_FROM,
]);

$sent = mail(MAIL_TO, $subject, $message, $headers, '-f ' . MAIL_FROM);
if (!$sent) {
    respond(502, ['ok' => false, 'message' => 'Не удалось отправить заявку. Попробуйте позже.']);
}

respond(200, ['ok' => true]);
