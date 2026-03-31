<?php
/** @var string $pageTitle */
/** @var string|null $role */
/** @var string|null $activeNav */
$pageTitle = $pageTitle ?? 'Демо';
$role = $role ?? ($_GET['role'] ?? 'chairman');
$activeNav = $activeNav ?? '';
?>
<!doctype html>
<html lang="ru">
<head>
    <meta charset="utf-8">
    <title><?= htmlspecialchars($pageTitle, ENT_QUOTES, 'UTF-8') ?></title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="stylesheet" href="assets/app.css">
</head>
<body>
<div class="page">
    <header class="site-header">
        <div class="site-brand">
            <a href="index.php?role=<?= htmlspecialchars(urlencode((string) $role), ENT_QUOTES, 'UTF-8') ?>" class="site-logo">Стройка · демо</a>
            <span class="site-badge">без связи с ботом</span>
        </div>
        <nav class="site-role-switch">
            <span class="muted">Роль:</span>
            <?php
            $roles = [
                'chairman' => 'Руководитель',
                'foreman' => 'Прораб',
                'pdo' => 'ПДО',
                'procurement' => 'Закупка',
                'admin' => 'Админ',
            ];
            foreach ($roles as $rk => $label) {
                $cls = $role === $rk ? 'role-link active' : 'role-link';
                echo '<a class="' . htmlspecialchars($cls) . '" href="index.php?role=' . htmlspecialchars(urlencode($rk)) . '">' . htmlspecialchars($label) . '</a>';
            }
            ?>
        </nav>
    </header>
    <?php require __DIR__ . '/nav.php'; ?>
