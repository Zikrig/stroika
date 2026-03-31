<?php
declare(strict_types=1);

/**
 * Загрузка JSON из site/data/*.json
 */
function site_load_json(string $name): array
{
    $path = dirname(__DIR__) . '/site_data/' . $name . '.json';
    if (!is_readable($path)) {
        return [];
    }
    $raw = file_get_contents($path);
    if ($raw === false) {
        return [];
    }
    $data = json_decode($raw, true);
    return is_array($data) ? $data : [];
}

function site_json_encode_for_js(array $data): string
{
    $json = json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    return $json !== false ? $json : '[]';
}
